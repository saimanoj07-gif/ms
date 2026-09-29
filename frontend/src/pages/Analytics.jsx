import { useEffect, useState } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, LineChart, Line, Legend,
} from 'recharts'
import { getAnalytics } from '../api.js'

export default function Analytics() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    getAnalytics().then((r) => setData(r.data)).catch(() => setError('Could not load analytics.'))
  }, [])

  if (error) return <div className="error-box">{error}</div>
  if (!data) return <div className="text-slate-400">Loading…</div>

  const pct = (arr) => arr.map((d) => ({ ...d, rate_pct: +(d.avg_rate * 100).toFixed(2) }))

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-white">Analytics</h1>
        <p className="mt-1 text-sm text-slate-400">Structured performance facts — one of the three inputs (with memory and request) behind every recommendation.</p>
      </header>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <div className="card"><div className="text-xs uppercase text-slate-400">Published</div><div className="mt-1 text-2xl font-bold text-white">{data.total_content}</div></div>
        <div className="card"><div className="text-xs uppercase text-slate-400">Total Engagement</div><div className="mt-1 text-2xl font-bold text-white">{data.total_engagement.toLocaleString()}</div></div>
        <div className="card"><div className="text-xs uppercase text-slate-400">Avg Engagement Rate</div><div className="mt-1 text-2xl font-bold text-white">{(data.avg_engagement_rate * 100).toFixed(2)}%</div></div>
        <div className="card"><div className="text-xs uppercase text-slate-400">Median</div><div className="mt-1 text-2xl font-bold text-white">{(data.median_engagement_rate * 100).toFixed(2)}%</div></div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="card">
          <h2 className="mb-4 font-semibold text-white">Engagement by Topic</h2>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={pct(data.by_topic)}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 11 }} interval={0} angle={-20} textAnchor="end" height={60} />
              <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} unit="%" />
              <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid #334155' }} />
              <Bar dataKey="rate_pct" fill="#818cf8" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </section>

        <section className="card">
          <h2 className="mb-4 font-semibold text-white">Engagement by Platform</h2>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={pct(data.by_platform)}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 11 }} />
              <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} unit="%" />
              <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid #334155' }} />
              <Bar dataKey="rate_pct" fill="#34d399" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </section>

        <section className="card">
          <h2 className="mb-4 font-semibold text-white">Engagement by Content Type</h2>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={pct(data.by_content_type)} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis type="number" tick={{ fill: '#94a3b8', fontSize: 11 }} unit="%" />
              <YAxis type="category" dataKey="name" width={140} tick={{ fill: '#94a3b8', fontSize: 11 }} />
              <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid #334155' }} />
              <Bar dataKey="rate_pct" fill="#f472b6" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </section>

        <section className="card">
          <h2 className="mb-4 font-semibold text-white">Engagement Over Time</h2>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={data.over_time}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="period" tick={{ fill: '#94a3b8', fontSize: 11 }} />
              <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} unit="%" />
              <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid #334155' }} />
              <Legend />
              <Line type="monotone" dataKey="engagement_rate" name="avg rate" stroke="#fbbf24" strokeWidth={2} dot />
            </LineChart>
          </ResponsiveContainer>
        </section>
      </div>
    </div>
  )
}
