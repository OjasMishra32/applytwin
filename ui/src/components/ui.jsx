import { useEffect, useRef, useState } from 'react'
import { motion } from 'motion/react'
import * as RSwitch from '@radix-ui/react-switch'
import * as RSlider from '@radix-ui/react-slider'
import { ChevronRight, UploadCloud } from 'lucide-react'
import { cn } from '../lib/utils'

export const spring = { type: 'spring', stiffness: 420, damping: 34, mass: 0.8 }
export const soft = { type: 'spring', stiffness: 220, damping: 28 }

export function Button({ variant = 'ink', size = 'md', className, children, arrow, loading, ...p }) {
  const v = {
    ink: 'bg-signal text-white hover:bg-[#2b95ff]', signal: 'bg-signal text-white hover:bg-[#2b95ff]', sky: 'bg-signal text-white hover:bg-[#2b95ff]',
    dark: 'bg-white text-[#1d1d1f] hover:bg-white/90',
    white: 'bg-white/[.08] text-ink hover:bg-white/[.13]',
    ghost: 'text-signal-ink hover:bg-signal/[.06]',
    danger: 'text-bad hover:bg-bad/[.06]',
  }[variant]
  const s = { sm: 'h-8 px-3.5 text-[13px] gap-1', md: 'h-10 px-5 text-[14px] gap-1.5', lg: 'h-12 px-6 text-[16px] gap-1.5' }[size]
  return (
    <motion.button whileTap={{ scale: 0.98 }} transition={spring} disabled={loading || p.disabled}
      className={cn('inline-flex shrink-0 items-center justify-center whitespace-nowrap rounded-full font-medium transition-colors duration-150 disabled:cursor-default disabled:opacity-50 cursor-pointer select-none', loading && '[&>svg]:hidden', v, s, className)} {...p}>
      {loading && <span className="size-4 animate-spin rounded-full border-2 border-current/30 border-t-current" />}
      {children}
      {arrow && <ChevronRight className="-mr-1 size-4" />}
    </motion.button>
  )
}
export function Card({ className, children, ...p }) {
  return <div className={cn('card', className)} {...p}>{children}</div>
}

export function Badge({ tone = 'gray', className, children }) {
  const t = { gray: 'bg-white/[.05] text-muted', good: 'bg-good/10 text-good', sky: 'bg-signal/10 text-signal-ink', warn: 'bg-warn/10 text-warn',
    bad: 'bg-bad/10 text-bad', ink: 'bg-ink text-white' }[tone]
  return <span className={cn('inline-flex items-center gap-1 rounded-[6px] px-2 py-[2px] text-[12px] font-medium', t, className)}>{children}</span>
}
export function Field({ label, hint, children, className }) {
  return (
    <label className={cn('block', className)}>
      <div className="label mb-1">{label}</div>
      {children}
      {hint && <div className="mt-1 text-[12px] text-faint">{hint}</div>}
    </label>
  )
}

export function Switch({ checked, onChange }) {
  return (
    <RSwitch.Root checked={checked} onCheckedChange={onChange}
      className="relative h-[26px] w-[44px] shrink-0 cursor-pointer rounded-full bg-white/[.14] transition-colors data-[state=checked]:bg-good">
      <RSwitch.Thumb className="block size-[22px] translate-x-[2px] rounded-full bg-white shadow-[0_3px_8px_rgb(0_0_0/.15),0_0_0_.5px_rgb(0_0_0/.04)] transition-transform duration-200 will-change-transform data-[state=checked]:translate-x-[20px]" />
    </RSwitch.Root>
  )
}

export function Slider({ value, onChange, min = 0, max = 100, step = 5 }) {
  return (
    <RSlider.Root value={[value]} onValueChange={v => onChange(v[0])} min={min} max={max} step={step} className="relative flex h-5 w-full touch-none items-center">
      <RSlider.Track className="relative h-[4px] grow rounded-full bg-white/[.08]"><RSlider.Range className="absolute h-full rounded-full bg-signal" /></RSlider.Track>
      <RSlider.Thumb className="block size-[24px] rounded-full bg-white shadow-[0_3px_8px_rgb(0_0_0/.18),0_0_0_.5px_rgb(0_0_0/.06)] outline-none" />
    </RSlider.Root>
  )
}

/* A macOS segmented control: the selected segment simply lights up (no sliding pill that can lag behind a page that's moving). */
export function Segmented({ options, value, onChange, className }) {
  return (
    <div role="tablist" className={cn('inline-flex shrink-0 rounded-[9px] bg-white/[.06] p-[2px]', className)}>
      {options.map(([v, label, Icon]) => (
        <button key={v} role="tab" aria-selected={value === v} onClick={() => onChange(v)}
          className={cn('flex h-7 items-center gap-1.5 whitespace-nowrap rounded-[7px] px-3 text-[13px] transition-colors duration-100',
            value === v ? 'bg-white/[.16] font-semibold text-ink shadow-[0_1px_3px_rgb(0_0_0/.3)]' : 'font-medium text-ink/70 hover:text-ink')}>
          {Icon && <Icon className="size-3.5" />}{label}
        </button>
      ))}
    </div>
  )
}
export function Ring({ value = 0, size = 64, stroke = 6, label, color, className }) {
  const r = (size - stroke) / 2, c = 2 * Math.PI * r
  const col = color || 'var(--color-signal)'   // one accent: the ring's length says how good, not a traffic-light color
  return (
    <div className={cn('relative grid place-items-center', className)} style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgb(255 255 255 / .08)" strokeWidth={stroke} />
        <motion.circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={col} strokeWidth={stroke} strokeLinecap="round"
          initial={{ strokeDashoffset: c }} animate={{ strokeDashoffset: c * (1 - Math.min(100, value) / 100) }} transition={{ duration: 0.6, ease: [0.2, 0.8, 0.2, 1] }}
          strokeDasharray={c} />
      </svg>
      <div className="absolute inset-0 grid place-items-center text-center font-semibold tabular-nums tracking-[-0.02em]" style={{ fontSize: size * 0.28 }}>
        {label ?? Math.round(value)}
      </div>
    </div>
  )
}
const SUFFIX = /\b(inc|llc|ltd|corp|corporation|co|company|technologies|technology|holdings|group|plc|lp|llp|incorporated|the)\b\.?/gi
const KNOWN = { 'd. e. shaw': 'deshaw.com', 'de shaw': 'deshaw.com', 'hudson river trading': 'hudsonrivertrading.com', 'meta': 'meta.com',
  'google': 'google.com', 'alphabet': 'abc.xyz', 'amazon': 'amazon.com', 'x': 'x.com', 'mayo clinic': 'mayoclinic.org' }
export const guessDomain = name => {
  const n = (name || '').toLowerCase().trim()
  if (KNOWN[n]) return KNOWN[n]
  const base = n.replace(SUFFIX, '').replace(/[^a-z0-9]/g, '')
  return base ? base + '.com' : ''
}

export function Avatar({ name, size = 40, domain, icon }) {
  const [ok, setOk] = useState(true)
  const d = domain || guessDomain(name)
  const src = icon || (d ? `https://www.google.com/s2/favicons?domain=${d}&sz=128` : '')
  const r = Math.round(size * 0.28)
  return (
    <div className="logo relative grid shrink-0 place-items-center overflow-hidden bg-white" style={{ width: size, height: size, borderRadius: r, boxShadow: "0 0 0 .5px rgb(0 0 0 / .1), 0 1px 3px rgb(0 0 0 / .06)" }}>
      {ok && src ? <img src={src} alt="" width={size} height={size} loading="lazy" referrerPolicy="no-referrer"
        onLoad={e => { if (e.currentTarget.naturalWidth <= 16) setOk(false) }} onError={() => setOk(false)}
        style={{ width: size * 0.62, height: size * 0.62, objectFit: 'contain' }} />
        : <span className="font-semibold text-muted" style={{ fontSize: size * 0.4 }}>{(name || '?').trim()[0]?.toUpperCase()}</span>}
    </div>
  )
}

export function Fit({ v }) {
  return <Gauge v={v} />
}
export function Stagger({ children, className, delay = 0.012 }) {
  return (
    <motion.div className={className} initial="h" animate="s" variants={{ s: { transition: { staggerChildren: delay } } }}>
      {children}
    </motion.div>
  )
}
export const item = { h: { opacity: 0 }, s: { opacity: 1, transition: { duration: 0.16, ease: 'easeOut' } } }

/* The title every page opens with (a macOS window title, 28pt bold). No entrance animation: the page itself fades in. */
export function Title({ children, sub, right }) {
  return (
    <div className="mb-8 flex flex-wrap items-end justify-between gap-x-6 gap-y-4">
      <div className="min-w-0">
        <h1 className="text-[28px] font-bold leading-[1.15] tracking-[-0.02em] text-white">{children}</h1>
        {sub && <p className="mt-1.5 max-w-xl text-[15px] leading-snug text-muted">{sub}</p>}
      </div>
      {right && <div className="flex flex-wrap items-center gap-2">{right}</div>}
    </div>
  )
}
export function Drop({ onFile, onText, compact }) {
  const [over, setOver] = useState(false)
  const input = useRef(null)
  const handle = async f => {
    if (!f) return
    const b = await f.arrayBuffer()
    let bin = ''; const u = new Uint8Array(b)
    for (let i = 0; i < u.length; i += 0x8000) bin += String.fromCharCode(...u.subarray(i, i + 0x8000))
    onFile({ name: f.name, data: btoa(bin) })
  }
  return (
    <div onDragOver={e => { e.preventDefault(); setOver(true) }} onDragLeave={() => setOver(false)}
      onDrop={e => { e.preventDefault(); setOver(false); handle(e.dataTransfer.files[0]) }} onClick={() => input.current.click()}
      className={cn('group relative flex cursor-pointer flex-col items-center justify-center rounded-[12px] border border-dashed text-center transition-colors',
        over ? 'border-signal bg-signal/[.06]' : 'border-white/[.16] bg-white/[.025] hover:border-white/30', compact ? 'px-6 py-7' : 'px-8 py-12')}>
      <input ref={input} type="file" accept=".pdf,.txt,.md,.docx" className="hidden" onChange={e => handle(e.target.files[0])} />
      <UploadCloud className="mb-3 size-7 text-muted" strokeWidth={1.6} />
      <div className="text-[15px] font-medium text-fg">Drop your resume here</div>
      <div className="mt-1 text-[13px] text-muted">PDF, Word or plain text</div>
      {onText && !compact && <button onClick={e => { e.stopPropagation(); onText() }} className="mt-4 text-[14px] font-medium text-signal-ink hover:underline">Or paste text instead</button>}
    </div>
  )
}

/* Fades/lifts content in the first time it scrolls into view. */
/* In the app, content is there the moment a page opens (a quick fade, nothing waits on scrolling), like a native app.
   The public site keeps its own scroll reveals. */
export function Reveal({ children, className, delay = 0 }) {
  return (
    <motion.div className={className} initial={{ opacity: 0 }} animate={{ opacity: 1 }}
      transition={{ duration: 0.18, ease: 'easeOut', delay: Math.min(delay, 0.08) }}>{children}</motion.div>
  )
}

/* A list whose hover highlight glides from row to row. rows: [{key, onClick, content}] */
export function GlideList({ rows, className }) {
  // only the rows you see first fade in: a 200-row list used to cascade for 3.6 seconds and animate every row it rendered.
  // The rest are plain rows the browser skips drawing until they scroll into view.
  const cls = 'group relative flex w-full items-center gap-4 px-5 py-3 text-left transition-colors hover:bg-white/[.035]'
  return (
    <div className={cn('relative', className)}>
      {rows.map((r, i) => {
        const inner = <>{i > 0 && <span className="absolute inset-x-5 top-0 h-px bg-white/[.06]" />}
          <span className="relative flex w-full items-center gap-4">{r.content}</span></>
        return i < 14
          ? <motion.button key={r.key} onClick={r.onClick} variants={item} className={cls}>{inner}</motion.button>
          : <button key={r.key} onClick={r.onClick} className={cls + ' [contain-intrinsic-size:auto_62px] [content-visibility:auto]'}>{inner}</button>
      })}
    </div>
  )
}

/* Small fit gauge that sweeps in. */
export function Gauge({ v }) {
  const n = Math.round(v)
  return <span className={cn('w-10 shrink-0 text-right text-[13px] font-medium tabular-nums', n >= 85 ? 'text-white' : 'text-muted')}>{n}%</span>
}
