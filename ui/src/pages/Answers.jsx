import { useEffect, useState } from 'react'
import { motion } from 'motion/react'
import { toast } from 'sonner'
import { Plus, Sparkles, Wand2 } from 'lucide-react'
import { api } from '../lib/api'
import { Page } from '../App'
import { Badge, Button, Title } from '../components/ui'

export default function Answers() {
  const [bank, setBank] = useState(null)
  const [q, setQ] = useState('')
  const [test, setTest] = useState(null)
  const [nq, setNq] = useState({ question: '', answer: '' })
  const add = async () => {
    if (!nq.question.trim() || !nq.answer.trim()) return
    await api('/api/answer', nq); setNq({ question: '', answer: '' }); setBank(await api('/api/answers')); toast.success('Added to your answers')
  }
  useEffect(() => { api('/api/answers').then(setBank) }, [])
  const save = async nb => { setBank(nb); await api('/api/answers', nb) }
  const [asking, setAsking] = useState(false)
  const ask = async () => {
    if (!q.trim() || asking) return
    setAsking(true)
    try { const [r] = await api('/api/answer/test', { questions: [q] }); setTest(r) } catch (e) { toast.error(e.message) }
    setAsking(false)
  }
  return (
    <div className="relative"><Page>
      <Title sub="Every application asks the same ~40 questions. Answer once; your twin handles every wording.">
        Answers</Title>
      <div className="card mb-8 p-5">
        <div className="text-[17px] font-semibold text-white">Try any question</div>
        <div className="mb-3 mt-0.5 text-[13px] text-muted">See how your twin would answer it on a real form.</div>
        <div className="flex flex-col gap-2 sm:flex-row"><input value={q} onChange={e => setQ(e.target.value)} onKeyDown={e => e.key === 'Enter' && ask()}
          placeholder="Will you now or in the future require H-1B sponsorship?" className="box h-10 py-0" /><Button onClick={ask} loading={asking} disabled={!q.trim()}><Wand2 className="size-4" />Answer</Button></div>
        {test && <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="mt-4 flex flex-wrap items-center gap-2 text-[14px]">
          {test.answer ? <><Typed text={test.answer} /><span className="text-muted">Matched “{test.key}” · {Math.round(test.confidence * 100)}% sure</span></>
            : test.action === 'write' ? <><Badge tone="good">Written for each job</Badge><span className="text-muted">Your twin writes this one fresh for every posting, from your resume.</span></>
            : <><Badge tone="warn">New question</Badge><span className="text-muted">Your twin will ask you once, then remember.</span></>}</motion.div>}
      </div>
      <div className="mb-2 flex items-baseline justify-between px-1"><h2 className="text-[20px] font-semibold tracking-[-0.02em] text-white">Your answers</h2>
        <span className="text-[13px] text-muted">Click an answer to change it</span></div>
      <div className="card overflow-hidden">
        {!bank ? <div className="space-y-px p-2">{[0, 1, 2, 3, 4].map(i => <div key={i} className="skel h-[52px]" />)}</div> : (
          <div className="divide-y divide-line">
            {!bank.length && <div className="px-5 py-10 text-center text-[14px] text-muted">No saved answers yet. Add one below, or answer questions as your twin asks them.</div>}
            {bank.map((r, i) => (
              <div key={r.key + i} className="grid items-center gap-x-4 gap-y-1.5 px-5 py-3 md:grid-cols-[1.1fr_1fr_72px]">
                <div className="text-[14px] text-fg">{r.question}</div>
                <input defaultValue={r.answer} placeholder="Your answer" className="h-9 w-full rounded-[8px] bg-transparent px-2.5 text-[14px] text-white outline-none transition-colors placeholder:text-faint hover:bg-white/[.05] focus:bg-white/[.06] focus:ring-2 focus:ring-signal md:-ml-2.5" onKeyDown={e => e.key === 'Enter' && e.currentTarget.blur()} onBlur={e => {
                  if (e.target.value !== r.answer) { const nb = [...bank]; nb[i] = { ...r, answer: e.target.value, source: 'user' }; save(nb); toast.success('Saved') } }} />
                <span className="hidden justify-self-end md:block"><Badge tone={r.source === 'user' ? 'sky' : 'gray'}>{r.source === 'user' ? 'Edited' : 'Setup'}</Badge></span>
              </div>))}
          </div>)}
        <div className="grid items-center gap-x-4 gap-y-2 border-t border-line bg-white/[.015] px-5 py-3 md:grid-cols-[1.1fr_1fr_72px]">
          <input value={nq.question} onChange={e => setNq({ ...nq, question: e.target.value })} placeholder="Add a question…" className="h-9 w-full rounded-[8px] bg-white/[.05] px-2.5 text-[14px] text-white outline-none placeholder:text-faint focus:ring-2 focus:ring-signal" />
          <input value={nq.answer} onChange={e => setNq({ ...nq, answer: e.target.value })} onKeyDown={e => e.key === 'Enter' && add()} placeholder="Its answer" className="h-9 w-full rounded-[8px] bg-white/[.05] px-2.5 text-[14px] text-white outline-none placeholder:text-faint focus:ring-2 focus:ring-signal" />
          <Button size="sm" className="justify-self-end" onClick={add} disabled={!nq.question.trim() || !nq.answer.trim()}><Plus className="size-4" />Add</Button>
        </div>
      </div>
    </Page></div>
  )
}

function Typed({ text }) {
  const [n, setN] = useState(0)
  useEffect(() => { setN(0); const t = setInterval(() => setN(x => { if (x >= text.length) { clearInterval(t); return x } return x + 1 }), 28); return () => clearInterval(t) }, [text])
  return <span className="rounded-[16px] rounded-bl-[6px] bg-signal px-4 py-2 text-[15px] font-medium text-white">{text.slice(0, n)}</span>
}
