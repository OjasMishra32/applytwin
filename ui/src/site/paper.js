/* A real one-page resume, drawn onto a canvas for the 3D scenes: Elon Musk's public record, set the way ApplyTwin
   renders a page. A tailored version reorders and rewrites lines for one company; the rewritten lines are tinted blue. */

const ROLES = {
  tesla: ['Tesla', 'CEO and Product Architect', '2008 – Present'],
  spacex: ['SpaceX', 'Founder, CEO and CTO', '2002 – Present'],
  paypal: ['X.com / PayPal', 'Co-founder', '1999 – 2002'],
  zip2: ['Zip2', 'Co-founder', '1995 – 1999'],
}
const BULLETS = {
  tesla: ['Scaled Tesla to millions of electric vehicles a year.', 'Took Model S, 3, X and Y from concept to volume production.',
    'Built Gigafactories in Nevada, Shanghai, Berlin and Texas.'],
  spacex: ['Falcon 9: first orbital-class rocket to land and reuse its first stage.',
    'Dragon: first private spacecraft to fly astronauts to the ISS, in 2020.', 'Starlink: thousands of satellites in low Earth orbit.'],
  paypal: ['Merged X.com with Confinity to form PayPal, sold to eBay for $1.5B.'],
  zip2: ['Built online city guides for newspapers; sold to Compaq for $307M.'],
}
// what each tailored version leads with: role order, which bullets, which lines were rewritten for it
export const VERSIONS = {
  base: { sub: 'Entrepreneur · Engineer', order: ['tesla', 'spacex', 'paypal', 'zip2'], pick: { tesla: [0, 1], spacex: [0, 1], paypal: [0], zip2: [0] }, hi: [],
    skills: 'Physics · Economics · Product · Manufacturing' },
  Google: { sub: 'Large-Scale Systems · Software · Product', order: ['tesla', 'spacex', 'paypal', 'zip2'], pick: { tesla: [0, 1], spacex: [2, 0], paypal: [0], zip2: [0] },
    hi: ['tesla1', 'spacex2', 'zip20'], skills: 'Distributed systems · Product engineering · Hiring and scaling teams' },
  NVIDIA: { sub: 'Autonomy · AI Compute · Hardware', order: ['tesla', 'spacex', 'paypal', 'zip2'], pick: { tesla: [1, 0], spacex: [0, 1], paypal: [0], zip2: [0] },
    hi: ['tesla1', 'spacex0', 'spacex1'], skills: 'Autonomy · Real-time control · Hardware and software co-design' },
  'Jane Street': { sub: 'Payments · Markets · Economics', order: ['paypal', 'zip2', 'tesla', 'spacex'], pick: { tesla: [0, 2], spacex: [0, 2], paypal: [0], zip2: [0] },
    hi: ['paypal0', 'zip20', 'tesla0'], skills: 'Economics (Wharton) · Physics · Risk and capital allocation' },
}

function wrap(g, text, x, y, max, lh) {
  const words = text.split(' '); let line = ''
  for (const w of words) {
    const t = line ? line + ' ' + w : w
    if (g.measureText(t).width > max && line) { g.fillText(line, x, y); line = w; y += lh } else line = t
  }
  g.fillText(line, x, y)
  return y + lh
}

export function paperCanvas(company, fit) {
  const v = !company ? VERSIONS.base : VERSIONS[company] || { ...VERSIONS.Google, sub: `Tailored for ${company}` }
  const c = document.createElement('canvas')
  c.width = 1020; c.height = 1320
  const g = c.getContext('2d')
  const serif = 'Georgia, "Times New Roman", serif', sans = '-apple-system, "Helvetica Neue", Helvetica, Arial, sans-serif'
  g.fillStyle = '#ffffff'; g.fillRect(0, 0, c.width, c.height)
  const L = 84, R = c.width - 84
  g.textAlign = 'center'; g.fillStyle = '#111'; g.font = `bold 58px ${serif}`
  g.fillText('ELON MUSK', c.width / 2, 132)
  g.fillStyle = company ? '#0058b9' : '#444'; g.font = `600 25px ${sans}`
  g.fillText(v.sub, c.width / 2, 178)
  g.fillStyle = '#888'; g.font = `22px ${sans}`
  g.fillText('Austin, TX  ·  x.com/elonmusk  ·  University of Pennsylvania', c.width / 2, 214)
  let y = 276
  const head = t => {
    g.textAlign = 'left'; g.fillStyle = '#111'; g.font = `bold 23px ${serif}`
    g.fillText(t, L, y); g.fillRect(L, y + 11, R - L, 2); y += 50
  }
  const entry = (a, b, date) => {
    g.textAlign = 'left'; g.fillStyle = '#111'; g.font = `bold 23px ${serif}`; g.fillText(a, L, y)
    const w = g.measureText(a).width
    g.font = `italic 22px ${serif}`; g.fillStyle = '#444'; g.fillText(b, L + w + 14, y)
    g.textAlign = 'right'; g.font = `21px ${serif}`; g.fillStyle = '#666'; g.fillText(date, R, y)
    y += 34
  }
  const bullet = (text, hi) => {
    g.textAlign = 'left'; g.font = `21px ${serif}`
    if (hi) {
      // measure the wrapped height first so the tint sits behind every line of it
      const lines = Math.ceil(g.measureText(text).width / (R - L - 34)) || 1
      g.fillStyle = 'rgba(0,113,227,0.11)'; g.beginPath(); g.roundRect(L + 14, y - 24, R - L - 10, lines * 30 + 8, 6); g.fill()
    }
    g.fillStyle = hi ? '#0071e3' : '#333'; g.fillText('•', L + 22, y)
    g.fillStyle = '#222'
    y = wrap(g, text, L + 44, y, R - L - 50, 31) + 8
  }
  head('EDUCATION')
  entry('University of Pennsylvania', 'B.S. Economics, B.A. Physics', '1997')
  y += 24
  head('EXPERIENCE')
  for (const k of v.order) {
    entry(...ROLES[k])
    for (const i of v.pick[k]) bullet(BULLETS[k][i], v.hi.includes(k + i))
    y += 22
  }
  y += 8
  head('PROJECTS')
  entry('Neuralink', 'Co-founder', '2016'); entry('The Boring Company', 'Founder', '2016'); entry('OpenAI', 'Co-founder', '2015')
  y += 24
  head('SKILLS')
  g.textAlign = 'left'; g.font = `21px ${serif}`; g.fillStyle = '#222'; wrap(g, v.skills, L, y, R - L, 30)
  if (company && fit) {
    g.fillStyle = fit >= 96 ? '#248a3d' : '#0071e3'
    g.beginPath(); g.roundRect(c.width - 238, 34, 186, 50, 25); g.fill()
    g.fillStyle = '#fff'; g.font = `700 25px ${sans}`; g.textAlign = 'center'
    g.fillText(`${fit}% match`, c.width - 145, 68)
  }
  return c
}
