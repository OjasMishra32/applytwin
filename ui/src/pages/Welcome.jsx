import { useCallback, useEffect, useMemo, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { toast } from 'sonner'
import { ArrowLeft, Check, Copy, FileText, Loader2 } from 'lucide-react'
import { AgentConnect } from '../components/AgentConnect'
import { ImportWait } from '../components/ImportWait'
import { api } from '../lib/api'
import { useApp } from '../App'
import { Drop, Segmented, Switch } from '../components/ui'
import { Logo } from '../components/Shell'
import { Chips, ROLE_SUGGEST } from './Settings'
import { WhereAbroad } from '../components/Regions'
import { ProfileQuestions, missing, useQuestions } from '../components/ProfileQuestions'

/* Setup, the way Apple does it: one clear question per screen, big choices, a gentle slide between screens, and you
   can't move on until the screen is answered. Everything here is used, unchanged, on every application. */

const DREAM_SUGGEST = ['Google', 'Apple', 'Microsoft', 'Jane Street', 'Citadel', 'Goldman Sachs', 'J.P. Morgan', 'McKinsey', 'Deloitte',
  'OpenAI', 'Anthropic', 'NVIDIA', 'Stripe', 'Mayo Clinic', 'Pfizer', 'Disney']
const KINDS = [['internship', 'Internship', 'A summer (or other term) internship'], ['co-op', 'Co-op', 'A paid term away from classes'],
  ['new-grad', 'New grad', 'Your first full-time role after graduating'], ['full-time', 'Full-time', 'You already have work experience']]
const ARRANGE = [['onsite', 'On-site'], ['hybrid', 'Hybrid'], ['remote', 'Remote']]
const SPRING = { type: 'spring', stiffness: 260, damping: 30 }

export default function Welcome() {
  const { profile, vault, refresh, go, setState } = useApp()
  const [i, setI] = useState(0)
  const [dir, setDir] = useState(1)
  const [p, setP] = useState(() => structuredClone(profile))
  // back in setup after a reload or a closed tab: the resume you already gave counts, no second upload needed
  const [imp, setImp] = useState(() => (vault?.experience?.length || vault?.projects?.length)
    ? { name: vault.basics?.name, counts: Object.fromEntries(['experience', 'research', 'projects', 'leadership', 'skills'].map(k => [k, (vault[k] || []).length])) } : null)
  const [busy, setBusy] = useState(false)
  const [pasted, setPasted] = useState(null)   // window.prompt() flattens line breaks, which the resume reader needs
  const [agents, setAgents] = useState(null)
  const [scan, setScan] = useState(null)
  const [queue, setQueue] = useState(null)
  const empty = !!queue && !queue.total
  const [tick, setTick] = useState(0)
  useEffect(() => { if (!busy) return; const t = setInterval(() => setTick(x => x + 1), 3500); return () => clearInterval(t) }, [busy])
  const READING = ['Reading your resume…', 'Finding your experience…', 'Pulling out projects and research…', 'Spotting your skills…', 'Filling in your answers…', 'Almost done…']
  const qs = useQuestions()
  const s = p.search || {}
  const ss = (k, v) => setP(x => ({ ...x, search: { ...x.search, [k]: v } }))
  const sa = (k, v) => setP(x => ({ ...x, apply: { ...x.apply, [k]: v } }))
  const now = new Date(), year = now.getFullYear() + (now.getMonth() >= 7 ? 1 : 0)   // from August, next summer's cycle
  const picked = (s.season || '').split(',').map(x => x.trim()).filter(Boolean)
  // the list never shifts under you (picking Winter used to move every tile a year on); a saved term outside it still shows, so you can unpick it
  const terms = [...new Set([`Summer ${year}`, `Fall ${year}`, `Winter ${year + 1}`, `Spring ${year + 1}`, `Summer ${year + 1}`, ...picked])]
  const intern = ['internship', 'co-op'].includes(s.kind)
  const groupLeft = g => missing((qs || []).filter(q => q.group === g), p).length
  const loadAgents = useCallback(() => api('/api/agents').then(setAgents).catch(() => setAgents(a => a || {})), [])
  useEffect(() => { loadAgents() }, [loadAgents])

  const save = () => api('/api/profile', p)
  const upload = async body => {
    setBusy(true)
    try {
      const r = await api('/api/import', body); setImp(r); setPasted(null)
      if (r.fallback) toast(r.fallback, { description: 'Check it in Resume Studio; your agent can polish it later.' })
      if (r.vault) setState(st => ({ ...st, vault: r.vault }))
      const fresh = (await api('/api/state')).profile
      setP(x => ({ ...structuredClone(fresh), search: { ...fresh.search, roles: fresh.search.roles?.length ? fresh.search.roles : (r.suggest_roles || []) } }))
    } catch (e) { toast.error(e.message) }
    setBusy(false)
  }
  const build = async () => {
    // never strand someone on this screen: a failed save, scan or poll retries, and after a minute it moves on anyway
    const t0 = Date.now()
    try { await save(); await api('/api/scan', {}) } catch { /* the scan also runs on its own later */ }
    const tick = async () => {
      try {
        const r = await api('/api/scan'); setScan(r.stats || {})
        if (r.running && Date.now() - t0 < 90000) return setTimeout(tick, 900)
      } catch { if (Date.now() - t0 < 90000) return setTimeout(tick, 1500) }
      try { setQueue(await api('/api/queue?n=5')); await refresh() } catch {}
      next()
    }
    tick()
  }

  // every screen: what it asks, whether it's answered, and what Continue does
  const screens = useMemo(() => [
    { id: 'hello', ok: true, cta: 'Get started' },
    { id: 'resume', ok: !!imp && !busy, cta: 'Continue' },
    { id: 'kind', ok: !!s.kind, cta: 'Continue' },
    { id: 'when', ok: intern ? picked.length > 0 : !!p.earliest_start, cta: 'Continue' },
    { id: 'roles', ok: (s.roles || []).length > 0, cta: 'Continue' },
    { id: 'where', ok: ((s.locations || []).length > 0 || (s.countries || []).length > 0) && (s.arrangement || []).length > 0, cta: 'Continue' },
    { id: 'companies', ok: true, cta: 'Continue' },
    { id: 'history', ok: true, cta: 'Continue' },
    { id: 'You', ok: groupLeft('You') === 0, cta: 'Continue' },
    { id: 'School', ok: groupLeft('School') === 0, cta: 'Continue' },
    { id: 'Work authorization', ok: groupLeft('Work authorization') === 0, cta: 'Continue' },
    { id: 'Standard questions', ok: groupLeft('Standard questions') === 0, cta: 'Continue' },
    { id: 'Voluntary self-identification', ok: groupLeft('Voluntary self-identification') === 0, cta: 'Continue' },
    { id: 'apply', ok: true, cta: 'Continue' },
    { id: 'agent', ok: true, cta: 'Find my jobs' },
    { id: 'scan', ok: false, cta: null },
    { id: 'done', ok: true, cta: empty ? 'Adjust my search' : 'Start applying' },
  ], [imp, busy, s, p, qs, empty])
  const cur = screens[i]
  const next = () => { setDir(1); setI(x => Math.min(screens.length - 1, x + 1)) }
  const back = () => { setDir(-1); setI(x => Math.max(0, x - 1)) }
  const [derived, setDerived] = useState([])
  const [hist, setHist] = useState('')
  const START = { summer: 'May', fall: 'August', winter: 'January', spring: 'January' }
  const onContinue = async () => {
    if (cur.id === 'when' && intern && !p.earliest_start && picked.length) {   // you picked the term, so the start date follows from it
      const [term, yr] = picked[0].toLowerCase().split(' ')
      setP(x => ({ ...x, earliest_start: `${START[term] || 'May'} ${yr}` })); setDerived(['earliest_start'])
    }
    if (cur.id === 'agent') { next(); return build() }
    if (cur.id === 'done') { api('/api/profile', { onboarded: true }).catch(() => {}); return go(empty ? 'settings' : 'agents') }   // an empty queue has nothing to start on
    if (i > 1) await save()
    next()
  }

  const body = {
    hello: <Center>
      <div className="flex justify-center"><Logo size={56} /></div>
      <H>Let's set up your twin</H>
      <Sub>About five minutes. You answer everything once. After that it finds jobs, writes a resume for each one and applies on its own.</Sub>
    </Center>,
    resume: <Center wide>
      <H>Start with your resume</H>
      <Sub>It reads everything you've done and fills in every answer it can. You'll check them later.</Sub>
      <div className="mx-auto mt-10 max-w-[560px] text-left">
        {busy ? <div className="card grid place-items-center py-14"><Loader2 className="size-6 animate-spin text-muted" />
          <AnimatePresence mode="wait"><motion.div key={tick} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }}
            className="mt-4 text-[15px] text-white">{READING[Math.min(tick, READING.length - 1)]}</motion.div></AnimatePresence>
          <ImportWait className="mt-1 text-center text-[13px] text-faint" /></div>
          : imp ? <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.2 }}
            className="card p-7 text-center">
            <div className="mx-auto grid size-10 place-items-center rounded-full bg-good text-white"><Check className="size-5" strokeWidth={3} /></div>
            <div className="mt-4 text-[22px] font-semibold tracking-[-0.02em] text-white">{imp.name || 'Got it'}</div>
            <div className="mt-1.5 text-[14px] text-muted">
              {[['experience', 'jobs'], ['research', 'research'], ['projects', 'projects'], ['leadership', 'leadership'], ['skills', 'skill groups']]
                .filter(([k]) => imp.counts?.[k]).map(([k, l]) => `${imp.counts[k]} ${imp.counts[k] === 1 ? l.replace(/s$/, '') : l}`).join(' · ')}
            </div>
            {imp.filled?.length > 0 && <div className="mt-1 text-[14px] text-muted">{imp.filled.length} application answers filled in from it</div>}
            <button onClick={() => setImp(null)} className="mt-5 text-[13px] text-signal-ink hover:underline">Use a different file</button>
          </motion.div>
          : pasted !== null ? <div><textarea autoFocus rows={10} value={pasted} onChange={e => setPasted(e.target.value)} placeholder="Paste your resume, your LinkedIn About + Experience, notes…"
              onKeyDown={e => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey) && pasted.trim()) upload({ text: pasted }) }}
              className="w-full rounded-[12px] bg-white/[.06] p-4 text-[15px] text-white outline-none placeholder:text-faint focus:ring-2 focus:ring-signal" />
            <div className="mt-3 flex justify-end gap-2"><button onClick={() => setPasted(null)} className="h-10 rounded-full px-4 text-[14px] text-white/70 hover:text-white">Back</button>
              <button onClick={() => upload({ text: pasted })} disabled={!pasted.trim()} className="h-10 rounded-full bg-signal px-5 text-[14px] font-semibold text-white disabled:opacity-40">Read it</button></div></div>
          : <Drop onFile={f => upload({ name: f.name, data: f.data })} onText={() => setPasted('')} />}
      </div>
    </Center>,
    kind: <Center>
      <H>What are you applying for?</H>
      <Sub>Pick one. You can change it any time in Settings.</Sub>
      <Tiles items={KINDS.map(([v, l, d]) => ({ v, l, d }))} value={[s.kind]} onPick={v => ss('kind', v)} />
    </Center>,
    when: intern ? <Center>
      <H>Which terms?</H>
      <Sub>Pick every term you'd take. Roles for other terms stay out of your queue.</Sub>
      <Tiles items={terms.map(t => ({ v: t, l: t }))} value={picked} multi
        onPick={v => ss('season', (picked.includes(v) ? picked.filter(x => x !== v) : [...picked, v]).join(', '))} />
    </Center> : <Center>
      <H>When can you start?</H>
      <Sub>A month and year is enough.</Sub>
      <input autoFocus value={p.earliest_start || ''} onChange={e => setP(x => ({ ...x, earliest_start: e.target.value }))} placeholder="June 2027"
        className="mx-auto mt-8 block h-12 w-full max-w-[320px] rounded-[12px] bg-white/[.07] px-5 text-center text-[18px] text-white outline-none focus:ring-2 focus:ring-signal" />
    </Center>,
    roles: <Center wide>
      <H>Which roles?</H>
      <Sub>{imp?.suggest_roles?.length ? 'We picked these from your resume. Add anything, in any field.' : 'Pick some, or type any role in any field.'}</Sub>
      <div className="mx-auto mt-8 max-w-[600px] text-left"><Chips large value={s.roles || []} onChange={v => ss('roles', v)} placeholder="Type a role and press Enter" suggestions={ROLE_SUGGEST} /></div>
    </Center>,
    where: <Center wide>
      <H>Where you'd work</H>
      <Sub>Pick how, then add places.</Sub>
      <Tiles items={ARRANGE.map(([v, l]) => ({ v, l }))} value={s.arrangement || []} multi small
        onPick={v => { const a = s.arrangement || []; const n = a.includes(v) ? a.filter(x => x !== v) : [...a, v]; ss('arrangement', n); setP(x => ({ ...x, search: { ...x.search, arrangement: n }, onsite_ok: n.some(y => y !== 'remote') || x.onsite_ok })) }} />
      <div className="mx-auto mt-6 max-w-[600px] text-left"><Chips large value={s.locations || []} onChange={v => ss('locations', v)} placeholder="United States, a city, Remote…"
        suggestions={['United States', 'Remote', 'New York', 'San Francisco', 'Seattle', 'Boston', 'Chicago', 'Austin', 'Los Angeles', 'Washington, DC']} /></div>
      <div className="mx-auto mt-8 max-w-[600px] text-left"><div className="mb-3 text-[15px] font-medium text-white">Outside the US? <span className="font-normal text-muted">Optional: Europe, India and more.</span></div>
        <WhereAbroad large compact p={p} setP={setP} /></div>
    </Center>,
    companies: <Center wide>
      <H>Dream companies</H>
      <Sub>Optional. Your twin applies to these first, the moment they post.</Sub>
      <div className="mx-auto mt-8 max-w-[600px] space-y-5 text-left">
        <Chips large value={s.companies_priority || []} onChange={v => ss('companies_priority', v)} placeholder="Type a company and press Enter" suggestions={DREAM_SUGGEST} />
        <div><div className="mb-2 text-[13px] text-muted">Never apply to</div><Chips large value={s.companies_skip || []} onChange={v => ss('companies_skip', v)} placeholder="Companies to skip (optional)" /></div>
      </div>
    </Center>,
    history: <Center wide>
      <H>Already applied somewhere?</H>
      <Sub>Your twin skips roles you've already applied to, so it never applies twice. Optional, and you can do it later from Applications.</Sub>
      <div className="mx-auto mt-10 grid max-w-[640px] gap-3 text-left sm:grid-cols-2">
        <button onClick={async () => { try { await api('/api/history/email', {}); setHist('email') } catch (e) { toast.error(e.message) } }}
          className={'rounded-[12px] px-5 py-4 text-left transition-colors ' + (hist === 'email' ? 'bg-[#1c1c1e] ring-2 ring-signal' : 'bg-[#1c1c1e] ring-1 ring-white/[.06] hover:bg-[#232325]')}>
          <div className="text-[16px] font-semibold text-white">Find them in my email</div>
          <div className="mt-1 text-[13.5px] text-muted">{hist === 'email' ? 'Started. Your twin is reading your "thank you for applying" emails.' : 'Your twin reads your "thank you for applying" emails. Any email works.'}</div></button>
        <label className={'cursor-pointer rounded-[12px] px-5 py-4 transition-colors ' + (hist === 'csv' ? 'bg-[#1c1c1e] ring-2 ring-signal' : 'bg-[#1c1c1e] ring-1 ring-white/[.06] hover:bg-[#232325]')}>
          <input type="file" accept=".csv,text/csv" className="hidden" onChange={async e => { const f = e.target.files?.[0]; if (!f) return
            try { const r = await api('/api/history', { text: await f.text() }); setHist('csv'); toast.success(`Found ${r.known_applications} applications`) } catch (err) { toast.error(err.message) } }} />
          <div className="text-[16px] font-semibold text-white">Import my tracker</div>
          <div className="mt-1 text-[13.5px] text-muted">{hist === 'csv' ? 'Imported.' : 'A CSV from Simplify, Huntr, Teal, Notion or a spreadsheet.'}</div></label>
      </div>
    </Center>,
    apply: <Center wide>
      <H>How your twin applies</H>
      <Sub>It follows these on every run. It never types passwords, solves CAPTCHAs or creates accounts. Those come to you.</Sub>
      <div className="card mx-auto mt-8 max-w-[600px] divide-y divide-white/[.06] overflow-hidden text-left">
        <Toggle l="Submit applications on its own" d="Off: it fills every form and stops so you press Submit." v={!!p.apply.auto_submit} f={v => sa('auto_submit', v)} />
        <Toggle l="Read verification codes from my email" d="Off: it notifies you to type the code." v={p.apply.email_codes === 'agent'} f={v => sa('email_codes', v ? 'agent' : 'notify')} />
        <Toggle l="Notify me when it needs me" d="A notification you can click to handle it." v={p.apply.notify_desktop !== false}
          f={v => { sa('notify_desktop', v); if (v && typeof Notification !== 'undefined' && Notification.permission === 'default') Notification.requestPermission() }} />
        <Pick l="Applications per day, at most" v={p.apply.daily_limit} opts={[10, 20, 40, 60, 100, 150]} f={v => sa('daily_limit', v)} />
        <Pick l="Per company, at most" v={p.apply.per_company_cap} opts={[1, 2, 3, 5, 10]} f={v => sa('per_company_cap', v)} />
      </div>
    </Center>,
    agent: <Center wide>
      <H>Which agent should apply?</H>
      <Sub>It runs on the plan you already pay for. No API keys.</Sub>
      <div className="mx-auto mt-8 grid max-w-[600px] gap-3 text-left sm:grid-cols-2">
        {[['claude', 'Claude Code', 'claude', 'then type /login'], ['codex', 'Codex', 'codex login', '']].map(([k, l, cmd, extra]) => {
          const st = agents?.[k], sel = (p.apply.agent || 'claude') === k
          return (
            <button key={k} onClick={() => sa('agent', k)} className={'rounded-[12px] bg-[#1c1c1e] p-5 text-left transition-colors ' + (sel ? 'ring-2 ring-signal' : 'ring-1 ring-white/[.06] hover:bg-[#232325]')}>
              <div className="flex items-center justify-between"><span className="text-[16px] font-semibold text-white">{l}</span>{sel && <Check className="size-5 text-signal" />}</div>
              <div className={'mt-1 text-[13px] ' + (!st ? 'text-muted' : st.signed_in ? 'text-good' : 'text-warn')}>
                {!st ? 'Checking…' : !st.installed ? 'Not installed' : st.signed_in ? 'Signed in, ready' : 'Installed, signed out'}</div>
              <AgentConnect name={k} st={st} onChange={loadAgents} />
            </button>)
        })}
      </div>
      {agents && !Object.values(agents).some(a => a.signed_in) && <p className="mt-4 text-[13px] text-muted">Sign in to one before you press Start. You can finish setup now.</p>}
    </Center>,
    scan: <Center>
      <H>Finding jobs that fit you</H>
      <div className="mt-8 text-[48px] font-semibold leading-none tracking-[-0.03em] text-white tabular-nums">{(scan?.fetched || 0).toLocaleString()}</div>
      <Sub>postings read from {scan?.done || 0} of {scan?.sources || '…'} sources</Sub>
      <div className="mx-auto mt-6 h-1 max-w-[320px] overflow-hidden rounded-full bg-white/[.08]">
        <motion.div className="h-full rounded-full bg-signal" animate={{ width: `${scan?.sources ? Math.max(4, 100 * scan.done / scan.sources) : 4}%` }} transition={SPRING} /></div>
    </Center>,
    done: <Center>
      <motion.div initial={{ scale: .9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ type: 'spring', stiffness: 300, damping: 28 }}
        className="mx-auto grid size-14 place-items-center rounded-full bg-good text-white"><Check className="size-7" strokeWidth={3} /></motion.div>
      {empty ? <><H>No roles in your queue yet</H>
        <Sub>{scan?.done < scan?.sources ? 'Your twin is still reading job boards in the background; matches show up in Jobs as they come in. ' : ''}Widening your roles, terms or places finds more, and new roles arrive as companies post them.</Sub></>
      : <><H>{(queue?.total || 0).toLocaleString()} roles ready</H>
      <Sub>{queue?.dream ? `${queue.dream} at your dream companies, first in line. ` : ''}Every one gets its own resume. Press Start and your twin takes it from here.</Sub></>}
    </Center>,
  }
  const group = qs && ['You', 'School', 'Work authorization', 'Standard questions', 'Voluntary self-identification'].includes(cur.id)
  const groupCopy = { You: ['About you', 'From your resume where we could. Check them.'], School: ['Your school', 'Forms ask these on almost every application.'],
    'Work authorization': ['Work authorization', 'Answered exactly as you say, on every form.'], 'Standard questions': ['A few standard questions', 'The ones most forms ask.'],
    'Voluntary self-identification': ['Voluntary self-identification', 'Optional for employers, so "Decline" is always a fine answer. Nothing is chosen for you.'] }

  return (
    <div className="relative min-h-screen overflow-hidden">
      <div className="fixed inset-x-0 top-0 z-20 h-[2px] bg-white/[.06]">
        <motion.div className="h-full bg-signal" animate={{ width: `${(100 * i) / (screens.length - 1)}%` }} transition={SPRING} /></div>
      <div className="relative mx-auto flex min-h-screen max-w-[820px] flex-col justify-center px-6 pb-36 pt-16">
        {i > 0 && cur.id !== 'scan' && cur.id !== 'done' && <button onClick={back} className="fixed left-4 top-4 z-30 flex h-8 items-center gap-1 rounded-[8px] px-2.5 text-[14px] text-signal-ink transition-colors hover:bg-white/[.06]"><ArrowLeft className="size-4" />Back</button>}
        <AnimatePresence mode="popLayout" custom={dir} initial={false}>
          <motion.div key={cur.id} custom={dir} variants={{ in: d => ({ x: d * 60, opacity: 0 }), at: { x: 0, opacity: 1 }, out: d => ({ x: d * -60, opacity: 0 }) }}
            initial="in" animate="at" exit="out" transition={SPRING}>
            {group ? <Center wide>
              <H>{groupCopy[cur.id][0]}</H><Sub>{groupCopy[cur.id][1]}</Sub>
              <div className="mx-auto mt-8 max-w-[640px] text-left"><ProfileQuestions qs={qs} p={p} setP={setP} groups={[cur.id]} showMissing large filled={[...(imp?.filled || []), ...derived]} /></div>
            </Center> : body[cur.id]}
          </motion.div>
        </AnimatePresence>
      </div>
      {cur.cta && <div className="fixed inset-x-0 bottom-0 z-20 border-t border-white/[.06] bg-paper pb-6 pt-4">
        <div className="mx-auto flex max-w-[760px] flex-col items-center gap-2 px-6">
          <motion.button whileTap={{ scale: .97 }} onClick={onContinue} disabled={!cur.ok}
            className="h-11 w-full max-w-[320px] rounded-full bg-signal text-[15px] font-semibold text-white transition-opacity disabled:opacity-35">{cur.cta}</motion.button>
          {!cur.ok && group && <div className="text-[13px] text-muted">{groupLeft(cur.id)} left to answer</div>}
          {cur.id === 'resume' && !imp && <button onClick={next} className="text-[13px] text-signal-ink hover:underline">I don't have one handy</button>}
          {cur.id === 'companies' && <div className="text-[13px] text-muted">You can skip this one.</div>}
        </div>
      </div>}
    </div>
  )
}

const Center = ({ children, wide }) => <div className={'mx-auto text-center ' + (wide ? 'max-w-[720px]' : 'max-w-[620px]')}>{children}</div>
const H = ({ children }) => <h1 className="mt-6 text-[clamp(28px,4vw,36px)] font-bold leading-[1.15] tracking-[-0.025em] text-white">{children}</h1>
const Sub = ({ children }) => <p className="mx-auto mt-3 max-w-[520px] text-[16px] leading-relaxed text-muted">{children}</p>

function Tiles({ items, value, onPick, multi, small }) {
  return (
    <div className={'mx-auto mt-8 grid gap-3 text-left ' + (small ? 'max-w-[480px] grid-cols-3' : 'max-w-[600px] sm:grid-cols-2')}>
      {items.map(({ v, l, d }) => {
        const on = value.includes(v)
        return (
          <motion.button key={v} whileTap={{ scale: .98 }} onClick={() => onPick(v)}
            className={'relative rounded-[12px] bg-[#1c1c1e] transition-colors ' + (on ? 'ring-2 ring-signal' : 'ring-1 ring-white/[.06] hover:bg-[#232325]') + (small ? ' px-4 py-3.5 text-center' : ' px-5 py-4 text-left')}>
            <div className={'font-semibold text-white ' + (small ? 'text-[15px]' : 'text-[16px]')}>{l}</div>
            {d && <div className="mt-0.5 pr-6 text-[13.5px] text-muted">{d}</div>}
            {on && !small && <span className="absolute right-4 top-4 grid size-5 place-items-center rounded-full bg-signal text-white"><Check className="size-3" strokeWidth={3} /></span>}
          </motion.button>)
      })}
      {multi && <div className="col-span-full text-center text-[12.5px] text-faint">Pick as many as you like</div>}
    </div>
  )
}

const Toggle = ({ l, d, v, f }) => (
  <div className="flex w-full items-center justify-between gap-4 px-5 py-3.5 text-left">
    <div><div className="text-[15px] text-white">{l}</div><div className="mt-0.5 text-[12.5px] text-muted">{d}</div></div>
    <Switch checked={v} onChange={f} />
  </div>)

const Pick = ({ l, v, opts, f }) => (
  <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 px-5 py-3.5"><div className="text-[15px] text-white">{l}</div>
    <Segmented value={v} onChange={f} options={opts.map(o => [o, String(o)])} /></div>)

