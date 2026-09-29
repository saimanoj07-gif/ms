import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { listContent } from '../api.js'

export default function Library() {
  const [items, setItems] = useState([])
  const [error, setError] = useState('')
  const [topic, setTopic] = useState('')

  useEffect(() => {
    listContent(topic ? { topic } : {})
      .then((r) => setItems(r.data))
      .catch(() => setError('Could not load content. Is the backend running?'))
  }, [topic])

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Content Library</h1>
          <p className="mt-1 text-sm text-slate-400">{items.length} published items — the history ContentMind remembers.</p>
        </div>
        <div className="flex gap-2">
          <input className="input w-56" placeholder="Filter by topic…" value={topic} onChange={(e) => setTopic(e.target.value)} />
          <Link to="/add" className="btn-primary">Add Content</Link>
        </div>
      </header>

      {error && <div className="error-box">{error}</div>}

      <div className="card overflow-x-auto p-0">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-slate-800 text-xs uppercase tracking-wide text-slate-400">
            <tr>
              <th className="px-4 py-3">Title</th>
              <th className="px-4 py-3">Platform</th>
              <th className="px-4 py-3">Topic</th>
              <th className="px-4 py-3">Type</th>
              <th className="px-4 py-3 text-right">Impressions</th>
              <th className="px-4 py-3 text-right">Engagement</th>
              <th className="px-4 py-3">Published</th>
            </tr>
          </thead>
          <tbody>
            {items.map((c) => (
              <tr key={c.id} className="border-b border-slate-800/60 hover:bg-slate-800/30">
                <td className="max-w-72 truncate px-4 py-3 font-medium text-slate-100" title={c.title}>{c.title}</td>
                <td className="px-4 py-3 text-slate-300">{c.platform}</td>
                <td className="px-4 py-3 text-slate-300">{c.topic}</td>
                <td className="px-4 py-3 text-slate-400">{c.content_type}</td>
                <td className="px-4 py-3 text-right text-slate-300">{c.impressions.toLocaleString()}</td>
                <td className="px-4 py-3 text-right">
                  <span className={c.engagement_rate >= 5 ? 'font-semibold text-emerald-400' : c.engagement_rate < 2 ? 'text-rose-400' : 'text-slate-300'}>
                    {c.engagement_rate.toFixed(2)}%
                  </span>
                </td>
                <td className="px-4 py-3 text-slate-400">{c.published_at || '—'}</td>
              </tr>
            ))}
            {!items.length && !error && (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-slate-400">No content yet — add some or run the Memory Demo seed.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
