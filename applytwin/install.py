"""Register ApplyTwin with the user's agents.

Claude Code: installs the plugin (skills + MCP server) from this folder's marketplace, or falls back to
             `claude mcp add` + copying skills into ~/.claude/skills.
Codex:       adds [mcp_servers.applytwin] to ~/.codex/config.toml and copies the skills into ~/.agents/skills.
"""
import json
import os
import re
import shutil
import subprocess
import sys

from . import store

APP = store.APP
APPLYTWIN_BIN = os.path.join(APP, 'bin', 'applytwin')


APP_URL = 'http://localhost:4747/'
NOTIFIER = os.path.join(store.HOME, 'ApplyTwin.app')
# A tiny app ApplyTwin builds for itself (macOS's own osacompile, nothing downloaded) so its notifications come from
# "ApplyTwin" and clicking one opens the page it's about. Plain osascript notifications belong to Script Editor, and a
# click opened Script Editor. The text arrives in a file, read as data, never as AppleScript source.
# (AppleScript names ignore case: every variable below must differ by more than case.)
_NOTIFIER_SRC = """on run
	set base to do shell script "dirname " & quoted form of (POSIX path of (path to me))
	set pendingFile to base & "/notify-pending.txt"
	set lastFile to base & "/notify-last.txt"
	try
		set parts to paragraphs of (read (POSIX file pendingFile) as «class utf8»)
		do shell script "mv -f " & quoted form of pendingFile & " " & quoted form of lastFile
		display notification (item 2 of parts) with title (item 1 of parts) sound name "Glass"
		delay 1
	on error
		set u to "%s"
		try
			set u to item 3 of paragraphs of (read (POSIX file lastFile) as «class utf8»)
		end try
		open location u
	end try
end run
""" % APP_URL
_NOTIFIER_VERSION = '4'


def _notifier():
    """The ApplyTwin.app that posts macOS notifications (built on first use), or None if it can't be built."""
    mark = os.path.join(NOTIFIER, 'Contents', 'Resources', 'applytwin-' + _NOTIFIER_VERSION)
    if os.path.exists(mark):
        return NOTIFIER
    try:
        import tempfile
        shutil.rmtree(NOTIFIER, ignore_errors=True)
        src = os.path.join(tempfile.mkdtemp(), 'n.applescript')
        open(src, 'w', encoding='utf-8').write(_NOTIFIER_SRC)
        if subprocess.run(['osacompile', '-o', NOTIFIER, src], capture_output=True, timeout=30).returncode:
            return None
        icon = os.path.join(APP, 'scripts', 'seo', 'icon-512.png')
        if os.path.exists(icon):
            subprocess.run(['sips', '-s', 'format', 'icns', icon, '--out', os.path.join(NOTIFIER, 'Contents', 'Resources', 'applet.icns')],
                           capture_output=True, timeout=30)
        plist = os.path.join(NOTIFIER, 'Contents', 'Info.plist')
        subprocess.run(['plutil', '-replace', 'CFBundleIdentifier', '-string', 'tech.twinly.applytwin.notifier', plist], capture_output=True)
        subprocess.run(['plutil', '-replace', 'LSUIElement', '-bool', 'YES', plist], capture_output=True)   # no Dock icon flash
        open(mark, 'wb').close()
        # edited, so sign it again (last: anything written into it afterwards breaks the signature and it won't open)
        if subprocess.run(['codesign', '--force', '--deep', '-s', '-', NOTIFIER], capture_output=True, timeout=60).returncode:
            os.remove(mark)
            return None
        return NOTIFIER
    except Exception:
        return None


def _app_link(url):
    """Where clicking the notification goes: a page of the local app, never anywhere else."""
    return url if isinstance(url, str) and re.match(r'^http://(localhost|127\.0\.0\.1):\d+/[\w#/.?=&%-]*$', url) else APP_URL


def _mac_app():
    """True when the ApplyTwin Mac app (the download, not the notifier above) is installed."""
    for d in ('/Applications', os.path.expanduser('~/Applications')):
        try:
            with open(os.path.join(d, 'ApplyTwin.app', 'Contents', 'Info.plist'), 'rb') as f:
                if b'tech.twinly.applytwin.app' in f.read():
                    return True
        except OSError:
            pass
    return False


def _click_link(url):
    """With the Mac app installed a notification click opens that page in its window (applytwin://open/#agents)."""
    return 'applytwin://open/' + url.split('/', 3)[3] if _mac_app() else url


def notify(title, msg, url=''):
    # title and message can come from a job page via the agent: they go in as data (argv / environment / a file), never
    # into AppleScript or PowerShell source, where a quote would let them run commands
    title, msg, url = ' '.join(str(title).split())[:120], ' '.join(str(msg).split())[:200], _app_link(url)
    try:
        if sys.platform == 'darwin':
            app = _notifier()
            if app:
                pending = os.path.join(os.path.dirname(app), 'notify-pending.txt')   # outside the app: it's signed
                for _ in range(30):   # one at a time: the last one is still being shown
                    if not os.path.exists(pending):
                        break
                    __import__('time').sleep(0.1)
                with open(pending, 'w', encoding='utf-8') as f:
                    f.write(f'{title}\n{msg}\n{_click_link(url)}\n')
                if not subprocess.run(['open', '-n', '-g', app], capture_output=True, timeout=15).returncode:
                    return
            subprocess.run(['osascript', '-e', 'on run argv', '-e',
                            'display notification (item 2 of argv) with title (item 1 of argv) sound name "Glass"', '-e', 'end run',
                            title, msg], capture_output=True)
        elif os.name == 'nt':
            # launch + protocol: clicking the toast opens the page in the browser (it used to do nothing)
            ps = ("[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null;"
                  "[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] > $null;"
                  "$e = [Security.SecurityElement];"
                  "$x = New-Object Windows.Data.Xml.Dom.XmlDocument;"
                  "$x.LoadXml('<toast activationType=''protocol'' launch=''' + $e::Escape($env:APPLYTWIN_NOTE_URL) + '''><visual><binding template=''ToastGeneric''><text>' + $e::Escape($env:APPLYTWIN_NOTE_TITLE) + '</text><text>' + $e::Escape($env:APPLYTWIN_NOTE_MSG) + '</text></binding></visual></toast>');"
                  "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\\WindowsPowerShell\\v1.0\\powershell.exe').Show([Windows.UI.Notifications.ToastNotification]::new($x))")
            # the app id is PowerShell's own: Windows drops toasts from an unregistered one (like 'ApplyTwin') without a word
            subprocess.run(['powershell', '-NoProfile', '-Command', ps], capture_output=True, creationflags=0x08000000,
                           env={**os.environ, 'APPLYTWIN_NOTE_TITLE': title, 'APPLYTWIN_NOTE_MSG': msg, 'APPLYTWIN_NOTE_URL': url})
        elif shutil.which('notify-send'):
            subprocess.run(['notify-send', '--', title, msg], capture_output=True)
    except Exception:
        pass


def _skills_src():
    return os.path.join(APP, 'skills')


def _copy_skills(dest):
    os.makedirs(dest, exist_ok=True)
    for name in os.listdir(_skills_src()):
        src = os.path.join(_skills_src(), name)
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(dest, name), dirs_exist_ok=True)


BROWSER_PROFILE = os.path.join(store.HOME, 'browser')
# on Windows npx is npx.cmd, which agents can't launch by bare name
# --sandbox: Playwright turns Chrome's sandbox off by default, which makes Chrome show an "unsupported command-line flag:
# --no-sandbox" warning on every launch and leaves sites less isolated. Linux keeps the default: many distros block the
# sandbox for apps like this, and Chrome would not start.
# the agent's browser tool connects to the twin's own window (ApplyTwin keeps it open between runs, see twin.py) instead of
# launching a Chrome that closes when the run ends and takes every half-filled application with it
from . import twin as _twin


def _which(name):
    """claude / codex / npx wherever they are now, including ones installed after the app started at login (a bare
    shutil.which keeps the PATH from that morning, so Node.js installed since still looked missing)."""
    from . import agents
    return agents.exe(name)


def playwright():
    """The browser tool's command, worked out when it's needed (not at import, before Node.js may have been installed)."""
    npx = (_which('npx') or 'npx') if os.name == 'nt' else 'npx'
    return [npx, '-y', '@playwright/mcp@latest', '--cdp-endpoint', _twin.ENDPOINT]


def _ours(args):
    """A browser entry ApplyTwin registered (any version): on the twin's profile, or connected to its window."""
    a = list(args or [])
    return BROWSER_PROFILE in a or _twin.ENDPOINT in a


def _pw_claude():
    """How Claude Code should launch the browser tool. On Windows npx is a .cmd file, which Node no longer starts without
    a shell, so it goes through `cmd /c` there."""
    return (['cmd', '/c', 'npx'] + playwright()[1:]) if os.name == 'nt' else playwright()


def _claude_cmd(claude, args, timeout=60):
    """Run `claude <args>`, never hanging past the timeout (on Windows `claude` is npm's .cmd wrapper, and a plain
    subprocess.run timeout leaves the real claude.exe running and the call waiting on it)."""
    try:
        return store.run_capture([claude] + args, timeout=timeout)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess([claude] + args, 1, '', f'Claude Code did not answer within {timeout} seconds')


LAST_ERROR = ['']   # why the browser couldn't be connected to the agent last time (shown when Start can't go ahead)


def _add_playwright(claude, previous=None):
    # the same patience as registering ApplyTwin itself: a first Claude Code start on Windows can take over a minute
    _claude_cmd(claude, ['mcp', 'remove', '--scope', 'user', 'playwright'], timeout=240)
    r = _claude_cmd(claude, ['mcp', 'add', '--scope', 'user', 'playwright', '--'] + _pw_claude(), timeout=240)
    LAST_ERROR[0] = '' if r.returncode == 0 else ((r.stderr or r.stdout or '').strip() or f'claude mcp add exited {r.returncode}')
    if r.returncode != 0 and previous:   # never leave the twin without a browser: put the old entry back
        _claude_cmd(claude, ['mcp', 'add', '--scope', 'user', 'playwright', '--', previous['command']] + list(previous.get('args') or []),
                    timeout=240)
    return r


def prewarm_browser_tool():
    """Download the browser tool once in the background when the app starts, so a run's first start of it is quick (Claude
    Code gives a tool server 30 seconds, and a first `npx` download on a slow connection took longer: no browser, 0
    applications)."""
    npx = _which('npx')
    if not npx:
        return
    try:
        store.run_capture([npx, '-y', '@playwright/mcp@latest', '--help'], timeout=600)
    except Exception:
        pass


def install_claude():
    claude = _which('claude')
    if not claude:
        return 'Claude Code CLI not found (skip). Install it, then rerun: applytwin install-agents'
    # a browser the agent can drive on any machine (Claude in Chrome works too, if installed); the profile keeps sign-ins
    if _which('npx'):
        _add_playwright(claude)
    _drop_plugin(claude)
    r3 = _claude_direct(claude)
    return ('Claude Code: MCP server added and skills copied to ~/.claude/skills' if r3.returncode == 0
            else f'Claude Code: could not add MCP ({r3.stderr.strip()[:200]})')


def _python():
    """The Python to register for the MCP server: a console one (pythonw, which the Windows Startup shortcut uses, has no
    stdin/stdout, so an MCP server started with it can't talk)."""
    py = sys.executable
    if os.path.basename(py).lower() == 'pythonw.exe':
        py = os.path.join(os.path.dirname(py), 'python.exe')
    return py


def _claude_direct(claude):
    """Register ApplyTwin's MCP server straight from the installed app (not Claude Code's plugin cache, which keeps a frozen
    copy from install day: none of the self-updates ever reached the agent that way) and copy the skills."""
    # a first Claude Code launch on Windows (antivirus scanning the fresh install) can take well over a minute
    _claude_cmd(claude, ['mcp', 'remove', '--scope', 'user', 'applytwin'], timeout=240)
    r = _claude_cmd(claude, ['mcp', 'add', '--scope', 'user', 'applytwin', '--', _python(), APPLYTWIN_BIN, 'mcp'], timeout=240)
    _copy_skills(os.path.expanduser('~/.claude/skills'))
    return r


def _plugin_installed():
    try:
        d = json.load(open(os.path.expanduser('~/.claude/plugins/installed_plugins.json'), encoding='utf-8'))
        return 'applytwin@applytwin' in (d.get('plugins', d) or {})
    except (OSError, ValueError):
        return False


def _drop_plugin(claude):
    if _plugin_installed():
        _claude_cmd(claude, ['plugin', 'uninstall', '--scope', 'user', 'applytwin@applytwin'])


def refresh_agents():
    """On every start: make Claude Code run the live app (moving installs off the frozen plugin copy) and keep the twin's
    browser settings current."""
    refresh_browser()
    claude = _which('claude')
    if not claude:
        return
    try:
        cj = os.path.expanduser('~/.claude.json')
        cur = (json.load(open(cj, encoding='utf-8')).get('mcpServers') or {}).get('applytwin') if os.path.exists(cj) else None
        stale = _plugin_installed() or not cur or cur.get('command') != _python() or cur.get('args') != [APPLYTWIN_BIN, 'mcp']
        if stale:   # also when it was never added (Claude Code installed after ApplyTwin)
            _drop_plugin(claude)
            _claude_direct(claude)
    except Exception:
        pass


def install_codex():
    cfg_dir = os.path.expanduser('~/.codex')
    os.makedirs(cfg_dir, exist_ok=True)
    cfg = os.path.join(cfg_dir, 'config.toml')
    txt = open(cfg, encoding='utf-8').read() if os.path.exists(cfg) else ''
    q = json.dumps   # TOML basic strings use JSON escaping, so Windows paths (C:\\Users\\...) stay valid
    # tool_timeout_sec: the resume tool can wait up to 15 minutes for a build on a slow laptop; 300 cut it off mid-run
    block = (f'\n[mcp_servers.applytwin]\ncommand = {q(_python())}\nargs = [{q(APPLYTWIN_BIN)}, "mcp"]\n'
             f'startup_timeout_sec = 20\ntool_timeout_sec = 960\ndefault_tools_approval_mode = "approve"\n')
    if '[mcp_servers.applytwin]' not in txt:
        with open(cfg, 'a', encoding='utf-8') as f:
            f.write(block)
    else:   # repair it in place (its Python may have been upgraded or removed since install)
        txt2 = re.sub(r'(\[mcp_servers\.applytwin\](?:(?!\n\[).)*?\ncommand = )"[^\n]*"', lambda m: m.group(1) + q(_python()), txt, count=1, flags=re.S)
        txt2 = re.sub(r'(\[mcp_servers\.applytwin\](?:(?!\n\[).)*?\nargs = )\[[^\n]*\]', lambda m: m.group(1) + f'[{q(APPLYTWIN_BIN)}, "mcp"]', txt2, count=1, flags=re.S)
        txt2 = re.sub(r'(\[mcp_servers\.applytwin\](?:(?!\n\[).)*?\ntool_timeout_sec = )300\b', r'\g<1>960', txt2, count=1, flags=re.S)
        if txt2 != txt:
            open(cfg, 'w', encoding='utf-8').write(txt2)
    if '[mcp_servers.playwright]' not in txt and _which('npx'):
        pw = playwright()
        args = ', '.join(q(x) for x in pw[1:])
        with open(cfg, 'a', encoding='utf-8') as f:
            f.write(f'\n[mcp_servers.playwright]\ncommand = {q(pw[0])}\nargs = [{args}]\nstartup_timeout_sec = 60\ndefault_tools_approval_mode = "approve"\n')
    # headless `codex exec` cancels MCP calls that need approval, so make sure existing blocks pre-approve ours
    txt = open(cfg, encoding='utf-8').read()
    for k in ('applytwin', 'playwright'):
        m = re.search(rf'\[mcp_servers\.{k}\]\n(?:(?!\n\[).)*', txt, re.S)
        if m and 'default_tools_approval_mode' not in m.group(0):
            txt = txt[:m.end()].rstrip('\n') + '\ndefault_tools_approval_mode = "approve"\n' + txt[m.end():]
    open(cfg, 'w', encoding='utf-8').write(txt)
    for d in ('~/.agents/skills', '~/.codex/skills'):
        _copy_skills(os.path.expanduser(d))
    return 'Codex: added [mcp_servers.applytwin] to ~/.codex/config.toml and skills to ~/.agents/skills'


def install():
    os.chmod(APPLYTWIN_BIN, 0o755)
    print(install_claude())
    if _which('codex') or os.path.isdir(os.path.expanduser('~/.codex')):
        print(install_codex())
    else:   # don't create Codex settings on a computer without Codex (the app adds them once Codex is installed)
        print('Codex not found (skip). Install it any time; ApplyTwin connects it on its next start.')
    print('\nDone. In Claude Code or Codex, say: "set me up with applytwin" to onboard, then "twin: apply to my top 10".')


def has_browser(agent):
    """The twin's browser (Playwright, on its own profile) is registered with this agent."""
    try:
        if agent == 'claude':
            cj = os.path.expanduser('~/.claude.json')
            return bool(os.path.exists(cj) and (json.load(open(cj, encoding='utf-8')).get('mcpServers') or {}).get('playwright'))
        cfg = os.path.expanduser('~/.codex/config.toml')
        return os.path.exists(cfg) and '[mcp_servers.playwright]' in open(cfg, encoding='utf-8').read()
    except (OSError, ValueError):
        return False


def _codex_has_applytwin():
    try:
        cfg = os.path.expanduser('~/.codex/config.toml')
        return os.path.exists(cfg) and '[mcp_servers.applytwin]' in open(cfg, encoding='utf-8').read()
    except OSError:
        return False


def _claude_has_applytwin():
    try:
        cj = os.path.expanduser('~/.claude.json')
        return bool(os.path.exists(cj) and (json.load(open(cj, encoding='utf-8')).get('mcpServers') or {}).get('applytwin'))
    except (OSError, ValueError):
        return False


def ensure_browser(agent):
    """Register ApplyTwin's own tools and the twin's browser when they're missing. Both only got written at install time,
    so anyone who installed Claude Code or Node.js after ApplyTwin was missing one: without the browser their agent fell
    back to tools that can't run unattended, and without ApplyTwin's tools a run had no queue and quit before one job."""
    claude = _which('claude') if agent == 'claude' else None
    if claude and not _claude_has_applytwin():
        try:
            _drop_plugin(claude)
            r = _claude_direct(claude)
            if r.returncode != 0 or not _claude_has_applytwin():
                why = (r.stderr or r.stdout or '').strip()[:300] or f'claude mcp add exited with code {r.returncode}'
                print(f"Couldn't add ApplyTwin to Claude Code: {why}", flush=True)
        except Exception as e:
            print(f"Couldn't add ApplyTwin to Claude Code: {e}", flush=True)
    if agent == 'codex' and os.path.isdir(os.path.expanduser('~/.codex')) and not _codex_has_applytwin():
        try:   # ApplyTwin's own tools, even when the user already had a Playwright server (it used to return before adding them)
            install_codex()
        except Exception as e:
            print(f"Couldn't add ApplyTwin to Codex: {e}", flush=True)
    if has_browser(agent) or not _which('npx'):
        return
    try:
        if claude:
            _add_playwright(claude)
        elif agent == 'codex' and os.path.isdir(os.path.expanduser('~/.codex')):
            install_codex()
    except Exception:
        pass


def refresh_browser():
    """Bring the twin's browser setup in Claude Code and Codex up to date when it was registered by an older version
    (it only gets written at install time), and add it where it's missing."""
    for a in ('claude', 'codex'):
        ensure_browser(a)
    try:
        cj = os.path.expanduser('~/.claude.json')
        cur = (json.load(open(cj, encoding='utf-8')).get('mcpServers') or {}).get('playwright') if os.path.exists(cj) else None
        claude = _which('claude')
        want = _pw_claude()
        if claude and cur and _ours(cur.get('args')) and [cur.get('command')] + list(cur.get('args') or []) != want \
                and not (os.path.basename(cur.get('command') or '') == want[0] and cur.get('args') == want[1:]):
            _add_playwright(claude, previous=cur)
    except Exception:
        pass
    try:
        cfg = os.path.expanduser('~/.codex/config.toml')
        if os.path.exists(cfg):
            txt = open(cfg, encoding='utf-8').read()
            m = re.search(r'(\[mcp_servers\.playwright\]\n(?:(?!\n\[).)*?\nargs = )\[[^\n]*\]', txt, re.S)
            want = '[' + ', '.join(json.dumps(x) for x in playwright()[1:]) + ']'
            if m and (json.dumps(BROWSER_PROFILE) in m.group(0) or json.dumps(_twin.ENDPOINT) in m.group(0)) and not m.group(0).endswith(want):
                open(cfg, 'w', encoding='utf-8').write(txt[:m.start()] + m.group(1) + want + txt[m.end():])
    except Exception:
        pass


def refresh_skills():
    """Keep agents' copies of the ApplyTwin skills current after an update (installs only copy them once)."""
    for d in ('~/.claude/skills', '~/.agents/skills', '~/.codex/skills'):
        dest = os.path.expanduser(d)
        if os.path.isdir(dest) and any(n.startswith('applytwin-') for n in os.listdir(dest)):
            _copy_skills(dest)
