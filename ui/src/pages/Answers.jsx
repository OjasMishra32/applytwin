import { useEffect, useState } from 'react'
import { motion } from 'motion/react'
import { toast } from 'sonner'
import { Plus, Sparkles, Wand2 } from 'lucide-react'
import { api } from '../lib/api'
import { Page } from '../App'
import { Badge, Button, Hand, Stagger, Title, item } from '../components/ui'

export default function Answers() {
  const [bank, setBank] = useState(null)
  const [q, setQ] = useState('')
  const [test, setTest] = useState(null)
  useEffect(() => { api('/api/answers').then(setBank) }, [])
  const save = async nb => { setBank(nb); await api('/api/answers', nb) }
  const ask = async () => { if (!q.trim()) return; const [r] = await api('/api/answer/test', { questions: [q] }); setTest(r) }
  return (
    <div className="relative"><Page>
      <Title n="04" sub="Every application asks the same ~40 questions. Answer once; your twin handles every wording.">
        Answers</Title>
      <div className="card mb-5 p-6">
        <Hand>try any question</Hand>
        <div className="mt-2 flex gap-2"><input value={q} onChange={e => setQ(e.target.value)} onKeyDown={e => e.key === 'Enter' && ask()}
          placeholder="“Will you now or in the future require H-1B sponsorship?”" className="box" /><Button onClick={ask}><Wand2 className="size-4" />Answer</Button></div>
        {test && <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="mt-4 flex flex-wrap items-center gap-2 text-[14px]">
          {test.answer ? <><Typed text={test.answer} /><Badge tone="good">matched</Badge><span className="text-muted">matched “{test.key}” · {Math.round(test.confidence * 100)}% sure</span></>
            : <><Badge tone="warn">New question</Badge><span className="text-muted">Your twin will ask you once, then remember.</span></>}</motion.div>}
      </div>
      <div className="card overflow-hidden">
        {!bank ? <div className="p-4"><div className="skel h-64" /></div> : (
          <Stagger className="divide-y divide-line" delay={0.012}>
            {bank.map((r, i) => (
              <motion.div variants={item} key={r.key + i} className="grid items-center gap-3 px-6 py-3.5 md:grid-cols-[1.1fr_1fr_auto]">
                <div className="text-[14px] text-fg">{r.question}</div>
                <input defaultValue={r.answer} placeholder="Your answer" className="uline left" onBlur={e => {
                  if (e.target.value !== r.answer) { const nb = [...bank]; nb[i] = { ...r, answer: e.target.value, source: 'user' }; save(nb); toast.success('Saved') } }} />
                <Badge tone={r.source === 'user' ? 'sky' : 'gray'}>{r.source === 'user' ? 'you' : 'profile'}</Badge>
              </motion.div>))}
          </Stagger>)}
        <div className="border-t border-line px-6 py-4"><Button variant="white" size="sm" onClick={async () => {
          const qq = prompt('Question'); if (!qq) return; const a = prompt('Your answer'); if (a == null) return
          await api('/api/answer', { question: qq, answer: a }); setBank(await api('/api/answers')) }}><Plus className="size-4" />Add a question</Button></div>
      </div>
    </Page></div>
  )
}

function Typed({ text }) {
  const [n, setN] = useState(0)
  useEffect(() => { setN(0); const t = setInterval(() => setN(x => { if (x >= text.length) { clearInterval(t); return x } return x + 1 }), 28); return () => clearInterval(t) }, [text])
  return <span className="rounded-[14px] rounded-bl-[4px] bg-signal px-4 py-2 text-[15px] font-medium text-white shadow-[0_8px_30px_rgb(76_141_255/.4)]">{text.slice(0, n)}<span className="animate-blink">▍</span></span>
}
