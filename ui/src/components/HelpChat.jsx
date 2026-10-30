import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { ArrowUp, LifeBuoy, X } from 'lucide-react'
import { toast } from 'sonner'
import { api } from '../lib/api'

const STARTERS = ['My resume disappeared', "It's showing roles I can't apply to", 'Autopilot stopped working', 'Change the cities I want']

// Something wrong, or something to change? Say it in plain words: your own Claude or Codex looks at your setup and fixes it.
export function HelpChat() {
  const [open, setOpen] = useState(false)
  const [msgs, setMsgs] = useState([])
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const end = useRef(null)
  const load = () => api('/api/jobs/help/thread').then(r => setMsgs(r.thread || [])).catch(() => {})
  useEffect(() => { if (!open) return; load(); const t = setInterval(load, 3000); return () => clearInterval(t) }, [open])
  useEffect(() => { end.current?.scrollIntoView({ block: 'end' }) }, [msgs.length, open])
  const send = async t => {
    const s = (t ?? text).trim()
    if (!s || busy) return
    setBusy(true); setText('')
    try { const r = await api('/api/jobs/help/message', { text: s }); setMsgs(r.thread || []) }
    catch (e) { toast.error(e.message); setText(s) }
    setBusy(false)
  }
  return (
    <>
      <button onClick={() => setOpen(o => !o)} aria-label="Help"
        className="fixed bottom-[88px] right-4 z-50 flex h-11 items-center gap-2 rounded-full bg-[#2c2c2e] px-4 text-[13.5px] font-medium text-white shadow-lg ring-1 ring-white/10 hover:bg-[#3a3a3c] md:bottom-6 md:right-6">
        {open ? <X className="size-4" /> : <LifeBuoy className="size-4" />}{open ? 'Close' : 'Help'}
      </button>
      <AnimatePresence>{open && (
        <motion.div initial={{ opacity: 0, y: 12, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 12, scale: 0.98 }}
          transition={{ type: 'spring', stiffness: 380, damping: 32 }}
          className="fixed bottom-[144px] right-4 z-50 flex max-h-[min(560px,70vh)] w-[min(400px,calc(100vw-32px))] flex-col overflow-hidden rounded-[20px] bg-[#1c1c1e] shadow-2xl ring-1 ring-white/10 md:bottom-20 md:right-6">
          <div className="border-b border-white/[.08] px-5 py-4">
            <div className="text-[15px] font-semibold text-white">Help</div>
            <div className="mt-0.5 text-[12.5px] text-muted">Say what's wrong or what to change. Your twin checks your setup and fixes it.</div>
          </div>
          <div className="flex-1 space-y-2.5 overflow-y-auto px-4 py-4">
            {!msgs.length && <div className="flex flex-wrap gap-1.5">{STARTERS.map(s => (
              <button key={s} onClick={() => send(s)} className="rounded-full bg-white/[.06] px-3 py-1.5 text-[12.5px] text-white/85 hover:bg-white/[.1]">{s}</button>))}</div>}
            {msgs.map((m, i) => (
              <div key={i} className={'max-w-[85%] whitespace-pre-wrap rounded-[16px] px-3.5 py-2 text-[13.5px] leading-snug ' +
                (m.role === 'you' ? 'ml-auto bg-signal text-white' : 'bg-white/[.07] text-white/90')}>{m.text}</div>))}
            <div ref={end} />
          </div>
          <form onSubmit={e => { e.preventDefault(); send() }} className="flex items-end gap-2 border-t border-white/[.08] p-3">
            <textarea value={text} onChange={e => setText(e.target.value)} rows={1} placeholder="Describe the problem…"
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
              className="max-h-28 min-h-[38px] flex-1 resize-none rounded-[12px] bg-white/[.06] px-3 py-2 text-[13.5px] text-white outline-none placeholder:text-faint" />
            <button type="submit" disabled={!text.trim() || busy} aria-label="Send"
              className="grid size-[38px] place-items-center rounded-full bg-signal text-white disabled:opacity-40"><ArrowUp className="size-4" /></button>
          </form>
        </motion.div>)}
      </AnimatePresence>
    </>)
}
