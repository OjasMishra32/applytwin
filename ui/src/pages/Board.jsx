import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'motion/react'
import { toast } from 'sonner'
import { api, fileUrl } from '../lib/api'
import { useApp, Page } from '../App'
import { Avatar, NumberTicker, Title, burst, spring } from '../components/ui'

const COLS = [['Needs User', 'Needs you', 'var(--color-signal)'], ['Applied', 'Applied', 'var(--color-ink)'], ['Interview', 'Interview', '#2f5bd3'], ['Offer', 'Offer', 'var(--color-good)'], ['Rejected', 'Rejected', '#9ca3af']]

export default function Board() {
  const [apps, setApps] = useState(null)
  const [drag, setDrag] = useState(null)
  const [over, setOver] = useState(null)
  const load = () => api('/api/applications').then(a => { const m = {}; a.forEach(x => { if (!m[x.job_id]) m[x.job_id] = x }); setApps(Object.values(m)) })
  useEffect(() => { load() }, [])
  const move = async (a, st) => {
    if (a.status === st) return
    setApps(xs => xs.map(x => x.job_id === a.job_id ? { ...x, status: st } : x))
    if (st === 'Offer') burst()
    await api(`/api/jobs/${a.job_id}/log`, { status: st, notes: `moved to ${st}` })
    toast.success(st === 'Offer' ? 'Congratulations!' : `Moved to ${st}`, { description: ['Interview', 'Offer', 'Rejected'].includes(st) ? 'Your twin learns from this.' : undefined })
  }
  return (
    <div className="relative"><Page wide>
      <Title n="05" sub="Drag a card when you hear back. Interviews and offers teach your twin what works for you.">
        Applications</Title>
      <div className="grid gap-4 overflow-x-auto pb-4 md:grid-cols-5">
        {COLS.map(([st, label, color]) => {
          const xs = (apps || []).filter(a => a.status === st)
          return (
            <div key={st} onDragOver={e => { e.preventDefault(); setOver(st) }} onDragLeave={() => setOver(null)}
              onDrop={() => { setOver(null); drag && move(drag, st); setDrag(null) }}
              className={`min-h-[420px] rounded-[18px] p-3 transition ${over === st ? 'bg-signal/[.07] ring-2 ring-signal/40' : 'bg-white/[.03]'}`}>
              <div className="mb-3 flex items-center justify-between px-1.5"><div className="flex items-center gap-2 text-[13.5px] font-semibold text-ink">
                <span className="size-2.5" style={{ background: color }} />{label}</div><span className="text-[20px] font-semibold tabular-nums tracking-[-0.03em] text-white"><NumberTicker value={xs.length} /></span></div>
              <div className="space-y-2.5">
                <AnimatePresence>{xs.map(a => (
                  <motion.div layout layoutId={a.job_id} key={a.job_id} transition={spring} draggable onDragStart={() => setDrag(a)}
                    initial={{ opacity: 0, scale: .96 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }}
                    className="card cursor-grab p-3.5 active:cursor-grabbing">
                    <div className="flex items-center gap-2.5"><Avatar name={a.company} size={30} />
                      <div className="min-w-0"><div className="truncate text-[13px] font-semibold text-ink">{a.company}</div>
                        <div className="truncate text-[12px] text-muted">{a.title}</div></div></div>
                    <div className="mt-2.5 flex items-center justify-between text-[11.5px] text-faint">
                      <span>{new Date(a.at * 1000).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}</span>
                      {a.resume_path && <a href={fileUrl(a.resume_path)} target="_blank" rel="noreferrer" className="font-medium text-signal-ink hover:underline">resume</a>}</div>
                  </motion.div>))}</AnimatePresence>
                {apps && !xs.length && <div className="rounded-[18px] border border-dashed border-line-2 px-3 py-8 text-center text-[12.5px] text-faint">Nothing here yet</div>}
              </div>
            </div>)
        })}
      </div>
    </Page></div>
  )
}
