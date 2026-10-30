export async function api(path, body) {
  const r = await fetch(path, body === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
  const j = await r.json()
  if (j && j.error) throw Object.assign(new Error(j.error), { server: true })   // vs the app being unreachable
  return j
}
/* Links from job boards or the agent: only real web pages, never javascript: or other schemes. */
export const safeUrl = u => (/^https?:\/\//i.test(u || '') ? u : undefined)
export const fileUrl = p => '/file?path=' + encodeURIComponent(p)
