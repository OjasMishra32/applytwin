import { useState } from 'react'
import { toast } from 'sonner'
import { X } from 'lucide-react'
import { api } from '../lib/api'
import { useApp, Page } from '../App'
import { Button, Segmented, Slider, Switch, Title } from '../components/ui'

export function Chips({ value = [], onChange, placeholder, suggestions = [] }) {
  const [t, setT] = useState('')
  const addv = x => { x = x.trim(); if (x && !value.includes(x)) onChange([...value, x]); setT('') }
  return (
    <div>
      <div className="flex flex-wrap items-center gap-1.5 rounded-[14px] bg-mist px-2 py-1.5 focus-within:bg-white/[.08] focus-within:ring-2 focus-within:ring-signal">
        {value.map(v => <span key={v} className="inline-flex items-center gap-1 rounded-full bg-signal/10 py-1 pl-3 pr-1.5 text-[13px] font-medium text-signal-ink">{v}
          <button onClick={() => onChange(value.filter(x => x !== v))} className="grid size-4 place-items-center rounded-full hover:bg-signal/20"><X className="size-3" /></button></span>)}
        <input value={t} onChange={e => setT(e.target.value)} placeholder={value.length ? '' : placeholder} onKeyDown={e => {
          if ((e.key === 'Enter' || e.key === ',') && t.trim()) { e.preventDefault(); addv(t) } if (e.key === 'Backspace' && !t && value.length) onChange(value.slice(0, -1)) }}
          className="h-8 min-w-[140px] flex-1 bg-transparent px-1.5 text-[14px] outline-none placeholder:text-faint" />
      </div>
      {suggestions.filter(s => !value.includes(s)).length > 0 && <div className="mt-2 flex flex-wrap gap-1.5">{suggestions.filter(s => !value.includes(s)).map(s =>
        <button key={s} onClick={() => addv(s)} className="rounded-full bg-white/[.04] px-3 py-1 text-[12.5px] text-muted transition hover:bg-signal/10 hover:text-signal-ink">+ {s}</button>)}</div>}
    </div>
  )
}

export const ROLE_SUGGEST = ['software engineer', 'machine learning', 'data science', 'quant', 'hardware', 'robotics', 'product', 'design', 'finance',
  'consulting', 'marketing', 'healthcare', 'research', 'policy', 'security', 'mechanical', 'operations', 'education']

function Group({ title, children }) {
  return <div className="mb-8"><div className="mb-2 px-4 text-[13px] text-muted">{title}</div><div className="card divide-y divide-line overflow-hidden">{children}</div></div>
}
function Row({ label, hint, children, stack }) {
  return (
    <div className={`px-5 py-3 ${stack ? '' : 'flex min-h-[52px] items-center justify-between gap-6'}`}>
      <div className={stack ? 'mb-2.5' : 'min-w-0'}><div className="text-[15px] text-ink">{label}</div>{hint && <div className="text-[12.5px] text-muted">{hint}</div>}</div>
      <div className={stack ? '' : 'w-[52%] shrink-0'}>{children}</div>
    </div>
  )
}

export default function Settings() {
  const { profile, refresh } = useApp()
  const [p, setP] = useState(structuredClone(profile))
  const s = p.search, a = p.apply
  const set = (k, v) => setP({ ...p, [k]: v })
  const ss = (k, v) => setP({ ...p, search: { ...s, [k]: v } })
  const sa = (k, v) => setP({ ...p, apply: { ...a, [k]: v } })
  const se = (k, v) => setP({ ...p, eeo: { ...p.eeo, [k]: v } })
  const save = async () => { await api('/api/profile', p); await refresh(); toast.success('Saved', { description: 'Rescan to re-rank jobs with your new preferences.' }) }
  const T = (k, ph) => <input className="uline" value={p[k] || ''} placeholder={ph} onChange={e => set(k, e.target.value)} />
  const Sel = (k, opts) => <select className="uline" value={p.eeo[k]} onChange={e => se(k, e.target.value)}>{opts.map(o => <option key={o}>{o}</option>)}</select>
  return (
    <div className="relative"><Page>
      <Title sub="Who you are, what you want, and how far your twin may go on its own." right={<Button onClick={save} arrow>Save</Button>}>
        Settings</Title>
      <div className="mx-auto max-w-[860px]">
        <Group title="Your twin's permissions">
          <Row label="Submit applications on its own" hint="Off: it fills everything and stops so you can press Submit."><div className="flex justify-end"><Switch checked={a.auto_submit} onChange={v => sa('auto_submit', v)} /></div></Row>
          <Row label="Read verification codes from my email" hint="When a site emails you a code, your agent finds it in your inbox and types it. Off: you get a notification instead."><div className="flex justify-end"><Switch checked={a.email_codes === 'agent'} onChange={v => sa('email_codes', v ? 'agent' : 'notify')} /></div></Row>
          <Row label="Desktop notifications" hint="Ping my Mac when my twin needs me."><div className="flex justify-end"><Switch checked={a.notify_desktop !== false} onChange={v => sa('notify_desktop', v)} /></div></Row>
          <Row label="Tailor a resume for every job" hint="A new one-page resume, rewritten for each posting."><div className="flex justify-end"><Switch checked={a.tailor_every_resume} onChange={v => sa('tailor_every_resume', v)} /></div></Row>
          <Row label={`Up to ${a.daily_limit} applications a day`}><Slider value={a.daily_limit} min={5} max={200} step={5} onChange={v => sa('daily_limit', v)} /></Row>
          <Row label={`At most ${a.per_company_cap} per company`} hint="Many companies cap or flag repeat applicants."><Slider value={a.per_company_cap} min={1} max={10} step={1} onChange={v => sa('per_company_cap', v)} /></Row>
        </Group>
        <Group title="What you're looking for">
          <Row label="Type"><div className="flex justify-end"><Segmented id="kind" value={s.kind} onChange={v => ss('kind', v)} options={[['internship', 'Internship'], ['new-grad', 'New grad'], ['full-time', 'Full-time']]} /></div></Row>
          <Row label="Cycle">{<input className="uline" value={s.season} onChange={e => ss('season', e.target.value)} placeholder="Summer 2027" />}</Row>
          <Row label="Roles" stack><Chips value={s.roles} onChange={v => ss('roles', v)} placeholder="Add a role" suggestions={ROLE_SUGGEST.slice(0, 10)} /></Row>
          <Row label="Dream companies" hint="Applied to first, every time they post." stack><Chips value={s.companies_priority} onChange={v => ss('companies_priority', v)} placeholder="e.g. Google, Jane Street, Mayo Clinic" /></Row>
          <Row label="Never apply to" stack><Chips value={s.companies_skip} onChange={v => ss('companies_skip', v)} placeholder="Companies to skip" /></Row>
          <Row label="Locations" stack><Chips value={s.locations} onChange={v => ss('locations', v)} placeholder="United States, Remote, New York…" suggestions={['United States', 'Remote', 'New York', 'San Francisco', 'Seattle', 'Boston']} /></Row>
          <Row label="Skip titles with" stack><Chips value={s.exclude} onChange={v => ss('exclude', v)} placeholder="senior, phd…" /></Row>
          <Row label={`Show jobs with fit ${s.min_fit}+`}><Slider value={s.min_fit} min={0} max={95} onChange={v => ss('min_fit', v)} /></Row>
        </Group>
        <Group title="About you">
          {[['name', 'Full name'], ['email', 'Email'], ['phone', 'Phone'], ['location', 'City, State'], ['linkedin', 'LinkedIn'], ['github', 'GitHub'], ['website', 'Website']].map(([k, l]) => <Row key={k} label={l}>{T(k, l)}</Row>)}
        </Group>
        <Group title="School">
          {[['school', 'School'], ['degree', 'Degree'], ['major', 'Major'], ['minor', 'Minor'], ['gpa', 'GPA'], ['grad_month', 'Graduation month'], ['grad_year', 'Graduation year'], ['earliest_start', 'Earliest start']].map(([k, l]) => <Row key={k} label={l}>{T(k, l)}</Row>)}
          <Row label="Class standing now" hint="Your twin answers year-in-school questions with this, and knows a sophomore is a rising junior next summer.">
            <select className="uline" value={p.class_standing || ''} onChange={e => set('class_standing', e.target.value)}>
              {['', 'Freshman', 'Sophomore', 'Junior', 'Senior', 'Graduate'].map(o => <option key={o} value={o}>{o || 'Not set'}</option>)}</select></Row>
        </Group>
        <Group title="Work authorization">
          <Row label="Authorized to work in the US"><div className="flex justify-end"><Switch checked={p.work_authorized_us} onChange={v => set('work_authorized_us', v)} /></div></Row>
          <Row label="Will need visa sponsorship"><div className="flex justify-end"><Switch checked={p.needs_sponsorship} onChange={v => set('needs_sponsorship', v)} /></div></Row>
          <Row label="Willing to relocate"><div className="flex justify-end"><Switch checked={p.willing_to_relocate} onChange={v => set('willing_to_relocate', v)} /></div></Row>
          <Row label="Citizenship" hint="Only used for roles that require it.">{T('citizenship', 'Optional')}</Row>
        </Group>
        <Group title="Voluntary self-identification">
          <Row label="Gender">{Sel('gender', ['Decline to self-identify', 'Male', 'Female', 'Non-binary'])}</Row>
          <Row label="Race / ethnicity">{Sel('race', ['Decline to self-identify', 'Asian', 'Black or African American', 'Hispanic or Latino', 'White', 'Native American or Alaska Native', 'Native Hawaiian or Pacific Islander', 'Two or more races'])}</Row>
          <Row label="Veteran">{Sel('veteran', ['I am not a protected veteran', 'I identify as a protected veteran', 'Decline to self-identify'])}</Row>
          <Row label="Disability">{Sel('disability', ['I do not want to answer', 'No, I do not have a disability', 'Yes, I have a disability'])}</Row>
        </Group>
      </div>
    </Page></div>
  )
}
