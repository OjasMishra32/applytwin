"""Fresh-user end-to-end test: a brand-new person, an empty machine profile, no API keys.

Runs everything in a throwaway HOME and APPLYTWIN_HOME, so the real user's data and agent configs are never touched.
Covers: doctor on an empty setup, resume import, profile, queue, tailoring + PDF, the MCP server over stdio,
install-agents (Claude Code + Codex configs), the web server's endpoints, and the signed-out run guard.

    python3 tests/e2e_fresh.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(ROOT, 'bin', 'applytwin')
TMP = tempfile.mkdtemp(prefix='applytwin-fresh-')
ENV = {k: v for k, v in os.environ.items() if k not in ('ANTHROPIC_API_KEY', 'OPENAI_API_KEY')}
ENV.update(HOME=TMP, APPLYTWIN_HOME=os.path.join(TMP, '.applytwin'))
PORT = 4859

RESUME = """Maya Chen
maya.chen@example.edu | (555) 201-3344 | Austin, TX | linkedin.com/in/mayachen-rn

EDUCATION
University of Texas at Austin, Bachelor of Science in Nursing, Expected May 2028. GPA 3.8

EXPERIENCE
Patient Care Technician, St. David's Medical Center, Austin, TX. June 2025 - Present
- Monitored vital signs for 12+ patients per shift on a 32-bed med-surg unit
- Assisted nurses with wound care, ambulation and EHR charting in Epic
Volunteer, Central Texas Food Bank. 2023 - 2025
- Coordinated weekend distribution for 400+ families

SKILLS
Epic EHR, BLS/CPR certified, phlebotomy, patient education, Spanish (conversational)
"""

JD = """Summer 2027 Nursing Extern. Work alongside RNs on med-surg and ICU units. Requirements: enrolled in a BSN program,
BLS certification, experience with Epic EHR, strong patient communication. Bilingual Spanish a plus."""

results = []


def check(name, ok, detail=''):
    results.append((name, bool(ok)))
    print(('\033[32mPASS\033[0m ' if ok else '\033[31mFAIL\033[0m ') + name + (f'  \033[2m{detail}\033[0m' if detail else ''))


def cli(*args, timeout=180, input=None):
    r = subprocess.run([sys.executable, BIN, *args], env=ENV, capture_output=True, text=True, timeout=timeout, input=input)
    return r.returncode, r.stdout + r.stderr


def http(path, body=None):
    req = urllib.request.Request(f'http://127.0.0.1:{PORT}{path}', data=None if body is None else json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read()
        return json.loads(raw) if r.headers.get('Content-Type', '').startswith('application/json') else raw.decode()


def mcp_session(requests):
    p = subprocess.Popen([sys.executable, BIN, 'mcp'], env=ENV, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    out = []
    for req in requests:
        p.stdin.write(json.dumps(req) + '\n')
        p.stdin.flush()
        if 'id' in req:
            out.append(json.loads(p.stdout.readline()))
    p.terminate()
    return out


def main():
    print(f'fresh home: {TMP}\n')

    # 1. empty setup: doctor must say what's missing, with fixes, and nothing about API keys
    code, out = cli('doctor')
    check('doctor runs on an empty setup', 'Resume imported' in out, f'exit {code}')
    check('doctor flags the missing resume with a fix', 'Drop your resume' in out)
    check('doctor never asks for an API key', 'API_KEY' not in out and 'api key' not in out.lower().replace('no api key', ''))

    # 2. import a resume from a non-CS field
    path = os.path.join(TMP, 'maya_resume.txt')
    open(path, 'w').write(RESUME)
    code, out = cli('import', path, timeout=600)
    check('resume import', code == 0, out.strip().splitlines()[-1] if out.strip() else '')
    vault = json.load(open(os.path.join(ENV['APPLYTWIN_HOME'], 'resume.json')))
    check('vault has experience', len(vault.get('experience', [])) >= 1, f"{len(vault.get('experience', []))} entries")
    prof = json.load(open(os.path.join(ENV['APPLYTWIN_HOME'], 'profile.json')))
    check('profile filled from resume', prof.get('email') == 'maya.chen@example.edu', prof.get('name', ''))

    # 3. web server: pages and endpoints a new user hits
    srv = subprocess.Popen([sys.executable, BIN, 'app', '--no-open', '--port', str(PORT)], env=ENV, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                http('/api/stats')
                break
            except Exception:
                time.sleep(0.2)
        html = http('/')
        check('web app serves', '<div id="root"' in html or 'id="root"' in html)
        d = http('/api/doctor')
        check('/api/doctor', 'items' in d, f"{sum(i['ok'] for i in d['items'])}/{len(d['items'])} ok")
        a = http('/api/agents')
        check('/api/agents reports both agents', set(a) == {'claude', 'codex'},
              ', '.join(f"{k}: {'signed in' if v['signed_in'] else 'signed out' if v['installed'] else 'not installed'}" for k, v in a.items()))

        # 4. add a job by URL + description, then the queue
        j = http('/api/jobs', {'url': 'https://jobs.lever.co/examplehealth/0f6c1f0e-1111-4c2b-9d7a-123456789abc', 'title': 'Summer 2027 Nursing Extern',
                               'company': 'Example Health', 'description': JD})
        check('add a job', j.get('id'), j.get('id', ''))
        q = http('/api/queue?n=10')
        check('job reaches the queue', any(x['id'] == j['id'] for x in q['jobs']), f"{q['total']} in queue")

        # 5. tailor + PDF (heuristic when no agent is signed in in this throwaway home)
        t = http(f"/api/jobs/{j['id']}/tailor", {'mode': 'auto'})
        check('tailored resume', t.get('pdf') and os.path.exists(t['pdf']), f"mode {t.get('mode')}, {t.get('pages')} page(s)")
        check('fits on one page', t.get('pages') == 1)
        txt = open(t['pdf'], 'rb').read()
        check('PDF is real', txt[:4] == b'%PDF' and len(txt) > 5000, f'{len(txt):,} bytes')

        # 6. answers the bank already knows for a new user
        ans = http('/api/answer/test', {'questions': ['Are you legally authorized to work in the United States?', 'What is your expected graduation date?']})
        check('answer bank fills standard questions', all(x.get('answer') for x in ans), ' | '.join(str(x.get('answer')) for x in ans))

        # 7. run guard: starting an agent that isn't signed in must fail with the fix, not hang
        name = next((k for k, v in a.items() if v['installed'] and not v['signed_in']), None)
        if name:
            try:
                http('/api/run', {'agent': name, 'n': 1})
                check('signed-out run is refused', False)
            except urllib.error.HTTPError as e:
                msg = json.loads(e.read()).get('error', '')
                check('signed-out run is refused with the fix', 'signed out' in msg.lower() and ('login' in msg), msg)
    finally:
        srv.terminate()

    # 8. MCP server over stdio, the way Claude Code / Codex talk to it
    init = {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-06-18', 'capabilities': {}, 'clientInfo': {'name': 'e2e', 'version': '1'}}}
    out = mcp_session([init, {'jsonrpc': '2.0', 'method': 'notifications/initialized'}, {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'},
                       {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': 'applytwin_setup_status', 'arguments': {}}}])
    tools = out[1].get('result', {}).get('tools', [])
    check('MCP initialize', out[0].get('result', {}).get('serverInfo'))
    check('MCP lists tools', len(tools) >= 30, f'{len(tools)} tools')
    check('MCP tool call works', not out[2].get('error') and out[2].get('result', {}).get('content'))

    # 9. install-agents writes working configs for both agents (into the throwaway HOME)
    code, out = cli('install-agents', timeout=300)
    check('install-agents runs', code == 0, out.strip().replace('\n', ' | ')[:160])
    ccfg = os.path.join(TMP, '.codex', 'config.toml')
    if shutil.which('codex'):
        t = open(ccfg).read() if os.path.exists(ccfg) else ''
        check('Codex config has ApplyTwin + browser', '[mcp_servers.applytwin]' in t and '[mcp_servers.playwright]' in t)
        check('Codex config pre-approves ApplyTwin tools', t.count('default_tools_approval_mode') >= 2)
        check('Codex skills installed', os.path.isdir(os.path.join(TMP, '.agents', 'skills', 'applytwin-apply')))
    if shutil.which('claude'):
        cj = os.path.join(TMP, '.claude.json')
        check('Claude Code has ApplyTwin', os.path.exists(cj) and 'applytwin' in open(cj).read())
        plug = os.path.join(TMP, '.claude', 'plugins')
        via_plugin = os.path.isdir(plug) and 'applytwin' in json.dumps([f for _, _, fs in os.walk(plug) for f in fs] + [d for _, ds, _ in os.walk(plug) for d in ds])
        check('Claude Code skills installed', via_plugin or os.path.isdir(os.path.join(TMP, '.claude', 'skills', 'applytwin-apply')),
              'via plugin' if via_plugin else 'copied')

    code, out = cli('doctor')
    if shutil.which('claude') or shutil.which('codex'):
        check('doctor after setup: agents connected', 'Resume imported' in out and 'connected to' in out)
    else:   # a machine with neither agent: doctor must say how to install one
        check('doctor without agents explains the install', 'npm install -g' in out)

    bad = [n for n, ok in results if not ok]
    print(f'\n{len(results) - len(bad)}/{len(results)} passed' + (f"  failed: {', '.join(bad)}" if bad else ''))
    shutil.rmtree(TMP, ignore_errors=True)
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
