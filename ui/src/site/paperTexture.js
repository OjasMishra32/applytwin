import * as THREE from 'three'
import { paperCanvas } from './paper'

// The resume canvas as a three.js texture. Kept apart from paper.js so the page's main bundle never pulls in three.js:
// only the lazily loaded 3D scenes import this.
export function paperTexture(company, fit) {
  const t = new THREE.CanvasTexture(paperCanvas(company, fit))
  t.colorSpace = THREE.SRGBColorSpace
  t.anisotropy = 16
  return t
}
