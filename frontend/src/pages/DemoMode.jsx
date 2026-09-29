import { useState } from 'react'
import { demoReset, demoSeed, generatePlan } from '../api.js'

export default function DemoMode() {
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)

  const run = async () => {
    setError(''); setResult(null)
    try {
      setBusy('Resetting database and memory…')
      await demoReset()

      setBusy('Step 1/4 — asking with an empty memory (BEFORE)…')
      const before = await generatePlan({ date_range_days: 7, num_posts: 3, use_memory: true })

      setBusy('Step 2/4 — ingesting 64 historical posts into memory…')
      const seed = await demoSeed(64)

      setBusy('Step 3/4 — re-asking the exact same question (AFTER)…')
      const after = await generatePlan({ date_range_days: 7, num_posts: 3, use_memory: true })

      setBusy('Step 4/4 — done.')
      setResult({ before: before.data, after: after.data, seed: seed.data })
    } catch (err) {
      setError(err.response?.data?.detail || 'Demo failed — is the backend running?')
    } finally {
      setBusy('')
    }
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-white">Memory Demo</h1>
        <p className="mt-1 max-w-2xl text-sm text-slate-400">
          The hackathon proof in one click: ask <em>“What should I post next week?”</em> with empty memory, seed 64 historical
          posts, ask the exact same question again — and watch the plan transform from generic to personalized.
        </p>
      </header>

      <div className="card">
        <button onClick={run} disabled={!!busy} className="btn-primary">
          {busy ? busy : '▶ Run Before / After Demo'}
        </button>
        {error && <div className="error-box mt-4">{error}</div>}
      </div>

      {result && (
        <>
          <div className="grid items-center gap-4 rounded-xl border border-indigo-500/30 bg-indigo-500/5 p-4 text-sm text-indigo-200 md:grid-cols-[1fr_auto_1fr]">
            <div>
              <span className="font-semibold text-amber-300">BEFORE</span> — {result.before.memory_count} memories · empty database
            </div>
            <div className="text-center text-lg">→</div>
            <div>
              <span className="font-semibold text-emerald-300">AFTER</span> — {result.after.memory_count} memories ·{' '}
              {result.seed.content_created} posts learned ({result.seed.memory_backend === 'hindsight' ? 'Hindsight connected' : 'local fallback'})
            </div>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <PlanColumn tag="BEFORE" tone="amber" plan={result.before} />
            <PlanColumn tag="AFTER" tone="emerald" plan={result.after} />
          </div>
        </>
      )}
    </div>
  )
}

function PlanColumn({ tag, tone, plan }) {
  const border = tone === 'amber' ? 'border-amber-500/40' : 'border-emerald-500/40'
  const text = tone === 'amber' ? 'text-amber-300' : 'text-emerald-300'
  return (
    <section className={'card ' + border}>
      <div className="mb-3 flex items-center justify-between">
        <h2 className={'text-lg font-bold ' + text}>{tag}</h2>
        <span className="chip">{plan.memory_count} memories</span>
      </div>
      <p className="mb-4 text-sm text-slate-300">{plan.strategy_summary}</p>
      <div className="space-y-3">
        {plan.items.map((it, i) => (
          <div key={i} className="rounded-lg bg-slate-950/60 p-3">
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">{it.platform} · {it.format}</div>
            <div className="mt-1 text-sm font-semibold text-white">{it.title}</div>
            <div className="mt-1 text-xs text-slate-400">Why: {it.reason}</div>
          </div>
        ))}
      </div>
    </section>
  )
}
