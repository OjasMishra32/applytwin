import { useEffect, useState } from 'react'
import { Star } from 'lucide-react'

/* "Star ApplyTwin on GitHub", shared by the website and the app. Stars are how a free project like this gets found. */
export const REPO_URL = 'https://github.com/OjasMishra32/applytwin'

export function useStars() {
  const [n, setN] = useState(null)
  useEffect(() => {
    let cached = null
    try { cached = JSON.parse(sessionStorage.getItem('at:stars') || 'null') } catch {}
    if (cached && Date.now() - cached.t < 3600e3) { setN(cached.n); return }
    fetch('https://api.github.com/repos/OjasMishra32/applytwin').then(r => r.ok ? r.json() : null).then(d => {
      if (d && typeof d.stargazers_count === 'number') {
        setN(d.stargazers_count)
        try { sessionStorage.setItem('at:stars', JSON.stringify({ n: d.stargazers_count, t: Date.now() })) } catch {}
      }
    }).catch(() => {})
  }, [])
  return n
}

export function StarButton({ className = '', label = 'Star', compact, quiet }) {   // quiet: the app's toolbar, one neutral control
  const n = useStars()
  return (
    <a href={REPO_URL} target="_blank" rel="noreferrer" title="Star ApplyTwin on GitHub"
      className={(quiet ? 'inline-flex h-8 items-center gap-1.5 rounded-[8px] px-2.5 text-[13px] text-muted transition-colors hover:bg-white/[.06] hover:text-ink '
        : 'inline-flex h-8 items-center gap-1.5 rounded-full bg-white/[.08] px-3 text-[13px] font-medium text-white transition hover:bg-white/[.14] ') + className}>
      <Star className={quiet ? 'size-3.5' : 'size-3.5 fill-[#ffd60a] text-[#ffd60a]'} />
      {!compact && <span>{label}</span>}
      {n !== null && <span className={quiet ? 'tabular-nums' : 'tabular-nums text-white/60'}>{n.toLocaleString()}</span>}
    </a>
  )
}
