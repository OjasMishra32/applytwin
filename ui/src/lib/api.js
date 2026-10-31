export async function api(path, body) {
  let r, j
  try { r = await fetch(path, body === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }) }
  catch { throw new Error("Can't reach ApplyTwin. It may be restarting; if this keeps happening, type applytwin in a terminal to start it.") }
  try { j = await r.json() }   // a half-restarted server or a proxy page answers with HTML, not JSON
  catch { throw new Error(`ApplyTwin sent an unexpected answer (${r.status}). It may be restarting after an update; try again in a few seconds.`) }
  if (j && j.error) throw Object.assign(new Error(j.error), { server: true })   // vs the app being unreachable
  if (!r.ok) throw Object.assign(new Error(`Something went wrong (${r.status}). Try again.`), { server: true })
  return j
}
/* Links from job boards or the agent: only real web pages, never javascript: or other schemes. */
export const safeUrl = u => (/^https?:\/\//i.test(u || '') ? u : undefined)
export const fileUrl = p => '/file?path=' + encodeURIComponent(p)
