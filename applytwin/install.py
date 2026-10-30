"""Register ApplyTwin with the user's agents.

Claude Code: installs the plugin (skills + MCP server) from this folder's marketplace, or falls back to
             `claude mcp add` + copying skills into ~/.claude/skills.
Codex:       adds [mcp_servers.applytwin] to ~/.codex/config.toml and copies the skills into ~/.agents/skills.
"""
import json
import os
import re
import platform
import shutil
import subprocess
import sys

from . import store

APP = store.APP
APPLYTWIN_BIN = os.path.join(APP, 'bin', 'applytwin')


def notify(title, msg):
    msg = msg.replace('"', "'")[:200]
    try:
        if platform.system() == 'Darwin':
            subprocess.run(['osascript', '-e', f'display notification "{msg}" with title "{title}" sound name "Glass"'], capture_output=True)
        elif platform.system() == 'Windows':
            ps = ("[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null;"
                  "$t = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent(1);"
                  f"$x = $t.GetElementsByTagName('text'); $x.Item(0).AppendChild($t.CreateTextNode('{title.replace(chr(39), '')}')) > $null;"
                  f"$x.Item(1).AppendChild($t.CreateTextNode('{msg.replace(chr(39), '')}')) > $null;"
                  "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('ApplyTwin').Show([Windows.UI.Notifications.ToastNotification]::new($t))")
            subprocess.run(['powershell', '-NoProfile', '-Command', ps], capture_output=True, creationflags=0x08000000)
        elif shutil.which('notify-send'):
            subprocess.run(['notify-send', title, msg], capture_output=True)
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
PLAYWRIGHT = [shutil.which('npx') or 'npx' if platform.system() == 'Windows' else 'npx', '-y', '@playwright/mcp@latest', '--user-data-dir', BROWSER_PROFILE] \
    + ([] if platform.system() == 'Linux' else ['--sandbox'])


def install_claude():
    claude = shutil.which('claude')
    if not claude:
        return 'Claude Code CLI not found (skip). Install it, then rerun: applytwin install-agents'
    # a browser the agent can drive on any machine (Claude in Chrome works too, if installed); the profile keeps sign-ins
    if shutil.which('npx'):
        subprocess.run([claude, 'mcp', 'remove', '--scope', 'user', 'playwright'], capture_output=True)
        subprocess.run([claude, 'mcp', 'add', '--scope', 'user', 'playwright', '--'] + PLAYWRIGHT, capture_output=True)
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
    subprocess.run([claude, 'mcp', 'remove', '--scope', 'user', 'applytwin'], capture_output=True, timeout=60)
    r = subprocess.run([claude, 'mcp', 'add', '--scope', 'user', 'applytwin', '--', _python(), APPLYTWIN_BIN, 'mcp'],
                       capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60)
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
        subprocess.run([claude, 'plugin', 'uninstall', '--scope', 'user', 'applytwin@applytwin'], capture_output=True, timeout=60)


def refresh_agents():
    """On every start: make Claude Code run the live app (moving installs off the frozen plugin copy) and keep the twin's
    browser settings current."""
    refresh_browser()
    claude = shutil.which('claude')
    if not claude:
        return
    try:
        cj = os.path.expanduser('~/.claude.json')
        cur = (json.load(open(cj, encoding='utf-8')).get('mcpServers') or {}).get('applytwin') if os.path.exists(cj) else None
        stale = _plugin_installed() or not cur or cur.get('command') != _python() or cur.get('args') != [APPLYTWIN_BIN, 'mcp']
        if stale and (cur or _plugin_installed() or os.path.isdir(os.path.expanduser('~/.claude/skills/applytwin-apply'))):
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
    block = (f'\n[mcp_servers.applytwin]\ncommand = {q(_python())}\nargs = [{q(APPLYTWIN_BIN)}, "mcp"]\n'
             f'startup_timeout_sec = 20\ntool_timeout_sec = 300\ndefault_tools_approval_mode = "approve"\n')
    if '[mcp_servers.applytwin]' not in txt:
        with open(cfg, 'a', encoding='utf-8') as f:
            f.write(block)
    if '[mcp_servers.playwright]' not in txt and shutil.which('npx'):
        args = ', '.join(q(x) for x in PLAYWRIGHT[1:])
        with open(cfg, 'a', encoding='utf-8') as f:
            f.write(f'\n[mcp_servers.playwright]\ncommand = {q(PLAYWRIGHT[0])}\nargs = [{args}]\nstartup_timeout_sec = 60\ndefault_tools_approval_mode = "approve"\n')
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
    print(install_codex())
    print('\nDone. In Claude Code or Codex, say: "set me up with applytwin" to onboard, then "twin: apply to my top 10".')


def refresh_browser():
    """Bring the twin's browser setup in Claude Code and Codex up to date when it was registered by an older version
    (it only gets written at install time)."""
    try:
        cj = os.path.expanduser('~/.claude.json')
        cur = (json.load(open(cj, encoding='utf-8')).get('mcpServers') or {}).get('playwright') if os.path.exists(cj) else None
        claude = shutil.which('claude')
        if claude and cur and BROWSER_PROFILE in (cur.get('args') or []) and cur.get('args') != PLAYWRIGHT[1:]:
            subprocess.run([claude, 'mcp', 'remove', '--scope', 'user', 'playwright'], capture_output=True, timeout=60)
            subprocess.run([claude, 'mcp', 'add', '--scope', 'user', 'playwright', '--'] + PLAYWRIGHT, capture_output=True, timeout=60)
    except Exception:
        pass
    try:
        cfg = os.path.expanduser('~/.codex/config.toml')
        if os.path.exists(cfg):
            txt = open(cfg, encoding='utf-8').read()
            m = re.search(r'(\[mcp_servers\.playwright\]\n(?:(?!\n\[).)*?\nargs = )\[[^\n]*\]', txt, re.S)
            want = '[' + ', '.join(json.dumps(x) for x in PLAYWRIGHT[1:]) + ']'
            if m and json.dumps(BROWSER_PROFILE) in m.group(0) and not m.group(0).endswith(want):
                open(cfg, 'w', encoding='utf-8').write(txt[:m.start()] + m.group(1) + want + txt[m.end():])
    except Exception:
        pass


def refresh_skills():
    """Keep agents' copies of the ApplyTwin skills current after an update (installs only copy them once)."""
    for d in ('~/.claude/skills', '~/.agents/skills', '~/.codex/skills'):
        dest = os.path.expanduser(d)
        if os.path.isdir(dest) and any(n.startswith('applytwin-') for n in os.listdir(dest)):
            _copy_skills(dest)
