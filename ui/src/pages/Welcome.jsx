import { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { toast } from 'sonner'
import { ArrowLeft, Check, Sparkles } from 'lucide-react'
import { api } from '../lib/api'
import { useApp } from '../App'
import { Hero3D } from '../components/Hero3D'
import { Sky } from '../components/Sky'
import { GoogleG } from '../components/Shell'
import { Button, Drop, NumberTicker, Segmented, Switch, soft } from '../components/ui'
import { Chips, ROLE_SUGGEST } from './Settings'
import { ProfileQuestions, missing, useQuestions } from '../components/ProfileQuestions'

const DREAM_SUGGEST = ['Google', 'Apple', 'Meta', 'Microsoft', 'Jane Street', 'Citadel', 'Goldman Sachs', 'McKinsey', 'OpenAI', 'Anthropic', 'NVIDIA', 'Stripe']

export default function Welcome() {
  const { profile, refresh, go, setState, auth, signIn } = useApp()
  const [step, setStep] = useState(0)
  const [imp, setImp] = useState(null)
  const [busy, setBusy] = useState(false)
  const [p, setP] = useState(() => structuredClone(profile))
  const [scan, setScan] = useState(null)
  const [queue, setQueue] = useState(null)
  const s = p.search
  const ss = (k, v) => setP({ ...p, search: { ...s, [k]: v } })
  const sa = (k, v) => setP({ ...p, apply: { ...p.apply, [k]: v } })
  const qs = useQuestions()
  const left = missing(qs, p)

  const upload = async body => {
    setBusy(true)
    try {
      const r = await api('/api/import', body); setImp(r)
      if (r.vault) setState(st => ({ ...st, vault: r.vault }))
      const fresh = await api('/api/state'); setP(pp => ({ ...structuredClone(fresh.profile), search: { ...fresh.profile.search, roles: r.suggest_roles?.length ? r.suggest_roles : fresh.profile.search.roles } }))
      setStep(1)
    } catch (e) { toast.error(e.message) }
    setBusy(false)
  }
  const build = async () => {
    await api('/api/profile', p); setStep(4)
    await api('/api/scan', {})
    const tick = async () => {
      const r = await api('/api/scan'); setScan(r.stats || {})
      if (r.running) return setTimeout(tick, 900)
      setQueue(await api('/api/queue?n=5')); await refresh(); setStep(5)
    }
    tick()
  }
  const pages = [
    <div key="0" className="grid items-center gap-10 md:grid-cols-[1.05fr_1fr]">
      <div className="text-white">
        <div className="flex items-center gap-3 text-[17px] font-medium text-white/80">Hi, I'm your twin.<span className="rounded-full bg-white/10 px-3 py-1 text-[13px] font-semibold text-white ring-1 ring-white/20">Free to use</span></div>
        <h1 className="mt-3 text-[72px] font-bold leading-[0.95] tracking-[-0.045em]">Give me your resume.<br /><span className="text-white/55">I'll get you hired.</span></h1>
        <p className="mt-6 max-w-[460px] text-[19px] leading-[1.45] text-white/80">I'll find every open role in your field, write the ideal resume for each one from everything you've done, and apply for you. You only step in when it matters.</p>
        {!auth?.signed_in && <button onClick={signIn} className="mt-8 flex h-12 items-center gap-3 rounded-full bg-white px-6 text-[16px] font-medium text-[#0b1020] transition hover:bg-white/90">
          <GoogleG className="size-5" />Continue with Google</button>}
        <div className="mt-5 max-w-[460px]">{busy ? <div className="card grid place-items-center py-14 text-ink">
          <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1.1, ease: 'linear' }}><Sparkles className="size-8 text-signal" /></motion.div>
          <div className="mt-3 text-[14px] text-muted">Reading your resume like a recruiter…</div></div>
          : <div><div className="rounded-[20px] bg-[#111526] ring-1 ring-white/10"><Drop onFile={f => upload({ name: f.name, data: f.data })} onText={() => { const t = prompt('Paste your resume or LinkedIn text'); if (t) upload({ text: t }) }} /></div></div>}</div>
        <button onClick={() => setStep(1)} className="mt-4 text-[14px] text-white/75 hover:text-white">Skip, I'll add it later</button>
      </div>
      <Hero3D name={profile.name || 'You'} />
    </div>,

    <div key="1" className="mx-auto max-w-[720px]">
      <div className="card p-8 md:p-10">
        <div className="text-[15px] font-semibold text-signal">Step 1 of 3 · What you want</div>
        <h2 className="mt-2 text-[40px] font-bold leading-[1.05] tracking-[-0.035em] text-ink">{imp?.name ? `Nice to meet you, ${imp.name.split(' ')[0]}.` : 'What are you going for?'}</h2>
        {imp && <p className="mt-2 text-[14px] text-muted">{imp.message}</p>}
        <div className="mt-8 space-y-7">
          <Q n="1" t="What kind of role?"><Segmented id="k" value={s.kind} onChange={v => ss('kind', v)} options={[['internship', 'Internship'], ['new-grad', 'New grad'], ['full-time', 'Full-time']]} />
            <input className="uline left mt-3 max-w-[220px]" value={s.season} onChange={e => ss('season', e.target.value)} placeholder="Summer 2027" /></Q>
          <Q n="2" t="Which roles?" sub="I suggested these from your resume."><Chips value={s.roles} onChange={v => ss('roles', v)} placeholder="Add a role" suggestions={ROLE_SUGGEST} /></Q>
          <Q n="3" t="Dream companies?" sub="I'll apply here first, the moment they post."><Chips value={s.companies_priority} onChange={v => ss('companies_priority', v)} placeholder="Type a company and press Enter" suggestions={DREAM_SUGGEST} /></Q>
          <Q n="4" t="Where?"><Chips value={s.locations} onChange={v => ss('locations', v)} placeholder="United States, Remote, a city…" suggestions={['United States', 'Remote', 'New York', 'San Francisco', 'Seattle', 'Boston', 'Chicago', 'Austin']} /></Q>
        </div>
        <div className="mt-9 flex items-center justify-between"><Button variant="ghost" onClick={() => setStep(0)}><ArrowLeft className="size-4" />Back</Button>
          <Button size="lg" onClick={async () => { await api('/api/profile', p); setStep(2) }} arrow disabled={!s.roles?.length}>Next</Button></div>
      </div>
    </div>,

    <div key="answers" className="mx-auto max-w-[760px]">
      <div className="card p-8 md:p-10">
        <div className="text-[15px] font-semibold text-signal">Step 2 of 3 · Your application answers</div>
        <h2 className="mt-2 text-[34px] font-bold leading-[1.08] tracking-[-0.035em] text-ink">Answer these once. Your twin uses them on every form.</h2>
        <p className="mt-2 text-[14px] text-muted">{imp?.filled?.length ? `${imp.filled.length} filled in from your resume; check them.` : 'Nothing is guessed.'} Answer the rest (you can decline the self-identification questions). You can change any of it later in Settings.</p>
        <div className="mt-7"><ProfileQuestions qs={qs} p={p} setP={setP} showMissing filled={imp?.filled || []} /></div>
        <div className="mt-9 flex flex-wrap items-center justify-between gap-3">
          <Button variant="ghost" onClick={() => setStep(1)}><ArrowLeft className="size-4" />Back</Button>
          <div className="flex items-center gap-3">
            {left.length > 0 && <span className="text-[13px] text-[#ff9f0a]">{left.length} left to answer</span>}
            <Button size="lg" onClick={async () => { await api('/api/profile', p); setStep(3) }} arrow disabled={!qs || left.length > 0}>Next</Button>
          </div>
        </div>
      </div>
    </div>,

    <div key="permissions" className="mx-auto max-w-[720px]">
      <div className="card p-8 md:p-10">
        <div className="text-[15px] font-semibold text-signal">Step 3 of 3 · How your twin applies</div>
        <h2 className="mt-2 text-[34px] font-bold leading-[1.08] tracking-[-0.035em] text-ink">Set it once, then let it run.</h2>
        <p className="mt-2 text-[14px] text-muted">Your twin follows these on every run, without checking with you. It never types passwords, solves CAPTCHAs or creates accounts; those come to you as a notification.</p>
        <div className="mt-7 divide-y divide-line overflow-hidden rounded-[16px] bg-white/[.035] ring-1 ring-white/[.06]">
          <Tog l="Submit applications on its own" hint="On: it applies start to finish. Off: it fills every form and stops so you press Submit." v={p.apply.auto_submit} f={v => sa('auto_submit', v)} />
          <Tog l="Read verification codes from my email" hint="When a site emails a code, your agent finds it in your inbox and enters it. Off: you get a notification." v={p.apply.email_codes === 'agent'} f={v => sa('email_codes', v ? 'agent' : 'notify')} />
          <Tog l="Desktop notifications" hint="Ping me when something needs me." v={p.apply.notify_desktop !== false} f={v => { sa('notify_desktop', v); if (v && typeof Notification !== 'undefined' && Notification.permission === 'default') Notification.requestPermission() }} />
          <div className="flex items-center justify-between gap-4 px-4 py-3"><div className="text-[14px] text-fg">Applications per day, at most</div>
            <select value={p.apply.daily_limit} onChange={e => sa('daily_limit', +e.target.value)} className="h-9 rounded-[10px] bg-white/[.06] px-3 text-[14px] text-white">
              {[10, 20, 40, 60, 100, 150].map(x => <option key={x} value={x} className="text-black">{x}</option>)}</select></div>
          <div className="flex items-center justify-between gap-4 px-4 py-3"><div><div className="text-[14px] text-fg">Per company, at most</div><div className="text-[12px] text-muted">Many companies flag repeat applicants.</div></div>
            <select value={p.apply.per_company_cap} onChange={e => sa('per_company_cap', +e.target.value)} className="h-9 rounded-[10px] bg-white/[.06] px-3 text-[14px] text-white">
              {[1, 2, 3, 5, 10].map(x => <option key={x} value={x} className="text-black">{x}</option>)}</select></div>
          <div className="flex items-center justify-between gap-4 px-4 py-3"><div className="text-[14px] text-fg">Applies with</div>
            <Segmented id="agentpick" value={p.apply.agent || 'claude'} onChange={v => sa('agent', v)} options={[['claude', 'Claude Code'], ['codex', 'Codex']]} /></div>
        </div>
        <div className="mt-9 flex items-center justify-between"><Button variant="ghost" onClick={() => setStep(2)}><ArrowLeft className="size-4" />Back</Button>
          <Button size="lg" onClick={build} arrow>Build my queue</Button></div>
      </div>
    </div>,

    <div key="scan" className="mx-auto max-w-[680px] text-center text-white">
      <div className="text-[17px] font-medium text-white/80">Hold tight.</div>
      <h2 className="mt-3 text-[60px] font-bold leading-[1] tracking-[-0.045em]">Reading every job board<br /><span className="text-white/55">for you.</span></h2>
      <div className="card mt-10 p-8 text-ink">
        <div className="text-[88px] font-semibold leading-none tracking-[-0.05em] tabular-nums">{(scan?.fetched || 0).toLocaleString()}</div>
        <div className="mt-1 text-[14px] text-muted">postings read from {scan?.done || 0} of {scan?.sources || '…'} sources</div>
        <div className="mt-6 h-1.5 overflow-hidden rounded-full bg-white/[.06]"><motion.div className="h-full rounded-full bg-signal"
          animate={{ width: `${scan?.sources ? Math.max(4, 100 * scan.done / scan.sources) : 4}%` }} transition={soft} /></div>
        <div className="mt-4 text-[14px] text-muted"><b className="text-ink">{(scan?.matched || 0).toLocaleString()}</b> strong matches so far</div>
      </div>
    </div>,

    <div key="done" className="mx-auto max-w-[680px] text-center">
      <motion.div initial={{ scale: .4, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ type: 'spring', stiffness: 260, damping: 14 }}
        className="mx-auto grid size-20 place-items-center rounded-full bg-good text-white"><Check className="size-10" strokeWidth={3} /></motion.div>
      <h2 className="mt-7 text-[68px] font-bold leading-[0.95] tracking-[-0.045em] text-white"><NumberTicker value={queue?.total || 0} /> roles queued.</h2>
      <p className="mt-4 text-[18px] text-white/80">{queue?.dream ? `${queue.dream} at your dream companies, first in line. ` : ''}Every one gets its own tailored resume.</p>
      <div className="mt-8 flex justify-center gap-3"><Button size="lg" variant="dark" className="bg-white text-[#0b1020] hover:bg-white/90" onClick={() => go('agents')} arrow>Start applying</Button><Button size="lg" variant="glass" onClick={() => go('home')}>Look around</Button></div>
    </div>,
  ]
  return (
    <div className="relative min-h-screen">
      <Sky height={step >= 1 && step <= 3 ? 460 : 980} />
      <div className="relative mx-auto max-w-[1240px] px-6 pb-24 pt-28">
        <AnimatePresence mode="wait"><motion.div key={step} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -12 }} transition={{ duration: .35, ease: [0.2, 0.8, 0.2, 1] }}>{pages[step]}</motion.div></AnimatePresence>
      </div>
    </div>
  )
}
const Q = ({ n, t, sub, children }) => (
  <div className="grid gap-3 md:grid-cols-[180px_1fr]"><div><div className="text-[13px] tabular-nums text-faint">{n}.</div><div className="text-[16px] font-semibold text-ink">{t}</div>
    {sub && <div className="text-[12.5px] text-muted">{sub}</div>}</div><div>{children}</div></div>)
const Tog = ({ l, hint, v, f }) => (
  <div className="flex items-center justify-between gap-4 px-4 py-3"><div><div className="text-[14px] text-fg">{l}</div>{hint && <div className="text-[12px] text-muted">{hint}</div>}</div><Switch checked={!!v} onChange={f} /></div>)
