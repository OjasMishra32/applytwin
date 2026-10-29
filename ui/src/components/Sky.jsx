import { Shader } from './Shader'

/* The ApplyTwin backdrop: the live shader, fading into the page. */
export function Sky({ height = 640 }) {
  return (
    <div className="pointer-events-none absolute inset-x-0 top-0 overflow-hidden" style={{ height,
      maskImage: 'linear-gradient(180deg, #000 0%, #000 62%, transparent 100%)', WebkitMaskImage: 'linear-gradient(180deg, #000 0%, #000 62%, transparent 100%)' }}>
      <div className="absolute inset-0" style={{ background: 'radial-gradient(80% 60% at 30% 20%, #1450c8 0%, transparent 60%), radial-gradient(70% 60% at 80% 40%, #2a2a9e 0%, transparent 60%), linear-gradient(180deg,#020a24,#06205e 55%,#0d3fa8)' }} />
      <div className="absolute inset-0"><Shader /></div>
    </div>
  )
}

export function SkyStrip() { return null }
