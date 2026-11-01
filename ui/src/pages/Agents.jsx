import { useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'motion/react'
import { toast } from 'sonner'
import { Check, ChevronDown, ChevronRight, CircleSlash, Copy, Hand, KeyRound, MessageCircleQuestion, Minus, MonitorX, Plus, Send, Star, TriangleAlert } from 'lucide-react'
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

/* The resume for the job your twin is on: while it's being written, a page that fills in line by line; once it's done,
   the real page, small, so you see exactly what's being sent. */
const SKEL = [[.42, 1], [.7, .5], [0], [.3, .9], [.95], [.9], [.6], [0], [.3, .9], [.92], [.85], [.95], [.5], [0], [.3, .9], [.9], [.8], [0], [.25, .9], [.9], [.7]]
function WritingPage({ p, W, S }) {
  const done = p ? Math.min(.97, p.elapsed / Math.max(1, p.elapsed + p.eta)) : .1
  const shown = Math.max(2, Math.round(done * SKEL.length))
  return (
    <div className="absolute inset-0 px-[14px] py-[16px]">
      {SKEL.map((l, i) => l[0] === 0 ? <div key={i} className="h-[7px]" /> : (
        <motion.div key={i} className={`mb-[4px] h-[4px] rounded-full ${l.length > 1 && i ? 'bg-black/55' : 'bg-black/25'}`}
          style={{ width: `${(l[1] ?? l[0]) * 100}%`, marginLeft: i === 0 ? `${(1 - l[0]) * 50}%` : 0, ...(i === 0 ? { width: `${l[0] * 100}%`, height: 7 } : {}) }}
          initial={false} animate={{ opacity: i < shown ? 1 : 0.12 }} transition={{ duration: 0.5 }} />))}
      <motion.div className="absolute inset-x-0 h-10 bg-gradient-to-b from-transparent via-[#0a84ff]/15 to-transparent"
        animate={{ top: ['-10%', '100%'] }} transition={{ duration: 2.2, repeat: Infinity, ease: 'linear' }} />
    </div>)
}

function ResumePreview({ r, p, company, title }) {
  const src = r ? `/file?path=${encodeURIComponent(r.pdf)}` : null
  const W = 612, H = 792, S = 0.3
  const step = (p?.steps || []).find(x => x.state === 'now')?.label || 'Writing your resume'
  return (
    <motion.section layout initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }}
      transition={{ type: 'spring', stiffness: 260, damping: 28 }} className="card mt-4 flex items-center gap-6 p-5 sm:p-6">
      <a href={src || undefined} target="_blank" rel="noreferrer" aria-label={src ? 'Open this resume full size' : 'Resume being written'}
        className={`group relative shrink-0 overflow-hidden rounded-[6px] bg-white shadow-[0_8px_30px_rgba(0,0,0,.45)] ring-1 ring-white/10 transition-transform ${src ? 'hover:-translate-y-0.5' : 'pointer-events-none'}`}
        style={{ width: W * S, height: H * S }}>
        <AnimatePresence initial={false}>
          {src ? <motion.div key="pdf" className="absolute inset-0" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.6 }}>
            <iframe title="Resume preview" src={`${src}#toolbar=0&navpanes=0&scrollbar=0&view=Fit`} tabIndex={-1}
              className="pointer-events-none origin-top-left border-0" style={{ width: W, height: H, transform: `scale(${S})` }} />
            <motion.div className="absolute inset-x-0 top-0 h-full bg-gradient-to-b from-transparent via-white/40 to-transparent"
              initial={{ y: '-100%' }} animate={{ y: '100%' }} transition={{ duration: 1.1, ease: 'easeInOut' }} />
          </motion.div> : <motion.div key="skel" className="absolute inset-0" exit={{ opacity: 0 }}><WritingPage p={p} W={W} S={S} /></motion.div>}
        </AnimatePresence>
      </a>
      <div className="min-w-0">
        <div className="text-[13px] font-medium text-muted">{r ? 'Resume written for this job' : `Writing a resume for this job · ${step}`}</div>
        <div className="mt-1 truncate text-[19px] font-semibold tracking-[-0.01em] text-white">{company.replace(/^\W+/, '')}</div>
        <div className="truncate text-[14px] text-muted">{title}</div>
        {r ? <>
          <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[13px] text-white/80">
            {r.score != null && <span className="tabular-nums">{r.score}% keyword match</span>}
            {r.rewrites > 0 && <span className="tabular-nums">{r.rewrites} bullet{r.rewrites === 1 ? '' : 's'} rewritten for this role</span>}
            {r.pages === 1 && <span>One page</span>}
          </div>
          {r.positioning && <p className="mt-2 line-clamp-2 max-w-md text-[13px] leading-snug text-faint">{r.positioning}</p>}
          <a href={src} target="_blank" rel="noreferrer" className="mt-3 inline-block text-[13px] font-medium" style={{ color: BLUE }}>Open full size</a>
        </> : <p className="mt-3 max-w-md text-[13px] leading-snug text-faint">Picking your strongest experience for this posting and rewriting it in its words. The page shows up here when it's done.</p>}
      </div>
    </motion.section>)
}

/* Autopilot, Apple-style: one quiet hero that says what your twin is doing, grouped lists for everything else. */

const SIZES = [5, 10, 25, 50, 100, 250]
const BLUE = '#0a84ff', GREEN = '#30d158', ORANGE = '#ff9f0a'
const safeGet = k => { try { return localStorage.getItem(k) } catch { return null } }
const safeSet = (k, v) => { try { localStorage.setItem(k, v) } catch {} }

export default function Agents() {
  const { app_dir, profile, go, stats } = useApp()
  const [q, setQ] = useState(null)
  const [run, setRun] = useState(null)
  const [agents, setAgents] = useState(null)
  const [agent, setAgent] = useState(profile.apply?.agent || safeGet('at:agent') || 'claude')   // Settings' choice comes first
  const [n, setN] = useState(+(safeGet('at:n') || 25))
  const [inbox, setInbox] = useState({ items: [], pending: [], groups: [] })
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
  const groups = inbox.groups || []

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
    : !run ? '' : q ? `${q.total.toLocaleString()} role${q.total === 1 ? '' : 's'} ready` : ''
  const subline = running ? (now?.company ? `${now.company.replace(/^\W+/, '')} · ${now.title} · ` : '') + `${session.length} of ${total} done`
    : !q ? '' : [q.dream ? `${q.dream} at your dream companies.` : 'Every open role that fits you.',
      session.length ? `Last run: ${session.length} handled, ${session.filter(a => a.status === 'Needs User').length} waiting on you.` : ''].filter(Boolean).join(' ')

  const dayStart = new Date().setHours(0, 0, 0, 0) / 1000
  const appliedToday = Math.max(stats?.applied_day ?? 0, apps.filter(a => a.status === 'Applied' && a.at >= dayStart).length)
  const pct = Math.max(3, (session.length / Math.max(1, total)) * 100)

  return (
    <Page>
      <div>
        <h1 className="text-[34px] font-bold leading-[1.1] tracking-[-0.025em] text-white">Autopilot</h1>

        {/* the one thing that matters: what your twin is doing, and the button to start or stop it */}
        <section className="card mt-6 overflow-hidden">
          <div className="flex flex-col gap-8 p-7 sm:flex-row sm:items-center sm:justify-between sm:p-9">
            <div className="min-w-0 flex-1">
              <div className="text-[13px] font-medium text-muted">{running ? `${label} is applying` : run ? 'Ready when you are' : 'Checking on your twin…'}</div>
              <div className="relative mt-1 h-[44px] overflow-hidden">
                {headline ? <AnimatePresence mode="popLayout" initial={false}>
                  <motion.div key={headline} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }} transition={{ duration: 0.22 }}
                    className="truncate text-[34px] font-semibold leading-[44px] tracking-[-0.025em] text-white">{headline}</motion.div>
                </AnimatePresence> : <div className="skel mt-2 h-8 w-64" />}
              </div>
              <div className="mt-1 min-h-[22px] line-clamp-2 text-[15px] text-muted">{subline}</div>
              {running && (
                <div className="mt-5 max-w-[480px]">
                  <div className="h-[5px] overflow-hidden rounded-full bg-white/[.08]">
                    <motion.div className="h-full rounded-full" style={{ background: BLUE }} initial={{ width: 0 }}
                      animate={{ width: `${pct}%` }} transition={{ type: 'spring', stiffness: 120, damping: 24 }} />
                  </div>
                  {now?.resume && !now?.built && <ResumeLine p={now.resume} />}
                </div>)}
            </div>
            <div className="flex shrink-0 flex-col items-stretch gap-3 sm:w-[260px]">
              <motion.button whileTap={{ scale: 0.97 }} transition={spring} onClick={running ? stop : start} disabled={!running && st && !st.signed_in}
                className="h-12 rounded-full text-[16px] font-semibold text-white transition-colors disabled:cursor-default disabled:opacity-40"
                style={{ background: running ? 'rgb(255 255 255 / .1)' : BLUE }}>
                {running ? 'Stop' : `Apply to ${n}`}
              </motion.button>
              {!running && <div className="flex items-center gap-2">
                <Segmented id="ag" value={agent} onChange={setAgent} options={[['claude', 'Claude Code'], ['codex', 'Codex']]} />
                <div className="ml-auto flex h-8 items-center rounded-[10px] bg-white/[.06]">
                  <button onClick={() => step(-1)} className="grid h-8 w-7 place-items-center text-white/70 hover:text-white" aria-label="Fewer jobs"><Minus className="size-3.5" /></button>
                  <span className="w-8 text-center text-[13px] font-medium tabular-nums text-white" aria-live="polite">{n}</span>
                  <button onClick={() => step(1)} className="grid h-8 w-7 place-items-center text-white/70 hover:text-white" aria-label="More jobs"><Plus className="size-3.5" /></button>
                </div>
              </div>}
              <div className="text-center text-[12.5px] leading-snug" style={{ color: !st || st.signed_in ? 'var(--color-faint)' : ORANGE }}>
                {!st ? '' : !st.signed_in ? (!st.installed ? `${label} isn't installed yet` : `${label} is signed out`)
                  : running ? 'Watch it in the Chrome window it opened.' : profile.apply?.auto_submit ? 'Submits on its own.' : 'Stops at review so you press Submit.'}
              </div>
              <AgentConnect name={agent} st={st} compact onChange={() => api('/api/agents').then(setAgents).catch(() => {})} />
            </div>
          </div>
          {/* today at a glance */}
          <div className="grid grid-cols-3 border-t border-white/[.06]">
            {[[appliedToday, 'Applied today'], [groups.length, groups.length === 1 ? 'Thing needs you' : 'Things need you'], [q ? q.total : null, 'Roles in your queue']].map(([v, l], k) => (
              <div key={l} className={'px-4 py-5 sm:px-7 ' + (k ? 'border-l border-white/[.06]' : '')}>
                <div className="text-[22px] font-semibold tabular-nums tracking-[-0.02em] text-white sm:text-[26px]">{v == null ? '—' : v.toLocaleString()}</div>
                <div className="mt-0.5 text-[12.5px] text-muted">{l}</div>
              </div>))}
          </div>
        </section>
        {gaps.length > 0 && !running && <button onClick={() => go('settings')} className="mt-3 px-1 text-[13px] text-signal-ink hover:underline">
          Answer {gaps.length} more question{gaps.length === 1 ? '' : 's'} so your twin never has to stop and ask</button>}

        <AnimatePresence mode="wait">
          {running && now?.company && (now.built || now.resume) &&
            <ResumePreview key={`${now.company}|${now.title}`} r={now.built} p={now.resume} company={now.company || ''} title={now.title || ''} />}
        </AnimatePresence>

        <div className="mt-10 grid gap-10 lg:grid-cols-[1.2fr_1fr]">
          <div className="min-w-0 space-y-10">
            <Group title="Needs you" detail={groups.length ? String(groups.length) : ''}
              footer={groups.length ? 'Grouped so you do each thing once. Your answers are saved for every future application.' : ''}>
              <AnimatePresence initial={false}>
                {groups.map(g => <TodoRow key={g.key} g={g} onDone={refresh} go={go} />)}
              </AnimatePresence>
              {!groups.length && <div className="flex items-center gap-3 px-4 py-5 text-[14px] text-muted"><Check className="size-4 text-good" />Nothing needs you right now.</div>}
            </Group>
            {session.length > 0 && (
              <Group title={running ? 'This run' : 'Last run'} detail={`${session.filter(a => a.status === 'Applied').length} applied`}>
                <AnimatePresence initial={false}>
                  {session.slice(0, 10).map(a => <ResultRow key={a.id} a={a} onClick={() => go('jobs', a.job_id)} />)}
                </AnimatePresence>
              </Group>)}
          </div>

          <div className="min-w-0 space-y-10">
            <Group title="Up next" detail={q ? `${q.total.toLocaleString()} in queue` : ''}
              action={<button onClick={() => go('settings')} className="text-[13px]" style={{ color: BLUE }}>Preferences</button>}>
              {(q?.jobs || []).slice(0, 8).map(j => (
                <Row key={j.id} onClick={() => go('jobs', j.id)} left={<Avatar name={j.company} size={30} />} title={j.title} sub={`${j.company} · ${atsName(j.ats)}`}
                  right={<span className="flex items-center gap-2">{j.dream && <Star className="size-3.5 fill-current text-muted" aria-label="Dream company" />}
                    <span className="w-9 text-right text-[13px] tabular-nums text-muted">{Math.round(j.fit)}%</span></span>} />))}
              {!q && <div className="space-y-px p-2">{[0, 1, 2, 3].map(i => <div key={i} className="skel h-[48px]" />)}</div>}
              {q && !q.jobs?.length && <div className="px-4 py-8 text-center text-[13.5px] text-muted">Your queue is empty. Scan for jobs on the Jobs page, or widen your roles in Preferences.</div>}
              {q?.total > 8 && <button onClick={() => go('jobs')} className="w-full px-4 py-3 text-left text-[13.5px] font-medium" style={{ color: BLUE }}>See all {q.total.toLocaleString()} in Jobs</button>}
            </Group>

            <div>
              <button onClick={() => setRaw(!raw)} className="flex items-center gap-1 px-1 text-[13px] text-muted hover:text-white">
                <ChevronDown className={'size-3.5 transition-transform ' + (raw ? 'rotate-180' : '')} />Terminal and technical log</button>
              <AnimatePresence initial={false}>{raw && (
                <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
                  <div className="card mt-2 overflow-hidden [&>*+*]:border-t [&>*+*]:border-white/[.06]">
                    {[['Check your setup', 'applytwin doctor'], [`Tell ${label} directly`, 'apply to my top 25 with applytwin'],
                      ['Start Autopilot from a terminal', `applytwin run --agent ${agent} --n ${n}`]].map(([l, t]) => <CopyRow key={t} label={l} text={t} />)}
                  </div>
                  {run?.log && <pre className="mt-2 max-h-[260px] overflow-auto whitespace-pre-wrap rounded-[12px] bg-black/40 p-4 font-mono text-[11px] leading-relaxed text-white/60">{live.clean}</pre>}
                </motion.div>)}
              </AnimatePresence>
            </div>
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

/* What happened, in a few plain words: agents write "sign-in required at https://ngc.wd1.myworkdayjobs.com/..." */
function reason(a) {
  const n = (a.notes || '').replace(/https?:\/\/\S+/g, '').replace(/\s+(at|on)\s*([.;,]|$)/gi, '$2').replace(/\s{2,}/g, ' ').trim()
  const rules = [[/^sign[- ]?in (required|needed)/i, 'Waiting on your sign-in'], [/^account (required|needed)/i, 'Needs an account'],
    [/captcha/i, 'A CAPTCHA to solve'], [/emailed code|verification code/i, 'Waiting on an emailed code'], [/^closed|no longer|does not exist/i, 'Posting closed'],
    [/duplicate|already applied/i, 'Already applied'], [/^ready to submit/i, 'Ready for your Submit click'], [/stuck|no progress/i, 'Skipped after no progress']]
  const hit = rules.find(([rx]) => rx.test(n))
  const q = n.match(/^required question:\s*"?([^".;]{3,70})/i)
  if (q) return `Asks: ${q[1]}`
  if (hit) return hit[1]
  const first = n.split(/(?<=[.;])\s/)[0].replace(/[.;]$/, '')
  return first.length > 90 ? first.slice(0, 88) + '…' : first
}

function ResultRow({ a, onClick }) {
  const [color, Icon, text] = STATUS[a.status] || ['var(--color-muted)', Check, a.status]
  return (
    <motion.div layout initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} transition={{ type: 'spring', stiffness: 300, damping: 30 }}>
      <Row onClick={onClick} left={<Avatar name={a.company} size={30} />} title={`${(a.company || '').replace(/^\W+/, '')} · ${a.title}`} sub={reason(a)}
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
      const answered = question && text.trim()
      if (answered) await api('/api/answer', { question, answer: text.trim() })
      await api(`/api/inbox/${item.id}/resolve`, {})
      // the application it came from closed with the run: send the twin back to fill it again, now with this answer
      const r = answered && item.job_id ? await api('/api/finish', { job_ids: [item.job_id] }).catch(() => null) : null   // submits if your settings say to
      toast.success(answered ? 'Saved to your answers' : 'Done', { description: !answered ? undefined
        : r?.queued ? 'Your twin finishes that application with it right after its current run.'
        : r ? 'Your twin is filling that application again with your answer.' : 'Used here and on every similar question.' })
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

/* One row per thing to do. Closed, it's a sentence and a count; open, it shows exactly what to press. */
const KIND_ICON = { question: MessageCircleQuestion, ready: Send, sites: KeyRound, browser: MonitorX }
function TodoRow({ g, onDone, go }) {
  const [open, setOpen] = useState(false)
  const Icon = KIND_ICON[g.kind] || TriangleAlert
  return (
    <motion.div layout="position" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0, height: 0 }}>
      <button onClick={() => setOpen(!open)} className="flex w-full items-center gap-3.5 px-4 py-3.5 text-left transition-colors hover:bg-white/[.035]">
        <span className="grid size-8 shrink-0 place-items-center rounded-full bg-white/[.07]"><Icon className="size-4 text-white/80" /></span>
        <div className="min-w-0 flex-1">
          <div className="truncate text-[14.5px] font-medium text-white">{g.title}</div>
          {!open && <div className="truncate text-[12.5px] text-muted">{g.detail}</div>}
        </div>
        {g.count > 1 && <span className="shrink-0 text-[13px] tabular-nums text-faint">{g.count}</span>}
        <ChevronDown className={'size-4 shrink-0 text-white/30 transition-transform ' + (open ? 'rotate-180' : '')} />
      </button>
      <AnimatePresence initial={false}>{open && (
        <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
          <div className="px-4 pb-4 pl-[62px]">
            <p className="text-[13px] leading-relaxed text-muted">{g.detail}</p>
            {g.kind === 'question' && <button onClick={() => go('answers')} className="mt-2 text-[13px] font-medium text-signal-ink hover:underline">Open the Answers page</button>}
            <div className="mt-3 space-y-1">
              {g.kind === 'sites' ? g.sites.map(st => <SiteRow key={st.key} st={st} onDone={onDone} />)
                : g.entries.map(e => e.item_id && g.kind === 'question'
                  ? <NeedsYou key={e.item_id} item={{ id: e.item_id, kind: 'question', title: e.text, message: e.note, job_id: e.job_id, url: e.url }} onDone={onDone} />
                  : <EntryRow key={e.item_id || e.job_id} e={e} onDone={onDone} />)}
            </div>
          </div>
        </motion.div>)}</AnimatePresence>
    </motion.div>)
}

function EntryRow({ e, onDone }) {
  const [open, setOpen] = useState(false)
  const name = (e.company || '').replace(/^\W+/, '')
  return (
    <div className="rounded-[10px] bg-white/[.03]">
      <button onClick={() => setOpen(!open)} className="flex w-full items-center gap-3 px-3 py-2.5 text-left">
        <Avatar name={name || '?'} size={24} />
        <div className="min-w-0 flex-1">
          <div className="truncate text-[13.5px] text-white">{name ? `${name} · ${e.title}` : e.text}</div>
          {!open && e.note && <div className="truncate text-[12px] text-faint">{e.note}</div>}
        </div>
        <ChevronRight className={'size-3.5 shrink-0 text-white/25 transition-transform ' + (open ? 'rotate-90' : '')} />
      </button>
      {open && <div className="px-3 pb-3">
        {e.note && <p className="mb-2 text-[12.5px] leading-relaxed text-muted">{e.note}</p>}
        <ItemActions item={{ id: e.item_id ?? 'p' + e.job_id, job_id: e.job_id, url: e.url, title: e.text, message: e.note, notes: e.note }} onDone={onDone} />
      </div>}
    </div>)
}

function SiteRow({ st, onDone }) {
  const [busy, setBusy] = useState('')
  const [open, setOpen] = useState(false)
  const first = st.entries.find(e => e.url) || {}
  const name = st.title.replace(/^(Sign in to|Create your|Type the emailed code for)\s+/, '').replace(/ account$/, '')
  const act = async (label, fn, ok) => {
    setBusy(label)
    try {
      const r = await fn()
      if (r?.done) toast(r.note || 'Nothing to finish here.')   // the server said nothing started: never a success toast for that
      else toast.success(r?.queued ? 'Queued' : r?.note || ok.title, { description: r?.queued ? 'Your twin finishes these right after its current run.' : ok.body })
      if (label === 'finish') onDone()
    }
    catch (err) { toast.error(err.message) }
    setBusy('')
  }
  return (
    <div className="rounded-[10px] bg-white/[.03] px-3 py-2.5">
      <div className="flex flex-wrap items-center gap-3">
        <Avatar name={name} size={24} />
        <button onClick={() => setOpen(!open)} className="min-w-0 flex-1 text-left">
          <div className="truncate text-[13.5px] text-white">{name}</div>
          <div className="truncate text-[12px] text-faint">{st.kind === 'account' ? 'Needs an account' : st.kind === 'email_code' ? 'Emailed code' : 'Sign-in'} · {st.count} job{st.count > 1 ? 's' : ''}</div>
        </button>
        <div className="flex items-center gap-1.5">
          {first.url && <button disabled={!!busy} onClick={() => act('open', () => api('/api/open-twin', { url: first.url }),
            { title: "Opened in your twin's browser", body: 'Sign in there (your login is saved for next time), then press Finish.' })}
            className="h-7 rounded-full bg-white/[.08] px-3 text-[12px] font-semibold text-white hover:bg-white/[.13] disabled:opacity-50">{busy === 'open' ? 'Opening…' : 'Open'}</button>}
          <button disabled={!!busy} onClick={() => act('finish', () => api('/api/finish/site', { site: st.site }),
            { title: `Finishing ${name}`, body: `Your twin continues ${st.count > 1 ? `all ${st.count} jobs` : 'the job'} where it stopped.` })}
            className="h-7 rounded-full bg-signal px-3 text-[12px] font-semibold text-white hover:bg-[#2b95ff] disabled:opacity-50">{busy === 'finish' ? 'Starting…' : 'Finish'}</button>
        </div>
      </div>
      {open && <div className="mt-2 space-y-1">{st.entries.map(e => <EntryRow key={e.item_id || e.job_id} e={e} onDone={onDone} />)}</div>}
    </div>)
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
