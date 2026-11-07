"""The user's own coding agents (Claude Code, Codex): where they are, whether they're signed in, and a full setup check.

ApplyTwin never needs an API key. Everything that needs a model runs on the subscription the user already pays for,
through the `claude` or `codex` command line.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time

from . import store

NAMES = {'claude': 'Claude Code', 'codex': 'Codex'}
INSTALL = {'claude': 'npm install -g @anthropic-ai/claude-code', 'codex': 'npm install -g @openai/codex'}
LOGIN = {'claude': 'claude  (then type /login)', 'codex': 'codex login'}
FALLBACK_MODEL = [False]   # set once Codex rejects the configured model, so later calls go straight to a supported one
_cache = {}


def _usual_dirs():
    """Where Claude Code, Codex and Node usually land. The app often starts from login with a short PATH (or the PATH from
    the day it was installed), so an agent installed later, by the native installer, nvm, Volta or Homebrew, looked missing."""
    import glob
    h = os.path.expanduser('~')
    d = [os.path.join(h, '.local', 'bin'), os.path.join(h, '.claude', 'local'), os.path.join(h, '.npm-global', 'bin'),
         os.path.join(h, '.volta', 'bin'), os.path.join(h, '.bun', 'bin')]
    if os.name == 'nt':
        d += [os.path.join(os.environ.get('APPDATA', ''), 'npm'), os.path.join(os.environ.get('ProgramFiles', ''), 'nodejs'),
              os.path.join(h, '.applytwin-app-runtime', 'node'),   # the Node.js ApplyTwin downloads when there's none
              os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'nodejs'), os.path.join(h, '.local', 'bin')]
    else:
        d += ['/opt/homebrew/bin', '/usr/local/bin'] + sorted(glob.glob(os.path.join(h, '.nvm', 'versions', 'node', '*', 'bin')), reverse=True)
        d.append(os.path.join(h, '.applytwin-app-runtime', 'node', 'bin'))   # the Node.js the Mac app downloads when there's none
    return [x for x in d if os.path.isdir(x)]


def exe(name):
    p = shutil.which(name)
    if not p and os.name == 'nt':   # installed after the app started: look again with the PATH as it is now
        store.refresh_path()
        p = shutil.which(name)
    if not p:
        for d in _usual_dirs():
            p = shutil.which(name, path=d)
            if p:   # its folder joins the PATH, so `claude` finds the node next to it (npm installs are node scripts)
                os.environ['PATH'] = d + os.pathsep + os.environ.get('PATH', '')
                break
    return p


NODE_V = 'v26.13.0'   # the same Node.js the Mac app downloads
_node_lock = __import__('threading').Lock()


def ensure_node():
    """npx, downloading ApplyTwin's own Node.js on Windows when the computer has none (the browser your twin fills forms
    in runs on it). A one-time ~40 MB download into ~/.applytwin-app-runtime/node: no admin rights, nothing for the user
    to install or click. Returns npx's path, or None if it couldn't be had."""
    npx = exe('npx')
    if npx or os.name != 'nt' or os.environ.get('APPLYTWIN_NO_NODE_DOWNLOAD') or os.environ.get('APPLYTWIN_NO_TWIN'):
        return npx   # (tests run with APPLYTWIN_NO_TWIN: they never download anything)
    import io
    import urllib.request
    import zipfile
    with _node_lock:   # Start and the start-up check can both ask at once: one download
        npx = exe('npx')
        if npx:
            return npx
        arch = 'arm64' if 'ARM64' in (os.environ.get('PROCESSOR_ARCHITECTURE', '') + os.environ.get('PROCESSOR_ARCHITEW6432', '')) else 'x64'
        rt = os.path.join(os.path.expanduser('~'), '.applytwin-app-runtime')
        dest = os.path.join(rt, 'node')
        tmp = os.path.join(rt, f'.dl-node-{os.getpid()}')
        if os.path.isdir(rt):   # a download cut off earlier (the app closed mid-way) leaves its folder: clear those
            for n in os.listdir(rt):
                if n.startswith('.dl-'):
                    shutil.rmtree(os.path.join(rt, n), ignore_errors=True)
        try:
            os.makedirs(tmp, exist_ok=True)
            url = f'https://nodejs.org/dist/{NODE_V}/node-{NODE_V}-win-{arch}.zip'
            with urllib.request.urlopen(url, timeout=600) as r:
                zipfile.ZipFile(io.BytesIO(r.read())).extractall(tmp)
            top = next(os.path.join(tmp, n) for n in os.listdir(tmp) if os.path.isdir(os.path.join(tmp, n)))
            if os.path.isdir(dest):
                shutil.rmtree(dest, ignore_errors=True)
            store.replace(top, dest)
        except Exception as e:
            print(f"Couldn't download Node.js: {e}", flush=True)
            return None
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        return exe('npx')


def windows_shell():
    """The shell Claude Code will use on Windows: Git for Windows' bash.exe if it's there (pointing Claude Code at it when
    Git was installed after the app started, so the app's old PATH doesn't hide it), else PowerShell 7, else the Windows
    PowerShell 5.1 every Windows has (current Claude Code falls back to it). Returns its path, '' off Windows, or None only
    when even Windows PowerShell is missing (an older Claude Code then asks for Git for Windows)."""
    if os.name != 'nt':
        return ''
    import glob
    p = os.environ.get('CLAUDE_CODE_GIT_BASH_PATH')
    if p and os.path.isfile(p):
        return p
    store.refresh_path()
    cands = []
    git = shutil.which('git')
    if git:   # ...\Git\cmd\git.exe or ...\Git\mingw64\bin\git.exe: bash is in ...\Git\bin
        d = os.path.dirname(git)
        for _ in range(3):
            d = os.path.dirname(d)
            cands.append(os.path.join(d, 'bin', 'bash.exe'))
    for base in (os.environ.get('ProgramFiles'), os.environ.get('ProgramW6432'), os.environ.get('ProgramFiles(x86)'),
                 os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs')):
        if base:
            cands.append(os.path.join(base, 'Git', 'bin', 'bash.exe'))
    for c in cands:
        if os.path.isfile(c):
            os.environ['CLAUDE_CODE_GIT_BASH_PATH'] = c
            return c
    pw = shutil.which('pwsh') or next(iter(sorted(glob.glob(os.path.join(os.environ.get('ProgramFiles', r'C:\Program Files'),
                                                                        'PowerShell', '*', 'pwsh.exe')), reverse=True)), None)
    ps5 = os.path.join(os.environ.get('SystemRoot', r'C:\Windows'), 'System32', 'WindowsPowerShell', 'v1.0', 'powershell.exe')
    return pw or (ps5 if os.path.isfile(ps5) else None)


def update_claude():
    """Bring Claude Code up to date (an old one won't run on Windows without Git; current ones use Windows PowerShell).
    npm installs update through npm; the native installer's through `claude update`. True if it ran without an error."""
    path = exe('claude')
    if not path:
        return False
    npm = exe('npm')
    in_npm = 'node_modules' in os.path.realpath(path).lower() or os.path.dirname(path).lower().endswith(os.sep + 'npm')
    cmd = [npm, 'install', '-g', '@anthropic-ai/claude-code@latest'] if (npm and in_npm) else [path, 'update']
    code, _ = _run(cmd, timeout=600)
    _cache.pop('claude', None)
    return code == 0


SHELL_FIX ='winget install --id Git.Git -e   (or download Git for Windows from git-scm.com), then press Start again'
SHELL_ERROR = re.compile(r'requires (?:either )?git(?:-bash| for windows)', re.I)   # an older Claude Code without a shell


def _run(cmd, timeout=20):
    try:
        r = store.run_capture(cmd, timeout=timeout)
        return r.returncode, (r.stdout or '') + (r.stderr or '')
    except subprocess.TimeoutExpired:
        return 1, f'{os.path.basename(str(cmd[0]))} did not answer within {timeout} seconds'
    except Exception as e:
        return 1, str(e)


def status(name, fresh=False):
    """{installed, signed_in, version, how} for one agent; cached for a few minutes because the checks spawn processes."""
    hit = _cache.get(name)
    if hit and not fresh and time.time() - hit[0] < 300:
        return hit[1]
    path = exe(name)
    out = {'name': name, 'label': NAMES[name], 'installed': bool(path), 'signed_in': False, 'version': '', 'how': ''}
    if path:
        # the first start of a freshly installed agent (a 300+ MB program antivirus scans first) can take most of a minute
        # on a slow laptop: a 20-second limit read that as "signed out"
        wait = 20 if hit else 60
        lines = _run([path, '--version'], timeout=wait)[1].strip().splitlines()
        out['version'] = lines[-1] if lines else ''
        if name == 'claude':
            code, txt = _run([path, 'auth', 'status'], timeout=wait)
            try:
                d = json.loads(txt[txt.index('{'):txt.rindex('}') + 1])
                out['signed_in'] = bool(d.get('loggedIn'))
                out['how'] = d.get('authMethod', '')
            except ValueError:
                out['signed_in'] = code == 0 and 'logged in' in txt.lower()
            out['needs_shell'] = windows_shell() is None
        else:
            code, txt = _run([path, 'login', 'status'], timeout=wait)
            out['signed_in'] = code == 0 and 'logged in' in txt.lower()
            out['how'] = next((l.strip() for l in txt.splitlines() if 'logged' in l.lower()), '')
    _cache[name] = (time.time(), out)
    return out


def preferred(profile):
    """Signed-in agents, the user's choice first."""
    first = (profile.get('apply') or {}).get('agent') or 'claude'
    order = [first] + [n for n in NAMES if n != first]
    return [n for n in order if ready(n)]


def ready(name):
    """Signed in and able to run here (Claude Code on Windows also needs Git for Windows or PowerShell 7)."""
    s = status(name)
    return bool(s['signed_in'] and not s.get('needs_shell'))


def any_ready():
    return any(ready(n) for n in NAMES)


def codex_model_args():
    """The config's model can be newer than this CLI or plan allows (the desktop app sets it); pick one the CLI lists."""
    home = os.path.expanduser('~/.codex')
    try:
        want = re.search(r'^model\s*=\s*"([^"]+)"', open(os.path.join(home, 'config.toml'), encoding='utf-8').read(), re.M)
        cached = json.load(open(os.path.join(home, 'models_cache.json'), encoding='utf-8'))
        models = cached.get('models', cached) if isinstance(cached, dict) else cached
        slugs = [m.get('slug') for m in models if isinstance(m, dict)]
    except Exception:
        return []
    bad = rejected_models()
    usable = [x for x in slugs if x and 'reserve' not in x and 'review' not in x and x not in bad]
    want = want and want.group(1)
    if usable and (FALLBACK_MODEL[0] or not want or want not in slugs or want in bad):
        return ['-m', usable[0]]
    return []


DESKTOP_BROWSER_FEATURES = ('browser_use', 'browser_use_external', 'computer_use', 'in_app_browser')
DESKTOP_BROWSER_SERVERS = ('node_repl', 'computer-use')


def codex_browser_args(exe='codex'):
    """Turn off Codex's desktop browser for an unattended run so the twin's browser (Playwright) is the only one it has.
    The ChatGPT app registers a desktop browser (node_repl) that only works inside the app: in `codex exec` its first call
    fails with "The browser access host is unavailable" and the run stops before applying anywhere. Only features this
    CLI knows and servers the config has are named (an unknown one would stop the run)."""
    if 'codex_features' not in _cache:
        try:
            out = store.run_capture([exe, 'features', 'list'], timeout=20).stdout
            _cache['codex_features'] = {ln.split()[0] for ln in out.splitlines() if ln.strip()}
        except Exception:
            _cache['codex_features'] = set()
    args = [a for f in DESKTOP_BROWSER_FEATURES if f in _cache['codex_features'] for a in ('--disable', f)]
    try:
        txt = open(os.path.expanduser('~/.codex/config.toml'), encoding='utf-8').read()
    except OSError:
        txt = ''
    for name in DESKTOP_BROWSER_SERVERS:
        if re.search(rf'^\[mcp_servers\.(?:"{re.escape(name)}"|{re.escape(name)})\]', txt, re.M):
            args += ['-c', f'mcp_servers.{name}.enabled=false']
    return args


def rejected_models():
    try:
        return set(json.load(open(store.path('codex_rejected.json'), encoding='utf-8')))
    except Exception:
        return set()


def reject_model(output):
    """Codex said 'The X model is not supported' (its model list includes models a plan can't use, and nothing in it says
    which): remember X so every later call, here and in Autopilot, goes to the next listed model. True if one was noted."""
    m = re.search(r"the '([^']+)' model is not supported", output or '', re.I)
    if not m:
        return False
    bad = rejected_models() | {m.group(1)}
    with open(store.path('codex_rejected.json'), 'w', encoding='utf-8') as f:
        json.dump(sorted(bad), f)
    FALLBACK_MODEL[0] = True
    return True


# ------------------------------------------------------------------ doctor

def doctor():
    """Everything a new user needs, checked. Each item: {id, ok, label, detail, fix}. Nothing here needs an API key."""
    from . import store
    items = []

    def add(id, ok, label, detail='', fix='', optional=False):
        items.append({'id': id, 'ok': bool(ok), 'label': label, 'detail': detail, 'fix': fix, 'optional': optional})

    v = sys.version_info
    add('python', v >= (3, 9), 'Python 3.9+', f'{v.major}.{v.minor}.{v.micro}', 'Install Python from python.org')
    ag = [status(n, fresh=True) for n in NAMES]
    for a in ag:
        if not a['installed']:
            add(a['name'], False, f"{a['label']} installed", 'not installed', f"Press Install and sign in on the Autopilot page (or run: {INSTALL[a['name']]})", optional=True)
        else:
            add(a['name'], a['signed_in'], f"{a['label']} signed in", a['version'] + (f" · {a['how']}" if a['how'] else ''),
                '' if a['signed_in'] else 'Press Sign in on the Autopilot page', optional=True)
            if a.get('needs_shell'):
                add('shell', False, 'Claude Code can run on this PC', 'Claude Code on Windows needs Git for Windows (or PowerShell 7)',
                    SHELL_FIX, optional=ag[1]['signed_in'] if len(ag) > 1 else False)
    add('agent', any(a['signed_in'] and not a.get('needs_shell') for a in ag), 'At least one agent ready',
        'Claude Code or Codex, on your own subscription', 'Install and sign in to Claude Code or Codex (any paid plan works, no API key)')
    npx = exe('npx')
    add('npx', bool(npx), 'Node.js (for the browser)', npx or 'npx not found',
        'ApplyTwin downloads it by itself when it starts (needs an internet connection)' if os.name == 'nt' else 'Install Node.js from nodejs.org')
    cfg = os.path.expanduser('~/.claude.json')
    claude_mcp = os.path.exists(cfg) and 'applytwin' in open(cfg, encoding='utf-8').read()
    ccfg = os.path.expanduser('~/.codex/config.toml')
    ctxt = open(ccfg, encoding='utf-8').read() if os.path.exists(ccfg) else ''
    if ag[0]['installed']:
        add('claude_mcp', claude_mcp or _claude_has_mcp(), 'ApplyTwin connected to Claude Code', '', 'Restart ApplyTwin: it connects them when it starts (or run: applytwin install-agents)', optional=True)
    if ag[1]['installed']:
        add('codex_mcp', '[mcp_servers.applytwin]' in ctxt, 'ApplyTwin connected to Codex', '', 'Restart ApplyTwin: it connects them when it starts (or run: applytwin install-agents)', optional=True)
        add('codex_approve', 'default_tools_approval_mode' in ctxt, 'Codex can run ApplyTwin unattended', '', 'Restart ApplyTwin: it connects them when it starts (or run: applytwin install-agents)', optional=True)
    p = store.profile()
    vault = store.resume()
    add('resume', bool(vault.get('experience') or vault.get('projects')), 'Resume imported', '', 'Drop your resume on the Welcome page')
    from . import answers as ans
    miss = ans.gaps(p)
    add('profile', not miss, 'Application answers complete',
        'all answered' if not miss else f"{len(miss)} unanswered: " + ', '.join(m['label'] for m in miss[:4]) + ('…' if len(miss) > 4 else ''),
        'Answer them in Settings (your twin asks instead of guessing)')
    n = store.rows('select count(*) n from jobs')[0]['n'] if _has_table('jobs') else 0
    add('jobs', n > 0, 'Jobs found', f'{n:,} in your database', 'Press Scan on the Jobs page')
    ready = all(i['ok'] for i in items if not i['optional'])
    return {'ok': ready, 'items': items}


def _claude_has_mcp():
    path = exe('claude')
    if not path:
        return False
    code, txt = _run([path, 'mcp', 'get', 'applytwin'], timeout=30)
    return code == 0


def _has_table(t):
    from . import store
    return bool(store.rows("select name from sqlite_master where type='table' and name=?", (t,)))
