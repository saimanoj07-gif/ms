import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getDashboard } from '../api.js'

export default function Dashboard() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    getDashboard()
      .then((r) => setData(r.data))
      .catch(() => setError('Could not reach the ContentMind backend. Is it running on port 8000?'))
  }, [])

  if (error) return <div className="error-box">{error}</div>
  if (!data) return <div className="text-slate-400">Loading…</div>

  const s = data.stats
  const kpis = [
    { label: 'Content Published', value: s.total_content },
    { label: 'Total Engagement', value: s.total_engagement.toLocaleString() },
    { label: 'Top Topic', value: s.top_topic || '—' },
    { label: 'Top Platform', value: s.top_platform || '—' },
    { label: 'Memories Learned', value: data.memories_learned },
    { label: 'Content Gaps', value: data.gaps.length },
  ]

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Dashboard</h1>
          <p className="mt-1 text-sm text-slate-400">
            Memory backend:{' '}
            <span className={data.hindsight_available ? 'text-emerald-400' : 'text-amber-400'}>
              {data.memory_backend === 'hindsight' ? 'Hindsight (connected)' : 'Local fallback (Hindsight not configured)'}
            </span>
          </p>
        </div>
        <div className="flex gap-3">
          <Link to="/planner" className="btn-primary">Plan My Content</Link>
          <Link to="/learned" className="btn-secondary">What Have I Learned?</Link>
        </div>
      </header>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-6">
        {kpis.map((k) => (
          <div key={k.label} className="card">
            <div className="text-xs uppercase tracking-wide text-slate-400">{k.label}</div>
            <div className="mt-1 truncate text-xl font-bold text-white" title={String(k.value)}>{k.value}</div>
          </div>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="card">
          <h2 className="mb-3 font-semibold text-white">Recent Learning</h2>
          {data.recent_learning.length ? (
            <ul className="space-y-2 text-sm text-slate-300">
              {data.recent_learning.map((l, i) => (
                <li key={i} className="flex gap-2"><span className="text-indigo-400">✓</span>{l}</li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-slate-400">No learning yet — add or seed content so ContentMind can start remembering.</p>
          )}
        </section>

        <section className="card border-indigo-500/30 bg-indigo-500/5">
          <h2 className="mb-3 font-semibold text-white">Recommended Next Action</h2>
          <p className="text-sm text-indigo-200">{data.recommended_next_action}</p>
          <Link to="/planner" className="btn-primary mt-4">Plan My Content</Link>
        </section>
      </div>

      <section className="card">
        <h2 className="mb-3 font-semibold text-white">Potential Content Gaps</h2>
        {data.gaps.length ? (
          <div className="flex flex-wrap gap-2">
            {data.gaps.map((g) => (
              <span key={g.topic} className="chip" title={g.reason}>{g.topic} · {g.priority}</span>
            ))}
          </div>
        ) : (
          <p className="text-sm text-slate-400">No gaps detected yet.</p>
        )}
      </section>
    </div>
  )
}
