import { useState } from 'react'
import { toast } from 'sonner'
import { api } from '../lib/api'

/* The right buttons for anything that needs you. The twin fills forms in its own browser, so "Open" never means a blank
   form in yours: a filled application gets Refill / Submit it; a sign-in opens in the twin's browser (so the login sticks)
   and then "I signed in, finish it". */

export function kindOf(item) {
  const t = `${item.title || ''} ${item.message || ''} ${item.notes || ''}`
  if (/ready to submit|ready for (your )?review|filled and verified/i.test(t)) return 'ready'
  if (/sign[- ]?in|log ?in|account|password|verify your email/i.test(t)) return 'signin'
  if (item.kind === 'question') return 'question'
  return 'other'
}

export function ItemActions({ item, onDone, compact }) {
  const [busy, setBusy] = useState('')
  const kind = kindOf(item)
  const job = item.job_id
  const run = async (label, fn, msg) => {
    setBusy(label)
    try { await fn(); toast.success(msg.title, { description: msg.body }); if (item.id && typeof item.id === 'number') await api(`/api/inbox/${item.id}/resolve`, {}); onDone?.() }
    catch (e) { toast.error(e.message) }
    setBusy('')
  }
  const finish = submit => run(submit ? 'submit' : 'refill', () => api('/api/finish', { job_ids: [job], submit }),
    submit ? { title: 'Submitting it', body: 'Your twin is filling and submitting this one application.' }
      : { title: 'Refilling it', body: 'Your twin is filling it again in its browser and will stop at review.' })
  const openTwin = () => run('open', () => api('/api/open-twin', { url: item.url }),
    { title: "Opened in your twin's browser", body: "Sign in there; your twin uses that same browser, so the login sticks." })
  const btn = 'h-8 rounded-full px-3.5 text-[12.5px] font-semibold transition disabled:opacity-50'
  const primary = btn + ' bg-signal text-white hover:bg-[#2b95ff]', secondary = btn + ' bg-white/[.08] text-white hover:bg-white/[.13]'
  return (
    <div className={'flex flex-wrap items-center gap-2 ' + (compact ? 'mt-2' : '')}>
      {kind === 'ready' && job && <>
        <button disabled={!!busy} onClick={() => finish(true)} className={primary}>{busy === 'submit' ? 'Starting…' : 'Submit it'}</button>
        <button disabled={!!busy} onClick={() => finish(false)} className={secondary}>{busy === 'refill' ? 'Starting…' : 'Refill to review'}</button>
      </>}
      {kind === 'signin' && <>
        {item.url && <button disabled={!!busy} onClick={openTwin} className={secondary}>{busy === 'open' ? 'Opening…' : "Open in twin's browser"}</button>}
        {job && <button disabled={!!busy} onClick={() => finish(false)} className={primary}>{busy === 'refill' ? 'Starting…' : 'I signed in, finish it'}</button>}
      </>}
      {kind === 'question' && job && <button disabled={!!busy} onClick={() => finish(false)} className={secondary}>{busy === 'refill' ? 'Starting…' : 'Answered, finish it'}</button>}
      {kind === 'other' && item.url && <a href={item.url} target="_blank" rel="noreferrer" className={secondary + ' inline-flex items-center'}>Open</a>}
      {typeof item.id === 'number' && <button onClick={async () => { await api(`/api/inbox/${item.id}/resolve`, {}); onDone?.() }} className="h-8 px-2 text-[12.5px] text-muted hover:text-white">Dismiss</button>}
    </div>
  )
}
