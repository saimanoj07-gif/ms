import { useState } from 'react'
import { createContent } from '../api.js'

const PLATFORMS = ['LinkedIn', 'X / Twitter', 'Blog', 'Newsletter', 'YouTube', 'Instagram']
const TYPES = ['Educational post', 'Case study', 'Product announcement', 'News commentary', 'How-to guide', 'Thought leadership', 'Video', 'Poll', 'Thread']
const AUDIENCES = ['Marketing managers', 'Engineering leaders', 'Founders / executives', 'Content strategists', 'Sales teams', 'General / mixed']

const empty = {
  title: '', body: '', platform: 'LinkedIn', content_type: 'Educational post',
  topic: '', audience: 'Marketing managers', published_at: '',
  impressions: '', likes: '', comments: '', shares: '', clicks: '',
}

export default function AddContent() {
  const [form, setForm] = useState(empty)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true); setError(''); setResult(null)
    const num = (v) => (v === '' ? 0 : Number(v))
    try {
      const payload = {
        ...form,
        published_at: form.published_at || undefined,
        impressions: num(form.impressions),
        likes: num(form.likes), comments: num(form.comments),
        shares: num(form.shares), clicks: num(form.clicks),
      }
      const r = await createContent(payload)
      setResult(r.data)
      setForm(empty)
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to add content.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-white">Add Content</h1>
        <p className="mt-1 text-sm text-slate-400">
          Add a published piece with its performance. ContentMind will analyze it, extract strategic insights, and remember them in Hindsight.
        </p>
      </header>

      <form onSubmit={submit} className="card space-y-4">
        <div>
          <label className="label">Title *</label>
          <input required className="input" value={form.title} onChange={set('title')} placeholder="5 AI Automation Mistakes" />
        </div>
        <div>
          <label className="label">Content body</label>
          <textarea className="input min-h-24" value={form.body} onChange={set('body')} placeholder="Optional — paste the post text for better insight extraction" />
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          <div>
            <label className="label">Platform</label>
            <select className="input" value={form.platform} onChange={set('platform')}>
              {PLATFORMS.map((p) => <option key={p}>{p}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Content type</label>
            <select className="input" value={form.content_type} onChange={set('content_type')}>
              {TYPES.map((t) => <option key={t}>{t}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Topic</label>
            <input className="input" value={form.topic} onChange={set('topic')} placeholder="AI automation" />
          </div>
          <div>
            <label className="label">Audience</label>
            <select className="input" value={form.audience} onChange={set('audience')}>
              {AUDIENCES.map((a) => <option key={a}>{a}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Publication date</label>
            <input type="date" className="input" value={form.published_at} onChange={set('published_at')} />
          </div>
        </div>

        <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-4">
          <div className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-400">Performance metrics</div>
          <div className="grid gap-4 md:grid-cols-5">
            {['impressions', 'likes', 'comments', 'shares', 'clicks'].map((m) => (
              <div key={m}>
                <label className="label capitalize">{m}</label>
                <input type="number" min="0" className="input" value={form[m]} onChange={set(m)} placeholder="0" />
              </div>
            ))}
          </div>
        </div>

        {error && <div className="error-box">{error}</div>}
        <button disabled={busy} className="btn-primary w-full">
          {busy ? 'Analyzing & remembering…' : 'Add & Learn'}
        </button>
      </form>

      {result && (
        <div className="card border-emerald-500/30 bg-emerald-500/5">
          <h2 className="font-semibold text-white">Learned from “{result.content.title}”</h2>
          <p className="mt-1 text-xs text-slate-400">
            Engagement rate {result.content.engagement_rate}% · memory:{' '}
            <span className={result.memory_stored ? 'text-emerald-400' : 'text-amber-400'}>
              {result.memory_stored ? 'stored in ' + result.memory_backend : 'not stored'}
            </span>
          </p>
          <ul className="mt-3 space-y-2 text-sm text-emerald-100">
            {result.insights.map((i, idx) => (
              <li key={idx} className="flex gap-2"><span className="text-emerald-400">✓</span>{i}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
