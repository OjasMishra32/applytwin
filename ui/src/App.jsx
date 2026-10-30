import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { Toaster, toast } from 'sonner'
import { Radar, Sparkles, FileText, Upload } from 'lucide-react'
import { api } from './lib/api'
import { TopBar, Palette } from './components/Shell'
import { Sky } from './components/Sky'
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

export default function App() {
  const parse = () => { const raw = location.hash.slice(1); if (raw.includes('access_token=')) return { page: 'home' }; const [p, arg] = (raw || 'home').split('/'); return { page: PAGES[p] ? p : 'home', arg } }
  const [route, setRoute] = useState(parse)
  const [state, setState] = useState(null)
  const [palette, setPalette] = useState(false)
  const [jobs, setJobs] = useState([])
  const [scan, setScan] = useState(null)

  const [auth, setAuth] = useState({ signed_in: false })
  const refresh = useCallback(async () => { const s = await api('/api/state'); setState(s); return s }, [])
  useEffect(() => {
    const h = location.hash
    if (h.includes('access_token=')) {
      const q = new URLSearchParams(h.slice(1))
      history.replaceState(null, '', location.pathname + '#home')
      api('/api/auth', { access_token: q.get('access_token'), refresh_token: q.get('refresh_token'), expires_in: q.get('expires_in') })
        .then(r => { setAuth(r); toast.success(`Signed in${r.user?.email ? ' as ' + r.user.email : ''}`, { description: r.restored ? 'Restored your vault from the cloud.' : 'Your vault now syncs to your account.' }); refresh() })
        .catch(e => toast.error('Sign-in failed: ' + e.message))
    } else api('/api/auth').then(setAuth)
  }, [refresh])
  const signIn = async () => { const r = await api('/api/auth/login?redirect=' + encodeURIComponent(location.origin + '/')); location.href = r.url }
  const signOut = async () => { setAuth(await api('/api/auth/logout', {})); toast('Signed out') }
  useEffect(() => { if (state && (!location.hash || location.hash === '#home') && !(state.vault?.experience?.length || state.vault?.projects?.length)) location.hash = 'welcome' }, [state])
  const loadJobs = useCallback(() => api('/api/jobs?limit=200').then(setJobs), [])
  useEffect(() => { refresh(); loadJobs() }, [refresh, loadJobs])
  useEffect(() => { const f = () => { setRoute(parse()); window.scrollTo({ top: 0 }) }; window.addEventListener('hashchange', f); return () => window.removeEventListener('hashchange', f) }, [])
  const go = (page, arg) => { location.hash = arg ? `${page}/${arg}` : page }

  const startScan = async () => {
    await api('/api/scan', {})
    const id = toast.loading('Scanning every career page…', { description: 'SimplifyJobs, SmartRecruiters, Greenhouse, Lever, Ashby, Workday' })
    const tick = async () => {
      const s = await api('/api/scan'); setScan(s)
      const st = s.stats || {}
      if (s.running) {
        toast.loading(`Read ${(st.fetched || 0).toLocaleString()} postings`, { id, description: `${st.done || 0} of ${st.sources || '…'} sources · ${st.new || 0} new` })
        return setTimeout(tick, 1000)
      }
      toast.success(`${st.new || 0} new jobs, ${st.matched || 0} strong matches`, { id, description: `${(st.fetched || 0).toLocaleString()} postings read` })
      refresh(); loadJobs()
    }
    tick()
  }
  const actions = [['Scan for new jobs', Radar, startScan], ['Open Resume Studio', FileText, () => go('studio')],
    ['Import a resume', Upload, () => go('studio', 'import')], ['Connect Claude or Codex', Sparkles, () => go('agents')]]

  if (!state) return <Loading />
  const Page = PAGES[route.page]
  return (
    <Ctx.Provider value={{ ...state, refresh, go, jobs, loadJobs, startScan, scan, setState, auth, signIn, signOut }}>
      {route.page !== 'welcome' && <TopBar page={route.page} go={go} onPalette={() => setPalette(true)} matched={state.stats?.matched} auth={auth} signIn={signIn} signOut={signOut} />}
      <Palette open={palette} setOpen={setPalette} go={go} jobs={jobs} actions={actions} />
      <motion.main key={route.page} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.25, ease: 'easeOut' }} className="relative min-h-full">
        <Page arg={route.arg} />
      </motion.main>
      <Toaster theme="dark" position="bottom-center" toastOptions={{ style: { borderRadius: 16, background: '#1c2033', border: '1px solid rgb(255 255 255 / .08)', color: '#fff' } }} />
    </Ctx.Provider>
  )
}

function Loading() {
  return <div className="grid h-full place-items-center"><motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1, ease: 'linear' }}
    className="size-7 rounded-full border-[3px] border-sky/25 border-t-sky" /></div>
}

export function Page({ children, wide }) {
  return <><Sky height={340} /><div className={`relative mx-auto px-6 pb-24 pt-24 ${wide ? 'max-w-[1320px]' : 'max-w-[1180px]'}`}>{children}</div></>
}

