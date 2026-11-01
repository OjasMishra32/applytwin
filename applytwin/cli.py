"""applytwin <command>

  applytwin app                 open the web app (http://localhost:4747)
  applytwin scan                scrape every source and score matches
  applytwin jobs [query]        list top matches
  applytwin tailor JOB_ID [--template classic] [--plan plan.json]
  applytwin render [--template classic]       master resume PDF
  applytwin ats [JOB_ID]        ATS report for the vault (vs a job)
  applytwin templates           list resume templates
  applytwin mcp                 run the MCP server (used by Claude Code / Codex)
  applytwin install-agents      register ApplyTwin with Claude Code and Codex on this machine
  applytwin watch [--every 120] keep scanning; notify on new matches
  applytwin import FILE      import a resume (pdf, docx, tex, txt) into your vault
  applytwin queue            show your apply queue (dream companies first)
  applytwin import-history tracker.csv   mark jobs you already applied to elsewhere
  applytwin run [--agent claude|codex] [--n 25]   let your agent work through the queue
  applytwin update           update to the latest version (installed copies also update themselves on start)
  applytwin doctor           check your setup (no API keys needed: it runs on your Claude / Codex plan)
"""
import json
import os
import sys
import time

from . import api


def _arg(flag, default=None):
    if flag in sys.argv:
        i = sys.argv.index(flag)
        return sys.argv[i + 1] if i + 1 < len(sys.argv) else default
    return default


def _p(x):
    print(json.dumps(x, indent=1, default=str, ensure_ascii=False))


def _no_console():
    """pythonw (the Windows Startup shortcut) has no console: sys.stdout/stderr are None, so messages and crash reports
    went nowhere. Send them to server.log in the data folder instead."""
    if sys.stdout is not None and sys.stderr is not None:
        return
    try:
        from . import store
        log = store.path('server.log')
        big = os.path.exists(log) and os.path.getsize(log) > 1_000_000
        f = open(log, 'w' if big else 'a', encoding='utf-8', errors='replace', buffering=1)
        sys.stdout = sys.stdout or f
        sys.stderr = sys.stderr or f
    except OSError:
        pass


def _paint(code, s):
    """Color in a terminal only: piped (the Windows installer shows this output) the escape codes print as junk."""
    return f'\033[{code}m{s}\033[0m' if sys.stdout is not None and sys.stdout.isatty() else s


def main():
    _no_console()
    # Windows consoles default to cp1252, which can't print ✓ or →; and the agent sends the MCP server UTF-8 on stdin
    # (José arrived as JosÃ©)
    for stream in (sys.stdout, sys.stderr, sys.stdin):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, ValueError):
            pass
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'app'
    if cmd in ('app', 'serve'):
        from .server import serve
        serve(int(_arg('--port', 4747)), '--no-open' not in sys.argv)
    elif cmd == 'mcp':
        from .mcp import main as m
        m()
    elif cmd == 'scan':
        _p(api.scan())
    elif cmd == 'scan-worker':   # the app's background scan, in its own process (not for typing by hand)
        import json as _json
        api.scan_worker(_json.loads(sys.argv[2]) if len(sys.argv) > 2 else None)
    elif cmd == 'jobs':
        q = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith('-') else ''
        for j in api.list_jobs(q, limit=int(_arg('--limit', 40))):
            print(f"{int(j['fit']):>3}  {j['id']}  {j['company'][:22]:<22} {j['title'][:70]}  [{j['ats']}]")
    elif cmd == 'tailor':
        plan = json.load(open(_arg('--plan'), encoding='utf-8')) if _arg('--plan') else None
        _p(api.tailor_apply(sys.argv[2], plan, _arg('--template'), 'agent' if plan else 'auto'))
    elif cmd == 'render':
        _p(api.render_resume(_arg('--template')))
    elif cmd == 'ats':
        _p(api.ats_report(sys.argv[2] if len(sys.argv) > 2 else None))
    elif cmd == 'templates':
        for t in api.templates():
            print(f"{t['id']:<9} {t['label']:<22} {t['best']}")
    elif cmd == 'import':
        import base64
        f = sys.argv[2]
        r = api.import_resume(os.path.basename(f), base64.b64encode(open(f, 'rb').read()).decode())
        print(r['message'])
    elif cmd == 'update':
        from . import update
        st = update.check()
        if not st['managed']:
            print('This is a git checkout: run git pull.')
        elif not st['available']:
            print(f"Already up to date ({st['current'] or 'unknown'}).")
        else:
            r = update.apply()
            print(f"Updated to {r['sha']}" if r.get('updated') else r.get('reason', 'No update applied.'))
    elif cmd == 'doctor':
        d = api.doctor()
        for i in d['items']:
            mark = _paint(32, '✓') if i['ok'] else (_paint(33, '·') if i['optional'] else _paint(31, '✗'))
            print(f"{mark} {i['label']}" + (f"  {_paint(2, i['detail'])}" if i['detail'] else ''))
            if not i['ok'] and i['fix']:
                print(f"    → {i['fix']}")
        print('\nReady to apply.' if d['ok'] else '\nFix the ✗ items above, then run `applytwin doctor` again.')
        print(_paint(33, '★') + ' Like ApplyTwin? Star it so other students find it: https://github.com/OjasMishra32/applytwin')
        sys.exit(0 if d['ok'] else 1)
    elif cmd == 'import-history':
        _p(api.import_history(sys.argv[2]))
    elif cmd == 'queue':
        q = api.queue(int(_arg('--n', 30)))
        print(f"{q['total']} in queue ({q['dream']} at dream companies), {q['remaining_today']} left today")
        for j in q['jobs']:
            print(f"{'*' if j['dream'] else ' '} {int(j['fit']):>3}  {j['id']}  {j['company'][:22]:<22} {j['title'][:70]}")
    elif cmd == 'run':
        import shutil
        import subprocess
        agent, n = _arg('--agent', 'claude'), int(_arg('--n', 25))
        exe = shutil.which(agent) or sys.exit(f'{agent} not found on PATH')
        p = api.run_prompt(n)
        if os.name == 'nt':
            # claude/codex are npm .cmd wrappers there: cmd.exe cuts a long argument at its first quote or & and exec can't
            # start a .cmd at all, so hand over a short instruction that points at the full one in a file
            from . import store
            with open(store.path('run-prompt.txt'), 'w', encoding='utf-8') as f:
                f.write(p)
            sys.exit(subprocess.call([exe, f'Read the file {store.path("run-prompt.txt")} and follow the instructions in it.']))
        os.execv(exe, [exe, p] if agent == 'claude' else [exe, p])
    elif cmd == 'install-agents':
        from .install import install
        install()
    elif cmd == 'watch':
        every = int(_arg('--every', 120))
        seen = {j['id'] for j in api.list_jobs(status='all', limit=100000)}
        while True:
            api.scan(['smartrecruiters', 'community'])
            new = [j for j in api.list_jobs(order='new', limit=50) if j['id'] not in seen]
            for j in new:
                seen.add(j['id'])
                print(time.strftime('%H:%M'), int(j['fit']), j['company'], '|', j['title'], '|', j['apply_url'])
            if new:
                from .install import notify
                notify('ApplyTwin: new match', f"{new[0]['company']}: {new[0]['title']}" + (f' (+{len(new) - 1})' if len(new) > 1 else ''),
                       f"http://localhost:4747/#jobs/{new[0]['id']}" if len(new) == 1 else 'http://localhost:4747/#jobs')
            time.sleep(every)
    else:
        print(__doc__)
