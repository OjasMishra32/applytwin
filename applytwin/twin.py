"""The twin's browser: one Chrome window that ApplyTwin keeps open between runs, on its own profile.

The agent's browser tool (Playwright) used to launch Chrome itself, so the window closed the moment a run ended and took
every half-filled application with it ("the tab is open" was never true by the time you looked). Now ApplyTwin starts
Chrome with a local debugging port and every agent session connects to that same window: tabs survive the run, the next
run sees them, and "Open in twin's browser" adds a tab to it instead of fighting it for the profile.

It also lets ApplyTwin itself (this code, not the AI) type a saved password into a sign-in page, so the agent can sign
in or create an account without ever seeing the password (see fill_password).
"""
import base64
import json
import os
import re
import socket
import struct
import subprocess
import time
import urllib.parse
import urllib.request

from . import store

PORT = int(os.environ.get('APPLYTWIN_TWIN_PORT') or 9343)
ENDPOINT = f'http://127.0.0.1:{PORT}'


def profile():
    from . import install
    return install.BROWSER_PROFILE


def _get(path, method='GET', timeout=2):
    req = urllib.request.Request(ENDPOINT + path, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8') or 'null')


def alive():
    if os.environ.get('APPLYTWIN_NO_TWIN'):
        return False
    try:
        return bool(_get('/json/version', timeout=1))
    except Exception:
        return False


def _close_other_windows():
    """A Chrome on this profile that isn't ours (an older ApplyTwin's window, or one Playwright launched) holds the profile
    lock, and ours couldn't start beside it."""
    prof = profile()
    try:
        if os.name == 'nt':
            ps = ("Get-CimInstance Win32_Process -Filter \"Name='chrome.exe' or Name='msedge.exe'\" | "
                  "Where-Object { $_.CommandLine -and $_.CommandLine.Contains($env:APPLYTWIN_PROF) } | "
                  "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }")
            subprocess.run(['powershell', '-NoProfile', '-Command', ps], capture_output=True, timeout=20,
                           env={**os.environ, 'APPLYTWIN_PROF': prof}, **store.NOWIN)
        else:
            subprocess.run(['pkill', '-f', '--', f'--user-data-dir={prof}( |$)'], capture_output=True, timeout=10)
        time.sleep(1)
    except Exception:
        pass


def ensure():
    """Start the twin's browser if it isn't running. True when it's up."""
    if os.environ.get('APPLYTWIN_NO_TWIN'):   # tests: never open (or reach) a real browser window
        return True
    if alive():
        return True
    from . import render
    exe = render.chrome()
    if not exe:
        return False
    _close_other_windows()
    os.makedirs(profile(), exist_ok=True)
    # the same keychain flags Playwright used for this profile, or Chrome can't read the sign-ins already saved in it
    args = [exe, f'--user-data-dir={profile()}', f'--remote-debugging-port={PORT}', '--remote-debugging-address=127.0.0.1',
            '--no-first-run', '--no-default-browser-check', '--use-mock-keychain', '--password-store=basic',
            '--disable-blink-features=AutomationControlled', 'about:blank']
    kw = {'creationflags': 0x00000008 | 0x00000200} if os.name == 'nt' else {'start_new_session': True}   # outlives the app
    subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, **kw)
    for _ in range(60):
        if alive():
            return True
        time.sleep(0.25)
    return False


def open_tab(url):
    """Open a page as a new tab in the twin's browser (starting it if needed)."""
    if not ensure():
        raise RuntimeError("Couldn't start your twin's browser. Is Google Chrome installed?")
    _get('/json/new?' + urllib.parse.quote(url, safe=':/?&=%#'), method='PUT', timeout=5)
    return {"opened": True}


def pages():
    try:
        return [t for t in _get('/json/list') if t.get('type') == 'page']
    except Exception:
        return []


# ------------------------------------------------------------------ a tiny CDP client (standard library only)

class _WS:
    def __init__(self, url, timeout=10):
        u = urllib.parse.urlparse(url)
        self.s = socket.create_connection((u.hostname, u.port), timeout=timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        self.s.sendall((f'GET {u.path} HTTP/1.1\r\nHost: {u.hostname}:{u.port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n'
                        f'Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n').encode())
        head = b''
        while b'\r\n\r\n' not in head:
            chunk = self.s.recv(4096)
            if not chunk:
                raise ConnectionError('no handshake')
            head += chunk
        if b' 101 ' not in head.split(b'\r\n', 1)[0]:
            raise ConnectionError('handshake refused')
        self.buf = head.split(b'\r\n\r\n', 1)[1]
        self.n = 0

    def _read(self, k):
        while len(self.buf) < k:
            chunk = self.s.recv(65536)
            if not chunk:
                raise ConnectionError('closed')
            self.buf += chunk
        out, self.buf = self.buf[:k], self.buf[k:]
        return out

    def send(self, obj):
        data = json.dumps(obj).encode()
        mask = os.urandom(4)
        n = len(data)
        head = bytes([0x81]) + (bytes([0x80 | n]) if n < 126 else bytes([0x80 | 126]) + struct.pack('>H', n) if n < 65536
                                else bytes([0x80 | 127]) + struct.pack('>Q', n))
        self.s.sendall(head + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def recv(self):
        msg = b''
        while True:
            b1, b2 = self._read(2)
            n = b2 & 0x7f
            if n == 126:
                n = struct.unpack('>H', self._read(2))[0]
            elif n == 127:
                n = struct.unpack('>Q', self._read(8))[0]
            data = self._read(n)
            op = b1 & 0x0f
            if op == 8:
                raise ConnectionError('closed')
            if op in (0, 1, 2):
                msg += data
                if b1 & 0x80:
                    return json.loads(msg.decode('utf-8'))

    def call(self, method, params=None):
        self.n += 1
        self.send({"id": self.n, "method": method, "params": params or {}})
        while True:
            m = self.recv()
            if m.get('id') == self.n:
                if 'error' in m:
                    raise RuntimeError(m['error'].get('message', 'CDP error'))
                return m.get('result', {})

    def close(self):
        try:
            self.s.close()
        except OSError:
            pass


def _page_for(url):
    """The open tab the agent is on for this site: same host, newest first (exact URL when it matches)."""
    host = (urllib.parse.urlparse(url or '').hostname or '').lower()
    ps = pages()
    exact = [p for p in ps if p.get('url') == url]
    same = [p for p in ps if (urllib.parse.urlparse(p.get('url') or '').hostname or '').lower() == host]
    return (exact or same or [None])[0]


# Fills every visible password box on the page (sign-in, or create-account with its confirm box) the way a person
# typing would, so React/Workday forms register it. The password goes in as a JSON string argument; it never comes back.
_FILL_JS = r"""
(function(pw){
  function vis(e){ var r=e.getBoundingClientRect(); var s=getComputedStyle(e);
    return r.width>0 && r.height>0 && s.visibility!=='hidden' && s.display!=='none' && !e.disabled && !e.readOnly; }
  function all(root){ var out=[].slice.call(root.querySelectorAll('input[type=password]'));
    [].slice.call(root.querySelectorAll('*')).forEach(function(n){ if(n.shadowRoot) out=out.concat(all(n.shadowRoot)); });
    return out; }
  var boxes = all(document).filter(vis), set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
  boxes.forEach(function(e){ e.focus(); set.call(e, pw);
    e.dispatchEvent(new Event('input',{bubbles:true})); e.dispatchEvent(new Event('change',{bubbles:true})); e.blur(); });
  return boxes.length;
})
"""


def fill_password(url, password):
    """Type the password into the password box(es) of the twin's open tab for this site, in the page and in its frames
    (Workday and iCIMS put some forms in one). Returns how many boxes were filled. It runs through the debugging port in
    a separate script world, so the agent driving the form never sees the password and the page's own scripts can't read
    this code."""
    p = _page_for(url)
    if not p or not p.get('webSocketDebuggerUrl'):
        return 0
    ws = _WS(p['webSocketDebuggerUrl'])
    try:
        frames, stack = [], [ws.call('Page.getFrameTree').get('frameTree') or {}]
        while stack:
            f = stack.pop()
            if f.get('frame'):
                frames.append(f['frame']['id'])
            stack += f.get('childFrames') or []
        n = 0
        for fid in frames:
            try:
                ctx = ws.call('Page.createIsolatedWorld', {"frameId": fid, "worldName": "applytwin"})['executionContextId']
                r = ws.call('Runtime.evaluate', {"expression": f"{_FILL_JS}({json.dumps(password)})", "contextId": ctx, "returnByValue": True})
                n += int((r.get('result') or {}).get('value') or 0)
            except Exception:
                continue   # a frame from another site that this tab can't reach
        return n
    finally:
        ws.close()


def site_of(url):
    h = (urllib.parse.urlparse(url or '').hostname or '').lower()
    return re.sub(r'^www\.', '', h)
