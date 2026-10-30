import { Suspense, lazy, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { motion, useInView, useMotionValueEvent, useReducedMotion, useScroll } from 'motion/react'
import { Check } from 'lucide-react'
import { Avatar } from '../components/ui'
import { paperCanvas } from './paper'

/* How it works, as four scenes. Each one is driven by the scroll: as a step passes through the screen, its picture
   plays out the mechanism (a search narrowing to three, one page turning into three versions, a form filling itself,
   a phone getting the one question only you can answer). Nothing is pinned, so the page stays short. */

const EASE = [0.25, 0.1, 0.25, 1]
const clamp = v => Math.min(1, Math.max(0, v))
const range = (p, a, b) => clamp((p - a) / (b - a))
const smooth = t => t * t * (3 - 2 * t)
const Flip3D = lazy(() => import('./Flip3D'))
const webgl = () => { try { const c = document.createElement('canvas'); return !!(c.getContext('webgl2') || c.getContext('webgl')) } catch { return false } }

export function Logo({ size = 20 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden>
      <rect x="4" y="4" width="38" height="38" rx="12" fill="#0071e3" /><rect x="22" y="22" width="38" height="38" rx="12" fill="#5ac8fa" fillOpacity=".9" />
    </svg>
  )
}

/* Scales a fixed-size drawing to the width it is given, so every scene is laid out once and stays crisp everywhere. */
function Stage({ w, h, max = 1.45, children }) {
  const ref = useRef(null)
  const [cw, setCw] = useState(w)
  useLayoutEffect(() => {
    const el = ref.current; if (!el) return
    const ro = new ResizeObserver(([e]) => setCw(e.contentRect.width))
    ro.observe(el); return () => ro.disconnect()
  }, [])
  const k = Math.min(max, cw / w)
  return (
    <div ref={ref} className="relative w-full" style={{ height: h * k }}>
      <div className="absolute top-0" style={{ width: w, height: h, left: (cw - w * k) / 2, transform: `scale(${k})`, transformOrigin: 'top left' }}>{children}</div>
    </div>
  )
}

function Step({ n, title, text, flip, children }) {
  const ref = useRef(null)
  const still = useReducedMotion()
  const { scrollYProgress } = useScroll({ target: ref, offset: ['start 0.95', 'end 0.25'] })
  const [p, setP] = useState(0)
  useMotionValueEvent(scrollYProgress, 'change', setP)
  const v = still ? 1 : p
  return (
    <div ref={ref} className={'step grid items-center gap-10 py-14 sm:py-20 md:gap-16 ' + (flip ? 'md:grid-cols-[minmax(0,7fr)_minmax(0,5fr)]' : 'md:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]')}>
      <motion.div className={flip ? 'md:order-last' : ''} initial={{ opacity: 0, y: 24 }} whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: '-60px' }} transition={{ duration: 0.9, ease: EASE }}>
        <div className="mono text-[13px] font-medium" style={{ color: 'var(--blue-text)' }}>{n}</div>
        <h3 className="display-l mt-2 text-[clamp(32px,3.8vw,52px)] [text-wrap:balance]">{title}</h3>
        <p className="mt-4 max-w-[440px] text-[19px] leading-[1.45] muted">{text}</p>
      </motion.div>
      <div>{children(v)}</div>
    </div>
  )
}

export function HowItWorks() {
  return (
    <div className="mt-6 sm:mt-10">
      <Step n="01" title="Finds the roles." text="It checks more than 600 company career sites and the student-run internship lists, and keeps only what fits your field, your cycle and your cities.">
        {p => <Sift p={p} />}
      </Step>
      <Step flip n="02" title="A new resume for every job." text="Your strongest experience, reordered and rewritten in each posting's language, fitted to one clean page. Your numbers, titles and employers never change.">
        {p => <Turn p={p} />}
      </Step>
      <Step n="03" title="Fills the whole form." text="Work authorization, graduation date, address, even the short essays. You answer once during setup. It answers everywhere after that.">
        {p => <Fill p={p} />}
      </Step>
      <Step flip n="04" title="Asks only when it has to." text="A sign-in, an emailed code, a question only you can answer. It pings you, moves on to the next job, and comes back when you're done.">
        {p => <Ping p={p} />}
      </Step>
    </div>
  )
}

/* 01. New postings rise through a frosted filter. The ones that don't fit dim and fall away under it; the ones that do
   turn green, pass through, and settle into your queue above. One list, a handful of rows, nothing repeated. */
const STREAM = [   // [company, domain, role, city, fits]
  ['Netflix', 'netflix.com', 'Content Strategy Intern', 'Los Gatos'], ['Salesforce', 'salesforce.com', 'Sales Operations Intern', 'Chicago'],
  ['Databricks', 'databricks.com', 'Software Engineer Intern', 'Seattle'], ['Adobe', 'adobe.com', 'Marketing Intern', 'San Jose'],
  ['Uber', 'uber.com', 'Senior Software Engineer', 'San Francisco'],
  ['Two Sigma', 'twosigma.com', 'Quantitative Research Intern', 'New York', true],
  ['Coinbase', 'coinbase.com', 'Product Design Intern', 'Remote'], ['Airbnb', 'airbnb.com', 'Finance Intern', 'San Francisco'],
  ['Microsoft', 'microsoft.com', 'Program Manager, Full-time', 'Redmond'], ['Robinhood', 'robinhood.com', 'Legal Intern', 'Menlo Park'],
  ['Anduril', 'anduril.com', 'Autonomy Engineer Intern', 'Costa Mesa', true],
  ['Snowflake', 'snowflake.com', 'Recruiting Coordinator', 'Bozeman'], ['Notion', 'notion.so', 'Community Intern', 'New York'],
  ['Ramp', 'ramp.com', 'Account Executive', 'Miami'], ['Figma', 'figma.com', 'Brand Design Intern', 'London'],
  ['Meta', 'meta.com', 'Data Center Technician', 'Prineville'], ['Tesla', 'tesla.com', 'Service Advisor', 'Austin'],
  ['Amazon', 'amazon.com', 'Area Manager Intern', 'Nashville'], ['Palantir', 'palantir.com', 'Business Development Intern', 'Washington'],
  ['Apple', 'apple.com', 'Retail Specialist', 'Gainesville']]
const FIRST = ['Stripe', 'stripe.com', 'Software Engineer Intern', 'San Francisco']
const RH = 58, GAP = 10, BAND = 300, BAND_H = 64, START = BAND + BAND_H + 18, TRAVEL = 980
function Sift({ p }) {
  const t = range(p, 0.1, 0.82)
  const off = t * TRAVEL
  const yOf = i => START + i * (RH + GAP) - off                      // a row's top inside the stage
  const through = i => smooth(range(BAND + BAND_H / 2 - yOf(i), 0, 70))   // 0 below the band's middle, 1 once it has passed
  const checked = Math.round(380 + 860 * t)
  const fits = STREAM.map((r, i) => [r, i]).filter(([r]) => r[4])
  const queue = [[FIRST, 1], ...fits.map(([r, i]) => [r, through(i)])]
  const inQueue = queue.filter(([, k]) => k > 0.5).length
  const fade = 'linear-gradient(to bottom, #000 0%, #000 70%, transparent 100%)'
  const row = ([c, d, role, city], extra) => (
    <><Avatar name={c} domain={d} size={34} />
      <div className="min-w-0 flex-1"><div className="truncate text-[15px] font-semibold">{role}</div><div className="truncate text-[13px] muted">{c} · {city}</div></div>{extra}</>)
  const check = <span className="grid size-6 shrink-0 place-items-center rounded-full" style={{ background: 'var(--green)' }}><Check className="size-3.5 text-white" strokeWidth={3} /></span>
  return (
    <Stage w={560} h={600}>
      {/* your queue */}
      <div className="absolute inset-x-0 top-0">
        <div className="flex items-baseline justify-between px-1">
          <div className="text-[13px] font-semibold uppercase tracking-[0.06em] faint">Your queue</div>
          <div className="text-[13px] tabular-nums muted">{inQueue} of {checked.toLocaleString()}</div>
        </div>
        <div className="mt-3 space-y-2.5">
          {queue.map(([r, k]) => (
            <div key={r[0]} className="sheet flex items-center gap-3 rounded-[16px] px-4"
              style={{ height: RH + 4, opacity: k, transform: `translateY(${(1 - k) * 60}px) scale(${0.96 + 0.04 * k})`, visibility: k > 0.01 ? 'visible' : 'hidden' }}>
              {row(r, check)}
            </div>))}
        </div>
      </div>
      {/* incoming postings, rising into the filter */}
      <div className="absolute inset-x-0 overflow-hidden" style={{ top: BAND, bottom: 0, maskImage: fade, WebkitMaskImage: fade }}>
        {STREAM.map((r, i) => {
          const y = yOf(i) - BAND
          if (y > 330 || y < -RH) return null
          const near = smooth(range(START + 40 - yOf(i), 0, 90))   // how close it is to the filter
          const fit = r[4]
          return (
            <div key={r[0]} className="absolute inset-x-[14px] flex items-center gap-3 rounded-[14px] px-4"
              style={{ top: y, height: RH, background: 'var(--bg-3)', boxShadow: fit && near > 0.2 ? '0 0 0 2px var(--green), var(--shadow)' : '0 0 0 1px var(--line)',
                opacity: fit ? 1 : 1 - 0.7 * near, transform: fit ? 'none' : `scale(${1 - 0.04 * near})`, filter: fit ? 'none' : `grayscale(${near})` }}>
              {row(r, fit ? <span style={{ opacity: near }}>{check}</span> : <span className="text-[12px] faint" style={{ opacity: near }}>Doesn't fit</span>)}
            </div>)
        })}
      </div>
      {/* the filter itself */}
      <div className="absolute inset-x-0 flex items-center justify-between rounded-[18px] px-5 backdrop-blur-2xl"
        style={{ top: BAND, height: BAND_H, background: 'color-mix(in srgb, color-mix(in srgb, var(--blue) 9%, var(--bg-2)) 78%, transparent)', boxShadow: '0 0 0 1px color-mix(in srgb, var(--blue) 35%, transparent), 0 12px 32px rgb(0 0 0 / .08)' }}>
        <div className="flex items-center gap-3">
          <span className="relative grid size-8 place-items-center rounded-full" style={{ background: 'var(--blue)' }}>
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="#fff" strokeWidth="1.8" strokeLinecap="round"><path d="M2 4h12M4.5 8h7M7 12h2" /></svg>
          </span>
          <div><div className="text-[15px] font-semibold">Your field, cycle and cities</div><div className="text-[12.5px] muted">Software · Summer 2027 · NYC, SF, LA</div></div>
        </div>
        <div className="text-right"><div className="display-l text-[24px] tabular-nums leading-none">{checked.toLocaleString()}</div><div className="mt-0.5 text-[12px] muted">postings checked</div></div>
      </div>
    </Stage>
  )
}

/* 02. One sheet, turned over as you scroll; each side is the same record rewritten for the next company. */
const VERS = [['Google', 98, 'google.com', 'Large-scale systems'], ['NVIDIA', 95, 'nvidia.com', 'Autonomy and AI compute'], ['Jane Street', 96, 'janestreet.com', 'Markets and economics']]
const VERSIONS = VERS.map(([c, f]) => [c, f])
function Turn({ p }) {
  const ref = useRef(null)
  const [ok] = useState(() => typeof window !== 'undefined' && webgl())
  const near = useInView(ref, { margin: '400px 0px', once: true })
  const stage = useRef(0)
  const s = smooth(range(p, 0.3, 0.46)) + smooth(range(p, 0.56, 0.72))
  stage.current = s
  const cur = Math.round(s)
  const still = useMemo(() => (ok ? null : typeof document !== 'undefined' ? paperCanvas('Google', 98).toDataURL('image/png') : null), [ok])
  return (
    <div ref={ref} className="relative grid grid-cols-1 items-center gap-2 sm:h-[600px] sm:grid-cols-[200px_minmax(0,1fr)] min-[1800px]:h-[740px]">
      <div className="relative z-10">
        <div className="mb-3 px-1 text-[12px] font-semibold uppercase tracking-[0.06em] faint">Written for</div>
        <div className="flex gap-1 sm:block sm:space-y-2">
          {VERS.map(([c, f, d, why], i) => (
            <div key={c} className="flex min-w-0 flex-1 items-center gap-2 rounded-[14px] px-2 py-2.5 transition-all duration-500 sm:gap-3 sm:px-3"
              style={{ background: i === cur ? 'var(--bg-3)' : 'transparent', boxShadow: i === cur ? 'var(--shadow)' : 'none', opacity: i === cur ? 1 : 0.45 }}>
              <Avatar name={c} domain={d} size={30} />
              <div className="min-w-0"><div className="truncate text-[13px] font-semibold sm:text-[14px]">{c}</div><div className="hidden truncate text-[12px] muted sm:block">{why}</div></div>
            </div>))}
        </div>
        <div className="mt-5 hidden items-center gap-2 px-1 text-[12px] muted sm:flex"><span className="inline-block h-3 w-5 shrink-0 rounded-[3px]" style={{ background: 'rgb(0 113 227 / .2)' }} />Rewritten for this job</div>
      </div>
      <div className="relative h-[440px] sm:h-full">
        <div className="absolute bottom-[1%] left-1/2 h-[30px] w-[70%] -translate-x-1/2 rounded-[50%] blur-[18px]" style={{ background: 'rgb(0 0 0 / .18)' }} />
        {ok ? (near && <Suspense fallback={null}><Flip3D stage={stage} versions={VERSIONS} /></Suspense>)
          : still && <img src={still} alt="" className="sheet absolute left-1/2 top-1/2 w-[80%] -translate-x-1/2 -translate-y-1/2 rounded-[6px]" />}
      </div>
    </div>
  )
}

/* 03. The application, in its browser window: it turns toward you and straightens while the answers type themselves in. */
const FIELDS = [['Are you authorized to work in the US?', 'Yes'], ['Expected graduation', 'May 2028'], ['Street address', '1 University Ave, Gainesville, FL'],
  ['What interests you about NVIDIA?', 'Your GPU kernels team ships the code I profile every day…']]
const TOTAL = FIELDS.reduce((n, [, a]) => n + a.length, 0)
function Fill({ p }) {
  const turn = smooth(range(p, 0.05, 0.42))
  const shown = Math.round(TOTAL * range(p, 0.3, 0.7))
  const done = shown >= TOTAL
  let before = 0, active = FIELDS.length
  const rows = FIELDS.map(([q, a], i) => {
    const start = before; before += a.length
    const n = Math.max(0, Math.min(a.length, shown - start))
    if (n < a.length && active === FIELDS.length) active = i
    return [q, a, n]
  })
  const cursorY = done ? 438 : 130 + active * 76
  const cursorX = done ? 470 : 380
  return (
    <Stage w={600} h={540}>
      <div className="absolute inset-0" style={{ perspective: 1400 }}>
        <div className="absolute inset-x-[10px] top-[10px] overflow-hidden rounded-[14px] appwin"
          style={{ background: 'var(--bg-3)', transform: `rotateY(${(1 - turn) * -28}deg) rotateX(${(1 - turn) * 10}deg) scale(${0.88 + 0.12 * turn})`, transformOrigin: '60% 50%' }}>
          <div className="flex h-10 items-center gap-2 border-b border-[var(--line)] px-3.5" style={{ background: 'var(--bg-2)' }}>
            {['#ff5f57', '#febc2e', '#28c840'].map(c => <span key={c} className="size-3 rounded-full" style={{ background: c }} />)}
            <div className="mx-auto flex h-6 w-[300px] items-center justify-center rounded-[7px] text-[12px] muted" style={{ background: 'var(--bg-3)' }}>nvidia.wd5.myworkdayjobs.com</div>
          </div>
          <div className="flex items-center gap-3 border-b border-[var(--line)] px-6 py-3.5">
            <Avatar name="NVIDIA" domain="nvidia.com" size={28} />
            <div className="min-w-0 flex-1"><div className="truncate text-[15px] font-semibold">Deep Learning Software Intern</div><div className="text-[12.5px] muted">NVIDIA · Application</div></div>
            <span className="text-[12.5px] font-semibold" style={{ color: done ? 'var(--green)' : 'var(--blue-text)' }}>{done ? 'All filled' : shown ? 'Filling…' : 'Ready'}</span>
          </div>
          <div className="space-y-3.5 px-6 py-5">
            {rows.map(([q, a, n], i) => (
              <div key={q}>
                <div className="text-[12.5px] muted">{q}</div>
                <div className={'mt-1.5 flex h-[40px] items-center rounded-[10px] border px-3 text-[14px] transition-colors duration-300 ' + (i === active && !done ? 'border-[var(--blue)] shadow-[0_0_0_3px_rgb(0_113_227/.15)]' : 'border-[var(--line)]')}>
                  <span className="truncate">{a.slice(0, n)}</span>{i === active && n > 0 && <span className="ml-px h-[17px] w-[1.5px] animate-pulse bg-[var(--blue)]" />}
                </div>
              </div>))}
          </div>
          <div className="flex justify-end border-t border-[var(--line)] px-6 py-3.5">
            <span className={'rounded-full px-4 py-1.5 text-[13px] font-medium transition-colors duration-500 ' + (done ? 'bg-[var(--blue)] text-white' : 'bg-[var(--bg-2)] faint')}>Review and submit</span>
          </div>
          {/* the pointer, moving field to field */}
          <motion.svg width="20" height="24" viewBox="0 0 20 24" className="pointer-events-none absolute left-0 top-0" style={{ filter: 'drop-shadow(0 2px 3px rgb(0 0 0 / .3))' }}
            animate={{ x: cursorX, y: cursorY, opacity: turn > 0.6 ? 1 : 0 }} transition={{ duration: 0.6, ease: EASE }}>
            <path d="M2 1.5v18.5l5-4.6 3.2 7 3-1.4-3.1-6.8H17L2 1.5z" fill="#fff" stroke="#000" strokeWidth="1.2" strokeLinejoin="round" />
          </motion.svg>
        </div>
      </div>
    </Stage>
  )
}

/* 04. Behind, the next application keeps filling on your Mac. In front, your phone gets the one thing only you can do. */
function Ping({ p }) {
  const turn = smooth(range(p, 0.05, 0.45))
  const n1 = smooth(range(p, 0.32, 0.44)), n2 = smooth(range(p, 0.58, 0.7))
  const fill = 0.12 + 0.84 * range(p, 0.3, 0.75)
  return (
    <Stage w={600} h={560}>
      <div className="absolute inset-0" style={{ perspective: 1600 }}>
        {/* the Mac, still working */}
        <div className="absolute left-0 top-[70px] w-[400px] overflow-hidden rounded-[12px] appwin"
          style={{ background: '#1c1c1e', color: '#f5f5f7', transform: `rotateY(${14 + (1 - turn) * 10}deg)`, transformOrigin: '0% 50%' }}>
          <div className="flex h-8 items-center gap-1.5 border-b border-white/[.07] px-3">
            {['#ff5f57', '#febc2e', '#28c840'].map(c => <span key={c} className="size-2.5 rounded-full" style={{ background: c }} />)}
            <span className="mx-auto pr-10 text-[11.5px] text-white/50">ApplyTwin</span>
          </div>
          <div className="p-5">
            <div className="text-[11.5px] font-medium text-[#30d158]">Meanwhile, next job · {p > 0.75 ? 3 : 2} of 25</div>
            <div className="mt-1 text-[21px] font-semibold tracking-[-0.02em]">{p > 0.75 ? 'Submitted' : 'Filling the application'}</div>
            <div className="mt-2 flex items-center gap-2 text-[12.5px] text-white/60"><Avatar name="Figma" domain="figma.com" size={18} />Figma · Software Engineer Intern</div>
            <div className="mt-4 h-[4px] overflow-hidden rounded-full bg-white/[.08]"><div className="h-full rounded-full bg-[#0a84ff]" style={{ width: `${fill * 100}%` }} /></div>
            <div className="mt-5 space-y-2.5">
              {[['Work authorization', 0.25], ['Graduation date', 0.45], ['Why Figma?', 0.7]].map(([l, at]) => (
                <div key={l} className="flex items-center gap-2 rounded-[8px] bg-white/[.05] px-3 py-2 text-[12px]">
                  <span className="grid size-4 place-items-center rounded-full transition-colors duration-500" style={{ background: fill > at ? '#30d158' : 'rgb(255 255 255 / .12)' }}>
                    <Check className="size-2.5 text-black" strokeWidth={3.5} style={{ opacity: fill > at ? 1 : 0 }} /></span>
                  <span className={fill > at ? 'text-white/85' : 'text-white/50'}>{l}</span>
                </div>))}
            </div>
          </div>
        </div>
        {/* the phone */}
        <div className="absolute right-[24px] top-0 h-[548px] w-[268px] rounded-[48px] p-[9px]"
          style={{ background: '#1d1d1f', boxShadow: '0 0 0 1.5px #3a3a3c inset, 0 40px 80px rgb(0 0 0 / .28), 0 8px 24px rgb(0 0 0 / .18)',
            transform: `rotateY(${(1 - turn) * -24}deg) rotateX(${(1 - turn) * 6}deg) translateZ(${turn * 30}px)`, transformOrigin: '100% 50%' }}>
          <div className="relative h-full w-full overflow-hidden rounded-[40px] text-white"
            style={{ background: 'radial-gradient(120% 80% at 20% 0%, #3b5bdb 0%, #1b2a6b 45%, #0b1026 100%)' }}>
            <div className="absolute left-1/2 top-[11px] h-[26px] w-[86px] -translate-x-1/2 rounded-full bg-black" />
            <div className="mt-[62px] text-center">
              <div className="text-[14px] font-medium text-white/80">Thursday, October 30</div>
              <div className="text-[76px] font-semibold leading-[1.02] tracking-[-0.03em]">9:41</div>
            </div>
            <div className="absolute inset-x-[10px] top-[230px] space-y-2">
              {[[n1, 'Code needed for Stripe', 'Check your email and type it in the open tab.', 'now'],
                [n2, 'Applied to Figma', 'Software Engineer Intern. 3 of 25 done today.', 'now']].map(([k, h, b, t]) => (
                <div key={h} className="rounded-[20px] px-3.5 py-3 backdrop-blur-xl"
                  style={{ background: 'rgb(255 255 255 / .2)', opacity: k, transform: `translateY(${(1 - k) * -24}px) scale(${0.94 + 0.06 * k})` }}>
                  <div className="flex items-start gap-2.5">
                    <div className="grid size-[34px] shrink-0 place-items-center rounded-[9px] bg-white"><Logo size={24} /></div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between text-[13px]"><span className="font-semibold">{h}</span><span className="text-white/60">{t}</span></div>
                      <div className="text-[13px] leading-snug text-white/85">{b}</div>
                    </div>
                  </div>
                </div>))}
            </div>
            <div className="absolute bottom-[9px] left-1/2 h-[5px] w-[120px] -translate-x-1/2 rounded-full bg-white/80" />
          </div>
        </div>
      </div>
    </Stage>
  )
}
