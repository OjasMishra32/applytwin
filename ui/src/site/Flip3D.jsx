import { useMemo, useRef } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import { paperTexture } from './paper'

/* Step 02: one sheet of paper, the same person. As you scroll it turns over, and each side it shows is that resume
   rewritten for the next company: the lines that changed are tinted blue. stage runs 0 -> 2 (Google, NVIDIA, Jane Street). */

const W = 0.85, H = 1.1
const clamp = v => Math.min(1, Math.max(0, v))

function Sheet({ stage, pointer, versions }) {
  const ref = useRef()
  const tex = useMemo(() => versions.map(([c, f]) => paperTexture(c, f)), [versions])
  const mats = useMemo(() => {
    const edge = new THREE.MeshStandardMaterial({ color: '#ececef', roughness: 0.8 })
    const face = new THREE.MeshStandardMaterial({ map: tex[0], emissiveMap: tex[0], emissive: '#ffffff', emissiveIntensity: 0.5, roughness: 0.6 })
    const back = new THREE.MeshStandardMaterial({ map: tex[1], emissiveMap: tex[1], emissive: '#ffffff', emissiveIntensity: 0.5, roughness: 0.6 })
    return [edge, edge, edge, edge, face, back]
  }, [tex])
  useFrame(({ clock }) => {
    const s = stage.current
    const m = ref.current
    // the front shows Google until it is turned away, then Jane Street; the back always shows NVIDIA
    const want = s < 1 ? tex[0] : tex[2]
    if (mats[4].map !== want) { mats[4].map = want; mats[4].emissiveMap = want; mats[4].needsUpdate = true }
    const turning = Math.sin(Math.PI * (s % 1))   // 0 at rest, 1 mid-turn
    m.rotation.y = -Math.PI * s + pointer.current.x * 0.12
    m.rotation.x = -0.08 + pointer.current.y * 0.06 - turning * 0.05
    m.position.z = turning * 0.08
    m.position.y = Math.sin(clock.elapsedTime * 0.9) * 0.012
  })
  return <mesh ref={ref} material={mats}><boxGeometry args={[W, H, 0.006]} /></mesh>
}

export default function Flip3D({ stage, versions }) {
  const pointer = useRef({ x: 0, y: 0 })
  return (
    <div className="h-full w-full" onPointerMove={e => {
      const r = e.currentTarget.getBoundingClientRect()
      pointer.current = { x: ((e.clientX - r.left) / r.width - 0.5) * 2, y: -((e.clientY - r.top) / r.height - 0.5) * 2 }
    }} onPointerLeave={() => { pointer.current = { x: 0, y: 0 } }}>
      <Canvas flat dpr={[1, 2]} camera={{ position: [0, 0, 2.15], fov: 34 }} gl={{ antialias: true, alpha: true }}>
        <ambientLight intensity={1.3} />
        <directionalLight position={[-2, 3, 3]} intensity={1.1} />
        <directionalLight position={[2.5, -1, 2]} intensity={0.3} />
        <Sheet stage={stage} pointer={pointer} versions={versions} />
      </Canvas>
    </div>
  )
}
