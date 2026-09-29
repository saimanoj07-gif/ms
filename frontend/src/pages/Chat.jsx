import { useRef, useEffect, useState } from 'react'
import { sendChat } from '../api.js'

const SUGGESTIONS = [
  'What should I post next week?',
  'What topics have worked best?',
  'What have we overused?',
  'What are our biggest content gaps?',
  'What has our audience responded to?',
  'Describe our brand voice.',
]

export default function Chat() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const endRef = useRef(null)

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, busy])

  const send = async (text) => {
    const message = (text || input).trim()
    if (!message || busy) return
    setInput(''); setBusy(true)
    setMessages((m) => [...m, { role: 'user', content: message }])
    try {
      const r = await sendChat(message)
      setMessages((m) => [...m, { role: 'assistant', ...r.data }])
    } catch {
      setMessages((m) => [...m, { role: 'assistant', reply: 'Chat failed — is the backend running?', memory_count: 0 }])
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto flex h-[calc(100vh-4rem)] max-w-4xl flex-col space-y-4">
      <header>
        <h1 className="text-2xl font-bold text-white">AI Strategy Chat</h1>
        <p className="mt-1 text-sm text-slate-400">Every answer is grounded in recalled Hindsight memories — citations shown under each reply.</p>
      </header>

      <div className="card flex-1 space-y-4 overflow-y-auto">
        {messages.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center gap-4 text-center">
            <p className="text-sm text-slate-400">Ask anything about your content history and strategy.</p>
            <div className="flex flex-wrap justify-center gap-2">
              {SUGGESTIONS.map((s) => (
                <button key={s} onClick={() => send(s)} className="btn-secondary text-xs">{s}</button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={m.role === 'user' ? 'flex justify-end' : 'flex justify-start'}>
            <div className={m.role === 'user'
              ? 'max-w-[80%] rounded-2xl rounded-br-sm bg-indigo-500 px-4 py-2.5 text-sm text-white'
              : 'max-w-[85%] space-y-2 rounded-2xl rounded-bl-sm bg-slate-800/80 px-4 py-3 text-sm text-slate-100'}>
              <div className="whitespace-pre-wrap">{m.role === 'user' ? m.content : m.reply}</div>
              {m.role === 'assistant' && (
                <div className="border-t border-slate-700/70 pt-2 text-xs text-slate-400">
                  {m.memory_count > 0 ? (
                    <details>
                      <summary className="cursor-pointer text-indigo-300">
                        ✦ Grounded in {m.memory_count} recalled memories {!m.llm_used && '(fallback answer)'}
                      </summary>
                      <ul className="mt-2 space-y-1">
                        {m.memories_used?.map((mem, j) => (
                          <li key={j}>– {mem.text}</li>
                        ))}
                      </ul>
                    </details>
                  ) : (
                    <span className="text-amber-400">⚠ No memories recalled — answer is generic</span>
                  )}
                </div>
              )}
            </div>
          </div>
        ))}
        {busy && <div className="text-sm text-slate-400">Recalling memories…</div>}
        <div ref={endRef} />
      </div>

      <form onSubmit={(e) => { e.preventDefault(); send() }} className="flex gap-3">
        <input className="input" placeholder="Ask your content strategy question…" value={input} onChange={(e) => setInput(e.target.value)} />
        <button disabled={busy} className="btn-primary shrink-0">Send</button>
      </form>
    </div>
  )
}
