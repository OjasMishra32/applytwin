import { useEffect, useState } from 'react'
import { motion } from 'motion/react'
import { ChevronRight, Check } from 'lucide-react'
import { api } from '../lib/api'
import { ago } from '../lib/utils'
import { useApp } from '../App'
import { Sky } from '../components/Sky'
import { Hero3D } from '../components/Hero3D'
import { Avatar, Button, Fit, GlideList, LightRing, Magnetic, NumberTicker, Odometer, Reveal, Stagger, Words, item, soft } from '../components/ui'
import { useScroll, useTransform } from 'motion/react'

export default function Home() {
  const { profile, stats, go, startScan, scan, jobs } = useApp()
  const [next, setNext] = useState(null)
  const [setup, setSetup] = useState([])
  useEffect(() => { api('/api/next?n=7').then(setNext); api('/api/setup').then(setSetup) }, [stats])
  const first = (profile.name || '').split(' ')[0]
  const h = new Date().getHours()
  const greet = h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening'
  const todo = setup.filter(s => !s.done)
  const scanning = scan?.running
  const fresh = [...jobs].sort((a, b) => b.found_at - a.found_at).slice(0, 16)
  const { scrollY } = useScroll()
  const heroY = useTransform(scrollY, [0, 600], [0, -120])
  const heroO = useTransform(scrollY, [0, 450], [1, 0])
  const artY = useTransform(scrollY, [0, 600], [0, 90])
  const artS = useTransform(scrollY, [0, 600], [1, 0.9])

  return (
    <div className="relative">
      <Sky height={760} />
      <div className="relative mx-auto grid max-w-[1240px] items-center gap-2 px-6 pt-28 md:grid-cols-[1.1fr_1fr]">
        <motion.div className="text-white" style={{ y: heroY, opacity: heroO }}>
          <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={soft} className="flex flex-wrap items-center gap-3 text-[17px] font-medium text-white/80">
            <span>{greet}{first ? `, ${first}` : ''}.</span>
            <span className="rounded-full bg-white/10 px-3 py-1 text-[13px] font-semibold text-white ring-1 ring-white/20">Free to use</span>
          </motion.div>
          <motion.h1 initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ ...soft, delay: 0.05 }}
            className="mt-3 text-[76px] font-bold leading-[0.95] tracking-[-0.045em]">
            <Words text="You apply once." /><br /><Words text="Your twin" delay={0.25} className="serif-i text-[#9cc8ff] text-[90px]" /><Words text="does the rest." delay={0.4} />
          </motion.h1>
          <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.15 }} className="mt-6 max-w-[470px] text-[19px] leading-[1.45] text-white/80">
            {(stats.matched || 0).toLocaleString()} open roles fit you right now. It writes the ideal resume for each one and applies through your own Claude or Codex. Free, forever.
          </motion.p>
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.22 }} className="mt-8 flex flex-wrap gap-3">
            <Magnetic><Button size="lg" variant="dark" className="bg-white text-[#0b1020] hover:bg-white/90" onClick={() => go('agents')} arrow>Start applying</Button></Magnetic>
            <Button size="lg" variant="glass" onClick={startScan} loading={scanning}>{scanning ? 'Scanning' : 'Find new jobs'}</Button>
          </motion.div>
        </motion.div>
        <motion.div style={{ y: artY, scale: artS }}><Hero3D name={profile.name || 'Your Name'} /></motion.div>
      </div>

      <div className="relative mx-auto mt-16 max-w-[1240px] px-6 pb-24">
        <Reveal><div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          {[['Fit you now', stats.matched, '#0a84ff'], ['Applied today', stats.applied_today, '#30d158'], ['This week', stats.applied_7d, '#bf5af2'],
            ['Left today', next?.remaining_today ?? 0, '#7d869f']].map(([l, v, c]) => (
            <div key={l} className="card px-5 py-4">
              <div className="text-[34px] font-semibold leading-none tracking-[-0.04em] text-white"><Odometer value={v || 0} /></div>
              <div className="mt-2 flex items-center gap-1.5 text-[13px] text-muted"><span className="size-2 rounded-full" style={{ background: c }} />{l}</div></div>))}
        </div></Reveal>

        <div className={`mt-8 grid gap-8 ${todo.length ? 'md:grid-cols-[1.7fr_1fr]' : ''}`}>
          <Reveal delay={0.05}><section>
            <div className="mb-3 flex items-end justify-between px-1"><h2 className="text-[28px] font-bold tracking-[-0.035em] text-white">Up next</h2>
              <button onClick={() => go('jobs')} className="flex items-center text-[15px] text-signal-ink hover:underline">See all<ChevronRight className="size-4" /></button></div>
            <Stagger className="card overflow-hidden py-1">
              <GlideList id="next" rows={(next?.jobs || []).map(j => ({ key: j.id, onClick: () => go('jobs', j.id), content: <>
                <Avatar name={j.company} />
                <div className="min-w-0 flex-1"><div className="truncate text-[15px] font-medium text-ink">{j.title}</div>
                  <div className="truncate text-[13px] text-muted">{j.company} · {j.location || 'Remote or multiple'} · {ago(j.found_at)} ago</div></div>
                <Fit v={j.fit} /><ChevronRight className="size-4 text-faint transition-transform group-hover:translate-x-1 group-hover:text-signal" /></> }))} />
              {next && !next.jobs.length && <div className="px-6 py-14 text-center text-[15px] text-muted">No matches yet. Tap <b>Find new jobs</b>.</div>}
            </Stagger>
          </section></Reveal>
          {todo.length > 0 && (
            <section>
              <div className="mb-3 px-1"><h2 className="text-[28px] font-bold tracking-[-0.035em] text-white">Finish setting up</h2></div>
              <div className="card divide-y divide-white/[.06] overflow-hidden">
                {setup.map(s => (
                  <button key={s.id} onClick={() => go({ profile: 'settings', vault: 'studio', skills: 'studio', search: 'settings', scan: 'jobs', chrome: 'agents' }[s.id])}
                    className="flex w-full items-center gap-3 px-5 py-3.5 text-left text-[15px] transition hover:bg-white/[.025]">
                    <span className={`grid size-[22px] place-items-center rounded-full ${s.done ? 'bg-good text-white' : 'ring-[1.5px] ring-inset ring-white/20'}`}>{s.done && <Check className="size-3.5" strokeWidth={3} />}</span>
                    <span className={`flex-1 ${s.done ? 'text-muted' : 'text-ink'}`}>{s.label}</span>{!s.done && <ChevronRight className="size-4 text-faint" />}
                  </button>))}
              </div>
            </section>)}
        </div>

        {fresh.length > 0 && (
          <Reveal><section className="mt-12">
            <div className="mb-3 px-1"><h2 className="text-[28px] font-bold tracking-[-0.035em] text-white">Just posted</h2></div>
            <div className="relative overflow-hidden [mask-image:linear-gradient(90deg,transparent,#000_6%,#000_94%,transparent)]">
              <div className="flex w-max animate-marquee gap-3 py-2 hover:[animation-play-state:paused]">
                {[...fresh, ...fresh].map((j, i) => (
                  <button key={i} onClick={() => go('jobs', j.id)} className="card lift flex w-[290px] shrink-0 items-center gap-3 p-4 text-left">
                    <Avatar name={j.company} size={36} /><div className="min-w-0"><div className="truncate text-[14px] font-medium">{j.title}</div>
                      <div className="truncate text-[12.5px] text-muted">{j.company}</div></div>
                  </button>))}
              </div>
            </div>
          </section></Reveal>)}

      </div>
    </div>
  )
}
