import { useMemo, useRef } from 'react'
import { useInView } from 'motion/react'
import { Canvas, useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import { paperTexture } from './paperTexture'

/* One resume becomes many: real paper sheets in studio light. Scrolled from 0 to 1, a single stack (your resume) fans out
   into an arc of versions, each tailored for one company, while the camera eases in. The pointer tilts the scene a little. */

const COMPANIES = [['Jane Street', 96], ['NVIDIA', 95], ['Google', 98], ['Meta', 96], [null, 0], ['Citadel', 94], ['Palantir', 97], ['Anduril', 94], ['Stripe', 95]]
const W = 0.85, H = 1.1   // a letter-size page, in scene units

const clamp = v => Math.min(1, Math.max(0, v))
const ease = t => 1 - Math.pow(1 - t, 3)

function Sheet({ i, n, company, fit, progress, pointer }) {
  const ref = useRef()
  const mats = useMemo(() => {
    const edge = new THREE.MeshStandardMaterial({ color: '#f2f2f4', roughness: 0.7 })
    const map = paperTexture(company, fit)
    const face = new THREE.MeshStandardMaterial({ map, emissiveMap: map, emissive: '#ffffff', emissiveIntensity: 0.45, roughness: 0.6 })
    const back = new THREE.MeshStandardMaterial({ color: '#fafafa', roughness: 0.7 })
    return [edge, edge, edge, edge, face, back]
  }, [company, fit, i])
  const mid = (n - 1) / 2
  const a = (i - mid) * 0.3
  useFrame(() => {
    const s = progress.current
    const t = ease(clamp(s * 1.35 - Math.abs(i - mid) * 0.06))
    const R = 2.2
    // stacked (a neat ream, your resume on top) -> fanned (an arc of tailored versions around you)
    const sx = 0, sy = -Math.abs(i - mid) * 0.008, sz = -Math.abs(i - mid) * 0.02
    const fx = Math.sin(a) * R, fy = 0.04 * Math.cos(a * 2) - 0.02, fz = (Math.cos(a) - 1) * R
    const m = ref.current
    m.position.set(sx + (fx - sx) * t, sy + (fy - sy) * t, sz + (fz - sz) * t + (i === Math.round(mid) ? 0.04 : 0))
    m.rotation.set(-0.06 * t, -a * t * 0.92 + pointer.current.x * 0.05, (i - mid) * 0.012 * (1 - t))
  })
  return <mesh ref={ref} castShadow receiveShadow material={mats}><boxGeometry args={[W, H, 0.004]} /></mesh>
}

function Rig({ progress, pointer }) {
  useFrame(({ camera, size }) => {
    const s = ease(clamp(progress.current))
    const back = Math.max(1, 0.95 / (size.width / size.height))   // narrow (phone) screens step back to see the whole fan
    camera.position.x += ((pointer.current.x * 0.25) - camera.position.x) * 0.05
    camera.position.y += ((0.12 + pointer.current.y * 0.12) - camera.position.y) * 0.05
    camera.position.z = (3.0 + s * 0.15) * back
    camera.lookAt(0, 0.02, -0.3 * s)
  })
  return null
}

export default function Fan3D({ progress }) {
  const pointer = useRef({ x: 0, y: 0 })
  const box = useRef(null)
  const seen = useInView(box, { margin: '100px 0px' })   // stop drawing frames while the scene is off screen
  return (
    <div ref={box} className="h-full w-full" onPointerMove={e => {
      const r = e.currentTarget.getBoundingClientRect()
      pointer.current = { x: ((e.clientX - r.left) / r.width - 0.5) * 2, y: -((e.clientY - r.top) / r.height - 0.5) * 2 }
    }}>
      <Canvas frameloop={seen ? 'always' : 'never'} shadows flat dpr={[1, 2]} camera={{ position: [0, 0.12, 3.9], fov: 30 }} gl={{ antialias: true, alpha: true }}>
        <ambientLight intensity={1.4} />
        <hemisphereLight args={['#ffffff', '#e4e7ee', 0.45]} />
        <directionalLight position={[-2.5, 4, 3]} intensity={1.25} castShadow shadow-mapSize={[2048, 2048]} shadow-radius={8}
          shadow-camera-left={-4} shadow-camera-right={4} shadow-camera-top={4} shadow-camera-bottom={-4} />
        <directionalLight position={[3, 1, 2]} intensity={0.35} />
        {COMPANIES.map(([c, f], i) => <Sheet key={i} i={i} n={COMPANIES.length} company={c} fit={f} progress={progress} pointer={pointer} />)}
        <mesh rotation-x={-Math.PI / 2} position={[0, -H / 2 - 0.02, -0.6]} receiveShadow>
          <planeGeometry args={[14, 14]} /><shadowMaterial opacity={0.12} />
        </mesh>
        <Rig progress={progress} pointer={pointer} />
      </Canvas>
    </div>
  )
}
