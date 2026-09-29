import { useEffect, useState } from 'react'
import { getMemory, learnMemory } from '../api.js'

const CATEGORY_ICONS = {
  'Audience': '👥', 'Topics': '🎯', 'Formats': '📐', 'Platforms': '📡',
  'Brand Voice': '🎙', 'Content Gaps': '🕳', 'Strategy': '♟', 'Performance': '📈',
}

const SOURCE_COLORS = {
  'historical performance': 'text-emerald-300 border-emerald-500/30 bg-emerald-500/10',
  'user preference': 'text-sky-300 border-sky-500/30 bg-sky-500/10',
  'content history': 'text-slate-300 border-slate-500/30 bg-slate-500/10',
  'Hindsight memory': 'text-indigo-300 border-indigo-500/30 bg-indigo-500/10',
}

export default function Learned() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [note, setNote] = useState('')
  const [saved, setSaved] = useState(false)

  const load = () => getMemory().then((r) => setData(r.data)).catch(() => setError('Could not load memory.'))
  useEffect(() => { load() }, [])

  const save = async (e) => {
    e.preventDefault()
    if (!note.trim()) return
    await learnMemory(note.trim())
    setNote(''); setSaved(true); setTimeout(() => setSaved(false), 2500)
    load()
  }

  if (error) return <div className="error-box">{error}</div>
  if (!data) return <div className="text-slate-400">Loading…</div>

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">What I've Learned</h1>
          <p className="mt-1 text-sm text-slate-400">
            {data.total} accumulated insights. Memory backend:{' '}
            <span className={data.hindsight_available ? 'text-emerald-400' : 'text-amber-400'}>
              {data.hindsight_available ? 'Hindsight (connected)' : 'Local fallback'}
            </span>
          </p>
        </div>
      </header>

      <form onSubmit={save} className="card flex gap-3">
        <input className="input" placeholder="Teach ContentMind a preference, e.g. “Never publish purely promotional posts”" value={note} onChange={(e) => setNote(e.target.value)} />
        <button className="btn-primary shrink-0">Remember this</button>
      </form>
      {saved && <div className="success-box">Stored in memory — future recommendations will account for it.</div>}

      <div className="grid gap-4 lg:grid-cols-2">
        {Object.entries(data.categories).filter(([, items]) => items.length > 0).map(([cat, items]) => (
          <section key={cat} className="card">
            <h2 className="mb-3 flex items-center gap-2 font-semibold text-white">
              <span>{CATEGORY_ICONS[cat] || '•'}</span>{cat}
              <span className="ml-auto text-xs font-normal text-slate-500">{items.length}</span>
            </h2>
            <ul className="space-y-2.5">
              {items.slice(0, 12).map((m, i) => (
                <li key={i} className="flex items-start gap-2 text-sm text-slate-300">
                  <span className="mt-0.5 text-emerald-400">✓</span>
                  <span className="flex-1">{m.text}</span>
                  <span className={'shrink-0 rounded border px-1.5 py-0.5 text-[10px] uppercase tracking-wide ' + (SOURCE_COLORS[m.source] || SOURCE_COLORS['content history'])}>
                    {m.source}
                  </span>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>

      {data.total === 0 && (
        <div className="card text-center text-sm text-slate-400">
          Nothing learned yet. Add content or run the Memory Demo seed — every piece of history becomes a memory.
        </div>
      )}
    </div>
  )
}
