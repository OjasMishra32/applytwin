import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { Segmented, Switch } from './ui'
import { Chips } from '../pages/Settings'

/* Working outside the US: countries and cities to work in, the right to work in each, local program types, and the
   questions European and Indian forms ask. All of it is optional; nothing here is filled in for the user. */

let cache = null
export function useRegions() {
  const [r, setR] = useState(cache)
  useEffect(() => { if (!cache) api('/api/regions').then(x => { cache = x; setR(x) }).catch(() => {}) }, [])
  return r
}

const STATUS = [['citizen', 'Citizen'], ['authorized', 'Have a visa'], ['sponsorship', 'Need sponsorship']]

// country names (or 'Europe', 'Nordics'...) -> codes
export function pickedCodes(names, r) {
  if (!r) return []
  const out = new Set()
  for (const n of names || []) {
    const low = (n || '').trim().toLowerCase()
    const c = r.countries.find(x => x.name.toLowerCase() === low || x.code.toLowerCase() === low || (low === 'uk' && x.code === 'GB'))
    if (c) out.add(c.code)
    else if (r.groups[low]) r.groups[low].forEach(x => out.add(x))
  }
  return [...out]
}

// the work-rights rows to ask: the UK, one row for the EU/EEA (free movement), then each other country
function rightsRows(codes, r) {
  const rows = []
  const eea = codes.filter(c => r.eea.includes(c))
  const name = c => r.countries.find(x => x.code === c)?.name || c
  if (codes.includes('GB')) rows.push(['GB', 'United Kingdom'])
  if (eea.length) rows.push(['EU', eea.length === 1 ? `${name(eea[0])} (EU/EEA)` : 'EU / EEA countries'])
  codes.filter(c => c !== 'GB' && c !== 'US' && !r.eea.includes(c)).forEach(c => rows.push([c, name(c)]))
  return rows
}

export function WhereAbroad({ p, setP, large, compact }) {
  const r = useRegions()
  const s = p.search || {}
  const ss = (k, v) => setP(x => ({ ...x, search: { ...x.search, [k]: v } }))
  const codes = pickedCodes([...(s.countries || []), ...(s.cities || []).map(c => cityCountry(c, r))].filter(Boolean), r)
  const wa = p.work_auth || {}
  if (!r) return null
  // a few from each picked country first (the list shows a dozen), then the rest
  const lists = codes.map(c => r.cities[c] || [])
  const cityOptions = [...new Set(Array.from({ length: Math.max(0, ...lists.map(l => l.length)) }, (_, i) => lists.map(l => l[i])).flat().filter(Boolean))]
  const featured = r.countries.slice(0, 18).map(c => c.name)
  const lbl = large ? 'mb-2 text-[13px] text-muted' : 'mb-1.5 text-[13px] text-muted'
  return (
    <div className="space-y-5">
      <div><div className={lbl}>Countries {compact ? '' : '(leave empty to search the US the usual way)'}</div>
        <Chips large={large} value={s.countries || []} onChange={v => ss('countries', v)} placeholder="United Kingdom, Germany, India, Europe…"
          suggestions={[...featured, 'Europe', 'Nordics']} /></div>
      {codes.length > 0 && <div><div className={lbl}>Cities (optional: ranked first, others in those countries still show)</div>
        <Chips large={large} value={s.cities || []} onChange={v => ss('cities', v)} placeholder="London, Bengaluru, Berlin…" suggestions={cityOptions} /></div>}
      {rightsRows(codes, r).length > 0 && <div><div className={lbl}>Your right to work there. Postings that need local work rights you don't have are skipped, with the reason.</div>
        <div className="space-y-2">{rightsRows(codes, r).map(([c, name]) =>
          <div key={c} className="flex flex-wrap items-center justify-between gap-2"><span className="text-[14.5px] text-ink">{name}</span>
            <Segmented value={wa[c] || ''} onChange={v => setP(x => ({ ...x, work_auth: { ...(x.work_auth || {}), [c]: v } }))} options={STATUS} /></div>)}</div></div>}
      {codes.some(c => c !== 'US') && <div><div className={lbl}>Program types (none picked = all)</div>
        <div className="flex flex-wrap gap-1.5">{r.programs.map(pr => {
          const on = (s.programs || []).includes(pr.key)
          return <button key={pr.key} onClick={() => ss('programs', on ? (s.programs || []).filter(x => x !== pr.key) : [...(s.programs || []), pr.key])}
            className={'rounded-[8px] px-2.5 py-1 text-[13px] transition-colors ' + (on ? 'bg-signal text-white' : 'bg-white/[.07] text-ink/80 hover:bg-white/[.12]')}>{pr.label}</button>
        })}</div></div>}
    </div>
  )
}

function cityCountry(c, r) {
  if (!r) return null
  const low = (c || '').toLowerCase()
  for (const [code, list] of Object.entries(r.cities)) if (list.some(x => x.toLowerCase() === low)) return r.countries.find(x => x.code === code)?.name
  return null
}

/* The questions forms in Europe and India ask; blank stays blank and the twin asks you. */
export function AbroadAnswers({ p, setP }) {
  const r = useRegions()
  const codes = pickedCodes(p.search?.countries || [], r)
  if (!codes.some(c => c !== 'US')) return null
  const india = codes.includes('IN')
  const set = (k, v) => setP(x => ({ ...x, [k]: v }))
  const T = (k, label, ph) => <label key={k} className="flex flex-wrap items-center justify-between gap-x-6 gap-y-1 px-4 py-3">
    <span className="text-[15px] text-ink">{label}</span>
    <input className="uline w-full sm:w-[44%]" value={p[k] || ''} placeholder={ph} onChange={e => set(k, e.target.value)} /></label>
  return (
    <div className="card mb-8 divide-y divide-line overflow-hidden">
      {T('nationality', 'Nationality', 'e.g. India, or India, United Kingdom')}
      {T('notice_period', 'Notice period', 'e.g. Immediately, or 30 days')}
      {T('expected_salary_local', 'Expected salary (local currency)', 'e.g. £30,000, or in line with the posted range')}
      {T('languages', 'Languages you speak', 'e.g. English (native), German (B1)')}
      {T('visa_type', 'Visa or permit you hold', 'Only if you have one')}
      {india && T('current_ctc', 'Current CTC', 'e.g. 0 (student), or 12 LPA')}
      {india && T('expected_ctc', 'Expected CTC', 'e.g. 18 LPA')}
      {india && T('cgpa', 'CGPA (out of 10)', 'As on your transcript')}
      {india && T('marks_10th', '10th marks', 'e.g. 95% (CBSE)')}
      {india && T('marks_12th', '12th marks', 'e.g. 93% (CBSE)')}
      <div className="flex items-center justify-between gap-6 px-4 py-3"><div><div className="text-[15px] text-ink">Consent to data processing (GDPR)</div>
        <div className="mt-0.5 text-[12.5px] text-muted">Most European forms require it to apply.</div></div>
        <Switch checked={p.gdpr_ok !== false} onChange={v => set('gdpr_ok', v)} /></div>
    </div>
  )
}
