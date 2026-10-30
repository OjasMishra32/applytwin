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
PLAYWRIGHT = [shutil.which('npx') or 'npx' if platform.system() == 'Windows' else 'npx', '-y', '@playwright/mcp@latest', '--user-data-dir', BROWSER_PROFILE]


def install_claude():
    claude = shutil.which('claude')
    if not claude:
        return 'Claude Code CLI not found (skip). Install it, then rerun: applytwin install-agents'
    # a browser the agent can drive on any machine (Claude in Chrome works too, if installed); the profile keeps sign-ins
    if shutil.which('npx'):
        subprocess.run([claude, 'mcp', 'remove', '--scope', 'user', 'playwright'], capture_output=True)
        subprocess.run([claude, 'mcp', 'add', '--scope', 'user', 'playwright', '--'] + PLAYWRIGHT, capture_output=True)
    # the plugin launches `python3`, which usually isn't on PATH on Windows; there, register this exact Python instead
    r2 = None
    if platform.system() != 'Windows':
        subprocess.run([claude, 'plugin', 'marketplace', 'add', APP], capture_output=True, text=True)
        r2 = subprocess.run([claude, 'plugin', 'install', 'applytwin@applytwin'], capture_output=True, text=True)
    if r2 is not None and r2.returncode == 0:
        return 'Claude Code: installed plugin applytwin@applytwin (skills + MCP). Restart Claude Code.'
    subprocess.run([claude, 'mcp', 'remove', '--scope', 'user', 'applytwin'], capture_output=True)
    r3 = subprocess.run([claude, 'mcp', 'add', '--scope', 'user', 'applytwin', '--', sys.executable, APPLYTWIN_BIN, 'mcp'],
                        capture_output=True, text=True)
    _copy_skills(os.path.expanduser('~/.claude/skills'))
    return ('Claude Code: MCP server added and skills copied to ~/.claude/skills' if r3.returncode == 0
            else f'Claude Code: could not add MCP ({r3.stderr.strip()[:200]})')


def install_codex():
    cfg_dir = os.path.expanduser('~/.codex')
    os.makedirs(cfg_dir, exist_ok=True)
    cfg = os.path.join(cfg_dir, 'config.toml')
    txt = open(cfg).read() if os.path.exists(cfg) else ''
    q = json.dumps   # TOML basic strings use JSON escaping, so Windows paths (C:\\Users\\...) stay valid
    block = (f'\n[mcp_servers.applytwin]\ncommand = {q(sys.executable)}\nargs = [{q(APPLYTWIN_BIN)}, "mcp"]\n'
             f'startup_timeout_sec = 20\ntool_timeout_sec = 300\ndefault_tools_approval_mode = "approve"\n')
    if '[mcp_servers.applytwin]' not in txt:
        with open(cfg, 'a') as f:
            f.write(block)
    if '[mcp_servers.playwright]' not in txt and shutil.which('npx'):
        args = ', '.join(q(x) for x in PLAYWRIGHT[1:])
        with open(cfg, 'a') as f:
            f.write(f'\n[mcp_servers.playwright]\ncommand = {q(PLAYWRIGHT[0])}\nargs = [{args}]\nstartup_timeout_sec = 60\ndefault_tools_approval_mode = "approve"\n')
    # headless `codex exec` cancels MCP calls that need approval, so make sure existing blocks pre-approve ours
    txt = open(cfg).read()
    for k in ('applytwin', 'playwright'):
        m = re.search(rf'\[mcp_servers\.{k}\]\n(?:(?!\n\[).)*', txt, re.S)
        if m and 'default_tools_approval_mode' not in m.group(0):
            txt = txt[:m.end()].rstrip('\n') + '\ndefault_tools_approval_mode = "approve"\n' + txt[m.end():]
    open(cfg, 'w').write(txt)
    for d in ('~/.agents/skills', '~/.codex/skills'):
        _copy_skills(os.path.expanduser(d))
    return 'Codex: added [mcp_servers.applytwin] to ~/.codex/config.toml and skills to ~/.agents/skills'


def install():
    os.chmod(APPLYTWIN_BIN, 0o755)
    print(install_claude())
    print(install_codex())
    print('\nDone. In Claude Code or Codex, say: "set me up with applytwin" to onboard, then "twin: apply to my top 10".')


def refresh_skills():
    """Keep agents' copies of the ApplyTwin skills current after an update (installs only copy them once)."""
    for d in ('~/.claude/skills', '~/.agents/skills', '~/.codex/skills'):
        dest = os.path.expanduser(d)
        if os.path.isdir(dest) and any(n.startswith('applytwin-') for n in os.listdir(dest)):
            _copy_skills(dest)
