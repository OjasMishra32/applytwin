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
/* A file picked in the app, as the server reads uploads: its name and its bytes in base64 (works for PDFs and Excel too). */
export async function fileBody(f) {
  const u = new Uint8Array(await f.arrayBuffer())
  let bin = ''
  for (let i = 0; i < u.length; i += 0x8000) bin += String.fromCharCode(...u.subarray(i, i + 0x8000))
  return { name: f.name, data: btoa(bin) }
}
/* Tracker files the import reads (applytwin/tracker.py ACCEPT). */
export const TRACKER_FILES = '.csv,.tsv,.txt,.xlsx,.xlsm,.ods,.pdf,.docx,.html,.htm,.md,.json,.numbers'
/* What the import said, as a toast. */
export function trackerToast(toast, r) {
  if (r.reading) return toast.success('Your twin is reading your tracker', { description: r.queued ? 'It starts as soon as the current run finishes, and adds every application it finds.' : r.note })
  toast.success(`Found ${r.known_applications.toLocaleString()} applications`, { description: `${r.matched.toLocaleString()} matched jobs in your queue, so your twin won't apply to them again.` })
}
