"""Click through the whole app in a real Windows browser, the way a person on a Windows laptop sees it (display scaling
125-150%, Chrome and Edge), and record everything that looks or acts broken: console errors, failed requests, pages wider
than the window, text cut off inside its box, and a screenshot of every page and every state a button opens.

Runs against the installed app (see .github/workflows/win-stress.yml). Never presses anything that applies, submits,
deletes or signs out.

    python tests/win_ui.py <out-dir>
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, ValueError):
        pass

OUT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else 'ui-out')
os.makedirs(OUT, exist_ok=True)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_DIR = os.environ.get('APPLYTWIN_DIR') or os.path.join(os.path.expanduser('~'), '.applytwin-app')
DATA = os.path.join(os.path.expanduser('~'), '.applytwin')
BASE = 'http://localhost:4747'
PAGES = ['home', 'jobs', 'studio', 'answers', 'board', 'agents', 'settings', 'welcome']
# never pressed: anything that applies, submits, deletes, signs out, installs or starts work
UNSAFE = re.compile(r'apply|submit|start|launch|run|delete|remove|clear|reset|forget|skip|sign|log ?out|restore|update|install|'
                    r'import|send|finish|refill|stop|connect|scan|find|tailor|generate|upload|save|done|accept|yes|confirm', re.I)
VIEWS = [('laptop-150', 'chrome', 1280, 720, 1.5), ('laptop-125', 'chrome', 1536, 864, 1.25), ('edge-100', 'msedge', 1366, 768, 1)]


def post(path, body):
    r = urllib.request.Request(BASE + path, data=json.dumps(body).encode(), method='POST',
                               headers={'Origin': BASE, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(r, timeout=120) as resp:
        return json.loads(resp.read() or b'null')


def up(t=90):
    for _ in range(t):
        try:
            urllib.request.urlopen(BASE + '/api/stats', timeout=2)
            return True
        except Exception:
            time.sleep(1)
    return False


def seed():
    os.makedirs(DATA, exist_ok=True)
    prof = json.load(open(os.path.join(ROOT, 'examples', 'profile.example.json'), encoding='utf-8'))
    prof['onboarded'] = True
    prof.setdefault('apply', {})['auto_update'] = False
    json.dump(prof, open(os.path.join(DATA, 'profile.json'), 'w', encoding='utf-8'))
    py = sys.executable
    pyw = os.path.join(os.path.dirname(py), 'pythonw.exe')
    subprocess.Popen([pyw if os.path.exists(pyw) else py, os.path.join(APP_DIR, 'bin', 'applytwin'), 'app', '--no-open'],
                     cwd=os.path.expanduser('~'), env={**os.environ, 'APPLYTWIN_SKIP_SIGNIN': '1', 'APPLYTWIN_NO_TELEMETRY': '1'},
                     creationflags=0x00000008 | 0x00000200)
    assert up(), 'app never started'
    post('/api/vault', json.load(open(os.path.join(ROOT, 'examples', 'resume.example.json'), encoding='utf-8')))
    jobs = [('https://boards.greenhouse.io/anduril/jobs/4810001?gh_src=x&t=1', 'Software Engineering Intern, Embedded (Summer 2027)', 'Anduril Industries',
             'C++, embedded Linux, RTOS, CAN bus, robotics. Build firmware for autonomous systems. ' * 6),
            ('https://jobs.lever.co/shieldai/ac38d092-0000', 'Summer 2027 Intern - Embedded Firmware - 5810', 'Shield AI',
             'Bare-metal firmware in C/C++, CI, unit testing, CMake, FPGA a plus. ' * 6),
            ('https://citadel.wd5.myworkdayjobs.com/en-US/External/job/Chicago/Software-Engineer-Intern_R123?source=LinkedIn&utm=1',
             'Software Engineer Intern - Summer 2027 (with a deliberately long title to see whether it wraps or gets cut off)', 'Citadel',
             'Python, C++, distributed systems, low latency. ' * 6),
            ('https://careers.example.com/job/42', 'Data Analyst Intern', 'Fußball Club Cincinnati (FC Cincinnati) Ñandú Ünïcödé',
             'SQL, Python, Tableau, statistics. ' * 6)]
    for url, title, company, desc in jobs:
        try:
            post('/api/jobs', {'url': url, 'title': title, 'company': company, 'description': desc})
        except Exception as e:
            print('seed job failed:', e)


CHECK_JS = r"""() => {
  const out = {overflowX: document.documentElement.scrollWidth - innerWidth, cut: []}
  for (const e of document.querySelectorAll('body *')) {
    const s = getComputedStyle(e), r = e.getBoundingClientRect()
    if (!r.width || !r.height || s.visibility === 'hidden') continue
    const text = (e.innerText || '').trim()
    if (!text || e.children.length > 3) continue
    const clipsX = e.scrollWidth > e.clientWidth + 2 && /hidden|clip/.test(s.overflowX) && s.textOverflow !== 'ellipsis'
    const clipsY = e.scrollHeight > e.clientHeight + 2 && /hidden|clip/.test(s.overflowY) && !/-webkit-box/.test(s.display)
    const offRight = r.right > innerWidth + 1 && s.position !== 'fixed'
    if (clipsX || clipsY || offRight) out.cut.push({text: text.slice(0, 80), why: [clipsX && 'clipped sideways', clipsY && 'clipped vertically', offRight && 'past the right edge'].filter(Boolean).join(', '), tag: e.tagName.toLowerCase(), cls: (e.className || '').toString().slice(0, 60)})
  }
  out.cut = out.cut.slice(0, 25)
  return out
}"""


def main():
    from playwright.sync_api import sync_playwright
    seed()
    findings = []
    with sync_playwright() as pw:
        for name, channel, w, h, dpr in VIEWS:
            try:
                browser = pw.chromium.launch(channel=channel)
            except Exception as e:
                findings.append({'view': name, 'page': '-', 'kind': 'browser', 'detail': str(e)[:300]})
                continue
            ctx = browser.new_context(viewport={'width': w, 'height': h}, device_scale_factor=dpr)
            page = ctx.new_page()
            log = []
            page.on('console', lambda m: m.type == 'error' and log.append(('console', m.text[:300])))
            page.on('pageerror', lambda e: log.append(('crash', str(e)[:300])))
            page.on('response', lambda r: r.status >= 400 and '/api/' in r.url and log.append(('http', f'{r.status} {r.request.method} {r.url[len(BASE):]}')))
            page.on('requestfailed', lambda r: log.append(('failed', f'{r.method} {r.url[len(BASE):]} {r.failure}')))

            def note(pg, what):
                for kind, detail in log:
                    findings.append({'view': name, 'page': pg, 'kind': kind, 'detail': detail, 'after': what})
                log.clear()

            for pg in PAGES:
                page.goto(f'{BASE}/#{pg}')
                page.wait_for_timeout(2500)
                page.screenshot(path=os.path.join(OUT, f'{name}-{pg}.png'), full_page=True)
                lay = page.evaluate(CHECK_JS)
                if lay['overflowX'] > 1:
                    findings.append({'view': name, 'page': pg, 'kind': 'layout', 'detail': f"page is {lay['overflowX']}px wider than the window"})
                for c in lay['cut']:
                    findings.append({'view': name, 'page': pg, 'kind': 'layout', 'detail': f"{c['why']}: {c['text']!r} <{c['tag']} {c['cls']}>"})
                note(pg, 'load')
                if name != 'laptop-150':   # buttons once is enough; the other views are for layout
                    continue
                labels = []
                for b in page.query_selector_all('button, [role=button], a[href^="#"]'):
                    try:
                        t = (b.inner_text() or b.get_attribute('aria-label') or b.get_attribute('title') or '').strip()
                    except Exception:
                        continue
                    if t and len(t) < 60 and not UNSAFE.search(t) and t not in labels and b.is_visible():
                        labels.append(t)
                for i, t in enumerate(labels[:25]):
                    try:
                        page.goto(f'{BASE}/#{pg}')
                        page.wait_for_timeout(1200)
                        page.get_by_text(t, exact=True).first.click(timeout=4000)
                        page.wait_for_timeout(1500)
                        safe = re.sub(r'[^a-z0-9]+', '-', t.lower())[:30]
                        page.screenshot(path=os.path.join(OUT, f'{name}-{pg}-click-{i:02d}-{safe}.png'))
                        lay = page.evaluate(CHECK_JS)
                        for c in lay['cut']:
                            findings.append({'view': name, 'page': pg, 'kind': 'layout', 'detail': f"after '{t}': {c['why']}: {c['text']!r}"})
                        page.keyboard.press('Escape')
                    except Exception as e:
                        findings.append({'view': name, 'page': pg, 'kind': 'click', 'detail': f"'{t}': {str(e)[:160]}"})
                    note(pg, f"click '{t}'")
            # the resume as the app previews it, and the PDF link it offers
            try:
                page.goto(f'{BASE}/#studio')
                page.wait_for_timeout(6000)
                page.screenshot(path=os.path.join(OUT, f'{name}-studio-preview.png'), full_page=True)
                for fr in page.frames[1:]:
                    lay = fr.evaluate(CHECK_JS)
                    for c in lay['cut']:
                        findings.append({'view': name, 'page': 'studio-preview', 'kind': 'layout', 'detail': f"{c['why']}: {c['text']!r}"})
                note('studio', 'preview')
            except Exception as e:
                findings.append({'view': name, 'page': 'studio', 'kind': 'preview', 'detail': str(e)[:300]})
            browser.close()
    json.dump(findings, open(os.path.join(OUT, 'findings.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    seen = set()
    for f in findings:
        k = (f['page'], f['kind'], f['detail'])
        if k not in seen:
            seen.add(k)
            print(f"[{f['view']}] {f['page']:8} {f['kind']:7} {f['detail']}" + (f"   (after {f['after']})" if f.get('after') not in (None, 'load') else ''))
    print(f'\n{len(seen)} distinct findings, {len(os.listdir(OUT)) - 1} screenshots in {OUT}')


main()
