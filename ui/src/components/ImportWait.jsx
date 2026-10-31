import { useEffect, useState } from 'react'
import { api } from '../lib/api'

/* While a resume import runs: the honest time left (learned from how long your agent takes on this computer), a note when
   it runs long, and Cancel, which stops your agent so the built-in reader finishes it in a second. */
export function ImportWait({ className = '' }) {
  const [p, setP] = useState(null)
  const [stopping, setStopping] = useState(false)
  useEffect(() => {
    let on = true
    const tick = () => api('/api/import').then(r => on && setP(r)).catch(() => {})
    tick(); const t = setInterval(tick, 1000)
    return () => { on = false; clearInterval(t) }
  }, [])
  if (!p?.running) return <div className={className}>A few seconds</div>
  const secs = Math.max(1, Math.round(p.eta)), left = secs < 60 ? `About ${secs} seconds left` : `About ${Math.round(secs / 60)} min left`
  return (
    <div className={className}>
      <div>{p.slow ? `Your agent is taking longer than usual (${Math.round(p.elapsed)} s). It stops after ${Math.round(p.limit / 60)} min and the built-in reader takes over.` : left}
        {p.written > 0 && <span> · {p.written.toLocaleString()} characters written</span>}</div>
      <button disabled={stopping} onClick={() => { setStopping(true); api('/api/import/cancel', {}).catch(() => setStopping(false)) }}
        className="mt-2 rounded-full px-3 py-1 text-[13px] font-medium underline-offset-2 hover:underline disabled:opacity-50">
        {stopping ? 'Stopping…' : 'Cancel and use the quick reader'}</button>
    </div>
  )
}
