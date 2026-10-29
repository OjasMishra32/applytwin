import { useRef, useState } from 'react'
import { motion, useScroll, useTransform, useSpring, useMotionValueEvent } from 'motion/react'
import { Avatar } from './ui'

/* Keynote-style scroll story, driven entirely by scroll position:
   A  everything you've done pours into one core
   B  the twin rewrites it for one job, letter by letter, as the job's keywords lock in
   C  the page multiplies into tailored copies, each sent to a real company */

const SCRAPS = ['Built a DCF for a $40M acquisition', '320 clinical hours, BLS certified', '1st of 120 at a case competition', 'Shipped an iOS app to 1,000+ users',
  'Led workshops for 80+ students', 'Redesigned a checkout flow in Figma', 'Dean\'s List, every semester', 'Cut API latency 38%',
  'Founded a tutoring nonprofit', 'Research assistant, psych lab']
const REWRITES = [
  ['Worked on the backend for the data team.', 'Built a Go ingestion service on Kafka processing 40K events/sec.'],
  ['Helped make the API faster.', 'Cut p99 API latency 38% (410 to 255 ms) with a Redis read-through cache.'],
  ['Did a hackathon project.', 'Won 1st of 120 teams at HackTX; the app now has 2,300 users.'],
]
const KEYWORDS = ['Go', 'Kafka', 'distributed systems', 'Redis', 'low latency']
const SENT = [['Pinterest', 'pinterest.com'], ['Figma', 'figma.com'], ['Stripe', 'stripe.com'], ['Jane Street', 'janestreet.com'], ['MongoDB', 'mongodb.com'],
  ['Notion', 'notion.so'], ['Roblox', 'roblox.com'], ['Databricks', 'databricks.com'], ['Anthropic', 'anthropic.com']]
const clamp = v => Math.min(1, Math.max(0, v))

export function Story() {
  const ref = useRef(null)
  const { scrollYProgress } = useScroll({ target: ref, offset: ['start start', 'end end'] })
  const p = useSpring(scrollYProgress, { stiffness: 120, damping: 26, mass: 0.35 })
  const [t, setT] = useState(0)
  useMotionValueEvent(p, 'change', v => setT(v))

  const h0 = { opacity: useTransform(p, [0, 0.04, 0.27, 0.31], [0, 1, 1, 0]), scale: useTransform(p, [0, 0.34], [0.92, 1.06]) }
  const h1 = { opacity: useTransform(p, [0.33, 0.37, 0.6, 0.64], [0, 1, 1, 0]), scale: useTransform(p, [0.32, 0.67], [0.92, 1.06]) }
  const h2 = { opacity: useTransform(p, [0.66, 0.71, 1], [0, 1, 1]), scale: useTransform(p, [0.65, 1], [0.94, 1.04]) }
  const coreScale = useTransform(p, [0, 0.28, 0.36], [0.2, 1.15, 0.6])
  const coreOp = useTransform(p, [0, 0.05, 0.3, 0.38], [0, 1, 1, 0])
  const card = { opacity: useTransform(p, [0.3, 0.38, 0.66, 0.74], [0, 1, 1, 0]), scale: useTransform(p, [0.3, 0.38, 0.66, 0.75], [0.6, 1, 1, 0.78]),
    rotateX: useTransform(p, [0.3, 0.4], [30, 0]) }
  const rw = i => clamp((t - 0.4 - i * 0.07) / 0.09)
  const vw = typeof window === 'undefined' ? 1200 : window.innerWidth   // spread scales with the screen, so phones stay in frame
  const rx = Math.min(560, vw * 0.36), ry = Math.min(240, vw * 0.5), fan = Math.min(150, vw / 7)
  const sent = Math.round(clamp((t - 0.7) / 0.28) * 1284)

  return (
    <section ref={ref} className="relative" style={{ height: '420vh' }}>
      <div className="sticky top-0 h-screen overflow-hidden">
        <div className="absolute inset-0" style={{ background: 'radial-gradient(60% 50% at 50% 58%, rgb(40 80 220 / .28), transparent 70%)' }} />
        <div className="absolute inset-x-0 top-[11vh] text-center">
          {[[h0, 'Everything', "you've ever done."], [h1, 'Rewritten', 'for each job.'], [h2, 'Sent.', 'Everywhere.']].map(([st, a, b]) => (
            <motion.h2 key={a} style={st} className="absolute inset-x-0 px-4 text-[clamp(52px,8.5vw,128px)] font-bold leading-[0.92] tracking-[-0.055em] text-white">
              {a} <span className="serif-i text-[#9cc8ff]">{b}</span>
            </motion.h2>))}
        </div>

        <div className="absolute inset-0 top-[32vh]" style={{ perspective: 1500 }}>
          <motion.div style={{ scale: coreScale, opacity: coreOp, x: '-50%', y: '-50%' }} className="absolute left-1/2 top-[34%] size-[180px] rounded-full">
            <div className="absolute inset-0 rounded-full bg-[radial-gradient(circle,#ffffff_0%,#9cc8ff_25%,#4c8dff_50%,transparent_72%)]" />
            <div className="absolute -inset-20 rounded-full bg-[radial-gradient(circle,rgb(76_141_255/.4),transparent_65%)]" />
          </motion.div>
          {SCRAPS.map((s, i) => {
            const a = (i / SCRAPS.length) * Math.PI * 2
            const k = clamp((t - 0.02 - i * 0.012) / 0.24)
            const r = Math.pow(1 - k, 3)
            return (
              <div key={s} className="absolute left-1/2 top-[34%] whitespace-nowrap rounded-full border border-white/15 bg-[#111a3d] px-4 py-2 text-[14px] font-medium text-white shadow-[0_10px_30px_rgb(0_0_0/.45)]"
                style={{ transform: `translate(-50%,-50%) translate(${Math.cos(a) * rx * r}px, ${Math.sin(a) * ry * r}px) scale(${0.25 + 0.75 * r})`,
                  opacity: t < 0.34 ? clamp(k * 5) * clamp(r * 20) : 0 }}>{s}</div>)
          })}

          <motion.div style={{ ...card, x: '-50%', y: '-50%' }} className="absolute left-1/2 top-[34%] w-[min(640px,88vw)] rounded-[16px] bg-white p-8 text-left shadow-[0_40px_100px_rgb(0_0_0/.5)]">
            <div className="flex items-baseline justify-between"><div className="text-[22px] font-semibold tracking-[-0.03em] text-[#0b1020]">Northwind Labs</div>
              <div className="text-[13px] text-[#6b7280]">Software Engineering Intern</div></div>
            <div className="mt-1 h-px bg-black/10" />
            <ul className="mt-4 space-y-3">
              {REWRITES.map(([a, b], i) => {
                const k = rw(i)
                return (
                  <li key={i} className="relative flex gap-2.5 text-[15.5px] leading-snug">
                    <span className="relative mt-[8px] size-1.5 shrink-0 rounded-full transition-colors duration-300" style={{ background: k >= 0.5 ? '#0a84ff' : '#c7cad3' }} />
                    <span className="relative grid flex-1">
                      <span className="col-start-1 row-start-1 text-[#9ca3af]" style={{ opacity: 1 - k, transform: `translateY(${-k * 6}px)` }}>{a}</span>
                      <span className="col-start-1 row-start-1 text-[#0b1020]" style={{ opacity: k, transform: `translateY(${(1 - k) * 6}px)` }}>{b}</span>
                    </span>
                  </li>)
              })}
            </ul>
            <div className="mt-6 flex flex-wrap gap-2">
              {KEYWORDS.map((w, i) => {
                const k = clamp((t - 0.44 - i * 0.035) / 0.08)
                return <span key={w} className="rounded-full px-3 py-1 text-[13px] font-semibold"
                  style={{ transform: `scale(${0.85 + 0.15 * k})`, opacity: k, background: '#0b1020', color: '#fff' }}>{w}</span>
              })}
            </div>
            <div className="mt-5 flex items-center justify-between text-[13px] text-[#6b7280]"><span>Keyword match for this job</span>
              <span className="text-[30px] font-semibold tabular-nums tracking-[-0.04em] text-[#0b1020]">{Math.round(41 + 57 * clamp((t - 0.42) / 0.22))}%</span></div>
          </motion.div>

          {SENT.map(([c, d], i) => {
            const k = clamp((t - 0.69 - i * 0.018) / 0.16)
            const e = 1 - Math.pow(1 - k, 3)
            const spread = i - (SENT.length - 1) / 2
            return (
              <div key={c} className="absolute left-1/2 top-[30%] w-[170px] rounded-[14px] bg-white p-3 shadow-[0_30px_70px_rgb(0_0_0/.55)]"
                style={{ opacity: k > 0 ? clamp(k * 3) : 0,
                  transform: `translate(-50%,-50%) translate(${spread * fan * e}px, ${Math.abs(spread) * 22 * e}px) rotate(${spread * 6 * e}deg) scale(${0.5 + 0.5 * e})` }}>
                <div className="flex items-center gap-2"><Avatar name={c} domain={d} size={26} /><span className="truncate text-[13px] font-semibold text-[#0b1020]">{c}</span></div>
                <div className="mt-2.5 space-y-1.5">{[90, 70, 82].map((w, j) => <div key={j} className="h-[4px] rounded-full bg-[#4c8dff]/35" style={{ width: `${w}%` }} />)}</div>
                <div className="mt-2.5 text-[11px] font-semibold text-[#16a34a]" style={{ opacity: k >= 1 ? 1 : 0 }}>✓ Applied</div>
              </div>)
          })}
          <div className="absolute inset-x-0 top-[62%] text-center" style={{ opacity: clamp((t - 0.74) * 8) }}>
            <div className="text-[clamp(48px,6vw,88px)] font-bold tabular-nums tracking-[-0.05em] text-white">{sent.toLocaleString()}</div>
            <div className="text-[16px] text-muted">applications sent, each with its own resume</div>
          </div>
        </div>
      </div>
    </section>
  )
}

export function LogoWall({ companies }) {
  const rows = [companies.slice(0, 14), companies.slice(14, 28), companies.slice(28, 42)].filter(r => r.length)
  return (
    <div className="relative h-[300px] overflow-hidden [mask-image:linear-gradient(180deg,transparent,#000_25%,#000_75%,transparent),linear-gradient(90deg,transparent,#000_10%,#000_90%,transparent)] [mask-composite:intersect]"
      style={{ perspective: 900 }}>
      <div className="absolute inset-x-[-10%] top-1/2 -translate-y-1/2 space-y-4" style={{ transform: 'rotateX(48deg) rotateZ(-8deg)', transformStyle: 'preserve-3d' }}>
        {rows.map((r, i) => (
          <div key={i} className="flex w-max gap-4" style={{ animation: `marquee ${50 + i * 12}s linear infinite ${i % 2 ? 'reverse' : ''}` }}>
            {[...r, ...r, ...r].map((c, j) => (
              <div key={j} className="flex items-center gap-3 rounded-[16px] border border-white/10 bg-[#0c1330] px-4 py-3">
                <Avatar name={c} size={34} /><span className="whitespace-nowrap text-[15px] font-medium text-white/90">{c}</span></div>))}
          </div>))}
      </div>
    </div>
  )
}
