// Search setup for apply.twinly.tech, run by build-site.sh after the Vite build: real icon files (Google won't show a
// data: URI favicon), titles and share cards, structured data (app, site name, FAQ), a static copy of the page for
// crawlers that don't run JavaScript, keyword landing pages, robots.txt, sitemap.xml and llms.txt.
import { copyFileSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { FAQ } from '../../ui/src/site/faq.js'
import { PAGES, REPO, SITE } from './pages.mjs'

const HERE = dirname(fileURLToPath(import.meta.url))
const OUT = join(HERE, '..', '..', 'site')
const VERSION = readFileSync(join(HERE, '..', '..', 'VERSION'), 'utf8').trim()
const TODAY = new Date().toISOString().slice(0, 10)
const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
const ld = o => `<script type="application/ld+json">${JSON.stringify(o).replace(/</g, '\\u003c')}</script>`

for (const f of ['favicon.ico', 'logo.svg', 'icon-48.png', 'icon-96.png', 'icon-192.png', 'icon-512.png', 'apple-touch-icon.png', 'og.png'])
  copyFileSync(join(HERE, f), join(OUT, f))

const TITLE = 'ApplyTwin: Free AI Job Application Autopilot for Internships'
const DESC = 'ApplyTwin finds internships that fit you, writes a tailored one-page resume for every posting and fills out the application. Free, open source, runs on your own Claude Code or Codex. No API key.'

function head({ title, description, path }) {
  const url = SITE + path
  return `<title>${esc(title)}</title>
  <meta name="description" content="${esc(description)}" />
  <link rel="canonical" href="${url}" />
  <meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1" />
  <meta name="theme-color" content="#000000" />
  <link rel="icon" href="/favicon.ico" sizes="48x48" />
  <link rel="icon" href="/logo.svg" type="image/svg+xml" />
  <link rel="icon" href="/icon-192.png" type="image/png" sizes="192x192" />
  <link rel="apple-touch-icon" href="/apple-touch-icon.png" />
  <meta property="og:type" content="website" />
  <meta property="og:site_name" content="ApplyTwin" />
  <meta property="og:url" content="${url}" />
  <meta property="og:title" content="${esc(title)}" />
  <meta property="og:description" content="${esc(description)}" />
  <meta property="og:image" content="${SITE}/og.png" />
  <meta property="og:image:width" content="1200" />
  <meta property="og:image:height" content="630" />
  <meta property="og:image:alt" content="ApplyTwin: You apply once. Your twin does the rest." />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="${esc(title)}" />
  <meta name="twitter:description" content="${esc(description)}" />
  <meta name="twitter:image" content="${SITE}/og.png" />`
}

const ORG = { '@type': 'Organization', '@id': `${SITE}/#org`, name: 'ApplyTwin', url: SITE, logo: `${SITE}/icon-512.png`, sameAs: [REPO] }
const SITE_LD = { '@type': 'WebSite', '@id': `${SITE}/#website`, name: 'ApplyTwin', alternateName: ['Apply Twin', 'ApplyTwin by Twinly'], url: `${SITE}/`, publisher: { '@id': `${SITE}/#org` } }
const APP = {
  '@type': 'SoftwareApplication', '@id': `${SITE}/#app`, name: 'ApplyTwin', url: `${SITE}/`, image: `${SITE}/og.png`,
  applicationCategory: 'BusinessApplication', applicationSubCategory: 'Job search', operatingSystem: 'macOS, Windows, Linux',
  softwareVersion: VERSION, description: DESC, isAccessibleForFree: true, license: 'https://polyformproject.org/licenses/strict/1.0.0',
  offers: { '@type': 'Offer', price: '0', priceCurrency: 'USD' }, downloadUrl: `${SITE}/install.sh`, codeRepository: REPO,
  publisher: { '@id': `${SITE}/#org` },
}
const faqLd = items => ({ '@type': 'FAQPage', mainEntity: items.map(([q, a]) => ({ '@type': 'Question', name: q, acceptedAnswer: { '@type': 'Answer', text: a } })) })

// the home page: real head tags, structured data, and the page's own words in #root (React replaces it on load, so
// visitors see the designed page; crawlers that don't run JavaScript still read what it says)
const STATIC = `<main style="max-width:760px;margin:0 auto;padding:64px 20px;font-family:-apple-system,BlinkMacSystemFont,sans-serif;line-height:1.5">
  <h1>You apply once. Your twin does the rest.</h1>
  <p>ApplyTwin is a free app for your computer. It finds internships that fit you, writes a one-page resume for each posting and fills out the application. It runs on the Claude Code or Codex plan you already pay for.</p>
  <p>Install on Mac or Linux: <code>curl -fsSL apply.twinly.tech/install | bash</code>. On Windows: <code>irm apply.twinly.tech/install.ps1 | iex</code>.</p>
  <h2>Everything between you and Submit.</h2>
  <p>It finds roles that fit your resume, graduation date and work authorization; writes an honest, tailored one-page resume for each; fills the application on Greenhouse, Lever, Ashby, Workday, iCIMS and more; and stops on the review screen so you press Submit.</p>
  <h2>No API key. No new subscription.</h2>
  <p>ApplyTwin runs on your own Claude Code or Codex subscription. It is free and open source: <a href="${REPO}">${REPO.replace('https://', '')}</a>.</p>
  <h2>Questions.</h2>
  ${FAQ.map(([q, a]) => `<h3>${esc(q)}</h3><p>${esc(a)}</p>`).join('\n  ')}
  <nav><a href="/auto-apply-internships">Auto apply to internships</a> · <a href="/tailor-resume-to-job-description">Tailor your resume to a job description</a> · <a href="/open-source-job-application-bot">Open-source job application bot</a></nav>
</main>`

let html = readFileSync(join(OUT, 'index.html'), 'utf8')
html = html.replace(/<title>[\s\S]*?<link rel="icon"[^>]*>/, head({ title: TITLE, description: DESC, path: '/' }))
  .replace('</head>', `  <script>document.documentElement.className+=' js'</script><style>.js #root>main{visibility:hidden}</style>\n</head>`)
  .replace('</head>', `  ${ld({ '@context': 'https://schema.org', '@graph': [ORG, SITE_LD, APP, faqLd(FAQ)] })}\n</head>`)
  .replace('<div id="root"></div>', `<div id="root">${STATIC}</div>`)
if (!html.includes('rel="canonical"')) throw new Error('index.html head did not match; SEO tags not added')
writeFileSync(join(OUT, 'index.html'), html)

// the local app's page must never be indexed
const app = join(OUT, 'app.html')
try { writeFileSync(app, readFileSync(app, 'utf8').replace('<head>', '<head>\n  <meta name="robots" content="noindex" />')) } catch { }

// keyword landing pages: static, fast, the same look as the site
const CSS = `:root{color-scheme:light dark;--fg:#1d1d1f;--muted:#6e6e73;--bg:#fff;--card:#f5f5f7;--link:#0066cc}
@media (prefers-color-scheme:dark){:root{--fg:#f5f5f7;--muted:#a1a1a6;--bg:#000;--card:#161617;--link:#2997ff}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:17px/1.5 -apple-system,BlinkMacSystemFont,"SF Pro Text","Helvetica Neue",Arial,sans-serif}
a{color:var(--link);text-decoration:none}a:hover{text-decoration:underline}
header{max-width:980px;margin:0 auto;padding:18px 20px;display:flex;align-items:center;justify-content:space-between}
.brand{display:flex;align-items:center;gap:10px;color:var(--fg);font-weight:600;font-size:18px}
main{max-width:820px;margin:0 auto;padding:40px 20px 80px}
h1{font-size:clamp(36px,6vw,60px);line-height:1.05;letter-spacing:-.03em;margin:24px 0 20px}
.lede{font-size:21px;color:var(--muted);margin:0 0 32px}
h2{font-size:28px;letter-spacing:-.02em;margin:48px 0 10px}h3{font-size:19px;margin:28px 0 6px}
.install{background:var(--card);border-radius:14px;padding:18px 20px;margin:28px 0;font:15px ui-monospace,SFMono-Regular,Menlo,monospace;overflow-x:auto}
.install div+div{margin-top:8px;color:var(--muted)}
.cta{display:inline-block;background:#0071e3;color:#fff;border-radius:980px;padding:12px 24px;font-weight:500;margin-top:8px}
.cta:hover{text-decoration:none;background:#0077ed}
footer{max-width:820px;margin:0 auto;padding:24px 20px 60px;color:var(--muted);font-size:14px;border-top:1px solid color-mix(in srgb,var(--muted) 25%,transparent)}
footer a{margin-right:18px}`

for (const p of PAGES) {
  const faq = p.faq.map(i => FAQ[i])
  const crumbs = { '@type': 'BreadcrumbList', itemListElement: [
    { '@type': 'ListItem', position: 1, name: 'ApplyTwin', item: `${SITE}/` },
    { '@type': 'ListItem', position: 2, name: p.h1, item: SITE + p.path }] }
  const page = `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  ${head(p)}
  <style>${CSS}</style>
  ${ld({ '@context': 'https://schema.org', '@graph': [ORG, SITE_LD, { ...APP, '@id': undefined, url: `${SITE}/` }, crumbs, faqLd(faq)] })}
</head>
<body>
  <header><a class="brand" href="/"><img src="/logo.svg" width="28" height="28" alt="" />ApplyTwin</a><a href="${REPO}">GitHub</a></header>
  <main>
    <h1>${esc(p.h1)}</h1>
    <p class="lede">${esc(p.lede)}</p>
    <div class="install"><div>curl -fsSL apply.twinly.tech/install | bash</div><div>Windows: irm apply.twinly.tech/install.ps1 | iex</div></div>
    <a class="cta" href="/">See how ApplyTwin works</a>
    ${p.sections.map(([h, t]) => `<h2>${esc(h)}</h2>\n    <p>${esc(t)}</p>`).join('\n    ')}
    <h2>Questions</h2>
    ${faq.map(([q, a]) => `<h3>${esc(q)}</h3>\n    <p>${esc(a)}</p>`).join('\n    ')}
  </main>
  <footer><a href="/">Home</a>${PAGES.filter(x => x !== p).map(x => `<a href="${x.path}">${esc(x.title.split(' | ')[0])}</a>`).join('')}<a href="${REPO}">Source code</a></footer>
</body>
</html>
`
  writeFileSync(join(OUT, p.path.slice(1) + '.html'), page)
}

writeFileSync(join(OUT, 'robots.txt'), `User-agent: *\nAllow: /\nDisallow: /app\n\nSitemap: ${SITE}/sitemap.xml\n`)
writeFileSync(join(OUT, 'sitemap.xml'), `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${['/', ...PAGES.map(p => p.path)].map(u => `  <url><loc>${SITE}${u}</loc><lastmod>${TODAY}</lastmod><priority>${u === '/' ? '1.0' : '0.8'}</priority></url>`).join('\n')}
</urlset>
`)
writeFileSync(join(OUT, 'llms.txt'), `# ApplyTwin

> ${DESC}

ApplyTwin is a free, open-source job application autopilot for students looking for internships and new-grad roles. It runs locally (Mac, Windows, Linux) and uses the person's own Claude Code or Codex subscription; no API key.

- Finds internships that fit the user's resume, graduation date, work authorization and location, and skips ones they can't get.
- Writes a tailored one-page resume for each posting from the user's real experience; numbers, titles and employers are never changed.
- Fills applications on Greenhouse, Lever, Ashby, Workday, iCIMS, SmartRecruiters and Oracle in its own browser, and stops at the review screen unless the user turns on auto-submit.
- Never types passwords, solves CAPTCHAs, creates accounts or accepts legal agreements.

Install: \`curl -fsSL apply.twinly.tech/install | bash\` (Windows: \`irm apply.twinly.tech/install.ps1 | iex\`)

## Pages
- [Home](${SITE}/)
${PAGES.map(p => `- [${p.title.split(' | ')[0]}](${SITE}${p.path}): ${p.description}`).join('\n')}
- [Source code](${REPO})

## FAQ
${FAQ.map(([q, a]) => `- ${q} ${a}`).join('\n')}
`)
console.log(`seo: ${PAGES.length + 1} pages, icons, sitemap, robots, llms.txt`)
