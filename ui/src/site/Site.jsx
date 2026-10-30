import { useState } from 'react'
import { motion, useScroll, useTransform } from 'motion/react'
import { Check, Copy } from 'lucide-react'
import { Toaster } from 'sonner'
import { Sky } from '../components/Sky'
import { Hero3D } from '../components/Hero3D'
import { LogoWall, Story } from '../components/Story'
import { Reveal, Words, soft, spring } from '../components/ui'

/* apply.twinly.tech: the public home of ApplyTwin. The app itself runs on each person's own computer,
   on the Claude Code or Codex plan they already pay for, so this page's one job is a calm, one-line setup. */

const INSTALL = 'curl -fsSL apply.twinly.tech/install | bash'
const COMPANIES = ['Stripe', 'Figma', 'Pinterest', 'Notion', 'Databricks', 'Anthropic', 'OpenAI', 'Ramp', 'Jane Street', 'Citadel', 'Two Sigma',
  'Roblox', 'MongoDB', 'Palantir', 'Duolingo', 'Airbnb', 'Robinhood', 'Plaid', 'Scale AI', 'Skydio', 'Anduril', 'SpaceX', 'Tesla', 'NVIDIA',
  'Microsoft', 'Google', 'Apple', 'Meta', 'Amazon', 'Netflix', 'Uber', 'Lyft', 'DoorDash', 'Coinbase', 'Snowflake', 'Datadog', 'Cloudflare',
  'Shopify', 'Atlassian', 'Salesforce', 'Adobe', 'Intuit']
const BLUE = '#0a84ff', GREEN = '#30d158'

const FAQ = [
  ['Do I need an API key?', 'No. ApplyTwin runs on the Claude Code or Codex subscription you already have. If you can use either one in a terminal, you can use ApplyTwin.'],
  ['Where does my data live?', 'On your computer, in a folder called ~/.applytwin. Your resume, answers and history never go to a server unless you sign in to back them up.'],
  ['Will it submit applications without me?', 'Only if you turn that on. By default it fills every form and stops on the review screen, so you press submit.'],
  ['What will it never do?', 'Type your passwords, solve CAPTCHAs, create accounts, accept legal agreements, or invent a single fact about you. Those come back to you as a notification.'],
  ['Is it only for software jobs?', 'No. It learns what a strong resume looks like in your field, whether that is nursing, finance, design, research or engineering, and tailors to each posting.'],
  ['What does it cost?', 'Nothing. ApplyTwin is free and open source under the MIT license.'],
]

export default function Site() {
  const { scrollY } = useScroll()
  const heroY = useTransform(scrollY, [0, 600], [0, -110])
  const heroO = useTransform(scrollY, [0, 450], [1, 0])
  const artY = useTransform(scrollY, [0, 600], [0, 80])
  return (
    <div className="min-h-screen overflow-x-clip bg-paper text-fg">
      <Toaster theme="dark" position="bottom-center" />
      <header className="glass fixed inset-x-0 top-0 z-50 border-b border-white/[.06]">
        <div className="mx-auto flex h-14 max-w-[1180px] items-center justify-between px-5">
          <a href="#" className="flex items-center gap-2 text-[15px] font-semibold text-white"><Logo />ApplyTwin</a>
          <nav className="flex items-center gap-5 text-[13.5px] text-white/70">
            <a href="#how" className="hidden hover:text-white sm:block">How it works</a>
            <a href="#faq" className="hidden hover:text-white sm:block">Questions</a>
            <a href="/app" className="hover:text-white">Your account</a>
            <a href="#start" className="rounded-full px-4 py-1.5 font-medium text-white" style={{ background: BLUE }}>Get started</a>
          </nav>
        </div>
      </header>

      <div className="relative">
        <Sky height={920} />
        <div className="relative mx-auto grid max-w-[1180px] items-center gap-6 px-5 pt-32 md:grid-cols-[1.1fr_1fr]">
          <motion.div style={{ y: heroY, opacity: heroO }} className="min-w-0 text-white">
            <motion.span initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={soft}
              className="inline-block rounded-full bg-white/10 px-3 py-1 text-[13px] font-semibold ring-1 ring-white/20">Free and open source</motion.span>
            <h1 className="mt-4 text-[clamp(48px,7vw,80px)] font-bold leading-[0.95] tracking-[-0.045em]">
              <Words text="You apply once." /><br />
              <Words text="Your twin" delay={0.25} className="serif-i text-[#9cc8ff]" /> <Words text="does the rest." delay={0.4} />
            </h1>
            <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.2 }} className="mt-6 max-w-[480px] text-[19px] leading-[1.45] text-white/80">
              Give it your resume once. It finds every open role that fits you, writes the ideal resume for each one, and fills the application,
              all through the Claude Code or Codex plan you already pay for. No API keys.
            </motion.p>
            <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }} className="mt-8 max-w-[520px]"><InstallBox /></motion.div>
            <p className="mt-3 text-[13px] text-white/55">macOS and Linux. Needs Python 3.9+, Node.js, and Claude Code or Codex.</p>
          </motion.div>
          <motion.div style={{ y: artY }} className="hidden md:block"><Hero3D name="Your Name" /></motion.div>
        </div>
      </div>

      <Reveal className="relative mt-6">
        <div className="text-center text-[15px] text-muted">Thousands of open roles, at companies like</div>
        <LogoWall companies={COMPANIES} />
      </Reveal>

      <div id="how"><Story /></div>

      <section className="mx-auto max-w-[1080px] px-5 py-24">
        <Reveal><h2 className="text-center text-[clamp(40px,5.5vw,64px)] font-bold leading-[1] tracking-[-0.045em] text-white">Set up in one line.</h2>
          <p className="mx-auto mt-4 max-w-[560px] text-center text-[18px] text-muted">One command installs ApplyTwin, connects it to your agent and checks everything. Then you drop in your resume.</p></Reveal>
        <Reveal delay={0.1}><Terminal /></Reveal>
      </section>

      <section id="faq" className="mx-auto max-w-[760px] px-5 pb-24">
        <Reveal><h2 className="mb-5 text-[32px] font-bold tracking-[-0.035em] text-white">Questions</h2></Reveal>
        <Reveal delay={0.05}><div className="overflow-hidden rounded-[20px] bg-[#111526] ring-1 ring-white/[.06] [&>*+*]:border-t [&>*+*]:border-white/[.06]">
          {FAQ.map(([q, a]) => <Faq key={q} q={q} a={a} />)}
        </div></Reveal>
      </section>

      <section id="start" className="px-5 pb-20">
        <Reveal className="relative mx-auto max-w-[1180px] overflow-hidden rounded-[32px] border border-white/10 px-6 py-24 text-center">
          <div className="absolute inset-0" style={{ background: 'radial-gradient(60% 80% at 50% 110%, rgb(76 141 255 / .55), transparent 70%), radial-gradient(40% 60% at 20% 0%, rgb(124 92 255 / .25), transparent 70%), #060b22' }} />
          <div className="relative">
            <div className="text-[clamp(64px,11vw,160px)] font-bold leading-[0.85] tracking-[-0.06em] text-white">Get <span className="serif-i text-[#9cc8ff]">hired.</span></div>
            <p className="mx-auto mt-6 max-w-[520px] text-[18px] text-muted">Paste this into your terminal. Your twin starts on its first applications in a few minutes.</p>
            <div className="mx-auto mt-10 min-w-0 max-w-[560px] text-left"><InstallBox /></div>
            <p className="mt-4 text-[14px] text-white/60">100% free. Open source. Your data stays on your computer.</p>
          </div>
        </Reveal>
      </section>

      <footer className="mx-auto flex max-w-[1180px] flex-wrap items-center justify-between gap-3 border-t border-white/[.06] px-5 py-8 text-[13px] text-faint">
        <span className="flex items-center gap-2"><Logo size={16} />ApplyTwin, from Twinly · MIT license</span>
        <span>Runs on your own Claude Code or Codex.</span>
      </footer>
    </div>
  )
}

function InstallBox() {
  const [ok, setOk] = useState(false)
  const copy = () => { navigator.clipboard.writeText(INSTALL); setOk(true); setTimeout(() => setOk(false), 1600) }
  return (
    <button onClick={copy} className="group flex w-full items-center gap-3 rounded-[16px] bg-black/55 px-4 py-3.5 text-left ring-1 ring-white/15 backdrop-blur transition hover:ring-white/30">
      <span className="select-none font-mono text-[14px] text-white/40">$</span>
      <span className="min-w-0 flex-1 break-words font-mono text-[13px] leading-snug text-white sm:text-[14px]">{INSTALL}</span>
      <span className="flex shrink-0 items-center gap-1.5 rounded-full px-3 py-1 text-[12.5px] font-semibold text-white" style={{ background: ok ? GREEN : BLUE }}>
        {ok ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}{ok ? 'Copied' : 'Copy'}</span>
    </button>
  )
}

const LINES = [
  ['$ ' + INSTALL, 'cmd'],
  ['Downloading ApplyTwin…', 'dim'],
  ['Claude Code: installed plugin applytwin (skills + tools)', 'ok'],
  ['Codex: connected, browser added', 'ok'],
  ['Python 3.12', 'check'], ['Codex signed in · your ChatGPT plan', 'check'], ['Node.js (for the browser)', 'check'],
  ['Resume imported', 'todo'],
  ['Opening ApplyTwin at http://localhost:4747', 'dim'],
]

function Terminal() {
  return (
    <motion.div initial="h" whileInView="s" viewport={{ once: true, margin: '-120px' }} variants={{ s: { transition: { staggerChildren: 0.28 } } }}
      className="mx-auto mt-12 max-w-[760px] overflow-hidden rounded-[18px] bg-[#0b0e1a] ring-1 ring-white/10 shadow-[0_40px_120px_rgb(0_0_0/.55)]">
      <div className="flex items-center gap-2 border-b border-white/[.06] px-4 py-3">
        {['#ff5f57', '#febc2e', '#28c840'].map(c => <span key={c} className="size-3 rounded-full" style={{ background: c }} />)}
        <span className="ml-2 text-[12.5px] text-white/40">Terminal</span>
      </div>
      <div className="space-y-1.5 p-5 font-mono text-[13px] leading-relaxed">
        {LINES.map(([t, k]) => (
          <motion.div key={t} variants={{ h: { opacity: 0, y: 6 }, s: { opacity: 1, y: 0, transition: spring } }} className="flex gap-2">
            {k === 'check' && <span style={{ color: GREEN }}>✓</span>}
            {k === 'ok' && <span style={{ color: BLUE }}>→</span>}
            {k === 'todo' && <span className="text-white/40">·</span>}
            <span className={k === 'cmd' ? 'text-white' : k === 'dim' ? 'text-white/45' : k === 'todo' ? 'text-white/55' : 'text-white/85'}>
              {t}{k === 'todo' && <span className="text-white/35">  → drop your resume in the app</span>}</span>
          </motion.div>))}
      </div>
    </motion.div>
  )
}

function Faq({ q, a }) {
  const [open, setOpen] = useState(false)
  return (
    <div>
      <button onClick={() => setOpen(!open)} className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left text-[16px] font-medium text-white hover:bg-white/[.03]">
        {q}<motion.span animate={{ rotate: open ? 45 : 0 }} transition={spring} className="text-[22px] font-light text-white/50">+</motion.span>
      </button>
      <motion.div initial={false} animate={{ height: open ? 'auto' : 0, opacity: open ? 1 : 0 }} transition={{ type: 'spring', stiffness: 260, damping: 30 }} className="overflow-hidden">
        <p className="px-5 pb-5 text-[15px] leading-relaxed text-muted">{a}</p>
      </motion.div>
    </div>
  )
}

function Logo({ size = 20 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden><defs><linearGradient id="lg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#38bdf8" /><stop offset="1" stopColor="#a78bfa" /></linearGradient></defs>
      <rect x="4" y="4" width="38" height="38" rx="12" fill="url(#lg)" /><rect x="22" y="22" width="38" height="38" rx="12" fill="#fff" fillOpacity=".85" /></svg>
  )
}
