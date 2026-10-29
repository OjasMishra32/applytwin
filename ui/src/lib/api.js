export async function api(path, body) {
  const r = await fetch(path, body === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
  const j = await r.json()
  if (j && j.error) throw new Error(j.error)
  return j
}
export const fileUrl = p => '/file?path=' + encodeURIComponent(p)
