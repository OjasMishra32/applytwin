import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'motion/react'
import { toast } from 'sonner'
import { api, fileUrl } from '../lib/api'
import { useApp, Page } from '../App'
import { Avatar, Button, Title, burst, spring } from '../components/ui'
import { Mail, Upload } from 'lucide-react'

const COLS = [['Needs User', 'Needs you', '#ff9f0a'], ['Applied', 'Applied', '#0a84ff'], ['Interview', 'Interview', '#bf5af2'], ['Offer', 'Offer', '#30d158'],
  ['Rejected', 'Rejected', '#7d869f'], ['Failed', "Didn't go through", '#ff453a'], ['Skipped', 'Skipped', '#5f6a8a']]

export default function Board() {
  const [apps, setApps] = useState(null)
  const [drag, setDrag] = useState(null)
  const [over, setOver] = useState(null)
  const load = () => api('/api/applications?history=1').then(a => { const m = {}; a.forEach(x => { if (!m[x.job_id]) m[x.job_id] = x }); setApps(Object.values(m)) })
  useEffect(() => { load() }, [])
  const move = async (a, st) => {
    if (a.status === st) return
    setApps(xs => xs.map(x => x.job_id === a.job_id ? { ...x, status: st } : x))
    if (st === 'Offer') burst()
    await api(`/api/jobs/${a.job_id}/log`, { status: st, notes: `moved to ${st}` })
    toast.success(st === 'Offer' ? 'Congratulations!' : `Moved to ${st}`, { description: ['Interview', 'Offer', 'Rejected'].includes(st) ? 'Your twin learns from this.' : undefined })
  }
  const importCsv = async e => {
    const f = e.target.files?.[0]; if (!f) return
    try {
      const r = await api('/api/history', { text: await f.text() }); load()
      toast.success(`Found ${r.known_applications.toLocaleString()} applications`, { description: `${r.matched.toLocaleString()} matched jobs in your queue, so your twin won't apply to them again.` })
    } catch (err) { toast.error(err.message) } e.target.value = ''
  }
  const ImportBtn = ({ primary }) => (
    <label className="cursor-pointer"><input type="file" accept=".csv,text/csv" className="hidden" onChange={importCsv} />
      <span className={'inline-flex h-10 items-center gap-1.5 rounded-full px-5 text-[14px] font-medium ' + (primary ? 'bg-white text-[#1d1d1f] hover:bg-white/90' : 'bg-white/[.08] text-ink hover:bg-white/[.13]')}>
        <Upload className="size-4" />Import your tracker</span></label>)
  const fromEmail = async () => {
    try {
      await api('/api/history/email', {})
      toast.success('Reading your confirmation emails', { description: "Your twin opens your email in its browser and records every job you already applied to. If you're not signed in there, it'll ask you to sign in once." })
    } catch (err) { toast.error(err.message) }
  }
  const EmailBtn = () => (
    <button onClick={fromEmail} className="inline-flex h-10 items-center gap-1.5 rounded-full bg-white/[.08] px-5 text-[14px] font-medium text-ink hover:bg-white/[.13]">
      <Mail className="size-4" />Find them in my email</button>)
  const empty = apps && apps.length === 0
  return (
    <div className="relative"><Page wide>
      <Title sub="Every application your twin sends lands here. Drag a card when you hear back; interviews and offers teach your twin what works."
        right={!empty && <div className="flex flex-wrap gap-2"><EmailBtn /><ImportBtn /></div>}>
        Applications</Title>
      {empty ? (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={spring}
          className="mx-auto mt-6 max-w-[560px] rounded-[22px] bg-[#1c1c1e] px-8 py-12 text-center ring-1 ring-white/[.06]">
          <h2 className="text-[22px] font-bold tracking-[-0.02em] text-white">No applications yet</h2>
          <p className="mx-auto mt-2 max-w-[400px] text-[15px] leading-relaxed text-muted">Start your twin and every application shows up here, from needs-you to offer. Already applied somewhere? Import your tracker so your twin never applies twice.</p>
          <div className="mt-7 flex flex-wrap justify-center gap-3">
            <a href="#agents" className="inline-flex h-10 items-center rounded-full bg-signal px-5 text-[14px] font-semibold text-white hover:bg-[#2b95ff]">Start Autopilot</a>
            <EmailBtn />
            <ImportBtn />
          </div>
          <p className="mt-4 text-[12.5px] text-faint">Your twin can read your "thank you for applying" emails, or import a CSV from Simplify, Huntr, Teal, Notion or a spreadsheet</p>
        </motion.div>
      ) : (
      <div className="-mx-4 flex gap-3 overflow-x-auto px-4 pb-4 sm:-mx-6 sm:px-6 md:-mx-10 md:px-10">
        {COLS.map(([st, label, color]) => {
          const xs = (apps || []).filter(a => a.status === st)
          return (
            <div key={st} onDragOver={e => { e.preventDefault(); setOver(st) }} onDragLeave={() => setOver(null)}
              onDrop={() => { setOver(null); drag && move(drag, st); setDrag(null) }}
              className={`min-h-[160px] w-[236px] shrink-0 rounded-[14px] bg-white/[.025] p-2 ring-1 transition-colors ${over === st ? 'bg-signal/[.08] ring-2 ring-signal' : 'ring-white/[.04]'}`}>
              <div className="mb-2 flex h-8 items-center justify-between px-2"><div className="flex items-center gap-2 text-[13px] font-semibold text-ink">
                <span className="size-2 rounded-full" style={{ background: color }} />{label}</div><span className="text-[13px] tabular-nums text-muted">{apps ? xs.length.toLocaleString() : ''}</span></div>
              <div className="space-y-2">
                <AnimatePresence>{xs.slice(0, 40).map(a => (
                  <motion.div layout layoutId={a.job_id} key={a.job_id} transition={spring} draggable onDragStart={() => setDrag(a)}
                    initial={{ opacity: 0, scale: .96 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }}
                    className="cursor-grab rounded-[10px] bg-[#232325] p-3 ring-1 ring-white/[.06] transition-colors hover:bg-[#2a2a2c] active:cursor-grabbing">
                    <div className="flex items-center gap-2.5"><Avatar name={a.company} size={30} />
                      <div className="min-w-0"><div className="truncate text-[13px] font-semibold text-ink">{a.company}</div>
                        <div className="truncate text-[12px] text-muted">{a.title}</div></div></div>
                    <div className="mt-2 flex items-center justify-between text-[12px] text-faint">
                      <span>{new Date(a.at * 1000).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}</span>
                      {a.resume_path && <a href={fileUrl(a.resume_path)} target="_blank" rel="noreferrer" draggable={false} className="font-medium text-signal-ink hover:underline">Resume</a>}</div>
                  </motion.div>))}</AnimatePresence>
                {xs.length > 40 && <div className="px-2 py-2 text-center text-[12.5px] text-faint">{(xs.length - 40).toLocaleString()} more</div>}
                {!apps && [0, 1].map(i => <div key={i} className="skel h-[76px]" />)}
                {apps && !xs.length && <div className="rounded-[10px] border border-dashed border-white/[.08] px-3 py-5 text-center text-[12.5px] text-faint">{st === 'Interview' || st === 'Offer' ? 'Drag a card here when you hear back' : 'None'}</div>}
              </div>
            </div>)
        })}
      </div>
      )}
    </Page></div>
  )
}
