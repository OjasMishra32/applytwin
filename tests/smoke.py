"""End-to-end smoke test on a throwaway APPLYTWIN_HOME: vault -> render every template -> tailor + fact guard -> answers -> MCP."""
import json, os, subprocess, sys, tempfile
os.environ["APPLYTWIN_NO_TELEMETRY"] = "1"   # tests never count as installs
os.environ["APPLYTWIN_SKIP_SIGNIN"] = "1"   # no Google account in tests
for _s in (sys.stdout, sys.stderr):   # Windows consoles default to cp1252, which can't print emoji
    try:
        _s.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, ValueError):
        pass
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ['APPLYTWIN_HOME'] = tempfile.mkdtemp(prefix='applytwin-test-')
sys.path.insert(0, ROOT)
from applytwin import api, render, store  # noqa: E402

store.save('resume.json', json.load(open(os.path.join(ROOT, 'examples', 'resume.example.json'))))
api.update_profile(json.load(open(os.path.join(ROOT, 'examples', 'profile.example.json'))))
ok = lambda c, m: print(('PASS ' if c else 'FAIL ') + m) or c
res = []
for t in render.TEMPLATES:
    r = api.render_resume(t)
    res.append(ok(r['pages'] == 1, f'template {t}: 1 page (score {r["score"]})'))
jd = 'Software Engineer Intern. Requirements: Python, Go, Kafka, PostgreSQL, Kubernetes, CI/CD, distributed systems, data structures.'
j = api.add_job('https://example.com/jobs/1', 'Software Engineer Intern, Summer 2027', 'Example Co', jd)
r = api.tailor_apply(j['id'], None, 'classic', 'heuristic')
res.append(ok(r['pages'] == 1 and r['coverage'] > 0, f'heuristic tailor: coverage {r["coverage"]}%'))
v = api.get_vault(); e = v['experience'][0]; i = e['id']
plan = {"experience": [{"id": i, "bullets": [{"from": i + '.0', "text": e['bullets'][0] + ' for 9 million users'},
                                            {"from": i + '.1', "text": 'Used Terraform and Kubernetes to deploy everything at scale for the team.'}]}]}
r = api.tailor_apply(j['id'], plan, 'classic')
res.append(ok(len(r['rejected']) == 2, f'fact guard blocked {len(r["rejected"])}/2 invented rewrites'))
a = api.answer_questions(['Will you now or in the future require sponsorship for employment visa status?',
                          {'question': 'Are you legally authorized to work in the United States?', 'options': ['Yes', 'No']},
                          'What is your favorite color?'])
res.append(ok(a[0]['answer'] == 'No' and a[1]['answer'] == 'Yes' and a[2]['answer'] is None, 'answer bank matches + asks on unknowns'))
p = subprocess.run([sys.executable, os.path.join(ROOT, 'bin', 'applytwin'), 'mcp'], input='\n'.join(json.dumps(x) for x in [
    {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
    {"jsonrpc": "2.0", "method": "notifications/initialized"},
    {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "applytwin_stats", "arguments": {}}}]) + '\n',
    capture_output=True, text=True, env=os.environ, timeout=60)
lines = [json.loads(x) for x in p.stdout.splitlines() if x.strip()]
res.append(ok(len(lines) == 3 and len(lines[1]['result']['tools']) >= 20 and 'applied_today' in lines[2]['result']['content'][0]['text'],
              f'MCP server: {len(lines[1]["result"]["tools"]) if len(lines) > 1 else 0} tools'))
from applytwin import match

same = [('Tesla', '🔥 Tesla'), ('JPMorgan', 'JPMorganChase'), ('JP Morgan Chase', 'JPMorgan Chase & Co.'), ('Micron', 'Micron Technology'),
        ('Meta', 'Facebook'), ('Google', 'Alphabet Inc.'), ('Stripe', '⭐️ Stripe, Inc.')]
different = [('Meta', 'Metabase'), ('Apple', 'Applied Materials'), ('Ramp', 'Rampart')]
prof = {'search': {'kind': 'internship', 'roles': [], 'companies_skip': ['Tesla', 'JPMorgan']}}
skipped = [match.fit({'title': 'Software Engineer Intern', 'company': c, 'location': 'Austin, TX'}, prof)[0] for c in ('🔥 Tesla', 'JPMorganChase')]
res.append(ok(all(match.same_company(a, b) for a, b in same) and not any(match.same_company(a, b) for a, b in different) and skipped == [0, 0],
              'skip list matches every spelling ("🔥 Tesla", "JPMorganChase") and nothing else'))
# Windows defaults files and pipes to cp1252, which turned en dashes and apostrophes on resumes into �.
# Every text-mode open() and text pipe must say UTF-8.
import glob as _g, re as _re
_bad = []
for _p in _g.glob(os.path.join(ROOT, 'applytwin', '*.py')):
    _s = open(_p, encoding='utf-8').read()
    for _m in _re.finditer(r'(?<![\w.])open\(', _s):
        _j, _d = _m.end(), 1
        while _d:
            _d += {'(': 1, ')': -1}.get(_s[_j], 0); _j += 1
        _a = _s[_m.end():_j - 1]
        if 'encoding=' not in _a and not _re.search(r"""['"][rwa]b['"]""", _a):
            _bad.append(f"{os.path.basename(_p)}:{_s.count(chr(10), 0, _m.start()) + 1}")
    _bad += [f"{os.path.basename(_p)}: text=True without encoding" for _ in _re.finditer(r'text=True(?!, encoding)', _s)]
res.append(ok(not _bad, 'every file and pipe is UTF-8 (Windows) ' + ', '.join(_bad[:5])))
from applytwin import store as _st
_st.save('enc_test.json', {"t": "June 2025 – Aug. 2025, it’s Zoë"})
res.append(ok(_st.load('enc_test.json')['t'] == "June 2025 – Aug. 2025, it’s Zoë", 'dashes and apostrophes survive a save'))
open(_st.path('enc_old.json'), 'wb').write('{"t": "a – b"}'.encode('cp1252'))
res.append(ok(_st.load('enc_old.json')['t'] == "a – b", 'old Windows-encoded files still load'))

from applytwin import answers as _an
_bank = _an.default_bank({**store.profile(), 'location': 'Gainesville, FL'})
_q = [_an.match(x, _bank) for x in ('Race/Ethnicity', 'Current location')]
res.append(ok((_q[0] or {}).get('answer') != 'Gainesville, FL' and (_q[1] or {}).get('answer') == 'Gainesville, FL',
              'Race/Ethnicity is never answered with your city'))
store.execute("insert or replace into jobs(id,source,company,title,url,apply_url,ats,found_at,fit,status) values('pend1','t','Acme','Intern','u','u','lever',0,90,'new')")
api.log_application('pend1', 'Needs User', 'sign-in needed')
_before = any(r['job_id'] == 'pend1' for r in api.pending_jobs())
api.skip_job('pend1')
res.append(ok(_before and not any(r['job_id'] == 'pend1' for r in api.pending_jobs()), 'dismissing a job that needs you clears it'))
_w = [_an.match(x, _bank) for x in ('Please tell us what interested you to apply to CFS', 'Anything else we should know?', 'How did you hear about us?')]
res.append(ok(_w[0].get('action') == 'write' and _w[1].get('action') == 'write' and _w[2].get('action') != 'write' and 'em dash' in _w[0]['how'],
              'open-ended questions get written for each job, facts still come from your answers'))
# a plan that numbers bullets from 1 (what models naturally do) must not shift or drop bullets on everyone's resumes
from applytwin import tailor as _tl
_v = _tl.ensure_ids(json.load(open(os.path.join(ROOT, 'examples', 'resume.example.json'))))
_roles = [e for e in _v['experience'] if len(e.get('bullets', [])) >= 2][:2]
_plan = {"experience": [{"id": e['id'], "bullets": [f"{e['id']}.{i + 1}" for i in range(len(e['bullets']))]} for e in _roles]}
_res, _ = _tl.apply(_v, _plan)
_ok1 = all(r['bullets'] == e['bullets'] for r, e in zip(_res['experience'], _roles))
_plan2 = {"experience": [{"id": e['id'], "bullets": [{"from": f"{e['id']}.{len(e['bullets'])}", "text": e['bullets'][-1]}]} for e in _roles]}
_res2, _ = _tl.apply(_v, _plan2)
_ok2 = all(len(r['bullets']) >= 2 and e['bullets'][-1] in r['bullets'] for r, e in zip(_res2['experience'], _roles))
res.append(ok(_ok1 and _ok2, 'bullets numbered from 1 still land right, and no role is left with fewer than 2'))
# real form questions that used to get the wrong answer
_pb = _an.default_bank({'name': 'Maya Chen', 'location': 'Austin, TX', 'grad_month': 'May', 'grad_year': '2028', 'major': 'Computer Science',
                        'work_authorized_us': True, 'needs_sponsorship': True, 'government_employee': False, 'willing_to_relocate': True})
_cases = {'Preferred First Name': 'Maya', 'Graduation Year': '2028', 'Major': 'Computer Science', 'Last Name': 'Chen',
          'How did you hear about this job? (Referral, LinkedIn, Other)': 'Company careers website',
          'Are you authorized to work in the US without the need for employer sponsorship, now or in the future?': 'No',
          'Are you a current or former employee of the U.S. government?': 'No'}
_bad = {q: _an.match(q, _pb).get('answer') for q, want in _cases.items() if _an.match(q, _pb).get('answer') != want}
_arb = _an.match('I agree to the Mutual Arbitration Agreement', _pb).get('answer')
_essay = _an.match('Please describe any major challenges you faced', _pb).get('action')
res.append(ok(not _bad and _arb is None and _essay == 'write', f'real form questions get the right answer {_bad or ""}'))
from applytwin import telemetry as _tm
res.append(ok(not _tm.enabled() and _tm.ping() is False and len(_tm.install_id()) == 36, 'install count is off in tests and uses only a random ID'))

print(f'\n{sum(res)}/{len(res)} passed')
sys.exit(0 if all(res) else 1)
