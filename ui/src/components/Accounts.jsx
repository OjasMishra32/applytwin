import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { Eye, EyeOff } from 'lucide-react'
import { api } from '../lib/api'
import { Switch } from './ui'

/* Optional: let your twin create candidate accounts and sign in on job sites (Workday, iCIMS...) with one email and
   password you choose. ApplyTwin types the password into the page itself; the AI never sees it, and it never leaves this
   computer. Off by default; Workday sign-ins were the most common thing waiting on people. */
export function Accounts({ defaultEmail = '', className = '' }) {
  const [st, setSt] = useState(null)
  const [email, setEmail] = useState('')
  const [pw, setPw] = useState('')
  const [show, setShow] = useState(false)
  const [busy, setBusy] = useState(false)
  useEffect(() => { api('/api/accounts').then(r => { setSt(r); setEmail(r.email || defaultEmail) }).catch(() => setSt({ enabled: false })) }, [defaultEmail])
  const save = async (body, ok) => {
    setBusy(true)
    try { const r = await api('/api/accounts', body); setSt(r); setPw(''); if (ok) toast.success(ok.title, { description: ok.body }); return r }
    catch (e) { toast.error(e.message) }
    finally { setBusy(false) }
  }
  if (!st) return null
  const on = st.enabled
  const turn = v => {
    if (v && !st.password_set && !st.google) { setSt({ ...st, draft: true }); return }   // nothing to sign in with yet: show the fields first
    save({ enabled: v, email }, v ? { title: 'Your twin can sign in for you', body: 'It creates accounts and signs in, with Google where a site offers it.' } : null)
  }
  const googleIn = async () => {
    try { await api('/api/accounts/google', {}); toast("Google opened in your twin's browser", { description: 'Sign in there once. Your twin then uses Continue with Google without a password.' }) }
    catch (e) { toast.error(e.message) }
  }
  useEffect(() => {   // after you sign in to Google in the twin's window, the check mark appears on its own
    if (!st?.enabled || !st.google || st.google_signed_in) return
    const t = setInterval(() => api('/api/accounts').then(r => setSt(x => ({ ...x, google_signed_in: r.google_signed_in }))).catch(() => {}), 5000)
    return () => clearInterval(t)
  }, [st?.enabled, st?.google, st?.google_signed_in])
  const open = on || st.draft
  return (
    <div className={className}>
      <div className="flex items-start gap-4 px-5 py-4">
        <div className="min-w-0 flex-1">
          <div className="text-[15px] text-white">Sign in and create accounts for me</div>
          <div className="mt-0.5 text-[13px] leading-snug text-muted">On sites like Workday that need an account. ApplyTwin types your password into the page itself: the AI never sees it, and it stays on this computer.</div>
        </div>
        <Switch checked={!!open} onChange={v => v ? turn(true) : (st.draft ? setSt({ ...st, draft: false, enabled: false }) : turn(false))} />
      </div>
      {open && (
        <div className="space-y-3 px-5 pb-5">
          <div className="rounded-[10px] bg-white/[.04] px-3.5 py-3">
            <div className="flex items-center gap-3">
              <div className="min-w-0 flex-1">
                <div className="text-[14px] text-white">Use Sign in with Google when a site offers it</div>
                <div className="mt-0.5 text-[12.5px] text-muted">{!st.google ? 'Off: it uses the email and password below.'
                  : st.google_signed_in ? <span className="text-good">Your twin's browser is signed in to Google.</span>
                  : "Sign in to Google once in your twin's browser so it never needs a Google password."}</div>
              </div>
              <Switch checked={!!st.google} onChange={v => save({ google: v })} />
            </div>
            {st.google && !st.google_signed_in && <button onClick={googleIn} className="mt-2.5 h-8 rounded-full bg-white/[.08] px-3.5 text-[12.5px] font-semibold text-white hover:bg-white/[.13]">Sign in to Google in your twin's browser</button>}
          </div>
          <label className="block">
            <span className="text-[12.5px] text-muted">Email for job site accounts</span>
            <input value={email} onChange={e => setEmail(e.target.value)} onBlur={() => on && email !== st.email && save({ email })} type="email" autoComplete="off"
              className="mt-1 h-10 w-full rounded-[10px] bg-white/[.06] px-3.5 text-[14px] text-white outline-none placeholder:text-faint focus:ring-2 focus:ring-signal" placeholder="you@school.edu" />
          </label>
          <label className="block">
            <span className="text-[12.5px] text-muted">{st.password_set ? 'Password (saved; type a new one to change it)' : 'Password for sites without Google sign-in'}</span>
            <div className="relative mt-1">
              <input value={pw} onChange={e => setPw(e.target.value)} type={show ? 'text' : 'password'} autoComplete="new-password"
                className="h-10 w-full rounded-[10px] bg-white/[.06] px-3.5 pr-10 text-[14px] text-white outline-none placeholder:text-faint focus:ring-2 focus:ring-signal"
                placeholder={st.password_set ? '••••••••••' : 'At least 8 characters, with a number and a symbol'} />
              <button type="button" onClick={() => setShow(!show)} aria-label={show ? 'Hide password' : 'Show password'}
                className="absolute right-2 top-1/2 grid size-7 -translate-y-1/2 place-items-center text-muted hover:text-white">
                {show ? <EyeOff className="size-4" /> : <Eye className="size-4" />}</button>
            </div>
          </label>
          <p className="text-[12.5px] leading-snug text-faint">Use a password only for job sites, never the one for your email or bank. If a site already has an account under this email with a different password, your twin stops there and asks you.</p>
          {(pw || !on) && <button disabled={busy || (pw.length < 8 && !(st.google && !pw)) || !email.includes('@')} onClick={() => save({ email, ...(pw ? { password: pw } : {}), enabled: true }, { title: 'Saved', body: 'Your twin signs in and creates accounts from now on.' })}
            className="h-9 rounded-full bg-signal px-4 text-[13px] font-semibold text-white transition hover:bg-[#2b95ff] disabled:opacity-40">{busy ? 'Saving…' : on ? 'Save new password' : 'Turn on'}</button>}
        </div>)}
    </div>)
}
