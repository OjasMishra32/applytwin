import { useEffect, useRef, useState } from 'react'
import { MotionConfig, motion, useInView } from 'motion/react'
import { ArrowRight, Check, CircleSlash, Hand, KeyRound, Send, Share } from 'lucide-react'
import { Logo } from './Steps'
import { InstallBox, useTheme } from './Site'
import './site.css'

/* apply.twinly.tech/demo: ApplyTwin without installing anything, on any phone. A made-up student and three made-up
   postings, but the resumes are real: scripts/demo/make_demo.py ran ApplyTwin's own tailor to make every rewrite, score
   and page shown here. The application run is a replay of what the app does, and says so. */

const EASE = [0.25, 0.1, 0.25, 1]
const IS_WIN = typeof navigator !== 'undefined' && /windows/i.test(navigator.userAgent)
const PHONE = typeof navigator !== 'undefined' && /iphone|android|ipad|mobile/i.test(navigator.userAgent)
const A = '/demo-assets/'

function Reveal({ children, className, delay = 0 }) {
  return <motion.div className={className} initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }}
    viewport={{ once: true, margin: '-40px' }} transition={{ duration: 0.8, ease: EASE, delay }}>{children}</motion.div>
}

function Count({ from, to }) {
  const ref = useRef(null)
  const seen = useInView(ref, { once: true })
  const [v, setV] = useState(from)
  useEffect(() => {
    if (!seen) return
    // a timer, not animation frames: those pause in a background tab and the number stayed at the old score
    const t0 = Date.now()
    const i = setInterval(() => {
      const k = Math.min(1, (Date.now() - t0) / 1100)
      setV(Math.round(from + (to - from) * (1 - Math.pow(1 - k, 3))))
      if (k >= 1) clearInterval(i)
    }, 30)
    return () => clearInterval(i)
  }, [seen, from, to])
  return <span ref={ref} className="tabular-nums">{v}</span>
}

export default function DemoPage() {
  const [theme] = useTheme()
  const [data, setData] = useState(null)
  const [err, setErr] = useState(false)
  const [pick, setPick] = useState(0)
  const [win, setWin] = useState(IS_WIN)
  useEffect(() => { fetch(A + 'data.json').then(r => r.json()).then(setData).catch(() => setErr(true)) }, [])
  const job = data?.jobs?.[pick]
  return (
    <MotionConfig reducedMotion="user">
    <div className="site min-h-screen overflow-x-clip" data-theme={theme}>
      <header className="nav fixed inset-x-0 top-0 z-50">
        <div className="mx-auto flex h-12 max-w-[1120px] items-center justify-between px-4">
          <a href="/" className="flex items-center gap-2 text-[15px] font-semibold"><Logo size={18} />ApplyTwin</a>
          <a href="#get" className="rounded-full bg-[var(--blue)] px-3.5 py-1 text-[13px] font-medium text-white">Get ApplyTwin</a>
        </div>
      </header>

      <section className="px-4 pt-24 sm:pt-32">
        <div className="mx-auto max-w-[900px] text-center">
          <h1 className="display-xl text-[clamp(40px,7vw,88px)] [text-wrap:balance]">See it work.<br /><span className="muted">No install.</span></h1>
          <p className="mx-auto mt-6 max-w-[620px] text-[18px] leading-[1.45] [text-wrap:balance] sm:text-[20px]">
            Meet Maya, a sample computer science sophomore. Pick a posting and watch ApplyTwin rewrite her resume for it, then apply.
            <span className="muted"> The resumes below are real output from the app. The student and companies are made up.</span>
          </p>
        </div>
      </section>

      {err && <p className="mt-16 px-4 text-center muted">The demo couldn't load. Refresh the page to try again.</p>}
      {!data && !err && <div className="mx-4 mt-16"><div className="mx-auto h-40 max-w-[900px] animate-pulse rounded-[22px] bg-[var(--bg-2)]" /></div>}

      {data && <>
        <section className="px-4 pt-16 sm:pt-24">
          <div className="mx-auto max-w-[900px]">
            <Step n="1" title="Pick a posting." />
            <div className="mt-6 grid gap-3 sm:grid-cols-3" role="tablist" aria-label="Sample postings">
              {data.jobs.map((j, i) => (
                <button key={j.id} role="tab" aria-selected={pick === i} onClick={() => setPick(i)}
                  className={'rounded-[18px] bg-[var(--bg-2)] p-4 text-left transition ' + (pick === i ? 'ring-2 ring-[var(--blue)]' : 'ring-1 ring-[var(--line)] hover:ring-[var(--fg-3)]')}>
                  <div className="text-[15px] font-semibold">{j.company}</div>
                  <div className="mt-0.5 text-[14px] leading-snug muted">{j.title}</div>
                  <div className="mt-2 text-[12.5px] faint">{j.location}</div>
                </button>))}
            </div>
            <details className="mt-4 rounded-[18px] bg-[var(--bg-2)] p-4 text-[14px] leading-relaxed ring-1 ring-[var(--line)]">
              <summary className="cursor-pointer font-medium">Read the posting</summary>
              <p className="mt-3 whitespace-pre-line muted">{job.description}</p>
            </details>
          </div>
        </section>

        <section className="px-4 pt-16 sm:pt-24">
          <div className="mx-auto max-w-[900px]">
            <Step n="2" title="It rewrites her resume for that job." sub="Same facts in the posting's words. Numbers, titles and employers never change." />
            {/* no exit animation to wait for: the new posting's content is there at once, even on a slow phone */}
            <div>
              <motion.div key={job.id} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35, ease: EASE }}>
                <div className="mt-6 grid grid-cols-2 gap-3">
                  <Stat label="Resume score for this posting, her usual resume" value={<>{job.score_before}</>} dim />
                  <Stat label="Resume score, rewritten for this posting" value={<Count from={job.score_before} to={job.score_after} />} />
                </div>
                {job.positioning && <p className="mt-4 rounded-[18px] bg-[var(--bg-2)] p-4 text-[15px] leading-relaxed ring-1 ring-[var(--line)]">
                  <span className="muted">How it pitches her: </span>{job.positioning}</p>}
                <div className="mt-4 space-y-3">
                  {job.rewrites.map((r, i) => (
                    <motion.div key={i} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.12 * i + 0.2, duration: 0.5, ease: EASE }}
                      className="rounded-[18px] bg-[var(--bg-2)] p-4 ring-1 ring-[var(--line)]">
                      <div className="text-[14px] leading-relaxed line-through faint">{r.from}</div>
                      <div className="mt-2 flex gap-2 text-[15px] leading-relaxed"><ArrowRight className="mt-1 size-4 shrink-0 text-[var(--blue-text)]" />{r.to}</div>
                    </motion.div>))}
                </div>
              </motion.div>
            </div>
          </div>
        </section>

        <section className="px-4 pt-16 sm:pt-24">
          <div className="mx-auto max-w-[900px]">
            <Step n="3" title="One clean page, made for this posting." sub="The exact resume it would upload, filled to the bottom margin." />
            <Pages before={A + 'master.png'} after={A + job.page} company={job.company} />
          </div>
        </section>

        <section className="px-4 pt-16 sm:pt-24">
          <div className="mx-auto max-w-[900px]">
            <Step n="4" title="Then it applies, one job after another." sub="A replay of an Autopilot run. In the app this happens in its own Chrome window on your computer." />
            <Run job={job} />
          </div>
        </section>

        <section className="px-4 pt-16 sm:pt-24">
          <div className="mx-auto max-w-[900px]">
            <Step n="5" title="Only what needs you comes back to you." sub="Grouped, so one sign-in finishes every job on that site." />
            <div className="mt-6 overflow-hidden rounded-[22px] bg-[var(--bg-2)] ring-1 ring-[var(--line)] [&>*+*]:border-t [&>*+*]:border-[var(--line)]">
              {[[KeyRound, 'Sign in to 2 sites', 'Workday at Lumen Bank and one more. Or let it sign in for you, without the AI ever seeing your password.', 3],
                [Hand, 'Answer 1 question only you know', '"Are you able to work on-site three days a week?" Saved for every future application.', 1],
                [Send, 'Review and submit 2 applications', 'Filled and waiting on the review screen, so you press Submit.', 2]].map(([I, t, d, c]) => (
                <div key={t} className="flex items-start gap-3.5 p-4 sm:p-5">
                  <span className="grid size-9 shrink-0 place-items-center rounded-full bg-[var(--bg-3)] ring-1 ring-[var(--line)]"><I className="size-4" /></span>
                  <div className="min-w-0 flex-1"><div className="text-[15px] font-semibold">{t}</div><div className="mt-0.5 text-[14px] leading-snug muted">{d}</div></div>
                  <span className="text-[14px] tabular-nums faint">{c}</span>
                </div>))}
            </div>
          </div>
        </section>
      </>}

      <section id="get" className="px-4 pb-28 pt-20 sm:pt-32">
        <div className="mx-auto max-w-[760px] text-center">
          <h2 className="display-l text-[clamp(34px,5.5vw,60px)] [text-wrap:balance]">Do this for your applications.</h2>
          <p className="mx-auto mt-4 max-w-[560px] text-[17px] leading-relaxed muted [text-wrap:balance]">
            ApplyTwin is free and runs on your computer, using the Claude Code or Codex plan you already have. Setup takes about five minutes.</p>
          {PHONE ? <PhoneGet /> : <div className="mx-auto mt-8 max-w-[640px] text-left"><InstallBox win={win} setWin={setWin} hero />
            <p className="mt-4 text-center text-[14px] muted">Paste it into {win ? 'PowerShell' : 'Terminal'}. It checks what you need and tells you what's missing.</p></div>}
          <a href="/" className="link mt-8 inline-block text-[16px]">How ApplyTwin works</a>
        </div>
      </section>
    </div>
    </MotionConfig>
  )
}

function Step({ n, title, sub }) {
  return (
    <Reveal>
      <div className="text-[14px] font-semibold text-[var(--blue-text)]">Step {n}</div>
      <h2 className="display-l mt-1 text-[clamp(28px,4.4vw,44px)] [text-wrap:balance]">{title}</h2>
      {sub && <p className="mt-2 max-w-[640px] text-[16px] leading-relaxed muted">{sub}</p>}
    </Reveal>)
}

function Stat({ label, value, dim }) {
  return (
    <div className="rounded-[18px] bg-[var(--bg-2)] p-4 ring-1 ring-[var(--line)] sm:p-5">
      <div className={'text-[34px] font-semibold tracking-[-0.03em] sm:text-[44px] ' + (dim ? 'faint' : '')}>{value}</div>
      <div className="mt-1 text-[13px] leading-snug muted">{label}</div>
    </div>)
}

function Pages({ before, after, company }) {
  const [show, setShow] = useState('after')
  return (
    <div className="mt-6">
      <div className="mx-auto mb-4 flex w-fit rounded-full bg-[var(--bg-2)] p-[3px] text-[13px] ring-1 ring-[var(--line)]" role="tablist">
        {[['before', 'Her usual resume'], ['after', `For ${company}`]].map(([k, l]) => (
          <button key={k} role="tab" aria-selected={show === k} onClick={() => setShow(k)}
            className={'rounded-full px-4 py-1.5 transition ' + (show === k ? 'bg-[var(--bg-3)] font-semibold shadow-sm' : 'muted')}>{l}</button>))}
      </div>
      <div className="mx-auto max-w-[620px] overflow-hidden rounded-[10px] bg-white shadow-[var(--shadow)] ring-1 ring-[var(--line)]">
        <motion.img key={show + after} src={show === 'after' ? after : before} alt={show === 'after' ? `Maya's resume rewritten for ${company}` : "Maya's usual resume"}
          initial={{ opacity: 0.4 }} animate={{ opacity: 1 }} transition={{ duration: 0.3 }} className="block w-full" />
      </div>
    </div>)
}

/* the replay: the job you picked first, then a few others, each line ticking through what the twin does */
function Run({ job }) {
  const ref = useRef(null)
  const seen = useInView(ref, { margin: '-80px' })
  const rows = [
    { company: job.company, title: job.title, end: 'Ready for your Submit click', icon: Send, steps: ['Opening the application', 'Filling contact details and education', 'Uploading the resume made for it', 'Answering 7 questions from her saved answers'] },
    { company: 'Brightline Labs', title: 'Software Engineer Intern', end: 'Submitted', icon: Check, steps: ['Opening the application', 'Filling the form', 'Uploading a new resume for it'] },
    { company: 'Lumen Bank', title: 'Technology Analyst Intern', end: 'Waiting on your sign-in', icon: KeyRound, steps: ['Opening the application', 'Workday asks for an account'] },
    { company: 'Redwood Systems', title: 'Backend Intern', end: 'Skipped: posting closed', icon: CircleSlash, steps: ['Opening the application'] },
  ]
  const [t, setT] = useState(0)
  useEffect(() => {
    setT(0)
    if (!seen) return
    const i = setInterval(() => setT(x => (x > 22 ? 0 : x + 1)), 700)
    return () => clearInterval(i)
  }, [seen, job.id])
  let clock = 0
  return (
    <div ref={ref} className="mt-6 overflow-hidden rounded-[22px] bg-[var(--bg-2)] ring-1 ring-[var(--line)] [&>*+*]:border-t [&>*+*]:border-[var(--line)]">
      {rows.map(r => {
        const start = clock
        clock += r.steps.length + 1
        const k = t - start
        const done = k > r.steps.length
        const status = k < 0 ? 'Up next' : done ? r.end : r.steps[Math.min(k, r.steps.length - 1)]
        const I = r.icon
        const color = r.end === 'Submitted' ? 'var(--green)' : r.end.startsWith('Skipped') ? 'var(--fg-3)' : 'var(--orange)'
        return (
          <div key={r.company + r.title} className={'flex items-center gap-3.5 p-4 transition-opacity duration-500 sm:p-5 ' + (k < 0 ? 'opacity-50' : '')}>
            <span className="grid size-9 shrink-0 place-items-center rounded-full bg-[var(--bg-3)] text-[14px] font-semibold ring-1 ring-[var(--line)]">{r.company[0]}</span>
            <div className="min-w-0 flex-1">
              <div className="truncate text-[15px] font-semibold">{r.company} <span className="font-normal muted">· {r.title}</span></div>
              <motion.div key={status} initial={{ opacity: 0.3, y: 3 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }}
                className={'mt-0.5 flex items-center gap-1.5 text-[13.5px] ' + (done ? '' : 'muted')} style={done ? { color } : undefined}>
                {done && <I className="size-3.5" />}{status}{!done && k >= 0 && <span className="animate-pulse">…</span>}
              </motion.div>
            </div>
          </div>)
      })}
    </div>)
}

function PhoneGet() {
  const [ok, setOk] = useState(false)
  const url = 'https://apply.twinly.tech'
  const share = async () => {
    if (navigator.share) { try { await navigator.share({ title: 'ApplyTwin', text: 'Set this up on my computer', url }) } catch {} return }
    navigator.clipboard?.writeText(url).then(() => { setOk(true); setTimeout(() => setOk(false), 1600) }).catch(() => {})
  }
  return (
    <div className="mx-auto mt-8 max-w-[440px] rounded-[22px] bg-[var(--bg-2)] p-6 text-left ring-1 ring-[var(--line)]">
      <div className="text-[17px] font-semibold">You're on your phone.</div>
      <p className="mt-1 text-[15px] leading-relaxed muted">ApplyTwin installs on a Mac, Windows or Linux computer. Send yourself the link and open it there.</p>
      <button onClick={share} className="mt-4 inline-flex h-11 w-full items-center justify-center gap-2 rounded-full bg-[var(--blue)] text-[16px] font-semibold text-white">
        <Share className="size-4" />{ok ? 'Link copied' : 'Send me the link'}</button>
    </div>)
}
