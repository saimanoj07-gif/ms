import { useState } from 'react'
import { generatePlan, listPlans } from '../api.js'

export default function Planner() {
  const [form, setForm] = useState({ date_range_days: 7, num_posts: 5, platforms: 'LinkedIn', campaign_topic: '', use_memory: true })
  const [plan, setPlan] = useState(null)
  const [pastPlans, setPastPlans] = useState([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  const generate = async (e) => {
    e.preventDefault()
    setBusy(true); setError('')
    try {
      const platforms = form.platforms.split(',').map((p) => p.trim()).filter(Boolean)
      const r = await generatePlan({
        date_range_days: Number(form.date_range_days),
        num_posts: Number(form.num_posts),
        platforms,
        campaign_topic: form.campaign_topic,
        use_memory: form.use_memory,
      })
      setPlan(r.data)
      listPlans().then((res) => setPastPlans(res.data.slice(0, 5))).catch(() => {})
    } catch (err) {
      setError(err.response?.data?.detail || 'Plan generation failed.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-white">Plan My Content</h1>
        <p className="mt-1 text-sm text-slate-400">
          ContentMind recalls your Hindsight memories, historical performance, and content gaps before recommending anything.
        </p>
      </header>

      <form onSubmit={generate} className="card grid gap-4 md:grid-cols-5">
        <div>
          <label className="label">Days</label>
          <input type="number" min="1" max="30" className="input" value={form.date_range_days} onChange={set('date_range_days')} />
        </div>
        <div>
          <label className="label">Posts</label>
          <input type="number" min="1" max="14" className="input" value={form.num_posts} onChange={set('num_posts')} />
        </div>
        <div>
          <label className="label">Platforms (comma-sep)</label>
          <input className="input" value={form.platforms} onChange={set('platforms')} placeholder="LinkedIn, Newsletter" />
        </div>
        <div>
          <label className="label">Campaign topic (optional)</label>
          <input className="input" value={form.campaign_topic} onChange={set('campaign_topic')} placeholder="e.g. AI ROI" />
        </div>
        <div className="flex items-end gap-3">
          <label className="flex items-center gap-2 text-sm text-slate-300">
            <input type="checkbox" checked={form.use_memory} onChange={(e) => setForm({ ...form, use_memory: e.target.checked })} />
            Use memory
          </label>
        </div>
        <div className="md:col-span-5">
          <button disabled={busy} className="btn-primary w-full md:w-auto">
            {busy ? 'Recalling memories…' : 'Generate Plan'}
          </button>
        </div>
      </form>

      {error && <div className="error-box">{error}</div>}

      {plan && (
        <>
          <div className={'card ' + (plan.memory_count > 0 ? 'border-indigo-500/40 bg-indigo-500/5' : 'border-amber-500/40 bg-amber-500/5')}>
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold text-white">{plan.title}</h2>
              <span className="chip">{plan.date_range}</span>
            </div>
            <p className="mt-2 text-sm text-slate-300">{plan.strategy_summary}</p>
            <p className={'mt-3 text-xs font-semibold ' + (plan.memory_count > 0 ? 'text-indigo-300' : 'text-amber-300')}>
              {plan.memory_count > 0
                ? `✦ Built from ${plan.memory_count} recalled memories${plan.llm_used ? '' : ' (fallback strategist)'}`
                : '⚠ Generated WITHOUT memory — recommendations are generic best practice'}
            </p>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            {plan.items.map((it, i) => (
              <div key={i} className="card">
                <div className="flex items-center justify-between text-xs text-slate-400">
                  <span className="font-semibold uppercase tracking-wide text-indigo-300">{it.platform}</span>
                  <span>{it.date || ''}</span>
                </div>
                <h3 className="mt-2 font-semibold text-white">{it.title}</h3>
                <div className="mt-1 text-xs text-slate-400">{it.topic} · {it.format}</div>
                {it.description && <p className="mt-2 text-sm text-slate-300">{it.description}</p>}
                <div className="mt-3 rounded-lg bg-slate-950/60 p-3 text-sm text-slate-300">
                  <span className="font-semibold text-indigo-300">Why: </span>{it.reason}
                </div>
                {it.memory_used?.length > 0 && (
                  <details className="mt-2">
                    <summary className="cursor-pointer text-xs text-indigo-400">Memories used ({it.memory_used.length})</summary>
                    <ul className="mt-2 space-y-1 text-xs text-slate-400">
                      {it.memory_used.map((m, j) => <li key={j}>– {m}</li>)}
                    </ul>
                  </details>
                )}
              </div>
            ))}
          </div>
        </>
      )}

      {pastPlans.length > 0 && (
        <section className="card">
          <h2 className="mb-3 font-semibold text-white">Past Plans</h2>
          <ul className="space-y-2 text-sm text-slate-300">
            {pastPlans.map((p) => (
              <li key={p.id} className="flex items-center justify-between border-b border-slate-800/60 pb-2">
                <span>{p.title}</span>
                <span className="text-xs text-slate-500">{p.memory_count} memories · {p.items.length} items</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
