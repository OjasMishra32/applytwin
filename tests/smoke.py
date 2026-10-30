"""End-to-end smoke test on a throwaway APPLYTWIN_HOME: vault -> render every template -> tailor + fact guard -> answers -> MCP."""
import json, os, subprocess, sys, tempfile, time
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
_by = {r['id']: r for r in _res['experience']}
_ok1 = all(_by[e['id']]['bullets'] == e['bullets'] for e in _roles)
_plan2 = {"experience": [{"id": e['id'], "bullets": [{"from": f"{e['id']}.{len(e['bullets'])}", "text": e['bullets'][-1]}]} for e in _roles]}
_res2, _ = _tl.apply(_v, _plan2)
_by2 = {r['id']: r for r in _res2['experience']}
_ok2 = all(len(_by2[e['id']]['bullets']) >= 2 and e['bullets'][-1] in _by2[e['id']]['bullets'] for e in _roles)
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
# messages to the twin: only clear, short phrasings act instantly; everything else goes to the agent
_it = {'did you submit this?': 'status', 'I submitted it': 'applied', 'skip it': 'skip', 'submit it': 'submit',
       'Done, I signed in. Finish it': None, 'I applied the change, now resubmit': None, "don't skip it, finish it": None,
       'remove this bullet from the resume and refill': None}
_wrong = {m: api.intent(m) for m, want in _it.items() if api.intent(m) != want}
res.append(ok(not _wrong, f'messages to the twin are never misread {_wrong or ""}'))
# limits, skip list and statuses hold everywhere the agent can go
p0 = store.profile()
api.update_profile({**p0, 'search': {**p0['search'], 'companies_skip': ['Skipco']}, 'apply': {**p0['apply'], 'daily_limit': 1}})
for _jid, _co in (('lim1', 'Skipco Inc'), ('lim2', 'Okco'), ('lim3', 'Okco2')):
    store.execute("insert or replace into jobs(id,source,company,title,url,apply_url,ats,found_at,fit,status) values(?,?,?,?,?,?,?,?,?,'new')",
                  (_jid, 't', _co, 'Software Intern', 'https://x/' + _jid, 'https://x/' + _jid, 'lever', 0, 95))
store.execute("delete from applications where at > ?", (time.time() - 86400,))
_q = [j['company'] for j in api.queue(50)['jobs']]
_skipped = 'Skipco Inc' not in _q and api.claim('lim1')['claimed'] is False
api.log_application('lim2', 'submitted')
_canon = store.rows("select status from applications where job_id='lim2'")[0]['status'] == 'Applied'
_limited = api.next_jobs(5)['jobs'] == [] and api.claim('lim3')['claimed'] is False and api.queue(5, for_agent=True)['jobs'] == []
store.claim('lim3'); api.release_claims()
_released = api._latest('lim3')['status'] == 'Needs User'
api.update_profile(p0)
res.append(ok(_skipped and _canon and _limited and _released, f'skip list, daily limit, statuses and unfinished claims hold ({_skipped}, {_canon}, {_limited}, {_released})'))
# a thin plan never ships a half-empty page: the tailor adds the user's next best true bullets until the page is full
_thin = {"experience": [{"id": _v['experience'][0]['id'], "bullets": [f"{_v['experience'][0]['id']}.0"]}], "projects": [], "leadership": []}
_tr = _tl.tailor(store.load('resume.json'), {'id': 'fill', 'title': 'Software Engineer Intern', 'company': 'Acme'},
                 'Python distributed systems backend APIs', plan=_thin, style='classic')
res.append(ok(_tr['pages'] == 1 and len(_tr['added']) >= 2, f"thin plans are filled to a full page ({len(_tr['added'])} added)"))
# importing without AI: job titles aren't headings, wrapped lines stay in their bullet, any bullet style (or none) works
from applytwin import importer as _imp
_txt = '''Jordan Lee
(555) 123-4567 | jordan@ufl.edu
Experience
Acme Corp Jun 2025 – Aug 2025
Software Engineering Intern Remote
• Built a payments API in Go serving 2M requests per day, cutting p99 latency by 30% across
the checkout flow launched in 2025
• Wrote integration tests in Python
UF Machine Learning Lab Jan 2025 – Present
Research Assistant
• Trained a ResNet model on 50K images reaching 92% accuracy
Projects
Ledgerly | TypeScript, Next.js
• Built an expenses app with 2,000 users
Tinydb | Rust
• Implemented an LSM-tree store at 180K writes/sec
'''
_shapes = []
for _t in (_txt, _txt.replace('• ', '➢ '), _txt.replace('• ', '')):
    _p = _imp.parse(_t)
    _shapes.append(([(e.get('org'), len(e.get('bullets', []))) for e in _p['experience']], [(e.get('name'), len(e.get('bullets', []))) for e in _p['projects']]))
_want = ([('Acme Corp', 2), ('UF Machine Learning Lab', 1)], [('Ledgerly', 1), ('Tinydb', 1)])
res.append(ok(all(sh == _want for sh in _shapes), f'resumes import right with any bullet style {[sh for sh in _shapes if sh != _want][:1]}'))
from applytwin import telemetry as _tm
res.append(ok(not _tm.enabled() and _tm.ping() is False and len(_tm.install_id()) == 36, 'install count is off in tests and uses only a random ID'))

print(f'\n{sum(res)}/{len(res)} passed')
sys.exit(0 if all(res) else 1)
