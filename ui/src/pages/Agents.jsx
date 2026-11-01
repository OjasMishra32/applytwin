import { useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'motion/react'
import { toast } from 'sonner'
import { Check, ChevronDown, ChevronRight, CircleSlash, Copy, Hand, Minus, Plus, Star } from 'lucide-react'
import { api } from '../lib/api'
import { parseRun } from '../lib/runlog'
import { useApp, Page } from '../App'
import { Avatar, Segmented, spring } from '../components/ui'
import { REPO_URL } from '../lib/star'
import { atsName } from '../lib/utils'
import { ItemActions } from '../components/ItemActions'
import { AgentConnect } from '../components/AgentConnect'

const clock = s => { s = Math.max(0, Math.round(s)); return s >= 60 ? `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}` : `${s}s` }

// The resume for the current job, written while the twin fills the form: its real step and time left.
function ResumeLine({ p }) {
  const [seen, setSeen] = useState(Date.now())
  const [now, setNow] = useState(Date.now())
  useEffect(() => { const i = setInterval(() => setNow(Date.now()), 250); return () => clearInterval(i) }, [])
  useEffect(() => setSeen(Date.now()), [p])
  const drift = Math.min(3, (now - seen) / 1000)   // between status polls, keep the countdown moving
  const left = Math.max(1, p.eta - drift), elapsed = p.elapsed + drift
  const label = (p.steps || []).find(s => s.state === 'now')?.label || 'Writing your resume'
  return (
    <div className="mt-3 max-w-[460px]">
      <div className="flex items-baseline justify-between gap-3 text-[13px]">
        <span className="truncate text-white/80">Resume: {label}</span>
        <span className="shrink-0 tabular-nums text-muted">about {clock(left)} left</span>
      </div>
      <div className="mt-1.5 h-[3px] overflow-hidden rounded-full bg-white/[.08]">
        <motion.div className="h-full rounded-full bg-white/60" animate={{ width: `${Math.min(97, (elapsed / (elapsed + left)) * 100)}%` }} transition={{ ease: 'linear', duration: 0.25 }} />
      </div>
    </div>)
}

/* The resume your twin just wrote for the job it's applying to: the real page, small, so you see what's being sent. */
function ResumePreview({ r, company, title }) {
  const src = `/file?path=${encodeURIComponent(r.pdf)}`
  const W = 612, H = 792, S = 0.3
  return (
    <motion.section key={r.pdf} layout initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }}
      transition={{ type: 'spring', stiffness: 260, damping: 28 }} className="card mt-4 flex items-center gap-6 p-5 sm:p-6">
      <a href={src} target="_blank" rel="noreferrer" aria-label="Open this resume full size"
        className="group relative shrink-0 overflow-hidden rounded-[6px] bg-white shadow-[0_8px_30px_rgba(0,0,0,.45)] ring-1 ring-white/10 transition-transform hover:-translate-y-0.5"
        style={{ width: W * S, height: H * S }}>
        <iframe title="Resume preview" src={`${src}#toolbar=0&navpanes=0&scrollbar=0&view=Fit`} tabIndex={-1}
          className="pointer-events-none origin-top-left border-0" style={{ width: W, height: H, transform: `scale(${S})` }} />
        <motion.div className="absolute inset-x-0 top-0 h-full bg-gradient-to-b from-transparent via-white/40 to-transparent"
          initial={{ y: '-100%' }} animate={{ y: '100%' }} transition={{ duration: 1.1, ease: 'easeInOut' }} />
      </a>
      <div className="min-w-0">
        <div className="text-[13px] font-medium text-muted">Resume written for this job</div>
        <div className="mt-1 truncate text-[19px] font-semibold tracking-[-0.01em] text-white">{company.replace(/^\W+/, '')}</div>
        <div className="truncate text-[14px] text-muted">{title}</div>
        <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[13px] text-white/80">
          {r.score != null && <span className="tabular-nums">{r.score}% keyword match</span>}
          {r.rewrites > 0 && <span className="tabular-nums">{r.rewrites} bullet{r.rewrites === 1 ? '' : 's'} rewritten for this role</span>}
          {r.pages === 1 && <span>One page</span>}
        </div>
        {r.positioning && <p className="mt-2 line-clamp-2 max-w-md text-[13px] leading-snug text-faint">{r.positioning}</p>}
        <a href={src} target="_blank" rel="noreferrer" className="mt-3 inline-block text-[13px] font-medium" style={{ color: BLUE }}>Open full size</a>
      </div>
    </motion.section>)
}

/* Autopilot, Apple-style: one quiet hero that says what your twin is doing, grouped lists for everything else. */

const SIZES = [5, 10, 25, 50, 100, 250]
const BLUE = '#0a84ff', GREEN = '#30d158', ORANGE = '#ff9f0a'
const safeGet = k => { try { return localStorage.getItem(k) } catch { return null } }
const safeSet = (k, v) => { try { localStorage.setItem(k, v) } catch {} }

export default function Agents() {
  const { app_dir, profile, go } = useApp()
  const [q, setQ] = useState(null)
  const [run, setRun] = useState(null)
  const [agents, setAgents] = useState(null)
  const [agent, setAgent] = useState(profile.apply?.agent || safeGet('at:agent') || 'claude')   // Settings' choice comes first
  const [n, setN] = useState(+(safeGet('at:n') || 25))
  const [inbox, setInbox] = useState({ items: [], pending: [] })
  const [apps, setApps] = useState([])
  const [raw, setRaw] = useState(false)
  const [gaps, setGaps] = useState([])
  useEffect(() => { api('/api/questions').then(d => setGaps(d.missing || [])).catch(() => {}) }, [])
  const since = useRef(+(safeGet('at:runStart') || 0) || Date.now() / 1000 - 3 * 3600)
  const refresh = () => { api('/api/inbox').then(setInbox); api('/api/applications').then(setApps) }

  useEffect(() => {
    api('/api/queue?n=60').then(setQ); refresh()
    api('/api/agents').then(a => {
      setAgents(a)
      if (!a[agent]?.signed_in) { const ok = Object.keys(a).find(k => a[k].signed_in); if (ok) setAgent(ok) }
    }).catch(() => {})
  }, [])
  useEffect(() => { if (!run?.running) return; const t = setInterval(refresh, 5000); return () => clearInterval(t) }, [run?.running])
  useEffect(() => {   // fast while a run is going, slow otherwise, so runs started elsewhere (Needs you, a message) show up too
    let t, live = true
    const poll = async () => {
      try { const r = await api('/api/run'); if (!live) return; setRun(r); if (!r.running) refresh(); t = setTimeout(poll, r.running ? 2000 : 6000) }
      catch { if (live) t = setTimeout(poll, 6000) }
    }
    poll(); return () => { live = false; clearTimeout(t) }
  }, [])
  useEffect(() => {   // the agent you pick here is the one everything uses (Needs you buttons, messages, email history)
    safeSet('at:agent', agent)
    if (agent && agent !== profile.apply?.agent) api('/api/profile', { apply: { agent } }).catch(() => {})
  }, [agent])
  useEffect(() => safeSet('at:n', n), [n])

  const live = parseRun(run?.log)
  const session = apps.filter(a => a.at >= since.current).sort((a, b) => b.at - a.at)
  const total = live.n || n
  const running = !!run?.running
  const st = agents?.[agent]
  const label = agent === 'claude' ? 'Claude Code' : 'Codex'
  const pending = inbox.pending.filter(p => !inbox.items.some(i => i.job_id === p.job_id))
  const needs = inbox.items.length + pending.length

  const start = async () => {
    if (typeof Notification !== 'undefined' && Notification.permission === 'default') Notification.requestPermission()   // so it can tell you when it needs you
    try {
      const r = await api('/api/run', { agent, n })
      setRun(r)
      if (r.busy) { toast("Your twin is already working", { description: 'It finishes what it is doing first. You can watch it here.' }); return }
      since.current = Date.now() / 1000; safeSet('at:runStart', since.current)
      toast.success(`${label} is applying`, { description: `Working through your next ${n} jobs.` })
    } catch (e) { toast.error(e.message) }
  }
  const stop = async () => { setRun(await api('/api/run/stop', {})); toast('Stopped. Your queue keeps its place.') }
  const step = d => setN(SIZES[Math.max(0, Math.min(SIZES.length - 1, SIZES.indexOf(n) + d))] ?? 25)

  const now = run?.now
  // idle, it says what Start will do (the queue); the last run is a footnote, not the headline
  const headline = running ? now?.step || live.step || 'Getting ready'
    : q ? `${q.total.toLocaleString()} role${q.total === 1 ? '' : 's'} ready` : ''
  const subline = running ? (now?.company ? `${now.company.replace(/^\W+/, '')} · ${now.title} · ` : '') + `${session.length} of ${total} done`
    : !q ? '' : [q.dream ? `${q.dream} at your dream companies.` : 'Every open role that fits you.',
      session.length ? `Last run: ${session.length} handled, ${session.filter(a => a.status === 'Needs User').length} waiting on you.` : ''].filter(Boolean).join(' ')

  return (
    <Page>
      <div>
        <h1 className="text-[28px] font-bold leading-[1.15] tracking-[-0.02em] text-white">Autopilot</h1>
        <p className="mt-1.5 max-w-xl text-[15px] leading-snug text-muted">Your twin applies to your queue in its own Chrome window, one job at a time, with a resume written for each.</p>

        <section className="card mt-8 p-6 sm:p-7">
          <div className="flex flex-wrap items-start justify-between gap-8">
            <div className="min-w-0 flex-1">
              <div className="text-[13px] font-medium text-muted">{running ? `${label} is applying` : 'Ready'}</div>
              <div className="relative mt-1.5 h-[38px] overflow-hidden">
                {headline ? <AnimatePresence mode="popLayout" initial={false}>
                  <motion.div key={headline} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.18 }}
                    className="truncate text-[28px] font-semibold leading-[38px] tracking-[-0.02em] text-white">{headline}</motion.div>
                </AnimatePresence> : <div className="skel mt-1.5 h-7 w-56" />}
              </div>
              <div className="mt-1 min-h-[22px] text-[15px] text-muted">{subline}</div>
              {running && now?.resume && <ResumeLine p={now.resume} />}
              {running && <div className="mt-2 text-[13px] text-faint">Watch it live in the Chrome window your twin opened. Don't close that window; it's the twin's.</div>}
              {running && (
                <div className="mt-6 h-1 max-w-[460px] overflow-hidden rounded-full bg-white/[.08]">
                  <motion.div className="h-full rounded-full" style={{ background: BLUE }} initial={{ width: 0 }}
                    animate={{ width: `${Math.max(3, (session.length / Math.max(1, total)) * 100)}%` }} transition={{ type: 'spring', stiffness: 120, damping: 24 }} />
                </div>)}
            </div>

            <div className="flex w-full flex-col gap-3 sm:w-auto sm:items-end">
              <div className="flex flex-wrap items-center gap-3">
                <Segmented id="ag" value={agent} onChange={setAgent} options={[['claude', 'Claude Code'], ['codex', 'Codex']]} />
                <div className="flex h-8 items-center rounded-[10px] bg-white/[.06]">
                  <button onClick={() => step(-1)} disabled={running} className="grid h-8 w-8 place-items-center text-white/80 hover:text-white disabled:opacity-40" aria-label="Fewer jobs"><Minus className="size-3.5" /></button>
                  <span className="w-[74px] text-center text-[13px] font-medium tabular-nums text-white" aria-live="polite">{n} jobs</span>
                  <button onClick={() => step(1)} disabled={running} className="grid h-8 w-8 place-items-center text-white/80 hover:text-white disabled:opacity-40" aria-label="More jobs"><Plus className="size-3.5" /></button>
                </div>
              </div>
              <div className="min-h-[18px] text-[12.5px]" style={{ color: !st || st.signed_in ? 'var(--color-muted)' : ORANGE }}>
                {!st ? '' : st.signed_in ? `Signed in · runs on your ${label} plan, no API key` : !st.installed ? `${label} isn't installed yet` : `${label} is signed out`}
              </div>
              <AgentConnect name={agent} st={st} compact onChange={() => api('/api/agents').then(setAgents).catch(() => {})} />
              <motion.button whileTap={{ scale: 0.96 }} transition={spring} onClick={running ? stop : start} disabled={!running && st && !st.signed_in}
                className="mt-1 h-10 w-full rounded-full px-10 text-[15px] font-semibold text-white transition-colors disabled:cursor-default disabled:opacity-40 sm:w-auto"
                style={{ background: running ? 'rgb(255 255 255 / .1)' : BLUE }}>
                {running ? 'Stop' : 'Start'}
              </motion.button>
              <div className="text-[12.5px] text-faint">{profile.apply?.auto_submit ? 'Submits on its own.' : 'Stops at the review screen so you press submit.'}</div>
              {gaps.length > 0 && <button onClick={() => go('settings')} className="text-left text-[12.5px] text-signal-ink hover:underline sm:text-right">
                Answer {gaps.length} more question{gaps.length === 1 ? '' : 's'} so it never stops to ask</button>}
            </div>
          </div>
        </section>
        <AnimatePresence mode="wait">
          {running && now?.built && <ResumePreview key={now.built.pdf} r={now.built} company={now.company || ''} title={now.title || ''} />}
        </AnimatePresence>

        <StarAsk count={apps.filter(a => a.status === 'Applied' || a.status === 'Needs User').length} />

        <div className="mt-8 grid gap-8 lg:grid-cols-[1.25fr_1fr]">
          <div className="min-w-0 space-y-8">
            {session.length > 0 && (
              <Group title={running ? 'This run' : 'Last run'}>
                <AnimatePresence initial={false}>
                  {session.slice(0, 12).map(a => <ResultRow key={a.id} a={a} onClick={() => go('jobs', a.job_id)} />)}
                </AnimatePresence>
              </Group>)}
            <Group title="Up next" detail={q ? `${q.total.toLocaleString()} in queue` : ''}
              action={<button onClick={() => go('settings')} className="text-[13px]" style={{ color: BLUE }}>Preferences</button>}>
              <div className="max-h-[520px] overflow-y-auto [&>*+*]:border-t [&>*+*]:border-white/[.06]">
                {(q?.jobs || []).slice(0, 40).map(j => (
                  <Row key={j.id} onClick={() => go('jobs', j.id)} left={<Avatar name={j.company} size={32} />} title={j.title} sub={`${j.company} · ${atsName(j.ats)}`}
                    right={<span className="flex items-center gap-2">{j.dream && <Star className="size-3.5 fill-current text-muted" aria-label="Dream company" />}
                      <span className="w-9 text-right text-[13px] tabular-nums text-muted">{Math.round(j.fit)}%</span>
                      <ChevronRight className="size-4 text-white/25" /></span>} />))}
                {!q && <div className="space-y-px p-2">{[0, 1, 2, 3].map(i => <div key={i} className="skel h-[48px]" />)}</div>}
                {q && !q.jobs?.length && <div className="px-4 py-8 text-center text-[13.5px] text-muted">Your queue is empty. Scan for jobs on the Jobs page, or widen your roles in Preferences.</div>}
              </div>
            </Group>
          </div>

          <div className="min-w-0 space-y-8">
            <Group title="Needs you" detail={needs ? String(needs) : ''}
              footer="Answers you give here are saved, so your twin never asks the same thing twice.">
              <AnimatePresence initial={false}>
                {inbox.items.map(i => <NeedsYou key={'i' + i.id} item={i} onDone={refresh} />)}
                {pending.map(p => (
                  <div key={'p' + p.job_id} className="px-4 py-3.5">
                    <div className="flex items-center gap-3.5"><Avatar name={p.company} size={32} />
                      <div className="min-w-0 flex-1"><div className="truncate text-[14.5px] text-white">{p.company} · {p.title}</div>
                        <div className="line-clamp-2 text-[12.5px] text-muted">{p.notes}</div></div></div>
                    <div className="mt-2 pl-[46px]"><ItemActions item={{ ...p, id: 'p' + p.job_id }} onDone={refresh} /></div>
                  </div>))}
              </AnimatePresence>
              {!needs && <div className="px-4 py-4 text-[14px] text-muted">Nothing right now.</div>}
            </Group>

            <Group title="Or use it from your terminal" footer="It never types passwords, solves CAPTCHAs, creates accounts or invents a fact.">
              {[['Check your setup', 'applytwin doctor'], [`Tell ${label} directly`, 'apply to my top 25 with applytwin'],
                ['Start Autopilot from a terminal', `applytwin run --agent ${agent} --n ${n}`]].map(([l, t]) => <CopyRow key={t} label={l} text={t} />)}
            </Group>

            {run?.log && (
              <div>
                <button onClick={() => setRaw(!raw)} className="flex items-center gap-1 px-1 text-[13px] text-muted hover:text-white">
                  <ChevronDown className={'size-3.5 transition-transform ' + (raw ? 'rotate-180' : '')} />Technical log</button>
                <AnimatePresence initial={false}>{raw && (
                  <motion.pre initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }}
                    className="mt-2 max-h-[260px] overflow-auto whitespace-pre-wrap rounded-[12px] bg-black/40 p-4 font-mono text-[11px] leading-relaxed text-white/60">{live.clean}</motion.pre>)}
                </AnimatePresence>
              </div>)}
          </div>
        </div>
      </div>
    </Page>
  )
}

function Group({ title, detail, action, footer, children }) {
  return (
    <section>
      <div className="mb-2 flex items-center justify-between px-1">
        <div className="flex items-baseline gap-2"><h2 className="text-[17px] font-semibold tracking-[-0.01em] text-white">{title}</h2>
          {typeof detail === 'string' ? <span className="text-[13px] text-faint">{detail}</span> : detail}</div>
        {action}
      </div>
      <div className="card overflow-hidden [&>*+*]:border-t [&>*+*]:border-white/[.06]">{children}</div>
      {footer && <p className="mt-2 px-1 text-[12.5px] leading-relaxed text-faint">{footer}</p>}
    </section>
  )
}

function Row({ left, title, sub, right, onClick, href }) {
  const C = href ? 'a' : 'button'
  return (
    <C {...(href ? { href, target: '_blank', rel: 'noreferrer' } : { onClick })}
      className="flex w-full items-center gap-3.5 px-4 py-3 text-left transition-colors hover:bg-white/[.035]">
      {left}
      <div className="min-w-0 flex-1"><div className="truncate text-[14.5px] text-white">{title}</div>
        {sub && <div className="truncate text-[12.5px] text-muted">{sub}</div>}</div>
      {right}
    </C>
  )
}

const STATUS = { Applied: ['var(--color-muted)', Check, 'Applied'], 'Needs User': [ORANGE, Hand, 'Needs you'], Skipped: ['var(--color-faint)', CircleSlash, 'Skipped'] }

function ResultRow({ a, onClick }) {
  const [color, Icon, text] = STATUS[a.status] || ['var(--color-muted)', Check, a.status]
  return (
    <motion.div layout initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} transition={{ type: 'spring', stiffness: 300, damping: 30 }}>
      <Row onClick={onClick} left={<Avatar name={a.company} size={32} />} title={`${a.company}  ·  ${a.title}`} sub={a.notes}
        right={<span className="flex shrink-0 items-center gap-1.5 text-[13px] font-medium" style={{ color }}><Icon className="size-3.5" />{text}</span>} />
    </motion.div>
  )
}

function CopyRow({ label, text }) {
  const [ok, setOk] = useState(false)
  return (
    <button onClick={() => { navigator.clipboard.writeText(text); setOk(true); setTimeout(() => setOk(false), 1400) }}
      className="flex w-full items-center justify-between gap-4 px-4 py-3 text-left hover:bg-white/[.035]">
      <span className="min-w-0"><span className="block text-[13px] text-muted">{label}</span>
        <span className="block font-mono text-[13px] text-white">{text}</span></span>
      <span className="shrink-0 text-[12.5px] font-medium" style={{ color: ok ? GREEN : BLUE }}>{ok ? 'Copied' : 'Copy'}</span>
    </button>
  )
}

function NeedsYou({ item, onDone }) {
  const question = item.kind === 'question' ? (item.title || '').replace(/^Add your answer:\s*/, '') : ''
  const [text, setText] = useState('')
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const finish = async e => {
    setBusy(true)
    try {
      if (question && text.trim()) await api('/api/answer', { question, answer: text.trim() })
      await api(`/api/inbox/${item.id}/resolve`, {})
      toast.success(question && text.trim() ? 'Saved to your answers' : 'Done', { description: question && text.trim() ? 'Used here and on every similar question.' : undefined })
      onDone()
    } catch (err) { toast.error(err.message) } finally { setBusy(false) }
  }
  return (
    <motion.div layout initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0, height: 0 }} className="px-4 py-3.5">
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <div className="text-[14.5px] font-medium text-white">{question || item.title}</div>
          {item.message && item.message !== (question || item.title) && <div className="mt-0.5 text-[13px] leading-relaxed text-muted">{item.message}</div>}
        </div>
        {question && <button onClick={() => setOpen(!open)} className="shrink-0 pt-0.5 text-[13px] font-medium text-signal-ink hover:underline">{open ? 'Cancel' : 'Answer'}</button>}
      </div>
      {!open && <div className="mt-2"><ItemActions item={item} onDone={onDone} /></div>}
      <AnimatePresence initial={false}>{open && (
        <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
          <textarea autoFocus value={text} onChange={e => setText(e.target.value)} rows={4} placeholder="Your answer, in your words."
            className="mt-3 w-full resize-none rounded-[10px] bg-white/[.05] px-3.5 py-3 text-[14px] text-white outline-none placeholder:text-faint focus:ring-2 focus:ring-signal" />
          <div className="mt-2 flex justify-end gap-2">
            <button onClick={finish} disabled={busy} className="h-8 rounded-full px-4 text-[13px] text-muted hover:text-white">Skip question</button>
            <motion.button whileTap={{ scale: 0.96 }} onClick={finish} disabled={busy || !text.trim()}
              className="h-8 rounded-full px-4 text-[13px] font-semibold text-white disabled:opacity-40" style={{ background: BLUE }}>Save</motion.button>
          </div>
        </motion.div>)}
      </AnimatePresence>
    </motion.div>
  )
}

function StarAsk({ count }) {
  // once your twin has done real work for you, ask (once) for a star; never again after a star or a dismiss
  const [gone, setGone] = useState(() => safeGet('at:starAsk') === 'done')
  if (gone || count < 1) return null   // right after the first round of applications
  const done = () => { safeSet('at:starAsk', 'done'); setGone(true) }
  return (
    <section className="card mt-4 flex flex-wrap items-center gap-x-4 gap-y-3 px-5 py-4">
      <div className="min-w-0 flex-1 basis-[220px]">
        <div className="text-[14px] font-medium text-white">Your twin has handled {count} applications</div>
        <div className="mt-0.5 text-[13px] text-muted">ApplyTwin is free. A star on GitHub helps other students find it.</div>
      </div>
      <div className="flex items-center gap-3">
        <button onClick={done} className="text-[13px] text-muted hover:text-white">Not now</button>
        <a href={REPO_URL} target="_blank" rel="noreferrer" onClick={done}
          className="inline-flex h-8 items-center gap-1.5 rounded-full bg-white/[.08] px-3.5 text-[13px] font-medium text-white transition-colors hover:bg-white/[.13]"><Star className="size-3.5" />Star on GitHub</a>
      </div>
    </section>

  )
}
