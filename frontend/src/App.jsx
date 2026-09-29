import { NavLink, Route, Routes } from 'react-router-dom'
import Dashboard from './pages/Dashboard.jsx'
import Library from './pages/Library.jsx'
import AddContent from './pages/AddContent.jsx'
import Planner from './pages/Planner.jsx'
import Analytics from './pages/Analytics.jsx'
import Learned from './pages/Learned.jsx'
import Chat from './pages/Chat.jsx'
import DemoMode from './pages/DemoMode.jsx'

const nav = [
  { to: '/', label: 'Dashboard', icon: '▦' },
  { to: '/planner', label: 'Planner', icon: '✦' },
  { to: '/library', label: 'Content Library', icon: '≡' },
  { to: '/add', label: 'Add Content', icon: '＋' },
  { to: '/analytics', label: 'Analytics', icon: '◫' },
  { to: '/learned', label: "What I've Learned", icon: '✓' },
  { to: '/chat', label: 'Strategy Chat', icon: '✳' },
  { to: '/demo', label: 'Memory Demo', icon: '◈' },
]

export default function App() {
  return (
    <div className="flex min-h-screen">
      <aside className="fixed inset-y-0 left-0 flex w-60 flex-col border-r border-slate-800 bg-slate-900/40 p-4">
        <div className="mb-8 px-2 pt-2">
          <div className="text-lg font-bold tracking-tight text-white">
            Content<span className="text-indigo-400">Mind</span>
          </div>
          <div className="mt-0.5 text-xs text-slate-400">Your content strategy remembers.</div>
        </div>
        <nav className="flex flex-1 flex-col gap-1">
          {nav.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              className={({ isActive }) =>
                'flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition ' +
                (isActive
                  ? 'bg-indigo-500/15 font-semibold text-indigo-300'
                  : 'text-slate-300 hover:bg-slate-800/60')
              }
            >
              <span className="w-4 text-center text-xs opacity-70">{n.icon}</span>
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="rounded-lg border border-indigo-500/20 bg-indigo-500/5 p-3 text-xs text-slate-400">
          Memory layer: <span className="font-semibold text-indigo-300">Hindsight</span> by Vectorize
        </div>
      </aside>
      <main className="ml-60 flex-1 p-8">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/library" element={<Library />} />
          <Route path="/add" element={<AddContent />} />
          <Route path="/planner" element={<Planner />} />
          <Route path="/analytics" element={<Analytics />} />
          <Route path="/learned" element={<Learned />} />
          <Route path="/chat" element={<Chat />} />
          <Route path="/demo" element={<DemoMode />} />
        </Routes>
      </main>
    </div>
  )
}
