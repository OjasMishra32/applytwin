import { useEffect, useMemo, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import * as Dialog from '@radix-ui/react-dialog'
import { toast } from 'sonner'
import { Check, ChevronRight, ExternalLink, Loader2, Plus, Search, Sparkles, X, FileDown, Bot } from 'lucide-react'
import { api, fileUrl, safeUrl } from '../lib/api'
import { ago, atsName } from '../lib/utils'
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
        <div className="card mb-4 flex flex-wrap items-center gap-2 p-2">
          <div className="relative min-w-[200px] flex-1 basis-[240px]"><Search className="absolute left-3 top-2.5 size-4 text-faint" />
            <input value={q} onChange={e => setQ(e.target.value)} placeholder="Search roles, companies or places" className="h-9 w-full rounded-[8px] bg-white/[.06] pl-9 pr-3 text-[14px] text-white outline-none placeholder:text-faint focus:ring-2 focus:ring-signal" /></div>
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
                      <Badge className="hidden sm:inline-flex">{atsName(j.ats)}</Badge>{j.found_at && <span className="text-faint">{ago(j.found_at)}</span>}
                    </div>
                  </div>
                  {j.status !== 'new' && <Badge tone={j.status === 'applied' ? 'good' : 'gray'} className="capitalize">{j.status}</Badge>}
                  <Fit v={j.fit} /><ChevronRight className="size-4 text-faint transition-transform group-hover:translate-x-1 group-hover:text-signal" /></> }))} />
              </Stagger>
            ) : <div className="px-6 py-16 text-center">
                <div className="text-[15px] font-semibold text-white">{q ? `Nothing matches “${q}”` : { applied: 'No applications yet', skipped: 'Nothing skipped' }[status] || 'No jobs here yet'}</div>
                <div className="mx-auto mt-1 max-w-[380px] text-[13px] text-muted">{q ? 'Try a company, a role or a city.' : status === 'new' ? 'Press Scan now to read every career page, or lower the minimum fit in Settings.' : 'Jobs you apply to or skip show up here.'}</div>
                {q ? <Button variant="white" size="sm" className="mt-4" onClick={() => setQ('')}>Clear search</Button>
                  : status === 'new' && <Button size="sm" className="mt-4" onClick={startScan} loading={scan?.running}>{scan?.running ? 'Scanning' : 'Scan now'}</Button>}
              </div>}
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
        <span className="font-medium text-ink">{p ? 'Building your resume' : 'Starting…'}</span>
        <span className="tabular-nums text-muted">{p ? `${p.slow ? 'Taking longer than usual · ' : ''}${clock(elapsed)} elapsed · about ${clock(left)} left` : ''}</span>
      </div>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-mist">
        <motion.div className="h-full rounded-full bg-signal" animate={{ width: `${pct}%` }} transition={{ ease: 'linear', duration: 0.25 }} />
      </div>
      <div className="mt-4 space-y-2">{steps.map(s => (
        <div key={s.id} className={`flex items-center gap-3 text-[13.5px] ${s.state === 'next' ? 'text-faint' : s.state === 'done' ? 'text-muted' : 'text-ink'}`}>
          <span className={`grid size-5 shrink-0 place-items-center rounded-full ${s.state === 'done' ? 'bg-good text-white' : s.state === 'now' ? 'bg-signal/15 text-signal-ink' : 'ring-[1.5px] ring-inset ring-white/15'}`}>
            {s.state === 'done' ? <Check className="size-3" strokeWidth={3} /> : s.state === 'now' ? <Loader2 className="size-3 animate-spin" /> : null}</span>{s.label}</div>))}</div>
      {p?.live && <Watch live={p.live} />}
    </div>)
}

// Watch it tailor: what the plan has decided so far, read live from the plan as it's written. The requirements this
// posting screens for, the story it tells about you, and each line turning from your words into the posting's.
function Watch({ live }) {
  const reqs = live.requirements || [], rw = (live.rewrites || []).slice(-3)
  if (!reqs.length && !live.positioning && !rw.length) return null
  return (
    <div className="mt-6 space-y-5 border-t border-line pt-5">
      {reqs.length > 0 && <div>
        <div className="text-[11.5px] font-semibold uppercase tracking-[0.06em] text-faint">What they screen for</div>
        <div className="mt-2 flex flex-wrap gap-1.5"><AnimatePresence initial={false}>{reqs.map((r, i) => (
          <motion.span key={i} layout initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={spring}
            className="rounded-full bg-white/[.06] px-3 py-1 text-[12.5px] text-ink"><span className="mr-1.5 text-faint">{i + 1}</span>{r}</motion.span>))}
        </AnimatePresence></div></div>}
      {live.positioning && <div>
        <div className="text-[11.5px] font-semibold uppercase tracking-[0.06em] text-faint">Your story for this job</div>
        <div className="mt-1.5 text-[15px] leading-snug text-ink">{live.positioning}</div></div>}
      {rw.length > 0 && <div>
        <div className="text-[11.5px] font-semibold uppercase tracking-[0.06em] text-faint">Rewriting your lines</div>
        <div className="mt-2 space-y-2.5"><AnimatePresence initial={false}>{rw.map(x => (
          <motion.div key={x.from || x.to} layout initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={spring}
            className="rounded-[12px] bg-white/[.04] px-3.5 py-2.5">
            {x.from && <div className="text-[12px] leading-snug text-faint line-through decoration-white/20">{x.from}</div>}
            <div className="mt-1 text-[13.5px] leading-snug text-ink"><Diff from={x.from} to={x.to} /></div>
          </motion.div>))}
        </AnimatePresence></div></div>}
    </div>)
}

// the words the rewrite brought in, tinted, so you see exactly what changed
function Diff({ from, to }) {
  // the same word pieces on both sides ("company's" is company + s, "1,000+" is 1 + 000): only truly new words are tinted
  const parts = s => (s || '').toLowerCase().match(/[a-z0-9]+/g) || []
  const old = new Set(parts(from))
  return (to || '').split(/(\s+)/).map((w, i) => {
    const p = parts(w)
    return p.length && p.some(x => !old.has(x)) ? <span key={i} className="text-signal">{w}</span> : <span key={i}>{w}</span>
  })
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
    api(`/api/jobs/${id}/resume`).then(r => r.result && setRes(prev => prev || r.result)).catch(() => {})   // the resume built last time
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
    try {
      if (st === 'applied') { await api(`/api/jobs/${id}/log`, { status: 'Applied', notes: 'marked in app' }); toast.success('Logged as applied', { description: 'Nice. Your twin will remember what worked.' }) }
      else if (st === 'skipped') await api(`/api/jobs/${id}/skip`, {})   // also clears it from Needs you
      else await api(`/api/jobs/${id}/status`, { status: st })
    } catch (e) { return toast.error("Couldn't update that job", { description: e.message }) }   // stay open so nothing looks done that isn't
    onChange(); onClose()
  }
  const hard = (rep?.matched || []).filter(m => m.hard), miss = (rep?.missing || []).filter(m => m.hard)
  return (
    <Dialog.Root open={!!id} onOpenChange={o => !o && onClose()}>
      <AnimatePresence>{id && (
        <Dialog.Portal forceMount>
          <Dialog.Overlay asChild><motion.div className="fixed inset-0 z-40 bg-black/25 backdrop-blur-[2px]" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} /></Dialog.Overlay>
          <Dialog.Content asChild aria-describedby={undefined} onOpenAutoFocus={e => e.preventDefault()}>
            <motion.div initial={{ x: '105%' }} animate={{ x: 0 }} exit={{ x: '105%' }} transition={{ type: 'spring', stiffness: 260, damping: 32 }}
              className="fixed bottom-2 right-2 top-2 z-50 w-[min(780px,calc(100vw-16px))] overflow-y-auto overscroll-contain rounded-[16px] bg-[#1c1c1e] p-5 shadow-[0_40px_100px_rgb(0_0_0/.5)] outline-none ring-1 ring-white/10 sm:p-8">
              <Dialog.Title className="sr-only">{job?.title || 'Job'}</Dialog.Title>
              <button onClick={onClose} aria-label="Close" className="absolute right-4 top-4 grid size-8 place-items-center rounded-full bg-white/[.06] text-muted transition hover:bg-white/[.1] hover:text-ink"><X className="size-4" /></button>
              {!job ? <div className="space-y-3 pt-6"><div className="skel h-12 w-2/3" /><div className="skel h-40" /><div className="skel h-64" /></div> : <>
                <div className="flex flex-col items-start gap-3 pr-10 sm:flex-row sm:gap-4">
                  <Avatar name={job.company} size={48} />
                  <div className="min-w-0"><div className="text-[14px] text-muted">{job.company}</div>
                    <h2 className="mt-0.5 text-[26px] font-bold leading-[1.15] tracking-[-0.02em] text-ink">{job.title}</h2>
                    <div className="mt-1.5 flex flex-wrap items-center gap-2 text-[13px] text-muted"><span>{job.location || 'Multiple / remote'}</span><Badge>{atsName(job.ats)}</Badge>
                      <Badge tone="sky">{Math.round(job.fit)}% fit</Badge></div>
                    {job.fit_why && <div className="mt-1 text-[12.5px] text-faint first-letter:uppercase">{job.fit_why}</div>}</div>
                </div>
                <div className="mt-5 flex flex-wrap gap-2">
                  <a href={safeUrl(job.apply_url || job.url)} target="_blank" rel="noreferrer"><Button variant="sky" tabIndex={-1}><ExternalLink className="size-4" />Open application</Button></a>
                  <Button variant="white" onClick={() => { navigator.clipboard.writeText(`twin: apply to job ${job.id}`); toast('Copied. Paste it into Claude Code or Codex.') }}><Bot className="size-4" />Have my agent apply</Button>
                  <Button variant="white" onClick={() => mark('applied')}><Check className="size-4" />I applied</Button>
                  <Button variant="danger" onClick={() => mark('skipped')}>Skip</Button>
                </div>

                <div className="mt-6 flex flex-col gap-4 rounded-[14px] bg-mist p-5 sm:flex-row sm:items-center sm:gap-5">
                  <Ring value={rep?.coverage ?? 0} size={80} stroke={7} label={rep ? undefined : ''} />
                  <div className="min-w-0 flex-1"><div className="text-[17px] font-semibold leading-tight text-ink">Keyword match</div>
                    <div className="mb-2.5 mt-0.5 text-[13px] text-muted">{rep?.terms || 0} skills in the posting. Tailoring surfaces the ones you have; the rest are a study list.</div>
                    <div className="flex flex-wrap gap-1.5">
                      {hard.slice(0, 14).map(m => <Badge key={m.term} tone="good"><Check className="size-3" />{m.term}</Badge>)}
                      {miss.slice(0, 8).map(m => <Badge key={m.term} tone="warn">{m.term}</Badge>)}</div></div>
                </div>

                <div className="mt-4 rounded-[14px] border border-line p-5">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="min-w-0"><div className="text-[17px] font-semibold leading-tight text-ink">Your resume for this job</div>
                      <div className="mt-0.5 text-[13px] text-muted">Built from your vault, written for this posting. Your numbers, titles and employers are checked against it.</div></div>
                    <div className="flex flex-wrap items-center gap-2">
                      <select value={tpl} onChange={e => setTpl(e.target.value)} disabled={building} className="h-10 max-w-full rounded-full bg-white/[.06] px-4 text-[13.5px] text-ink outline-none focus:ring-2 focus:ring-signal disabled:opacity-50">
                        <option value="">Best template for this field</option>{templates.map(t => <option key={t.id} value={t.id}>{t.label}</option>)}</select>
                      <Button variant={res ? 'white' : 'ink'} onClick={tailor} loading={building}><Sparkles className="size-4" />{building ? 'Building…' : res ? 'Rebuild' : 'Build it'}</Button>
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
                        <Badge>{res.pages} page{res.pages === 1 ? '' : 's'}</Badge><Badge className="capitalize">{templates.find(t => t.id === res.style)?.label || res.style}</Badge>{res.field && <Badge className="capitalize">{res.field}</Badge>}
                        {res.rewrites > 0 && <Badge tone="good">{res.rewrites} lines rewritten</Badge>}
                        {res.rejected?.length > 0 && <Badge tone="warn">{res.rejected.length} blocked by fact guard</Badge>}
                        <a href={fileUrl(res.pdf)} target="_blank" rel="noreferrer" className="ml-auto"><Button size="sm" variant="sky" tabIndex={-1}><FileDown className="size-4" />Download PDF</Button></a>
                      </div>
                      {res.positioning && <div className="mt-4 rounded-[12px] bg-white/[.04] px-4 py-3">
                        <div className="text-[12.5px] font-medium text-muted">How your twin positioned you</div>
                        <div className="mt-1 text-[14.5px] leading-snug text-white">{res.positioning}</div>
                        {res.requirements?.length > 0 && <div className="mt-2 flex flex-wrap gap-1.5">{res.requirements.map(r => <Badge key={r}>{r}</Badge>)}</div>}
                      </div>}
                      <Paper src={`/preview?job=${id}&template=${res.style}&t=${Date.now()}`} className="mt-4" />
                      {res.dropped?.length > 0 && <div className="mt-3 text-[12.5px] text-faint">Left out to fit one page: {res.dropped.slice(0, 6).join(' · ')}{res.dropped.length > 6 ? '…' : ''}</div>}
                    </motion.div>)}
                </div>
                <div className="mt-6"><div className="mb-2 text-[17px] font-semibold text-ink">The posting</div>
                  <div className="max-h-[420px] overflow-y-auto whitespace-pre-wrap rounded-[14px] bg-mist p-5 text-[13.5px] leading-relaxed text-fg">{job.description || 'No description available. Open the posting to read it.'}</div></div>
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
  const submit = async () => { try { const j = await api('/api/jobs', f); setOpen(false); setF({ url: '', title: '', company: '', description: '' }); toast.success('Added'); go('jobs', j.id) } catch (e) { toast.error("Couldn't add it", { description: e.message }) } }
  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/25 backdrop-blur-[2px]" />
        <Dialog.Content aria-describedby={undefined} className="fixed left-1/2 top-1/2 z-50 max-h-[calc(100vh-32px)] w-[min(520px,calc(100vw-32px))] -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-[16px] bg-[#1c1c1e] p-6 shadow-[0_40px_100px_rgb(0_0_0/.5)] outline-none ring-1 ring-white/10">
          <Dialog.Title className="text-[22px] font-bold tracking-[-0.02em] text-ink">Add a job</Dialog.Title>
          <p className="mb-5 mt-1 text-[14px] text-muted">Paste the link. Pasting the description too makes the resume sharper.</p>
          <div className="space-y-4">
            {[['url', 'Job link', 'https://…'], ['title', 'Title', 'Software Engineer Intern'], ['company', 'Company', 'Acme']].map(([k, l, ph]) => (
              <label key={k} className="block"><div className="label mb-1.5">{l}</div><input className="box" placeholder={ph} value={f[k]} onChange={e => setF({ ...f, [k]: e.target.value })} /></label>))}
            <label className="block"><div className="label mb-1.5">Description (optional)</div><textarea rows={5} className="box resize-none" value={f.description} onChange={e => setF({ ...f, description: e.target.value })} /></label>
          </div>
          <div className="mt-6 flex justify-end gap-2"><Button variant="ghost" onClick={() => setOpen(false)}>Cancel</Button><Button onClick={submit} disabled={!f.url.trim() && !f.description.trim()}>Add job</Button></div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
