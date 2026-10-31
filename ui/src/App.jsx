import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { HelpChat } from './components/HelpChat'
import { Toaster, toast } from 'sonner'
import { Radar, Play, FileText, Upload } from 'lucide-react'
import { api } from './lib/api'
import { Logo, TopBar, TabBar, Palette, Sidebar } from './components/Shell'
import Home from './pages/Home'
import Jobs from './pages/Jobs'
import Studio from './pages/Studio'
import Answers from './pages/Answers'
import Board from './pages/Board'
import Settings from './pages/Settings'
import Agents from './pages/Agents'
import Welcome from './pages/Welcome'

const Ctx = createContext(null)
export const useApp = () => useContext(Ctx)
const PAGES = { home: Home, jobs: Jobs, studio: Studio, answers: Answers, board: Board, settings: Settings, agents: Agents, welcome: Welcome }

/* After an update the open page reloads itself onto the new version, so the page and the app never disagree.
   It waits until the tab is in the background or you've been idle a minute, so nothing you're in the middle of is lost. */
function keepCurrent() {
  const mine = (document.querySelector('script[src*="assets/index-"]')?.getAttribute('src') || '').split('/').pop()
  if (!mine) return
  let stale = false, last = Date.now()
  const touch = () => { last = Date.now() }
  addEventListener('pointerdown', touch); addEventListener('keydown', touch)
  const check = async () => {
    try { const v = await api('/api/version'); if (v.ui && v.ui !== mine) stale = true } catch { /* restarting; try next time */ }
    if (stale && !location.hash.startsWith('#welcome') && (document.hidden || Date.now() - last > 60000)) location.reload()   // never mid-setup
  }
  const t = setInterval(check, 20000)
  const vis = () => { if (!document.hidden) check() }
  document.addEventListener('visibilitychange', vis)
  return () => { clearInterval(t); document.removeEventListener('visibilitychange', vis); removeEventListener('pointerdown', touch); removeEventListener('keydown', touch) }
}

/* Set when this tab sends you to Google; read once when you come back with tokens. */
const loginStarted = () => { try { const v = sessionStorage.getItem('applytwin_login'); sessionStorage.removeItem('applytwin_login'); return !!v } catch { return true } }

export default function App() {
  const parse = () => { const raw = location.hash.slice(1); if (raw.includes('access_token=')) return { page: 'home' }; const [p, arg] = (raw || 'home').split('/'); return { page: PAGES[p] ? p : 'home', arg } }
  const [route, setRoute] = useState(parse)
  const [state, setState] = useState(null)
  const [palette, setPalette] = useState(false)
  const [jobs, setJobs] = useState([])
  const [scan, setScan] = useState(null)

  const [auth, setAuth] = useState({ signed_in: false })
  const [authReady, setAuthReady] = useState(false)
  const [loadErr, setLoadErr] = useState(null)
  const [wide, setWide] = useState(() => matchMedia('(min-width: 768px)').matches)
  useEffect(() => { const m = matchMedia('(min-width: 768px)'); const f = () => setWide(m.matches); m.addEventListener('change', f); return () => m.removeEventListener('change', f) }, [])
  const refresh = useCallback(async () => {
    try { const s = await api('/api/state'); setState(s); setLoadErr(null); return s }
    catch (e) { setLoadErr(e.message || "Couldn't reach ApplyTwin"); return null }
  }, [])
  useEffect(() => {
    const h = location.hash
    if (h.includes('error_description=') || h.includes('error=')) {   // Google or Supabase said no (cancelled, blocked): say so
      const q = new URLSearchParams(h.slice(1))
      history.replaceState(null, '', location.pathname + '#home')
      toast.error("Sign-in didn't finish", { description: (q.get('error_description') || q.get('error') || '').replace(/\+/g, ' ') + ' Try again.' })
      api('/api/auth').then(r => { setAuth(r); setAuthReady(true) }).catch(() => setAuthReady(true))
    } else if (h.includes('access_token=') && !loginStarted()) {
      // tokens this tab didn't ask for (a link to localhost:4747/#access_token=...) would sign you into someone else's
      // account and sync your vault to it: ignore them
      history.replaceState(null, '', location.pathname + '#home')
      api('/api/auth').then(r => { setAuth(r); setAuthReady(true) }).catch(() => setAuthReady(true))
    } else if (h.includes('access_token=')) {
      const q = new URLSearchParams(h.slice(1))
      history.replaceState(null, '', location.pathname + '#home')
      api('/api/auth', { access_token: q.get('access_token'), refresh_token: q.get('refresh_token'), expires_in: q.get('expires_in') })
        .then(r => { setAuth(r); setAuthReady(true); toast.success(`Signed in${r.user?.email ? ' as ' + r.user.email : ''}`, { description: r.restored ? 'Brought in what your account had that this computer didn\'t (nothing here was overwritten).' : 'Your vault now syncs to your account.' }); refresh() })
        .catch(e => { setAuthReady(true); toast.error('Sign-in failed: ' + e.message) })
    } else api('/api/auth').then(r => { setAuth(r); setAuthReady(true) }).catch(() => setAuthReady(true))
  }, [refresh])
  const signIn = async () => { try { sessionStorage.setItem('applytwin_login', '1') } catch {} const r = await api('/api/auth/login?redirect=' + encodeURIComponent(location.origin + '/')); location.href = r.url }
  const signOut = async () => { setAuth(await api('/api/auth/logout', {})); toast('Signed out') }
  useEffect(() => {   // first time only: once setup is finished, an empty resume never sends you back into it
    if (state && !state.profile?.onboarded && (!location.hash || location.hash === '#home') && !(state.vault?.experience?.length || state.vault?.projects?.length)) location.hash = 'welcome'
  }, [state])
  const loadJobs = useCallback(() => api('/api/jobs?limit=200').then(setJobs).catch(() => {}), [])   // the state load already shows when the app is unreachable
  useEffect(() => { refresh(); loadJobs() }, [refresh, loadJobs])
  useEffect(() => keepCurrent(), [])
  useEffect(() => { const f = () => { setRoute(parse()); window.scrollTo({ top: 0 }) }; window.addEventListener('hashchange', f); return () => window.removeEventListener('hashchange', f) }, [])
  const go = (page, arg) => { location.hash = arg ? `${page}/${arg}` : page }

  const startScan = async () => {
    try { await api('/api/scan', {}) } catch (e) { return toast.error("Couldn't start a scan", { description: e.message }) }
    const id = toast.loading('Scanning every career page…', { description: 'SimplifyJobs, SmartRecruiters, Greenhouse, Lever, Ashby, Workday' })
    let misses = 0
    const tick = async () => {
      let s
      try { s = await api('/api/scan'); misses = 0 } catch (e) {   // a restart mid-scan: keep checking a while, never spin forever
        if (++misses < 20) return setTimeout(tick, 3000)
        return toast.error('Lost track of the scan', { id, description: 'It may still be running. New jobs show up in Jobs when it finishes.' })
      }
      setScan(s)
      const st = s.stats || {}
      if (s.running) {
        toast.loading(`Read ${(st.fetched || 0).toLocaleString()} postings`, { id, description: `${st.done || 0} of ${st.sources || '…'} sources · ${st.new || 0} new` })
        return setTimeout(tick, 1000)
      }
      if (st.new) toast.success(`${st.new.toLocaleString()} new jobs, ${(st.matched || 0).toLocaleString()} fit you`, { id, description: `${(st.fetched || 0).toLocaleString()} postings read from ${st.sources || 0} sources` })
      else toast.success("You're up to date", { id, description: `Read ${(st.fetched || 0).toLocaleString()} postings. Nothing new since your last scan; new roles appear here as companies post them.` })
      refresh(); loadJobs()
    }
    tick()
  }
  const actions = [['Scan for new jobs', Radar, startScan], ['Open Resume Studio', FileText, () => go('studio')],
    ['Import a resume', Upload, () => go('studio', 'import')], ['Connect Claude or Codex', Play, () => go('agents')]]

  if (!state && loadErr) return (
    <div className="grid h-full place-items-center px-6 text-center">
      <div><div className="text-[22px] font-semibold text-white">ApplyTwin isn't answering</div>
        <p className="mt-2 text-[15px] text-muted">It may be restarting after an update. {loadErr}</p>
        <button onClick={refresh} className="mt-6 h-9 rounded-full bg-signal px-5 text-[14px] font-medium text-white">Try again</button></div>
    </div>)
  if (!state || !authReady) return <Loading />
  if (!auth.signed_in && auth.required !== false) return <SignInGate signIn={signIn} />
  const Page = PAGES[route.page]
  return (
    <Ctx.Provider value={{ ...state, refresh, go, jobs, loadJobs, startScan, scan, setState, auth, signIn, signOut }}>
      {route.page !== 'welcome' && (wide   // only the layout on screen is mounted, so nothing polls twice
        ? <Sidebar page={route.page} go={go} onPalette={() => setPalette(true)} auth={auth} signIn={signIn} signOut={signOut} />
        : <><TopBar page={route.page} go={go} onPalette={() => setPalette(true)} matched={state.stats?.matched} auth={auth} signIn={signIn} signOut={signOut} /><TabBar page={route.page} go={go} /></>)}
      <Palette open={palette} setOpen={setPalette} go={go} jobs={jobs} actions={actions} />
      {route.page !== 'welcome' && <HelpChat />}
      <motion.main key={route.page} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.2, ease: 'easeOut' }}
        className={'relative min-h-full ' + (route.page !== 'welcome' ? 'md:pl-[220px]' : '')}>
        <Page arg={route.arg} />
      </motion.main>
      <Toaster theme="dark" position="bottom-center" offset={wide ? 24 : 80} toastOptions={{ style: { borderRadius: 14, background: '#2c2c2e', border: '1px solid rgb(255 255 255 / .08)', color: '#fff' } }} />
    </Ctx.Provider>
  )
}

/* Everyone signs in with Google before using ApplyTwin: their setup is saved to their account (so a new laptop or a
   reinstall picks up where they left off), and it's how we know who uses it. */
function SignInGate({ signIn }) {
  const [busy, setBusy] = useState(false)
  const go = async () => { setBusy(true); try { await signIn() } catch (e) { setBusy(false); toast.error("Couldn't reach Google. Check your internet and try again.") } }
  return (
    <div className="relative grid min-h-full place-items-center px-6 py-12">
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.25, ease: 'easeOut' }}
        className="relative w-full max-w-[380px] text-center">
        <div className="flex justify-center"><Logo size={48} /></div>
        <h1 className="mt-6 text-[26px] font-bold leading-tight tracking-[-0.02em] text-white">Sign in to ApplyTwin</h1>
        <p className="mx-auto mt-2 max-w-[340px] text-[15px] leading-relaxed text-muted">Your setup, answers and applications are saved to your account, so nothing is lost if you switch laptops.</p>
        <button onClick={go} disabled={busy}
          className="mx-auto mt-8 flex h-11 w-full items-center justify-center gap-2.5 rounded-[10px] bg-white text-[15px] font-medium text-[#1d1d1f] transition-colors hover:bg-white/90 disabled:opacity-60">
          <svg viewBox="0 0 48 48" className="size-5" aria-hidden><path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z"/><path fill="#FF3D00" d="m6.3 14.7 6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"/><path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-7.9l-6.5 5C9.5 39.6 16.2 44 24 44z"/><path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z"/></svg>
          {busy ? 'Opening Google…' : 'Continue with Google'}
        </button>
        <div className="card mt-8 divide-y divide-line text-left">
          {[['Why sign in', 'Your setup and every application you send are backed up and open on any device at apply.twinly.tech.'],
            ['What we see', 'Your name and email from Google. Not your inbox, contacts or files.'],
            ['What we never do', 'Sell or share your data, post anything, or email anyone as you.']].map(([h, t]) => (
            <div key={h} className="px-4 py-3"><div className="text-[13px] font-medium text-white">{h}</div><div className="mt-0.5 text-[12.5px] leading-snug text-muted">{t}</div></div>))}
        </div>
        <p className="mt-4 text-[12px] text-faint">ApplyTwin is free and open source.</p>
      </motion.div>
    </div>
  )
}

function Loading() {
  return <div className="grid h-full place-items-center"><div className="size-6 animate-spin rounded-full border-2 border-white/15 border-t-white/70" /></div>
}

export function Page({ children }) {   // one width everywhere, so every page's title sits in the same spot
  return <div className={`relative mx-auto px-4 pb-28 pt-[76px] sm:px-6 md:pb-24 md:px-10 md:pt-[72px] max-w-[1120px]`}>{children}</div>
}

