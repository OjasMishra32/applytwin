import { Suspense, lazy, useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion, useInView, useMotionValueEvent, useScroll, useTransform, useReducedMotion } from 'motion/react'
import { Check, Copy, Star } from 'lucide-react'
import { Toaster } from 'sonner'
import { Avatar } from '../components/ui'
import { REPO_URL, useStars } from '../lib/star'
import { HowItWorks, Logo } from './Steps'
import './site.css'

/* apply.twinly.tech: the public home of ApplyTwin, built the way Apple builds a product page. One idea per scroll,
   the system font set large and tight, real product UI as the picture, and motion only where it explains something:
   the window opening, the resume fanning into versions, the bullets rewriting themselves, the words lighting up. */

const INSTALL = 'curl -fsSL apply.twinly.tech/install | bash'
const INSTALL_WIN = 'irm apply.twinly.tech/install.ps1 | iex'
const IS_WIN = typeof navigator !== 'undefined' && /windows/i.test(navigator.userAgent)

const FAQ = [
  ['Do I need an API key?', 'No. ApplyTwin runs on the Claude Code or Codex subscription you already have. If you can use either one in a terminal, you can use ApplyTwin.'],
  ['Where does my data live?', 'On your computer, in a folder called ~/.applytwin. Signing in backs up your setup so a new laptop picks up where you left off.'],
  ['Will it submit applications without me?', 'Only if you turn that on. Otherwise it fills every form and stops on the review screen, so you press Submit.'],
  ['What will it never do?', 'Type your passwords, solve CAPTCHAs, create accounts, accept legal agreements, or change your numbers, titles or employers. Those come to you instead.'],
  ['Does it work on Windows?', 'Yes. Mac, Windows and Linux. On Windows, paste the PowerShell command.'],
  ['Is it only for software jobs?', 'No. It knows what a strong resume looks like in your field, from nursing and finance to design, research and engineering.'],
  ['Why do I sign in with Google?', 'So your setup, answers and applications are saved to your account. ApplyTwin never posts, emails or signs up for anything as you.'],
  ['Does it track me?', 'It counts installs with a random ID, your OS and its version, once a day. Never your resume, jobs or applications. You can turn it off in Settings.'],
  ['What does it cost?', 'Nothing. ApplyTwin is free.'],
]

// Apple's motion: long, eased, small. Nothing bounces; things settle.
const EASE = [0.25, 0.1, 0.25, 1]
function Reveal({ children, className, style, delay = 0 }) {
  return (
    <motion.div className={className} style={style} initial={{ opacity: 0, y: 24 }} whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-40px' }} transition={{ duration: 0.9, ease: EASE, delay }}>{children}</motion.div>
  )
}
const clamp = v => Math.min(1, Math.max(0, v))

const Fan3D = lazy(() => import('./Fan3D'))   // three.js loads only when the fan is near the screen
const webgl = () => { try { const c = document.createElement('canvas'); return !!(c.getContext('webgl2') || c.getContext('webgl')) } catch { return false } }

export default function Site() {
  const stars = useStars()   // fetched once, shown on every star button
  return (
    <div className="site min-h-screen overflow-x-clip">
      <Toaster position="bottom-center" />
      <Nav stars={stars} />

      {/* 1. What it is, with the app itself as the picture */}
      <section className="px-4 pt-28 sm:pt-36">
        <div className="mx-auto max-w-[1120px] min-[1800px]:max-w-[1360px] text-center">
          <h1 className="display-xl text-[clamp(44px,7.4vw,104px)] [text-wrap:balance]">
            <span style={{ animationDelay: '0.04s' }} className="rise block">You apply once.</span>
            <span style={{ animationDelay: '0.12s' }} className="rise block muted">Your twin does the rest.</span>
          </h1>
          <p style={{ animationDelay: '0.22s' }} className="rise mx-auto mt-7 max-w-[640px] text-[19px] leading-[1.42] [text-wrap:balance] sm:text-[21px]">
            It finds internships that fit you, writes a one-page resume for each posting and fills out the application.
            <span className="muted"> All on the Claude Code or Codex plan you already pay for.</span>
          </p>
          <div style={{ animationDelay: '0.3s' }} className="rise mt-8 flex flex-wrap items-center justify-center gap-x-7 gap-y-3">
            <a href="#start" className="btn">Install free</a>
            <StarButton n={stars} />
          </div>
        </div>
        <div className="mx-auto mt-14 max-w-[1120px] min-[1800px]:max-w-[1360px] sm:mt-20"><Lid><AppWindow /></Lid></div>
        <p className="mx-auto mt-5 max-w-[1120px] min-[1800px]:max-w-[1360px] text-center text-[13px] faint">Autopilot, mid-run. Twenty-five applications queued, three already in.</p>
      </section>

      {/* 2. One resume becomes many */}
      <OneToMany />

      {/* 3. How a single bullet changes */}
      <Becomes />

      {/* 4. The four things it does, one at a time */}
      <section id="how" className="px-4 pt-24 sm:pt-32">
        <div className="mx-auto max-w-[1120px] min-[1800px]:max-w-[1360px]">
          <Reveal><h2 className="display-l max-w-[820px] text-[clamp(38px,6vw,72px)] [text-wrap:balance]">Everything between you and Submit.</h2></Reveal>
          <HowItWorks />
        </div>
      </section>

      {/* 5. Where it applies */}
      <section className="px-4 pt-20 sm:pt-28">
        <div className="mx-auto max-w-[1120px] min-[1800px]:max-w-[1360px]">
          <Scrub className="display-l max-w-[1040px] text-[clamp(32px,5.2vw,64px)] [text-wrap:balance]" parts={[
            ['It applies at', 0], ['Google, Meta, Apple, NVIDIA, Jane Street, Citadel, Palantir, Anduril, Stripe, OpenAI, Two Sigma', 1],
            ['and more than 600 other companies, straight through their own career sites.', 0]]} />
        </div>
      </section>

      {/* 6. The lines it won't cross */}
      <Never />

      {/* 7. Price */}
      <section className="px-4 pt-24 sm:pt-36">
        <div className="mx-auto grid max-w-[1120px] min-[1800px]:max-w-[1360px] gap-8 md:grid-cols-[auto_minmax(0,1fr)] md:items-end md:gap-16">
          <Reveal><div className="display-xl text-[clamp(120px,20vw,240px)] leading-[0.82]">$0</div></Reveal>
          <Reveal delay={0.1} className="pb-2">
            <h2 className="display-l text-[clamp(28px,3.4vw,40px)] [text-wrap:balance]">No API key. No new subscription.</h2>
            <p className="mt-4 max-w-[520px] text-[19px] leading-[1.45] muted">
              ApplyTwin is free and open source. The thinking happens in Claude Code or Codex, on your own computer, under the plan you already have.
            </p>
          </Reveal>
        </div>
      </section>

      {/* 8. Install */}
      <section id="start" className="px-4 pt-24 sm:pt-36">
        <div className="mx-auto max-w-[1120px] min-[1800px]:max-w-[1360px] text-center">
          <Reveal><h2 className="display-l text-[clamp(38px,6vw,72px)]">Set up in one line.</h2></Reveal>
          <Reveal delay={0.05} className="mx-auto mt-4 max-w-[560px] text-[19px] leading-[1.45] muted [text-wrap:balance]">Paste this into your terminal. It installs ApplyTwin, connects your agent and opens the app.</Reveal>
          <Reveal delay={0.1} className="mx-auto mt-10 max-w-[760px] text-left"><InstallBox /></Reveal>
          <p className="mt-4 text-[14px] faint">Mac, Windows and Linux. Needs Python 3.9+, Node.js, and Claude Code or Codex.</p>
          <Reveal delay={0.12} className="mx-auto mt-8 flex max-w-[760px] flex-wrap items-center justify-center gap-x-5 gap-y-3 rounded-[18px] px-6 py-5" style={{ background: 'var(--bg-2)' }}>
            <span className="text-[15px] [text-wrap:balance]">ApplyTwin is free and open source. <span className="muted">A star helps other students find it.</span></span>
            <StarButton n={stars} size="sm" />
          </Reveal>
          <ol className="mx-auto mt-14 grid max-w-[880px] gap-8 sm:grid-cols-3 sm:gap-6">
            {[['Paste the command', 'in Terminal, or PowerShell on Windows.'], ['Drop in your resume', 'and answer the setup questions once.'],
              ['Press Start', 'and watch it apply in its own window.']].map(([t, d], i) => (
              <Reveal key={t} delay={i * 0.06}>
                <li className="list-none">
                  <div className="mx-auto grid size-9 place-items-center rounded-full text-[15px] font-semibold" style={{ background: 'var(--bg-2)' }}>{i + 1}</div>
                  <div className="mt-3 text-[17px] font-semibold">{t}</div>
                  <div className="mx-auto max-w-[240px] text-[15px] muted">{d}</div>
                </li>
              </Reveal>))}
          </ol>
        </div>
      </section>

      {/* 9. Questions */}
      <section id="faq" className="px-4 pt-24 sm:pt-36">
        <div className="mx-auto grid max-w-[1120px] min-[1800px]:max-w-[1360px] gap-8 md:grid-cols-[minmax(0,4fr)_minmax(0,7fr)] md:gap-16">
          <Reveal><h2 className="display-l text-[clamp(34px,4.4vw,48px)] md:sticky md:top-24">Questions.</h2></Reveal>
          <Reveal delay={0.05}><div className="border-t border-[var(--line)]">{FAQ.map(([q, a]) => <Faq key={q} q={q} a={a} />)}</div></Reveal>
        </div>
      </section>

      {/* 10. Close */}
      <section className="px-4 pb-28 pt-28 sm:pb-40 sm:pt-40">
        <Reveal className="mx-auto max-w-[1120px] min-[1800px]:max-w-[1360px] text-center">
          <h2 className="display-xl text-[clamp(56px,10vw,128px)]">Get hired.</h2>
          <p className="mx-auto mt-5 max-w-[520px] text-[19px] leading-[1.45] muted [text-wrap:balance]">ApplyTwin is free and has no ads. A star on GitHub is how other students find it.</p>
          <div className="mt-9 flex flex-wrap items-center justify-center gap-x-7 gap-y-3">
            <a href="#start" className="btn">Install free</a>
            <StarButton n={stars} />
          </div>
        </Reveal>
      </section>

      <footer className="border-t border-[var(--line)] bg-[var(--bg-2)] px-4 py-8 text-[12px] faint">
        <div className="mx-auto flex max-w-[1120px] min-[1800px]:max-w-[1360px] flex-wrap items-center justify-between gap-3">
          <span>Copyright © 2026 Ojasva Mishra. ApplyTwin, from Twinly.</span>
          <span className="flex gap-5"><a href="/app" className="hover:underline">Your account</a><a href={REPO_URL} target="_blank" rel="noreferrer" className="hover:underline">GitHub</a></span>
        </div>
      </footer>
    </div>
  )
}

function Nav({ stars }) {
  return (
    <header className="nav fixed inset-x-0 top-0 z-50">
      <div className="mx-auto flex h-12 max-w-[1120px] min-[1800px]:max-w-[1360px] items-center justify-between px-4">
        <a href="#" className="flex items-center gap-2 text-[15px] font-semibold"><Logo size={18} />ApplyTwin</a>
        <nav className="flex items-center gap-5 text-[13px]">
          <a href="#how" className="hidden opacity-80 hover:opacity-100 sm:block">How it works</a>
          <a href="#faq" className="hidden opacity-80 hover:opacity-100 sm:block">Questions</a>
          <a href="/app" className="hidden opacity-80 hover:opacity-100 sm:block">Account</a>
          <span className="hidden sm:inline-flex"><StarButton n={stars} size="nav" /></span>
          <a href="#start" className="rounded-full bg-[var(--blue)] px-3.5 py-1 text-[13px] font-medium text-white">Install</a>
        </nav>
      </div>
    </header>
  )
}

/* One resume becomes many, in 3D: pinned while you scroll, the stack fans out into versions tailored for each company. */
function OneToMany() {
  const ref = useRef(null)
  const progress = useRef(0)
  const [ok] = useState(() => typeof window !== 'undefined' && webgl())
  const [show, setShow] = useState(false)
  const near = useInView(ref, { margin: '600px 0px' })
  useEffect(() => { if (near) setShow(true) }, [near])
  const { scrollYProgress } = useScroll({ target: ref, offset: ['start start', 'end end'] })
  const [p, setP] = useState(0)
  useMotionValueEvent(scrollYProgress, 'change', v => { progress.current = v; setP(v) })
  if (!ok) return null
  const t = clamp((p - 0.05) / 0.55)
  const n = Math.max(1, Math.round(t * 8))
  return (
    <section ref={ref} className="relative mt-16 h-[210vh] sm:mt-24">
      <div className="sticky top-0 h-[100svh] overflow-hidden">
        <div className="pointer-events-none absolute inset-x-0 top-[11vh] z-10 px-4">
          <h2 className="display-l mx-auto max-w-[1120px] min-[1800px]:max-w-[1360px] text-[clamp(38px,6vw,72px)]">
            <span className="block">One resume.</span>
            <span className="block" style={{ color: 'var(--fg-2)', opacity: 0.18 + 0.82 * t }}>A version for every job.</span>
          </h2>
        </div>
        <div className="absolute inset-x-0 bottom-[11vh] top-[24vh]">
          {show && <Suspense fallback={null}><Fan3D progress={progress} /></Suspense>}
        </div>
        <div className="pointer-events-none absolute inset-x-0 bottom-[6vh] z-10 px-4">
          <div className="mx-auto flex max-w-[1120px] min-[1800px]:max-w-[1360px] items-baseline justify-between gap-4 text-[14px]">
            <span className="muted"><span className="font-semibold tabular-nums text-[var(--fg)]">{n} {n === 1 ? 'resume' : 'resumes'}</span>{n > 1 ? ', each written for one company' : ', yours'}</span>
            <span className="hidden items-center gap-2 faint sm:flex"><span className="inline-block h-[3px] w-5 rounded-full bg-[var(--blue)]" />rewritten for that job</span>
          </div>
        </div>
      </div>
    </section>
  )
}

/* Words light up as you read down the page: the sentence fills in at reading speed, the company names land hardest. */
function Scrub({ parts, className }) {
  const ref = useRef(null)
  const { scrollYProgress } = useScroll({ target: ref, offset: ['start 0.85', 'end 0.5'] })
  const words = parts.flatMap(([t, strong]) => t.split(' ').filter(Boolean).map(w => [w, strong]))
  return (
    <p ref={ref} className={className}>
      {words.map(([w, s], i) => <Word key={i} p={scrollYProgress} at={i / words.length} span={3 / words.length} strong={s}>{w}</Word>)}
    </p>
  )
}
function Word({ p, at, span, strong, children }) {
  const still = useReducedMotion()
  const opacity = useTransform(p, [at, Math.min(1, at + span)], [0.16, 1])
  return <><motion.span style={{ opacity: still ? 1 : opacity, color: strong ? 'var(--fg)' : 'var(--fg-2)' }}>{children}</motion.span>{' '}</>
}

/* The hard limits, in a dark band, scrubbed line by line. */
const NEVER = ['Type your password.', 'Solve a CAPTCHA.', 'Create an account in your name.', 'Accept a legal agreement.', 'Change a number or a title on your resume.']
function Never() {
  const ref = useRef(null)
  const { scrollYProgress } = useScroll({ target: ref, offset: ['start 0.75', 'end 0.6'] })
  return (
    <section className="band mt-24 px-4 py-24 sm:mt-32 sm:py-32">
      <div ref={ref} className="mx-auto max-w-[1120px] min-[1800px]:max-w-[1360px]">
        <div className="text-[17px] font-semibold sm:text-[19px]" style={{ color: 'var(--band-fg-2)' }}>What it will never do</div>
        <ul className="mt-6">
          {NEVER.map((l, i) => <NeverLine key={l} p={scrollYProgress} i={i} n={NEVER.length}>{l}</NeverLine>)}
        </ul>
        <p className="mt-12 max-w-[560px] text-[19px] leading-[1.45]" style={{ color: 'var(--band-fg-2)' }}>
          Those come to you as a notification. And unless you turn on auto-submit, it stops on the review screen so you press Submit yourself.
        </p>
      </div>
    </section>
  )
}
function NeverLine({ p, i, n, children }) {
  const still = useReducedMotion()
  const a = i / (n + 1)
  const opacity = useTransform(p, [a, a + 1 / (n + 1)], [0.2, 1])
  const strike = useTransform(p, [a + 0.5 / (n + 1), a + 1.4 / (n + 1)], [0, 1])
  return (
    <motion.li style={{ opacity: still ? 1 : opacity }} className="display-l relative w-fit py-1 text-[clamp(30px,4.6vw,60px)] [text-wrap:balance]">
      {children}
      <motion.span aria-hidden className="absolute left-0 right-0 top-[54%] h-[0.07em] origin-left rounded-full bg-[var(--orange)]" style={{ scaleX: still ? 1 : strike }} />
    </motion.li>
  )
}

/* The heart of it, pinned while you scroll: a job's requirements light up one by one, and the resume rewrites itself
   to prove each one. A well-known public resume; every rewrite keeps the original facts, as the real fact checker requires. */
const ROLE = { company: 'NASA', domain: 'nasa.gov', title: 'Human Spaceflight Program Lead' }
// Elon Musk's public record, tailored for one role: every "after" line is a real, public fact about him
const STEPS = [
  { req: 'Has built and scaled organizations',
    before: 'Started a few companies.',
    after: <>Co-founded <b>Zip2</b>, sold to Compaq for <b>$307M</b>, and <b>X.com</b>, which became <b>PayPal</b>.</> },
  { req: 'Launch vehicle experience',
    before: 'Worked on rockets.',
    after: <>Founded <b>SpaceX</b> in 2002; Falcon 9 became the first orbital-class rocket to <b>land and reuse</b> its first stage.</> },
  { req: 'Engineering at scale',
    before: 'Runs a car company.',
    after: <>CEO of <b>Tesla</b> since 2008, scaling it to <b>millions of electric vehicles</b> a year.</> },
]

function Becomes() {
  const ref = useRef(null)
  const { scrollYProgress } = useScroll({ target: ref, offset: ['start start', 'end end'] })
  const [p, setP] = useState(0)
  useMotionValueEvent(scrollYProgress, 'change', setP)
  const still = useReducedMotion()
  const at = i => (still ? 1 : clamp((p - (0.1 + i * 0.22)) / 0.16))
  const done = STEPS.filter((_, i) => at(i) >= 1).length
  const match = Math.round(38 + (94 - 38) * Math.min(1, (at(0) + at(1) + at(2)) / 3))
  const role = at(0) > 0.5
  return (
    <section ref={ref} className="relative h-auto px-4 pt-20 md:h-[250vh] md:pt-0">
      <div className="mx-auto max-w-[1120px] min-[1800px]:max-w-[1360px] md:sticky md:top-0 md:flex md:h-screen md:flex-col md:justify-center md:pb-6 md:pt-16">
        <h2 className="display-l max-w-[900px] text-[clamp(38px,5.4vw,64px)] [text-wrap:balance]">Same person.<br /><span className="muted">Proven for this job.</span></h2>
        <p className="mt-4 max-w-[640px] text-[19px] leading-[1.45] muted [text-wrap:pretty]">It reads what the team screens for, then rewrites your real experience to prove each point. Here is Elon Musk's public record, aimed at one NASA posting.</p>
        <div className="mt-8 grid gap-5 md:grid-cols-[0.9fr_1.1fr]">
          <div className="sheet flex flex-col p-6 sm:p-8">
            <div className="flex items-center gap-3"><Avatar name={ROLE.company} domain={ROLE.domain} size={36} />
              <div><div className="text-[15px] font-semibold">{ROLE.title}</div><div className="text-[13px] muted">{ROLE.company}</div></div></div>
            <div className="mt-6 text-[12px] font-semibold uppercase tracking-[0.05em] faint">What they screen for</div>
            <div className="mt-3 space-y-2.5">
              {STEPS.map((s, i) => (
                <div key={s.req} className="flex items-center gap-3 rounded-[12px] px-3 py-2.5 transition-colors duration-500"
                  style={{ background: at(i) > 0 ? 'var(--bg-2)' : 'transparent' }}>
                  <span className="grid size-6 shrink-0 place-items-center rounded-full text-[12px] font-semibold transition-colors duration-500"
                    style={{ background: at(i) >= 1 ? 'var(--green)' : at(i) > 0 ? 'var(--blue)' : 'var(--line)', color: at(i) > 0 ? '#fff' : 'var(--fg-3)' }}>
                    {at(i) >= 1 ? <Check className="size-3.5" strokeWidth={3} /> : i + 1}</span>
                  <span className={'text-[16px] transition-colors duration-500 ' + (at(i) > 0 ? '' : 'faint')}>{s.req}</span>
                </div>))}
            </div>
            <div className="mt-auto flex items-end justify-between pt-8">
              <div className="text-[13px] muted">Match for this role</div>
              <div className="display-l text-[52px] tabular-nums leading-none" style={{ color: done === 3 ? 'var(--green)' : 'var(--fg)' }}>{match}%</div>
            </div>
          </div>
          <div className="sheet p-6 text-left sm:p-8" style={{ fontFamily: 'Georgia, "Times New Roman", serif' }}>
            <div className="text-center text-[22px] font-bold tracking-[0.04em]">ELON MUSK</div>
            <div className="relative mt-1 h-[20px] overflow-hidden text-center text-[13px] font-semibold">
              <AnimatePresence mode="popLayout" initial={false}>
                <motion.div key={role ? 'r' : 'g'} initial={{ y: 14, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: -14, opacity: 0 }}
                  transition={{ duration: 0.5, ease: EASE }}>
                  {role ? 'Human Spaceflight · Reusable Rockets · Engineering Leadership' : 'Entrepreneur'}
                </motion.div>
              </AnimatePresence>
            </div>
            <div className="mt-5 border-b border-[var(--line)] pb-1 text-[12px] font-semibold tracking-[0.08em]">EXPERIENCE & PROJECTS</div>
            <div className="mt-3 space-y-4">
              {STEPS.map((s, i) => {
                const k = at(i)
                return (
                  <div key={s.req} className="relative grid text-[15px] leading-[1.45]">
                    <div className="col-start-1 row-start-1 flex gap-2 muted" style={{ opacity: 1 - clamp(k * 2), filter: `blur(${clamp(k * 2) * 4}px)` }}>
                      <span>•</span><span>{s.before}</span></div>
                    <div className="col-start-1 row-start-1 flex gap-2" style={{ opacity: clamp(k * 2 - 1), transform: `translateY(${(1 - clamp(k * 2 - 1)) * 8}px)` }}>
                      <span style={{ color: 'var(--blue)' }}>•</span><span>{s.after}</span></div>
                  </div>)
              })}
            </div>
            <div className="mt-6 flex flex-wrap gap-2" style={{ fontFamily: 'inherit' }}>
              {['reusable rockets', 'human spaceflight', 'scaling teams', 'physics', 'manufacturing'].map((w, i) => (
                <span key={w} className="rounded-full px-3 py-1 text-[12.5px] font-semibold text-[var(--bg)] transition-all duration-500"
                  style={{ background: 'var(--fg)', opacity: done > i * 0.6 ? 1 : 0, transform: `scale(${done > i * 0.6 ? 1 : 0.85})`,
                    fontFamily: '-apple-system, BlinkMacSystemFont, system-ui, sans-serif' }}>{w}</span>))}
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

/* As it scrolls in, the window tilts up toward you and settles flat, the way Apple opens a MacBook on its pages. */
function Lid({ children }) {
  const ref = useRef(null)
  const still = useReducedMotion()
  const { scrollYProgress } = useScroll({ target: ref, offset: ['start end', 'center center'] })
  const [narrow] = useState(() => typeof window !== 'undefined' && window.innerWidth < 640)   // a tall phone-width window tilts less, or it leaves a gap above
  const rotateX = useTransform(scrollYProgress, [0, 1], [narrow ? 6 : 16, 0])
  const scale = useTransform(scrollYProgress, [0, 1], [narrow ? 0.97 : 0.92, 1])
  const opacity = useTransform(scrollYProgress, [0, 0.3], [0.75, 1])
  return (
    <div ref={ref} style={{ perspective: 1800 }}>
      <motion.div style={still ? {} : { rotateX, scale, opacity, transformOrigin: 'center bottom' }}>{children}</motion.div>
    </div>
  )
}

/* The app itself, at work: what you'd see on your Mac while your twin applies. It really runs through its steps. */
function AppWindow() {
  const queue = [['Google', 'google.com', 'Software Engineering Intern', 98], ['OpenAI', 'openai.com', 'Research Engineer Intern', 97],
    ['Jane Street', 'janestreet.com', 'Software Engineer Intern', 96], ['Citadel', 'citadel.com', 'Quantitative Research Intern', 95],
    ['Two Sigma', 'twosigma.com', 'Quant Research Intern', 94], ['Anthropic', 'anthropic.com', 'Software Engineer Intern', 94]]
  const STEPS = ['Opening the posting', 'Tailoring your resume', 'Filling the application', 'Submitted']
  const box = useRef(null)
  const seen = useInView(box, { margin: '-20% 0px' })
  const [tick, setTick] = useState(0)
  useEffect(() => {
    if (!seen) return
    const t = setInterval(() => setTick(x => x + 1), 1700)
    return () => clearInterval(t)
  }, [seen])
  const job = Math.floor(tick / STEPS.length) % (queue.length - 3)
  const step = STEPS[tick % STEPS.length]
  const cur = queue[job]
  const next = queue.slice(job + 1, job + 5)
  const done = [['Apple', 'apple.com', 'Software Engineering Intern'], ['Palantir', 'palantir.com', 'Forward Deployed Engineer Intern'],
    ['Meta', 'meta.com', 'Software Engineer Intern'], ...queue.slice(0, job).map(([c, d, t]) => [c, d, t])].slice(-3).reverse()
  const count = 3 + job + (step === 'Submitted' ? 1 : 0)
  const nav = ['Today', 'Jobs', 'Resume', 'Answers', 'Applications', 'Autopilot']
  return (
    <div ref={box} className="mx-auto w-full max-w-[1120px] min-[1800px]:max-w-[1360px] overflow-hidden appwin rounded-[14px] text-left"
      style={{ background: '#1c1c1e', color: '#f5f5f7', colorScheme: 'dark' }}>
      <div className="grid md:grid-cols-[200px_1fr] [&>*]:min-w-0">
        {/* the real app's sidebar */}
        <aside className="hidden flex-col border-r border-white/[.07] px-3 pb-4 pt-3 md:flex" style={{ background: '#232325' }}>
          <div className="flex gap-2 px-1 pb-5 pt-1">{['#ff5f57', '#febc2e', '#28c840'].map(c => <span key={c} className="size-3 rounded-full" style={{ background: c }} />)}</div>
          <div className="mb-4 flex items-center gap-2 px-2.5"><Logo size={18} /><span className="text-[14px] font-semibold">ApplyTwin</span></div>
          {nav.map(n => (
            <div key={n} className={'flex h-8 items-center rounded-[7px] px-2.5 text-[13px] ' + (n === 'Autopilot' ? 'bg-[#0a84ff] text-white' : 'text-white/80')}>{n}</div>))}
          <div className="mt-auto px-2.5 text-[13px] text-white/60">Settings</div>
        </aside>
        <div className="min-w-0">
          <div className="flex h-11 items-center gap-2 border-b border-white/[.07] px-4 md:hidden">
            {['#ff5f57', '#febc2e', '#28c840'].map(c => <span key={c} className="size-3 rounded-full" style={{ background: c }} />)}
            <span className="mx-auto pr-14 text-[13px] font-medium text-white/60">ApplyTwin</span>
          </div>
          <div className="grid gap-7 p-5 sm:p-8 lg:grid-cols-[1.2fr_1fr] [&>*]:min-w-0">
            <div>
              <div className="text-[28px] font-bold tracking-[-0.02em]">Autopilot</div>
              <div className="mt-4 rounded-[14px] p-5" style={{ background: '#2c2c2e' }}>
                <div className="text-[12.5px] font-medium text-[#30d158]">Claude Code is applying</div>
                <div className="relative mt-1 h-[34px] overflow-hidden">
                  <AnimatePresence mode="popLayout" initial={false}>
                    <motion.div key={step + job} initial={{ y: 20, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: -20, opacity: 0 }}
                      transition={{ duration: 0.55, ease: EASE }} className="flex items-center gap-2 text-[26px] font-semibold tracking-[-0.02em]">
                      {step}{step === 'Submitted' && <Check className="size-6 text-[#30d158]" />}
                    </motion.div>
                  </AnimatePresence>
                </div>
                <div className="flex items-center gap-2 text-[13.5px] text-white/60">
                  <Avatar name={cur[0]} domain={cur[1]} size={18} />{cur[0]} · {cur[2]} · {count} of 25</div>
                <div className="mt-4 h-[4px] overflow-hidden rounded-full bg-white/[.08]">
                  <motion.div className="h-full rounded-full bg-[#0a84ff]" animate={{ width: `${(count / 25) * 100}%` }} transition={{ duration: 0.9, ease: EASE }} /></div>
              </div>
              <div className="mt-6 px-1 text-[12px] font-semibold uppercase tracking-[0.05em] text-white/45">Up next</div>
              <div className="mt-2 overflow-hidden rounded-[14px]" style={{ background: '#2c2c2e' }}>
                <AnimatePresence initial={false}>
                  {next.map(([c, d, t, f]) => (
                    <motion.div layout key={c} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -12 }}
                      transition={{ duration: 0.6, ease: EASE }} className="flex items-center gap-3 border-b border-white/[.06] px-4 py-2.5 last:border-0">
                      <Avatar name={c} domain={d} size={28} />
                      <div className="min-w-0 flex-1"><div className="truncate text-[14px] font-medium">{t}</div><div className="text-[12.5px] text-white/55">{c}</div></div>
                      <div className="text-[13.5px] tabular-nums text-white/60">{f}%</div>
                    </motion.div>))}
                </AnimatePresence>
              </div>
            </div>
            <div>
              <div className="px-1 pt-1 text-[12px] font-semibold uppercase tracking-[0.05em] text-white/45 lg:mt-12">Needs you</div>
              <div className="mt-2 rounded-[14px] p-4" style={{ background: '#2c2c2e' }}>
                <div className="flex items-center gap-3"><Avatar name="NVIDIA" domain="nvidia.com" size={28} />
                  <div className="min-w-0"><div className="text-[14px] font-medium">Sign in to Workday</div><div className="truncate text-[12.5px] text-white/55">NVIDIA · Deep Learning Software Intern</div></div></div>
                <div className="mt-3 flex flex-wrap gap-2">
                  <span className="rounded-full bg-[#0a84ff] px-3 py-1.5 text-[12.5px] font-medium text-white">I signed in, finish it</span>
                  <span className="rounded-full bg-white/[.08] px-3 py-1.5 text-[12.5px] font-medium">Skip this job</span>
                </div>
                <div className="mt-3 rounded-full bg-white/[.06] px-3.5 py-2 text-[12.5px] text-white/40">Message your twin about this one…</div>
              </div>
              <div className="mt-6 px-1 text-[12px] font-semibold uppercase tracking-[0.05em] text-white/45">Submitted today</div>
              <div className="mt-2 overflow-hidden rounded-[14px]" style={{ background: '#2c2c2e' }}>
                <AnimatePresence initial={false}>
                  {done.map(([c, d, t]) => (
                    <motion.div layout key={c} initial={{ opacity: 0, y: -12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                      transition={{ duration: 0.6, ease: EASE }} className="flex items-center gap-3 border-b border-white/[.06] px-4 py-2.5 last:border-0">
                      <Avatar name={c} domain={d} size={28} />
                      <div className="min-w-0 flex-1"><div className="truncate text-[14px] font-medium">{t}</div><div className="text-[12.5px] text-white/55">{c}</div></div>
                      <Check className="size-4 text-[#30d158]" />
                    </motion.div>))}
                </AnimatePresence>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function InstallBox() {
  const [win, setWin] = useState(IS_WIN)
  const [ok, setOk] = useState(false)
  const cmd = win ? INSTALL_WIN : INSTALL
  const copy = () => { navigator.clipboard.writeText(cmd); setOk(true); setTimeout(() => setOk(false), 1600) }
  return (
    <div>
      <div className="mb-3 flex w-fit rounded-full bg-[var(--bg-2)] p-[3px] text-[13px]">
        {[[false, 'Mac & Linux'], [true, 'Windows']].map(([w, l]) => (
          <button key={l} onClick={() => setWin(w)} className={'rounded-full px-4 py-1.5 transition ' + (win === w ? 'bg-[var(--bg-3)] font-semibold shadow-sm' : 'muted')}>{l}</button>))}
      </div>
      <button onClick={copy} aria-label="Copy the install command"
        className="flex w-full items-center gap-3 rounded-[16px] bg-[var(--bg-2)] py-4 pl-5 pr-4 text-left transition hover:brightness-[.98] sm:py-5 sm:pl-6">
        <span className="mono min-w-0 flex-1 text-[13px] leading-snug sm:text-[17px]"><span className="faint select-none">$ </span>{cmd}</span>
        <span className="flex shrink-0 items-center gap-1.5 text-[14px] font-medium link">
          {ok ? <Check className="size-4" /> : <Copy className="size-4" />}<span className="hidden sm:inline">{ok ? 'Copied' : 'Copy'}</span></span>
      </button>
    </div>
  )
}

/* The GitHub star ask, in the page's own style: a quiet pill with GitHub's mark, the words, and the live count. */
function StarButton({ n, size = 'lg' }) {
  const lg = size === 'lg', sm = size === 'sm'
  return (
    <a href={REPO_URL} target="_blank" rel="noreferrer" aria-label={`Star ApplyTwin on GitHub${n ? `, ${n} stars` : ''}`}
      className={'star group inline-flex items-center rounded-full font-medium ' + (lg ? 'h-11 pl-5 pr-1.5 text-[17px]' : sm ? 'h-9 pl-4 pr-1 text-[14px]' : 'h-8 pl-3 pr-1 text-[13px]')}>
      <GitHubMark size={lg ? 18 : 15} />
      <span className={lg ? 'ml-2.5' : 'ml-2'}>{size === 'nav' ? 'Star' : 'Star on GitHub'}</span>
      <span className={'star-count ml-3 inline-flex items-center gap-1 rounded-full tabular-nums ' + (lg ? 'h-8 px-3 text-[15px]' : 'h-7 px-2.5 text-[12.5px]')}>
        <Star className={(lg ? 'size-4' : 'size-3.5') + ' fill-[#ffcc00] text-[#ffcc00] transition-transform duration-300 group-hover:rotate-[72deg] group-hover:scale-110'} />
        {n == null ? '–' : n.toLocaleString()}
      </span>
    </a>
  )
}
function GitHubMark({ size = 16 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" aria-hidden fill="currentColor">
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
    </svg>
  )
}

function Faq({ q, a }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="border-b border-[var(--line)]">
      <button onClick={() => setOpen(!open)} aria-expanded={open} className="flex w-full items-center justify-between gap-4 py-5 text-left text-[19px] font-medium tracking-[-0.015em]">
        {q}<span aria-hidden className="relative size-3.5 shrink-0">
          <span className="absolute inset-x-0 top-1/2 h-[1.5px] -translate-y-1/2 rounded-full bg-[var(--fg-2)]" />
          <span className="absolute inset-y-0 left-1/2 w-[1.5px] -translate-x-1/2 rounded-full bg-[var(--fg-2)] transition-transform duration-300" style={{ transform: `translateX(-50%) scaleY(${open ? 0 : 1})` }} />
        </span>
      </button>
      <motion.div initial={false} animate={{ height: open ? 'auto' : 0, opacity: open ? 1 : 0 }} transition={{ duration: 0.35, ease: EASE }} className="overflow-hidden">
        <p className="max-w-[600px] pb-6 text-[17px] leading-[1.5] muted">{a}</p>
      </motion.div>
    </div>
  )
}
