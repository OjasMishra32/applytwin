import { useEffect, useMemo, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import * as Dialog from '@radix-ui/react-dialog'
import { toast } from 'sonner'
import { Check, ChevronRight, ExternalLink, Loader2, Plus, Search, Sparkles, X, FileDown, Bot } from 'lucide-react'
import { api, fileUrl, safeUrl } from '../lib/api'
import { ago } from '../lib/utils'
import { useApp, Page } from '../App'
import { Avatar, Badge, Button, Fit, GlideList, Reveal, Ring, Segmented, Stagger, Title, item, spring } from '../components/ui'

export default function Jobs({ arg }) {
  const { go, startScan, scan } = useApp()
  const [q, setQ] = useState('')
  const [status, setStatus] = useState('new')
  const [order, setOrder] = useState('fit')
  const [list, setList] = useState(null)
  const [add, setAdd] = useState(false)
  const t = useRef()
  const load = () => api(`/api/jobs?q=${encodeURIComponent(q)}&status=${status}&order=${order}&limit=200${status === 'new' ? '' : '&min=0'}`).then(setList)
  useEffect(() => { clearTimeout(t.current); t.current = setTimeout(load, 180) }, [q, status, order, scan?.running])

  return (
    <div className="relative">
      
      <Page>
        <Title sub="Every match from every source, scored against you." right={<>
          <Button variant="white" onClick={() => setAdd(true)}><Plus className="size-4" />Add a job</Button>
          <Button onClick={startScan} loading={scan?.running}>{scan?.running ? 'Scanning' : 'Scan now'}</Button></>}>
          Jobs
        </Title>
        <div className="card mb-4 flex flex-wrap items-center gap-3 p-2.5">
          <div className="relative min-w-[240px] flex-1"><Search className="absolute left-3.5 top-2.5 size-4 text-faint" />
            <input value={q} onChange={e => setQ(e.target.value)} placeholder="Search roles, companies or places" className="h-9 w-full rounded-[10px] bg-white/[.06] pl-10 pr-4 text-[14px] text-white outline-none placeholder:text-faint focus:ring-2 focus:ring-signal" /></div>
          <Segmented id="st" value={status} onChange={setStatus} options={[['new', 'New'], ['applied', 'Applied'], ['skipped', 'Skipped'], ['all', 'All']]} />
          <Segmented id="ord" value={order} onChange={setOrder} options={[['fit', 'Best fit'], ['new', 'Newest']]} />
        </div>
        <div className="card overflow-hidden">
          {!list ? <div className="space-y-px p-2">{Array.from({ length: 8 }, (_, i) => <div key={i} className="skel h-[62px]" />)}</div> :
            list.length ? (
              <Stagger className="py-1" delay={0.018}>
                <GlideList id="jobs" rows={list.map(j => ({ key: j.id, onClick: () => go('jobs', j.id), content: <>
                  <Avatar name={j.company} />
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-[15px] font-medium text-ink">{j.title}</div>
                    <div className="mt-0.5 flex items-center gap-2 truncate text-[13px] text-muted">
                      <span className="truncate">{j.company} · {j.location || 'Multiple / remote'}</span>
                      <Badge className="hidden sm:inline-flex">{j.ats}</Badge>{j.found_at && <span className="text-faint">{ago(j.found_at)}</span>}
                    </div>
                  </div>
                  {j.status !== 'new' && <Badge tone={j.status === 'applied' ? 'good' : 'gray'}>{j.status}</Badge>}
                  <Fit v={j.fit} /><ChevronRight className="size-4 text-faint transition-transform group-hover:translate-x-1 group-hover:text-signal" /></> }))} />
              </Stagger>
            ) : <div className="py-20 text-center text-[14px] text-muted">Nothing here yet. Scan, or loosen your filters in Settings.</div>}
        </div>
      </Page>
      <JobSheet id={arg} onClose={() => go('jobs')} onChange={load} />
      <AddJob open={add} setOpen={setAdd} />
    </div>
  )
}

// the steps follow the real work: the agent's writing is the long one (about a minute), so it says so and counts up
const clock = s => { s = Math.max(0, Math.round(s)); return s >= 60 ? `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}` : `${s}s` }

// Live progress of a resume build: the step it is really on, and time left from how long each step takes on this computer.
// Polled twice a second; between polls the countdown runs locally so it moves smoothly.
function BuildProgress({ p, since }) {
  const [now, setNow] = useState(Date.now())
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 200); return () => clearInterval(t) }, [])
  const drift = p ? (now - since) / 1000 : 0
  const elapsed = (p?.elapsed || 0) + drift, left = Math.max(1, (p?.eta || 0) - drift)
  const pct = p ? Math.min(97, (elapsed / (elapsed + left)) * 100) : 2
  const steps = (p?.steps || []).filter(s => s.state !== 'skipped')
  return (
    <div className="mt-5">
      <div className="flex items-baseline justify-between text-[13px]">
        <span className="font-medium text-ink">{p ? steps.find(s => s.state === 'now')?.label || 'Starting' : 'Starting'}</span>
        <span className="tabular-nums text-muted">{p ? `${p.slow ? 'taking a bit longer than usual · ' : ''}about ${clock(left)} left · ${clock(elapsed)}` : ''}</span>
      </div>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-mist">
        <motion.div className="h-full rounded-full bg-signal" animate={{ width: `${pct}%` }} transition={{ ease: 'linear', duration: 0.25 }} />
      </div>
      <div className="mt-4 space-y-2">{steps.map(s => (
        <div key={s.id} className={`flex items-center gap-3 text-[13.5px] ${s.state === 'next' ? 'opacity-40' : ''}`}>
          <span className={`grid size-5 place-items-center rounded-full ${s.state === 'done' ? 'bg-good text-white' : s.state === 'now' ? 'bg-signal/10 text-signal' : 'bg-mist text-faint'}`}>
            {s.state === 'done' ? <Check className="size-3" strokeWidth={3} /> : s.state === 'now' ? <Loader2 className="size-3 animate-spin" /> : null}</span>{s.label}</div>))}</div>
    </div>)
}

function JobSheet({ id, onClose, onChange }) {
  const { templates } = useApp()
  const [job, setJob] = useState(null)
  const [rep, setRep] = useState(null)
  const [tpl, setTpl] = useState('')
  const [building, setBuilding] = useState(false)
  const [prog, setProg] = useState(null)   // [progress, when it was read]
  const [res, setRes] = useState(null)
  useEffect(() => {   // a build already running (Autopilot started it when it claimed this job) shows its progress too
    if (!id) return
    let alive = true
    const poll = () => api(`/api/jobs/${id}/progress`).then(r => { if (alive) setProg(r.progress ? [r.progress, Date.now()] : null) }).catch(() => {})
    poll(); const t = setInterval(poll, 500)
    return () => { alive = false; clearInterval(t) }
  }, [id])
  useEffect(() => {
    setJob(null); setRep(null); setRes(null); setBuilding(false); setProg(null)
    if (!id) return
    api('/api/jobs/' + id).then(setJob); api(`/api/jobs/${id}/ats`).then(setRep)
  }, [id])
  const tailor = async () => {
    const fresh = !!res
    setRes(null); setBuilding(true)
    const go = () => api(`/api/jobs/${id}/tailor`, { template: tpl || undefined, mode: 'auto', fresh })
    try {
      setRes(await go())
    } catch (e) {
      // the app restarts itself after an update; if that cut the build off, wait for it and build again once
      if (e.server) toast.error('Could not build: ' + e.message)
      else {
        await new Promise(ok => setTimeout(ok, 5000))
        try { setRes(await go()) } catch (e2) { toast.error('Could not build: ' + e2.message) }
      }
    }
    setBuilding(false)
  }
  const mark = async st => {
    if (st === 'applied') { await api(`/api/jobs/${id}/log`, { status: 'Applied', notes: 'marked in app' }); toast.success('Logged as applied', { description: 'Nice. Your twin will remember what worked.' }) }
    else if (st === 'skipped') await api(`/api/jobs/${id}/skip`, {})   // also clears it from Needs you
    else await api(`/api/jobs/${id}/status`, { status: st })
    onChange(); onClose()
  }
  const hard = (rep?.matched || []).filter(m => m.hard), miss = (rep?.missing || []).filter(m => m.hard)
  return (
    <Dialog.Root open={!!id} onOpenChange={o => !o && onClose()}>
      <AnimatePresence>{id && (
        <Dialog.Portal forceMount>
          <Dialog.Overlay asChild><motion.div className="fixed inset-0 z-40 bg-black/25 backdrop-blur-[2px]" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} /></Dialog.Overlay>
          <Dialog.Content asChild aria-describedby={undefined}>
            <motion.div initial={{ x: '105%' }} animate={{ x: 0 }} exit={{ x: '105%' }} transition={{ type: 'spring', stiffness: 260, damping: 32 }}
              className="fixed bottom-3 right-3 top-3 z-50 w-[min(780px,calc(100vw-24px))] overflow-y-auto rounded-[18px] bg-[#1c1c1e] ring-1 ring-white/10 p-7 shadow-[0_40px_100px_rgb(0_0_0/.28)] outline-none">
              <Dialog.Title className="sr-only">{job?.title || 'Job'}</Dialog.Title>
              <button onClick={onClose} className="absolute right-5 top-5 grid size-9 place-items-center rounded-full bg-white/[.05] text-muted transition hover:text-ink"><X className="size-4" /></button>
              {!job ? <div className="space-y-3 pt-6"><div className="skel h-12 w-2/3" /><div className="skel h-40" /><div className="skel h-64" /></div> : <>
                <div className="flex items-start gap-4 pr-10">
                  <Avatar name={job.company} size={52} />
                  <div className="min-w-0"><div className="text-[14px] text-muted">{job.company}</div>
                    <h2 className="font-display text-[34px] font-semibold tracking-[-0.035em] leading-[1.05] text-ink">{job.title}</h2>
                    <div className="mt-1.5 flex flex-wrap items-center gap-2 text-[13px] text-muted"><span>{job.location || 'Multiple / remote'}</span><Badge>{job.ats}</Badge>
                      <Badge tone="sky">fit {Math.round(job.fit)}</Badge>{job.fit_why && <span className="text-faint">{job.fit_why}</span>}</div></div>
                </div>
                <div className="mt-5 flex flex-wrap gap-2">
                  <a href={safeUrl(job.apply_url || job.url)} target="_blank" rel="noreferrer"><Button variant="sky"><ExternalLink className="size-4" />Open application</Button></a>
                  <Button variant="white" onClick={() => { navigator.clipboard.writeText(`twin: apply to job ${job.id}`); toast('Copied. Paste it into Claude Code or Codex.') }}><Bot className="size-4" />Have my agent apply</Button>
                  <Button variant="white" onClick={() => mark('applied')}><Check className="size-4" />I applied</Button>
                  <Button variant="danger" onClick={() => mark('skipped')}>Skip</Button>
                </div>

                <div className="mt-6 flex items-center gap-6 rounded-[18px] bg-mist p-5">
                  <Ring value={rep?.coverage ?? 0} size={92} stroke={8} />
                  <div className="min-w-0 flex-1"><div className="font-display text-[22px] font-semibold tracking-[-0.035em] leading-tight text-ink">Keyword match</div>
                    <div className="mb-2.5 text-[13px] text-muted">{rep?.terms || 0} skills in the posting. Tailoring surfaces the ones you have; the rest are a study list.</div>
                    <div className="flex flex-wrap gap-1.5">
                      {hard.slice(0, 14).map(m => <Badge key={m.term} tone="good"><Check className="size-3" />{m.term}</Badge>)}
                      {miss.slice(0, 8).map(m => <Badge key={m.term} tone="warn">{m.term}</Badge>)}</div></div>
                </div>

                <div className="mt-5 rounded-[18px] border border-line p-5">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div><div className="font-display text-[24px] font-semibold tracking-[-0.035em] leading-tight text-ink">Your resume for this job</div>
                      <div className="text-[13px] text-muted">Built from your vault. Nothing invented: a fact guard checks every line.</div></div>
                    <div className="flex items-center gap-2">
                      <select value={tpl} onChange={e => setTpl(e.target.value)} className="h-10 rounded-full bg-white/[.05] px-4 text-[13.5px] outline-none">
                        <option value="">Best template for this field</option>{templates.map(t => <option key={t.id} value={t.id}>{t.label}</option>)}</select>
                      <Button onClick={tailor} loading={building}><Sparkles className="size-4" />{res ? 'Rebuild' : 'Build it'}</Button>
                    </div>
                  </div>
                  <AnimatePresence>{(building || prog) && !res && (
                    <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
                      <BuildProgress p={prog?.[0]} since={prog?.[1] || Date.now()} />
                    </motion.div>)}</AnimatePresence>
                  {res && (
                    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={spring}>
                      <div className="mt-5 flex flex-wrap items-center gap-2">
                        <Badge tone={res.coverage >= 70 ? 'good' : 'sky'}>{res.coverage}% keywords</Badge><Badge tone="sky">ATS {res.score}</Badge>
                        <Badge>{res.pages} page</Badge><Badge>{res.style}</Badge><Badge>{res.field}</Badge>
                        {res.rewrites > 0 && <Badge tone="good">{res.rewrites} lines rewritten</Badge>}
                        {res.rejected?.length > 0 && <Badge tone="warn">{res.rejected.length} blocked by fact guard</Badge>}
                        <a href={fileUrl(res.pdf)} target="_blank" rel="noreferrer" className="ml-auto"><Button size="sm" variant="sky"><FileDown className="size-4" />Download PDF</Button></a>
                      </div>
                      {res.positioning && <div className="mt-4 rounded-[12px] bg-white/[.04] px-4 py-3">
                        <div className="text-[12px] font-semibold uppercase tracking-[0.05em] text-faint">How your twin positioned you</div>
                        <div className="mt-1 text-[14.5px] leading-snug text-white">{res.positioning}</div>
                        {res.requirements?.length > 0 && <div className="mt-2 flex flex-wrap gap-1.5">{res.requirements.map(r => <Badge key={r}>{r}</Badge>)}</div>}
                      </div>}
                      <Paper src={`/preview?job=${id}&template=${res.style}&t=${Date.now()}`} className="mt-4" />
                      {res.dropped?.length > 0 && <div className="mt-3 text-[12.5px] text-faint">Left out to fit one page: {res.dropped.slice(0, 6).join(' · ')}{res.dropped.length > 6 ? '…' : ''}</div>}
                    </motion.div>)}
                </div>
                <div className="mt-6"><div className="label mb-2">The posting</div>
                  <div className="max-h-[420px] overflow-y-auto whitespace-pre-wrap rounded-[18px] bg-mist p-5 text-[13.5px] leading-relaxed text-fg">{job.description || 'No description available. Open the posting to read it.'}</div></div>
              </>}
            </motion.div>
          </Dialog.Content>
        </Dialog.Portal>)}</AnimatePresence>
    </Dialog.Root>
  )
}

export function Paper({ src, className, html }) {
  const box = useRef(null)
  const [k, setK] = useState(0.6)
  useEffect(() => { const f = () => box.current && setK(box.current.clientWidth / 816); f(); const ro = new ResizeObserver(f); ro.observe(box.current); return () => ro.disconnect() }, [])
  return (
    <div ref={box} className={`relative aspect-[8.5/11] overflow-hidden rounded-[8px] bg-white shadow-[0_2px_6px_rgb(0_0_0/.06),0_24px_60px_rgb(0_0_0/.12)] ${className || ''}`}>
      <iframe title="resume" src={src} srcDoc={html} className="absolute left-0 top-0 h-[1056px] w-[816px] origin-top-left border-0" style={{ transform: `scale(${k})` }} />
    </div>
  )
}

function AddJob({ open, setOpen }) {
  const { go } = useApp()
  const [f, setF] = useState({ url: '', title: '', company: '', description: '' })
  const submit = async () => { const j = await api('/api/jobs', f); setOpen(false); toast.success('Added'); go('jobs', j.id) }
  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/25 backdrop-blur-[2px]" />
        <Dialog.Content aria-describedby={undefined} className="fixed left-1/2 top-1/2 z-50 w-[min(560px,92vw)] -translate-x-1/2 -translate-y-1/2 rounded-[18px] bg-[#1c1c1e] ring-1 ring-white/10 p-7 shadow-[0_40px_100px_rgb(0_0_0/.28)] outline-none">
          <Dialog.Title className="font-display text-[32px] font-semibold tracking-[-0.035em] text-ink">Add any job</Dialog.Title>
          <p className="mb-5 text-[14px] text-muted">Paste the link. Pasting the description too makes the resume sharper.</p>
          <div className="space-y-4">
            {[['url', 'Job link', 'https://…'], ['title', 'Title', 'Software Engineer Intern'], ['company', 'Company', 'Acme']].map(([k, l, ph]) => (
              <label key={k} className="block"><div className="label mb-1">{l}</div><input className="uline left" placeholder={ph} value={f[k]} onChange={e => setF({ ...f, [k]: e.target.value })} /></label>))}
            <label className="block"><div className="label mb-1">Description (optional)</div><textarea rows={6} className="box" value={f.description} onChange={e => setF({ ...f, description: e.target.value })} /></label>
          </div>
          <div className="mt-6 flex justify-end gap-2"><Button variant="ghost" onClick={() => setOpen(false)}>Cancel</Button><Button onClick={submit} arrow>Add job</Button></div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
