import { useEffect, useState } from 'react'
import { ChevronRight, Check } from 'lucide-react'
import { api } from '../lib/api'
import { ago } from '../lib/utils'
import { useApp, Page } from '../App'
import { Avatar, Button, Fit, GlideList, Reveal, Stagger } from '../components/ui'

/* Today: what a native Mac app shows when you open it. A large title, two actions, your numbers, and what's next. */
export default function Home() {
  const { profile, stats, go, startScan, scan, jobs } = useApp()
  const [next, setNext] = useState(null)
  const [setup, setSetup] = useState([])
  const [ready, setReady] = useState(null)
  useEffect(() => { api('/api/next?n=7').then(setNext).catch(() => {}); api('/api/setup').then(setSetup).catch(() => {})
    api('/api/queue?n=0').then(q => setReady(q.total)).catch(() => {}) }, [stats])   // the same "ready" number Autopilot shows
  const first = (profile.name || '').split(' ')[0]
  const h = new Date().getHours()
  const greet = h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening'
  const todo = setup.filter(s => !s.done)
  const scanning = scan?.running
  const shown = new Set((next?.jobs || []).map(j => j.id))
  const fresh = [...jobs].filter(j => !shown.has(j.id)).sort((a, b) => b.found_at - a.found_at).slice(0, 6)
  const today = new Date().toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' })

  return (
    <Page>
      <div>
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-[28px] font-bold leading-[1.15] tracking-[-0.02em] text-white">{greet}{first ? `, ${first}` : ''}</h1>
            <p className="mt-1.5 text-[15px] text-muted">{today}</p>
          </div>
          <div className="flex gap-2">
            <Button variant="white" onClick={startScan} loading={scanning}>{scanning ? 'Scanning' : 'Find new jobs'}</Button>
            <Button onClick={() => go('agents')}>Start applying</Button>
          </div>
        </div>

        {/* one summary panel with hairline dividers, not a row of separate tiles */}
        <div className="card mt-8 grid grid-cols-2 md:grid-cols-4">
          {[['Ready to apply', ready], ['Applied today', stats.applied_day ?? 0], ['This week', stats.applied_7d ?? 0], ['Left today', next ? (next.remaining_today ?? 0) : null]].map(([l, v], i) => (
            <div key={l} className={'px-5 py-4 ' + (i % 2 ? 'border-l border-line ' : '') + (i > 1 ? 'border-t border-line md:border-t-0 ' : '') + (i === 2 ? 'md:border-l' : '')}>
              <div className="text-[13px] text-muted">{l}</div>
              <div className="mt-1 text-[22px] font-semibold leading-tight tracking-[-0.02em] text-white tabular-nums">{v == null ? <span className="text-faint">—</span> : Number(v).toLocaleString()}</div></div>))}
        </div>

        {todo.length > 0 && (
          <Reveal><section className="mt-8">
            <div className="mb-2 flex items-baseline justify-between px-1">
              <h2 className="text-[17px] font-semibold tracking-[-0.01em] text-white">Finish setting up</h2>
              <span className="text-[13px] text-muted">{setup.length - todo.length} of {setup.length} done</span>
            </div>
            <div className="card divide-y divide-white/[.06] overflow-hidden">
              {setup.map(s => (
                <button key={s.id} onClick={() => go({ profile: 'settings', vault: 'studio', skills: 'studio', search: 'settings', scan: 'jobs', chrome: 'agents' }[s.id])}
                  className="flex min-h-[44px] w-full items-center gap-3 px-4 py-2.5 text-left text-[14px] transition-colors hover:bg-white/[.03]">
                  <span className={`grid size-[20px] shrink-0 place-items-center rounded-full ${s.done ? 'bg-good text-white' : 'ring-[1.5px] ring-inset ring-white/25'}`}>{s.done && <Check className="size-3" strokeWidth={3} />}</span>
                  <span className={`min-w-0 flex-1 truncate ${s.done ? 'text-muted' : 'text-white'}`}>{s.label}</span>
                  {s.detail && !s.done && <span className="shrink-0 text-[12.5px] text-warn">{s.detail}</span>}
                  <ChevronRight className="size-4 shrink-0 text-faint" />
                </button>))}
            </div>
          </section></Reveal>)}

        <Reveal delay={0.05}><section className="mt-8">
          <div className="mb-2 flex items-end justify-between px-1"><h2 className="text-[17px] font-semibold tracking-[-0.01em] text-white">Up next</h2>
            <button onClick={() => go('jobs')} className="text-[13px] text-signal-ink hover:underline">See all</button></div>
          <Stagger className="card overflow-hidden py-1">
            <GlideList id="next" rows={(next?.jobs || []).map(j => ({ key: j.id, onClick: () => go('jobs', j.id), content: <>
              <Avatar name={j.company} />
              <div className="min-w-0 flex-1"><div className="truncate text-[15px] font-medium text-ink">{j.title}</div>
                <div className="truncate text-[13px] text-muted">{j.company} · {j.location || 'Remote or multiple'} · {ago(j.found_at)} ago</div></div>
              <Fit v={j.fit} /><ChevronRight className="size-4 text-faint" /></> }))} />
            {!next && <div className="space-y-px p-2">{[0, 1, 2].map(i => <div key={i} className="skel h-[56px]" />)}</div>}
            {next && !next.jobs.length && <div className="px-6 py-12 text-center"><div className="text-[15px] font-medium text-white">No matches yet</div>
              <div className="mt-1 text-[13px] text-muted">Find new jobs reads every career page and scores each role against you.</div></div>}
          </Stagger>
        </section></Reveal>

        {fresh.length > 0 && (
          <Reveal><section className="mt-8">
            <div className="mb-2 px-1"><h2 className="text-[17px] font-semibold tracking-[-0.01em] text-white">Just posted</h2></div>
            <div className="card divide-y divide-white/[.06] overflow-hidden">
              {fresh.map(j => (
                <button key={j.id} onClick={() => go('jobs', j.id)} className="flex w-full items-center gap-3 px-4 py-3 text-left transition hover:bg-white/[.03]">
                  <Avatar name={j.company} size={32} />
                  <div className="min-w-0 flex-1"><div className="truncate text-[14.5px] font-medium text-white">{j.title}</div>
                    <div className="truncate text-[12.5px] text-muted">{j.company} · {ago(j.found_at)} ago</div></div>
                  <ChevronRight className="size-4 shrink-0 text-faint" />
                </button>))}
            </div>
          </section></Reveal>)}
      </div>
    </Page>
  )
}
