import { useEffect, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { api } from '../lib/api'

const LABEL = { claude: 'Claude Code', codex: 'Codex' }
const SITE = { claude: 'Claude', codex: 'ChatGPT' }

// Get Claude Code or Codex ready from inside the app: it installs the agent if it's missing, then opens its sign-in in the
// browser and notices the moment you're done. No terminal.
export function AgentConnect({ name, st, onChange, compact }) {
  const [asked, setAsked] = useState(false)
  const busy = st?.connecting && st.connecting.step !== 'failed'
  useEffect(() => {   // while it's installing or waiting on the browser sign-in, check every two seconds
    if (!(busy || asked) || st?.signed_in) return
    const t = setInterval(onChange, 2000)
    return () => clearInterval(t)
  }, [busy, asked, st?.signed_in, onChange])
  useEffect(() => { if (st?.signed_in && asked) { toast.success(`${LABEL[name]} is signed in`); setAsked(false) } }, [st?.signed_in, asked, name])
  if (!st || st.signed_in) return null
  const go = async e => {
    e?.stopPropagation()
    try { await api(`/api/agents/${name}/connect`, {}); setAsked(true); onChange() } catch (err) { toast.error(err.message) }
  }
  const step = st.connecting?.step
  if (step === 'installing') return <Note busy>Installing {LABEL[name]}… this takes about a minute.</Note>
  if (step === 'signing_in') return <Note busy>Finish signing in to {SITE[name]} in the browser tab that just opened.</Note>
  return (
    <div className={compact ? '' : 'mt-3'}>
      {step === 'failed' && <div className="mb-2 text-[12.5px] text-[#ff9f0a]">{st.connecting.error}</div>}
      <span role="button" tabIndex={0} onClick={go} onKeyDown={e => e.key === 'Enter' && go(e)}
        className="inline-flex h-8 cursor-pointer items-center rounded-full bg-signal px-4 text-[13px] font-semibold text-white hover:brightness-110">
        {!st.installed ? 'Install and sign in' : `Sign in with ${SITE[name]}`}</span>
    </div>)
}

function Note({ children, busy }) {
  return <div className="mt-3 flex items-center gap-2 text-[12.5px] text-muted">{busy && <Loader2 className="size-3.5 animate-spin" />}{children}</div>
}
