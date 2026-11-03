"""Windows stress test, run on a real Windows machine after a real install (see .github/workflows/win-stress.yml).

Unlike the other tests it uses no stand-ins: the installed app, real Chrome as the twin's browser, the real Playwright
browser tool, and the real Claude Code CLI when it's installed. Every check runs even when an earlier one fails, and
the summary at the end lists them all.

    python tests/win_stress.py <scenario>
"""
import concurrent.futures
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, ValueError):
        pass

SCENARIO = sys.argv[1] if len(sys.argv) > 1 else 'local'
APP_DIR = os.environ.get('APPLYTWIN_DIR') or os.path.join(os.path.expanduser('~'), '.applytwin-app')
BASE = 'http://127.0.0.1:4747'
TWIN = 'http://127.0.0.1:9343'
NOWIN = {'creationflags': 0x08000000} if os.name == 'nt' else {}
results = []


def check(name):
    def wrap(f):
        t = time.time()
        try:
            detail = f()
            results.append((True, name, detail or ''))
            print(f'PASS  {name}  {detail or ""}  ({time.time() - t:.1f}s)', flush=True)
        except Exception as e:
            results.append((False, name, f'{type(e).__name__}: {e}'))
            print(f'FAIL  {name}  {type(e).__name__}: {e}  ({time.time() - t:.1f}s)', flush=True)
        return f
    return wrap


def req(path, body=None, timeout=30):
    data = None if body is None else json.dumps(body).encode()
    r = urllib.request.Request(BASE + path, data=data, method='GET' if body is None else 'POST',
                               headers={'Origin': 'http://127.0.0.1:4747', 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw[:1] in (b'{', b'[') else raw)
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, raw


def up(timeout=60):
    for _ in range(timeout):
        try:
            with urllib.request.urlopen(BASE + '/api/stats', timeout=2):
                return True
        except Exception:
            time.sleep(1)
    return False


def py():
    p = sys.executable
    w = os.path.join(os.path.dirname(p), 'pythonw.exe')
    return w if os.path.exists(w) else p


def start_app():
    subprocess.Popen([py(), os.path.join(APP_DIR, 'bin', 'applytwin'), 'app', '--no-open'], cwd=os.path.expanduser('~'),
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
                     creationflags=0x00000008 | 0x00000200)


def twin_pages():
    with urllib.request.urlopen(TWIN + '/json/list', timeout=5) as r:
        return [p for p in json.loads(r.read()) if p.get('type') == 'page']


def wait_for_page(host, timeout=30):
    seen = []
    for _ in range(timeout * 2):
        try:
            seen = [p['url'] for p in twin_pages()]
            if any(host in u for u in seen):
                return seen
        except Exception:
            pass
        time.sleep(0.5)
    raise AssertionError(f'no tab on {host}; tabs: {seen}')


def claude():
    return shutil.which('claude')


# ------------------------------------------------------------------ the app itself

@check('app is running on localhost:4747')
def _():
    if not up(5):
        start_app()
        assert up(90), 'never answered'
    return req('/api/version')[1]


@check('every GET route answers without a server error')
def _():
    routes = ['stats', 'jobs', 'applications', 'profile', 'vault', 'queue', 'templates', 'scan', 'import', 'dump', 'ats', 'next',
              'run', 'doctor', 'version', 'questions', 'update', 'agents', 'auth', 'inbox', 'needs-you', 'answers', 'state',
              'setup', 'regions', 'history', 'accounts', 'vault/backups']
    bad = {}
    for r in routes:
        code, body = req('/api/' + r, timeout=60)
        if code >= 500:
            bad[r] = (code, str(body)[:200])
    assert not bad, bad
    return f'{len(routes)} routes'


@check('the page and its scripts load')
def _():
    code, html = req('/')
    assert code == 200 and b'<script' in html, (code, html[:200])
    import re
    assets = re.findall(rb'(?:src|href)="(/assets/[^"]+)"', html)
    assert assets, 'no assets in the page'
    for a in assets:
        c, b = req(a.decode())
        assert c == 200 and len(b) > 100, (a, c)
    return f'{len(assets)} assets'


@check('a cross-site POST is refused')
def _():
    r = urllib.request.Request(BASE + '/api/run', data=b'{}', method='POST', headers={'Origin': 'https://evil.example'})
    try:
        urllib.request.urlopen(r, timeout=10)
        raise AssertionError('accepted')
    except urllib.error.HTTPError as e:
        assert e.code == 403, e.code


@check('60 requests at once: no errors, no database locks')
def _():
    paths = ['/api/stats', '/api/jobs', '/api/run', '/api/needs-you', '/api/inbox', '/api/state'] * 10
    with concurrent.futures.ThreadPoolExecutor(30) as ex:
        codes = list(ex.map(lambda p: req(p, timeout=60)[0], paths))
    bad = [c for c in codes if c >= 500]
    assert not bad, bad
    return f'{len(codes)} ok'


@check('add a job by link')
def _():
    code, body = req('/api/jobs', {'url': 'https://boards.greenhouse.io/example/jobs/123?gh_src=x&t=1', 'title': 'Software Intern',
                                   'company': 'Example Co', 'description': 'C++, Python, robotics.'})
    assert code < 400, (code, body)
    return str(body)[:80]


@check('import a resume from text')
def _():
    text = ('José Example\njose@example.com\nUniversity of Florida, B.S. Computer Engineering, 2029\n'
            'Experience\nRobotics Intern, Acme: wrote C++ motor control and PID loops\nSkills: Python, C++, Git')
    code, body = req('/api/import', {'name': 'resume.txt', 'text': text}, timeout=120)
    assert code < 500, (code, body)
    return str(body)[:120]


@check('render a resume PDF (headless Chrome/Edge)')
def _():
    code, body = req('/api/render', {}, timeout=180)
    assert code < 400, (code, str(body)[:300])
    pdf = body.get('pdf') if isinstance(body, dict) else None
    assert pdf and os.path.exists(pdf) and os.path.getsize(pdf) > 1000, body
    return f'{os.path.getsize(pdf)} bytes'


# ------------------------------------------------------------------ the twin's browser (the "about:blank" path)

@check('Open in twin browser opens the real job page, not about:blank')
def _():
    url = 'https://example.com/?gh_jid=123&source=applytwin'
    code, body = req('/api/open-twin', {'url': url}, timeout=90)
    assert code < 400, (code, body)
    tabs = wait_for_page('example.com')
    assert any('gh_jid=123' in u and 'source=applytwin' in u for u in tabs), f'query string lost: {tabs}'
    return f'{len(tabs)} tabs'


@check('the twin browser comes back after it is closed')
def _():
    if os.name == 'nt':
        subprocess.run(['taskkill', '/F', '/IM', 'chrome.exe', '/T'], capture_output=True)
        subprocess.run(['taskkill', '/F', '/IM', 'msedge.exe', '/T'], capture_output=True)
    time.sleep(3)
    code, body = req('/api/open-twin', {'url': 'https://example.net/'}, timeout=90)
    assert code < 400, (code, body)
    wait_for_page('example.net')


@check('the Playwright browser tool drives the twin window')
def _():
    if not shutil.which('npx'):
        return 'skipped: no Node.js'
    cmd = (['cmd', '/c', 'npx'] if os.name == 'nt' else ['npx']) + ['-y', '@playwright/mcp@latest', '--cdp-endpoint', TWIN]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8')
    out = []
    threading.Thread(target=lambda: [out.append(l) for l in p.stdout], daemon=True).start()

    def send(m):
        p.stdin.write(json.dumps(m) + '\n')
        p.stdin.flush()

    def wait_id(i, t=180):
        end = time.time() + t
        while time.time() < end:
            for l in out:
                try:
                    m = json.loads(l)
                except ValueError:
                    continue
                if m.get('id') == i:
                    return m
            time.sleep(0.3)
        raise TimeoutError(f'no reply {i}; stderr: {p.stderr.read(2000) if p.poll() is not None else "(running)"}')
    try:
        send({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2024-11-05', 'capabilities': {},
                                                                           'clientInfo': {'name': 'stress', 'version': '1'}}})
        wait_id(1)
        send({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
        send({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'name': 'browser_navigate',
                                                                             'arguments': {'url': 'https://example.org/'}}})
        r = wait_id(2)
        assert 'error' not in r and not r.get('result', {}).get('isError'), str(r)[:400]
        assert 'Example Domain' in json.dumps(r), str(r)[:400]
        wait_for_page('example.org')
    finally:
        if os.name == 'nt':
            subprocess.run(['taskkill', '/T', '/F', '/PID', str(p.pid)], capture_output=True)
        else:
            p.kill()


# ------------------------------------------------------------------ Claude Code

@check('Pressing Apply with Claude Code signed out says so (never silent)')
def _():
    if not claude():
        code, body = req('/api/run', {'agent': 'claude', 'n': 1})
        assert code >= 400 and 'install' in json.dumps(body).lower(), (code, body)
        return 'no Claude Code: ' + json.dumps(body)[:120]
    code, body = req('/api/run', {'agent': 'claude', 'n': 1})
    assert code >= 400, (code, body)
    msg = json.dumps(body).lower()
    assert 'sign' in msg, body
    return json.dumps(body)[:140]


@check("Claude Code has ApplyTwin's tools and the browser, both connected")
def _():
    if not claude():
        return 'skipped: no Claude Code'
    sys.path.insert(0, APP_DIR)
    from applytwin import install   # what a run start does
    install.ensure_browser('claude')
    r = subprocess.run([claude(), 'mcp', 'list'], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=240)
    lines = [l for l in r.stdout.splitlines() if l.startswith(('applytwin:', 'playwright:'))]
    assert len(lines) == 2 and all('Connected' in l for l in lines), r.stdout[-1500:]
    return ' | '.join(l.rsplit(' - ', 1)[-1] for l in lines)


@check('ApplyTwin skills copied for Claude Code')
def _():
    if not claude():
        return 'skipped: no Claude Code'
    d = os.path.join(os.path.expanduser('~'), '.claude', 'skills', 'applytwin-apply', 'SKILL.md')
    assert os.path.exists(d), d


# ------------------------------------------------------------------ the install on disk

@check('the applytwin command works in a fresh Command Prompt')
def _():
    if os.name != 'nt':
        return 'skipped'
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Environment') as k:
        user_path = winreg.QueryValueEx(k, 'Path')[0]
    env = {**os.environ, 'PATH': os.path.expandvars(user_path) + ';' + os.environ.get('SystemRoot', r'C:\Windows') + r'\System32'}
    r = subprocess.run(['cmd', '/c', 'applytwin templates'], capture_output=True, text=True, encoding='utf-8', errors='replace',
                       env=env, timeout=120)
    assert r.returncode == 0 and r.stdout.strip(), (r.returncode, r.stdout[-300:], r.stderr[-300:])


if SCENARIO.startswith('live'):
    @check('starts at sign-in and is in the Start menu')
    def _():
        startup = os.path.join(os.environ['APPDATA'], r'Microsoft\Windows\Start Menu\Programs\Startup\ApplyTwin.lnk')
        menu = os.path.join(os.environ['APPDATA'], r'Microsoft\Windows\Start Menu\Programs\ApplyTwin.lnk')
        assert os.path.exists(startup) and os.path.exists(menu), (os.path.exists(startup), os.path.exists(menu))

    @check('running the installer again while the app is open updates it and the app comes back')
    def _():
        shell = 'pwsh' if SCENARIO == 'live-pwsh7' else 'powershell'
        r = subprocess.run([shell, '-NoProfile', '-Command', 'irm https://apply.twinly.tech/install.ps1 | iex'],
                           capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=600)
        assert 'ApplyTwin in' in r.stdout, (r.stdout[-1500:], r.stderr[-800:])
        assert up(90), 'app did not come back'
        assert not [d for d in os.listdir(os.path.dirname(APP_DIR)) if d.startswith('.applytwin-app.old')], 'old copy left'
        return req('/api/version')[1]


# ------------------------------------------------------------------ summary

print('\n' + '=' * 70)
failed = [r for r in results if not r[0]]
for ok, name, detail in results:
    print(('ok    ' if ok else 'FAIL  ') + name + ('' if ok else f'\n        {detail[:600]}'))
print(f'{SCENARIO}: {len(results) - len(failed)}/{len(results)} passed')
log = os.path.join(os.path.expanduser('~'), '.applytwin', 'server.log')
if failed and os.path.exists(log):
    print('\n--- app log (last 60 lines) ---\n' + ''.join(open(log, encoding='utf-8', errors='replace').readlines()[-60:]))
sys.exit(1 if failed else 0)
