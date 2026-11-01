"""End-to-end smoke test on a throwaway APPLYTWIN_HOME: vault -> render every template -> tailor + fact guard -> answers -> MCP."""
import json
import time, os, subprocess, sys, tempfile, time
os.environ.setdefault('APPLYTWIN_NO_TWIN', '1')   # never open or reach the real twin browser
os.environ.setdefault('APPLYTWIN_SCAN_INLINE', '1')   # scans stay in-process so tests can stand in for them
os.environ["APPLYTWIN_NO_TELEMETRY"] = "1"   # tests never count as installs
os.environ["APPLYTWIN_SKIP_SIGNIN"] = "1"   # no Google account in tests
for _s in (sys.stdout, sys.stderr):   # Windows consoles default to cp1252, which can't print emoji
    try:
        _s.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, ValueError):
        pass
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ['APPLYTWIN_HOME'] = tempfile.mkdtemp(prefix='applytwin-test-')
os.environ['APPLYTWIN_NO_AGENT'] = '1'   # no real Claude/Codex calls: same results here as on CI
sys.path.insert(0, ROOT)
from applytwin import api, render, store  # noqa: E402

store.save('resume.json', json.load(open(os.path.join(ROOT, 'examples', 'resume.example.json'))))
api.update_profile(json.load(open(os.path.join(ROOT, 'examples', 'profile.example.json'))))
ok = lambda c, m: print(('PASS ' if c else 'FAIL ') + m) or c
res = []
from applytwin import ats as _ats
_norm = lambda s: ' '.join(s.translate(str.maketrans({'\u2019': "'", '\u2018': "'", '\u201c': '"', '\u201d': '"'})).split())
for t in render.TEMPLATES:
    r = api.render_resume(t)
    res.append(ok(r['pages'] == 1, f'template {t}: 1 page (score {r["score"]})'))
    # what a resume parser reads: every bullet that made the page, word for word and in order, no ligature glyphs or
    # words broken onto their own lines, headings in reading order, the email exactly as typed
    _txt = _norm(render.pdf_text(r['pdf']) or '')
    _bl = [_norm(_ats.plain(render.clean(b))) for s in ('experience', 'projects', 'leadership') for e in r['resume'].get(s, []) for b in e.get('bullets', [])]
    _miss = [b[:50] for b in _bl if b not in _txt]
    _iss = _ats.text_layer_issues(render.pdf_text(r['pdf']), r['resume'])
    _lint = next(c for c in r['lint'] if c['id'] == 'parse')
    res.append(ok(_bl and not _miss and not _iss and _lint['level'] == 'pass' and r['scale'] >= .9,
                  f'template {t}: clean text layer, {len(_bl)} bullets intact at type scale {r["scale"]} {_miss[:2]} {_iss}'))
# the fitter fills the page: a short resume sets its type a little larger and opens up its spacing instead of ending
# halfway down; ligature glyphs and invisible characters pasted from a PDF never reach the page
_short = api.get_vault()
_short = {**_short, 'experience': _short['experience'][:1], 'projects': _short['projects'][:1], 'research': [], 'leadership': [],
          'awards': [], 'skills': _short['skills'][:2]}
_short['experience'] = [{**_short['experience'][0], 'bullets': ['Built an \ufb01nance e\ufb03cient work\ufb02ow\u00ad tool with zero\u200bwidth care.'] + _short['experience'][0]['bullets'][1:]}]
_rs = render.render(_short, 'classic', os.path.join(os.environ['APPLYTWIN_HOME'], 'short.pdf'))
_ts = render.pdf_text(_rs['pdf']) or ''
res.append(ok(_rs['pages'] == 1 and _rs['scale'] > 1 and _rs.get('spacing', 1) > 1 and 'efficient workflow tool with zerowidth' in _ts
              and not _ats.text_layer_issues(_ts), f'short resume fills the page (scale {_rs["scale"]}, spacing {_rs.get("spacing")}); pasted ligatures cleaned'))
_rl = render.render(json.load(open(os.path.join(ROOT, 'examples', 'resume.example.json'))), 'latex', os.path.join(os.environ['APPLYTWIN_HOME'], 'l.pdf'))
_tl = render.pdf_text(_rl['pdf']) or ''
res.append(ok(_rl['pages'] == 1 and not _ats.text_layer_issues(_tl), f'latex template: 1 page, no ligature glyphs in the text layer {_ats.text_layer_issues(_tl)}'))
jd = 'Software Engineer Intern. Requirements: Python, Go, Kafka, PostgreSQL, Kubernetes, CI/CD, distributed systems, data structures.'
j = api.add_job('https://example.com/jobs/1', 'Software Engineer Intern, Summer 2027', 'Example Co', jd)
r = api.tailor_apply(j['id'], None, 'classic', 'heuristic')
res.append(ok(r['pages'] == 1 and r['coverage'] > 0, f'heuristic tailor: coverage {r["coverage"]}%'))
v = api.get_vault(); e = v['experience'][0]; i = e['id']
plan = {"experience": [{"id": i, "bullets": [{"from": i + '.0', "text": e['bullets'][0] + ' for 9 million users'},
                                            {"from": i + '.1', "text": 'Deployed everything to 40 Kubernetes clusters serving 2M requests a day for the team.'}]}]}
r = api.tailor_apply(j['id'], plan, 'classic')
res.append(ok(len(r['rejected']) == 2, f'fact guard blocked {len(r["rejected"])}/2 rewrites with invented numbers'))
# policy (2026-10-30): numbers, titles and awards are locked; tools and outcomes may be framed toward the posting
from applytwin import tailor as _tg
_ent = 'Backend intern. Built a Go service on Kafka handling 40K events/sec.'
_why = _tg.check_rewrite('Built a Go service on Kafka handling 40K events/sec.', 'Built a Go service on Kafka handling 40K events/sec, deployed with Terraform on Kubernetes.',
                         'Go Kafka 40K events/sec', jd, _ent)
res.append(ok(_why is None, f'a rewrite may add tools; only numbers and titles are locked ({_why})'))
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
_roles = [e for e in _v['experience'] if len(e.get('bullets', [])) >= 2 and not _tl.WEAK.search(e['bullets'][-1])][:2]
_plan = {"experience": [{"id": e['id'], "bullets": [f"{e['id']}.{i + 1}" for i in range(len(e['bullets']))]} for e in _roles]}
_res, _ = _tl.apply(_v, _plan)
_by = {r['id']: r for r in _res['experience']}
_ok1 = all(_by[e['id']]['bullets'] == e['bullets'] for e in _roles)
_plan2 = {"experience": [{"id": e['id'], "bullets": [{"from": f"{e['id']}.{len(e['bullets'])}", "text": e['bullets'][-1]}]} for e in _roles]}
_res2, _ = _tl.apply(_v, _plan2)
_by2 = {r['id']: r for r in _res2['experience']}
_ok2 = all(len(_by2[e['id']]['bullets']) >= 2 and e['bullets'][-1] in _by2[e['id']]['bullets'] for e in _roles)
res.append(ok(_ok1 and _ok2, 'bullets numbered from 1 still land right, and no role is left with fewer than 2'))
# filler never takes a line from a stronger true bullet in the same role; the plan's order among recent roles stands;
# an award already stated elsewhere isn't repeated
_r3 = {"id": "acme", "org": "Acme", "title": "Analyst", "dates": "Jan 2020 – Present",
       "bullets": ["Helped with literature review for the team.", "Built a **pandas** pipeline that cut report time **70%** across 12 desks.",
                   "Attended weekly meetings."]}
_r4 = {"id": "bigco", "org": "BigCo", "title": "Intern", "start": "Jun " + time.strftime('%Y'), "end": "Aug " + time.strftime('%Y'),
       "bullets": ["Modeled a $40M acquisition in Excel.", "Wrote 3 CIM sections."]}
_v3 = {"basics": {"name": "T"}, "education": [{"school": "State U", "honors": ["Dean's List (6 semesters)"]}],
       "experience": [_r3, _r4], "awards": ["Dean's List (6 semesters)", "CFA Research Challenge finalist"]}
_res3, _ = _tl.apply(_v3, {"experience": [{"id": "bigco"}, {"id": "acme", "bullets": ["acme.0", "acme.2"]}], "awards": [0, 1]})
_b3 = _res3['experience'][1]['bullets'] if _res3['experience'][0]['id'] == 'bigco' else []
res.append(ok(_res3['experience'][0]['id'] == 'bigco' and _r3['bullets'][1] in _b3 and _r3['bullets'][0] not in _b3
              and not _res3['awards'] and _res3['education'][0]['honors'][-1] == "CFA Research Challenge finalist",
              f'filler bullets swapped for stronger true ones, recent roles keep relevance order, no repeated awards {_b3}'))
# a rewrite and the bullet it came from never both appear; skills/awards close the page; degree lines read right
from applytwin.render import degree_line as _dl
_v5 = {"basics": {"name": "T"}, "education": [{"school": "U", "degree": "Bachelor of Science in Management", "major": "Finance"}],
       "experience": [{"id": "lab", "org": "Lab", "title": "RA", "dates": "2025", "bullets": [
           "Wrote regression tests comparing outputs to the legacy code to 1e-12 relative tolerance.",
           "Ported a 40K-line Fortran solver to C++ and CUDA, cutting runtime 9x on A100s.", "Ran nightly builds on 3 clusters."]}],
       "skills": [{"label": "Languages", "items": ["C++"]}], "order": ["skills", "education", "experience"]}
_res5, _ = _tl.apply(_v5, {"order": ["skills", "experience"], "experience": [{"id": "lab", "bullets": [
    {"from": "lab.0", "text": "Built a regression test suite comparing outputs to the legacy code to 1e-12 relative tolerance."}, "lab.1"]}]})
_b5 = _res5['experience'][0]['bullets']
res.append(ok(not any(b == _v5['experience'][0]['bullets'][0] for b in _b5) and len(_b5) >= 2 and _res5['order'][-1] == 'skills'
              and _dl(_v5['education'][0]) == 'Bachelor of Science in Management, Finance'
              and _dl({"degree": "B.S.", "major": "Physics"}) == 'B.S. in Physics',
              f'no bullet twice (rewrite + original), skills close the page, degree lines read right {_b5} {_res5["order"]}'))
# an overclaiming rewrite goes back to the user's own words; one fact never takes two lines
_orig_call = _tl.call_llm
_tl.call_llm = lambda text, timeout=600, fast=False: {"overclaims": [{"id": "0", "why": "ran vs analyzed"}]}
_rep6 = {"rewrites": [{"bullet": "x.0", "from": "Analyzed a checkout A/B test across 2.4M users.", "to": "Ran a checkout A/B test across 2.4M users."},
                      {"bullet": "x.1", "from": "Wrote dbt models replacing 9 SQL queries.", "to": "Replaced 9 SQL queries with dbt models."}], "rejected": []}
_res6 = {"experience": [{"bullets": [r["to"] for r in _rep6["rewrites"]]}]}
_tl.audit(_res6, _rep6)
_tl.call_llm = _orig_call
res.append(ok(_res6["experience"][0]["bullets"] == ["Analyzed a checkout A/B test across 2.4M users.", "Replaced 9 SQL queries with dbt models."]
              and len(_rep6["rejected"]) == 1 and _tl._one_per_fact([
                  "Implemented an implicit-explicit time-stepping scheme allowing 6x larger time steps",
                  "Wrote an implicit-explicit Runge-Kutta time stepper that allowed 6x larger time steps at the same accuracy",
                  "Scaled the solver to 2,048 cores on Frontera"]).__len__() == 2,
              'overclaiming rewrites revert to the vault, one fact never takes two lines'))
# trimming to one page keeps the measured, plan-chosen bullet over an unmeasured one that merely shares a keyword
from applytwin import ats as _ats
_jd7 = 'You will review code and pull requests in Python and TypeScript for developer tools.'
_res7 = {"projects": [{"bullets": ["Merged **5 PRs** into kubernetes/kubectl, including a fix for events sorting and clearer selector errors.",
                                   "Reviewed pull requests and triaged open issues as part of SIG CLI."]}]}
_w7 = _tl.trim_worth(_res7, _ats.keywords(_jd7), _jd7)
res.append(ok(_w7(_res7["projects"][0]["bullets"][0]) > _w7(_res7["projects"][0]["bullets"][1]), 'trimming keeps measured results over keyword-only lines'))
# the headline can name the role in vault-backed words; a tool the posting names joins skills; coursework is trimmed to fit
_v8 = {"basics": {"name": "T", "headline": ["NLP"]}, "education": [{"school": "U", "coursework": ["Organic Chemistry", "Process Control",
       "Biochemistry", "Transport Phenomena", "Lean Manufacturing", "Poetry", "Statistics for Engineers"]}],
       "projects": [{"id": "rec", "name": "Recipe Recommender", "tech": ["Python", "Excel"], "bullets": ["Built a recommender system with matrix factorization over 2M ratings."]}],
       "skills": [{"label": "Software", "items": ["Python"]}]}
_jd8 = "Process engineering intern: lean manufacturing, process control, statistics. Proficiency with Microsoft Excel required."
_res8, _ = _tl.apply(_v8, {"headline": ["Recommendation Systems", "Quantum Gravity", "NLP"], "projects": [{"id": "rec"}]}, _jd8)
res.append(ok(_res8['basics']['headline'] == ["Recommendation Systems", "NLP"] and 'Excel' in _res8['skills'][0]['items']
              and len(_res8['education'][0]['coursework']) == 6 and 'Poetry' not in _res8['education'][0]['coursework'],
              f"role-named headline from vault words, posting's named tools in skills, coursework trimmed {_res8['basics']['headline']}"))
# a titled design-team role can lead Experience when it's the best proof, and then it isn't listed twice
_v9 = {"basics": {"name": "T"}, "experience": [{"id": "bb", "org": "Best Buy", "title": "Tech", "dates": "2024", "bullets": ["Repaired 300 laptops."]}],
       "leadership": [{"id": "rj", "org": "RoboJackets", "title": "Electrical Lead", "dates": "Aug 2025 – Present",
                       "bullets": ["Designed power-distribution boards in Altium for an autonomous race car.", "Cut board respins from 3 to 1."]}]}
_res9, _ = _tl.apply(_v9, {"experience": [{"id": "rj"}, {"id": "bb"}]})
res.append(ok([e['id'] for e in _res9['experience']] == ['rj', 'bb'] and not _res9.get('leadership'),
              'a design-team role can lead Experience without appearing twice'))
# a misspelled entry id from the model still finds the entry (it used to silently drop someone's best role)
_v10 = {"basics": {"name": "T"}, "experience": [{"org": "UT Austin Oden Institute", "title": "RA", "dates": "2025",
        "bullets": ["Scaled a C++/MPI solver to 2,048 cores at 83% efficiency.", "Ported kernels to CUDA, 9x faster."]}]}
_id10 = _tl.ensure_ids(json.loads(json.dumps(_v10)))['experience'][0]['id']
_typo = _id10[:-3] + ('x' if _id10[-3] != 'x' else 'y') + _id10[-2:]
_res10, _ = _tl.apply(_v10, {"experience": [{"id": _typo, "bullets": [f"{_typo}.0", f"{_typo}.1"]}]})
res.append(ok(len(_res10['experience']) == 1 and len(_res10['experience'][0]['bullets']) == 2, f'misspelled plan ids still match ({_typo} -> {_id10})'))
# publications always appear, whatever the plan picked
_v11 = {"basics": {"name": "T"}, "research": [{"id": "p1", "title": "Paper One", "venue": "ICRA"}, {"id": "p2", "title": "Paper Two", "venue": "T-RO"}],
        "experience": [{"id": "x", "org": "X", "title": "SWE", "dates": "2025", "bullets": ["Built a service handling 12M requests/day."]}]}
_res11, _ = _tl.apply(_v11, {"experience": [{"id": "x"}], "order": ["education", "experience"]})
_res12, _ = _tl.apply(_v11, {"experience": [{"id": "x"}], "research": ["p2"]})
res.append(ok(len(_res11['research']) == 2 and 'research' in _res11['order'] and [p['id'] for p in _res12['research']] == ['p2', 'p1'],
              'publications always appear on the page (the plan only orders them)'))
# live build progress: the real step, time left that only counts steps still to run, and learned step lengths
_tk = _tl._Track('progress-test', ai=True)
_v14a = _tl.progress('progress-test')
_tk.stage('audit')   # the fact-check fix step didn't run this time
_v14b = _tl.progress('progress-test')
_tk.done()
res.append(ok(_v14a['stage'] == 'plan' and _v14a['eta'] > _v14b['eta'] and [s['state'] for s in _v14b['steps']] == ['done', 'skipped', 'now', 'next']
              and _tl.progress('progress-test') is None and _tl._timings()['plan']['n'] >= 1,
              f"build progress: real step, honest time left, learned timings {_v14a['eta']} -> {_v14b['eta']}"))
# service jobs leave a page with real material; finance reads strictly newest first; an award named elsewhere isn't repeated
_v16 = {"basics": {"name": "T"}, "education": [{"school": "U", "honors": ["Kelley Investment Banking Workshop (selective, ~20% admit)"]}],
        "experience": [{"id": "lg", "org": "City Pool", "title": "Lifeguard", "dates": "Jun 2026 – Aug 2026", "bullets": ["Guarded 300 swimmers a day."]},
                       {"id": "hw", "org": "Harris Williams", "title": "IB Intern", "dates": "Jun 2025 – Aug 2025", "bullets": ["Built a 3-statement model for a $400M deal."]},
                       {"id": "ta", "org": "Kelley", "title": "Teaching Assistant", "dates": "Jan 2026 – May 2026", "bullets": ["Taught Excel labs to 40 students."]}],
        "projects": [{"id": "p1", "name": "LBO", "bullets": ["Built a 5-year LBO model."]}, {"id": "p2", "name": "DCF", "bullets": ["Valued YETI at $48/share."]}],
        "awards": ["Kelley Investment Banking Workshop, admitted 2026", "Case Competition 2025, 1st place"]}
_res16, _ = _tl.apply(_v16, {"experience": [{"id": "hw"}, {"id": "ta"}, {"id": "lg"}], "projects": [{"id": "p1"}, {"id": "p2"}], "awards": [0, 1]}, 'Investment banking analyst intern')
_tl._house_rules(_res16, {"field": "finance"})
res.append(ok([e['id'] for e in _res16['experience']] == ['ta', 'hw'] and _res16['awards'] == [] and
              _res16['education'][0]['honors'][-1] == "Case Competition 2025, 1st place",
              f"service jobs dropped when there's real material, finance strictly newest first, no award twice {[e['id'] for e in _res16['experience']]}"))
# the database is never left open: thousands of requests used to exhaust the open-file limit ("Too many open files")
import subprocess as _sp
for _ in range(300):
    store.rows('select 1')
_open = _sp.run(['lsof', '-p', str(os.getpid())], capture_output=True, text=True).stdout.count('applytwin.db') if sys.platform != 'win32' else 0
res.append(ok(_open <= 3, f'database connections close after each request ({_open} open files after 300 reads)'))
# a rescan never replaces a full posting with a feed's one-line summary
from applytwin import sources as _src
_full = 'Machine learning intern building recommendation and ranking systems in Python. ' * 12
store.execute("insert or replace into jobs(id,source,company,title,location,url,apply_url,ats,posted,description,found_at,fit,fit_why,status) values('desc-test','community','Pinterest','Machine Learning Intern','Remote','u','u','greenhouse','',?,0,90,'','new')", (_full,))
with store.db() as _con:
    _src._ingest(_con, [{"id": 'desc-test', "source": 'community', "company": 'Pinterest', "title": 'Machine Learning Intern', "location": 'Remote',
                         "url": 'u', "apply_url": 'u', "ats": 'greenhouse', "posted": '', "description": 'Summer 2027 Other'}],
                 store.profile(), set(), {'fetched': 0, 'new': 0, 'matched': 0}, 0)
res.append(ok(store.rows("select description from jobs where id='desc-test'")[0]['description'] == _full, 'a rescan keeps the full job description'))
# pressing Scan: the page's first "still running?" check must hear yes (it used to report 0 new jobs every time)
import applytwin.sources as _srcs
_orig_scan = _srcs.scan
_srcs.scan = lambda *a, **k: (__import__('time').sleep(0.5), {"new": 3, "matched": 2, "fetched": 10})[1]
api.scan(background=True)
_first = api.scan_status()
__import__('time').sleep(1.0)
_after = api.scan_status()
_srcs.scan = _orig_scan
res.append(ok(_first['running'] and not _after['running'] and _after['stats'].get('new') == 3, 'a scan reads as running from the moment it starts'))
# the app's background scan runs as its own process (so pages stay fast during it) and its results come back
os.environ.pop('APPLYTWIN_SCAN_INLINE', None)
api.scan(['none'], background=True)
for _ in range(100):
    if not api.scan_status()['running']:
        break
    __import__('time').sleep(0.1)
os.environ['APPLYTWIN_SCAN_INLINE'] = '1'
res.append(ok(not api.scan_status()['running'] and api.scan_status()['stats'].get('sources') == 0 and bool(store.load('last_scan.json', {}).get('at')),
              f"a background scan runs in its own process and reports back ({api.scan_status().get('stats')})"))
# a job page's styles and scripts never become its description
from applytwin.sources import strip_html as _sh
_t = _sh('<html><head><style>@font-face{font-family:Meta}</style></head><body><script>var x=1</script><h1>Robotics Intern</h1><p>Build robots in C++.</p><svg><text>icon</text></svg></body></html>')
res.append(ok('font-face' not in _t and 'var x' not in _t and 'icon' not in _t and 'Build robots' in _t, f'page code is never kept as a job description ({_t!r})'))
# someone with only Codex set up gets Codex, whatever the button asked for
import shutil as _sh
from applytwin import agents as _ag
_ow, _os = _sh.which, _ag.status
_sh.which = lambda n, *a, **k: '/usr/bin/codex' if n == 'codex' else None
_ag.status = lambda n, fresh=False: {"name": n, "signed_in": n == 'codex', "label": n}
_pick = api.pick_agent('claude')
_sh.which, _ag.status = _ow, _os
res.append(ok(_pick == 'codex', f'a run asked to use Claude uses Codex when only Codex is set up ({_pick})'))
# getting an agent ready from the app: signed in already, no Node to install with, and a real sign-in started
import shutil as _sh2, subprocess as _sp2
from applytwin import agents as _ag2
_ow2, _os2, _op2 = _sh2.which, _ag2.status, _sp2.Popen
_ag2.status = lambda n, fresh=False: {"name": n, "label": n, "installed": True, "signed_in": n == 'claude'}
_r1 = api.connect_agent('claude')
_sh2.which = lambda n, *a, **k: None   # neither codex nor npm on this machine
_ag2.status = lambda n, fresh=False: {"name": n, "label": n, "installed": False, "signed_in": False}
api.connect_agent('codex')
for _ in range(50):
    if (api._connecting.get('codex') or {}).get('step') == 'failed':
        break
    time.sleep(0.05)
_r2 = api._connecting.get('codex') or {}
api._connecting.pop('codex', None)
_started = []
_sh2.which = lambda n, *a, **k: '/usr/local/bin/' + n
_sp2.Popen = lambda cmd, **k: _started.append(cmd) or type('P', (), {'poll': lambda self: None, 'pid': 0})()
api.connect_agent('codex')
for _ in range(50):
    if _started:
        break
    time.sleep(0.05)
_sh2.which, _ag2.status, _sp2.Popen = _ow2, _os2, _op2
api._connecting.pop('codex', None)
res.append(ok(_r1.get('signed_in') and _r2.get('step') == 'failed' and 'Node.js' in (_r2.get('error') or '')
              and _started and _started[0][-1] == 'login', f'agents install and sign in from the app ({_r2.get("error", "")[:40]}; {_started})'))
# a resume can never be wiped by an empty save, every save keeps a backup, and a backup can be restored
_full = api.get_vault()
_n = len(_full.get('experience', []))
try:
    api.save_vault({"basics": _full.get('basics', {}), "experience": [], "projects": []})
    _refused = False
except RuntimeError:
    _refused = True
api.save_vault({**_full, "experience": _full['experience'][:1]})   # a real edit: keeps a backup of the full version
_bk = store.vault_backups()
store.save('resume.json', {"basics": {"name": "x"}})                # simulate a wipe that got through some other way
_r = api.restore_vault()
res.append(ok(_refused and _bk and _bk[0]['experience'] >= 1 and len(api.get_vault().get('experience', [])) >= 1,
              f'an empty save is refused, saves keep backups, restore brings the resume back ({_n} roles, {len(_bk)} backups)'))
api.save_vault(_full)
# firms that take one application per candidate get one (the best-fitting role), not the user's cap of three
for _i, (_t, _f) in enumerate([('Quantitative Trader Intern', 90), ('Software Engineer Intern', 85), ('Quantitative Researcher Intern', 80)]):
    store.execute("insert or replace into jobs(id,source,company,title,location,url,apply_url,ats,posted,description,found_at,fit,fit_why,status) "
                  "values(?, 'greenhouse','Jane Street',?,'New York','u','u','greenhouse','','',?,?,'','new')", (f'js-{_i}', _t, time.time(), _f))
_q = [j for j in api.queue(500)['jobs'] if j['company'] == 'Jane Street']
for _i in range(3):
    store.execute("delete from jobs where id=?", (f'js-{_i}',))
res.append(ok(len(_q) == 1 and _q[0]['title'] == 'Quantitative Trader Intern', f"one-application firms get one, the best fit ({[j['title'] for j in _q]})"))
# a name on the same header line as the city never becomes part of the location
from applytwin.importer import clean_location as _cl
res.append(ok(_cl('JANE DOE West Lafayette, IN', 'Jane Doe') == 'West Lafayette, IN' and _cl('JOHN SMITH West Lafayette, IN') == 'West Lafayette, IN'
              and _cl('San Francisco, CA') == 'San Francisco, CA', 'the name in a resume header is never read as part of the location'))
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
# job finding: US vs abroad, roles that are the same vs different, internships the default excludes used to kill
from applytwin import match as _m
_places = {'Bengaluru, IN': 'foreign', 'Indianapolis, IN': 'us', 'Tel Aviv, IL': 'foreign', 'Berlin, DE': 'foreign',
           'Cambridge, United Kingdom': 'foreign', 'Cambridge, MA': 'us', 'New York, NY or Toronto, ON': 'us', '2 Locations': 'unknown',
           'Vancouver, WA': 'us', 'Toronto, ON': 'foreign', 'Amsterdam, NH, NL': 'foreign', 'Toronto, ON, CA': 'foreign', 'San Jose, CA': 'us'}
_pl = {k: _m.place(k) for k, want in _places.items() if _m.place(k) != want}
_same = api.role_key('Acme', 'Software Engineer Intern - New York') == api.role_key('Acme', 'Software Engineering Internship - Seattle')
_diff = api.role_key('Acme', 'Intern - Software Engineering') != api.role_key('Acme', 'Intern - Investment Banking')
_P = {'search': {'kind': 'internship', 'exclude': ['master', 'manager', 'senior'], 'roles': []}}
_kept = all(_m.fit({'title': t, 'company': 'X'}, _P)[0] > 0 for t in ('Product Manager Intern', 'Software Engineer Intern, Mastercard Send',
                                                                     'Software Engineer Intern - Undergraduate Students Only'))
_roles = _m.role_hit('software engineering', 'software developer intern') and not _m.role_hit('machine learning', 'aircraft maintenance intern')
res.append(ok(not _pl and _same and _diff and _kept and _roles, f'job matching: places, same/different roles, excludes, role words {_pl or ""}'))
# a posting that disappeared from its company's board leaves the queue; one bad posting never stops a scan
from applytwin import sources as _src
for _i in ('g1', 'g2'):
    store.execute("insert or replace into jobs(id,source,company,title,url,apply_url,ats,found_at,fit,status) values(?,?,?,?,?,?,?,?,?,'new')",
                  (_i, 'greenhouse', 'Gco', 'Intern ' + _i, f'https://boards.greenhouse.io/gco/jobs/{_i}', '', 'greenhouse', 0, 90))
with store.db() as _con:
    _src._retire(_con, 'greenhouse:gco', [{'id': 'g1'}])
    _st = {'fetched': 0, 'new': 0, 'matched': 0}
    _src._ingest(_con, [{'id': 'bad'}], store.profile(), set(), _st, 0)   # missing fields: skipped, not fatal
_closed = {r['id']: r['status'] for r in store.rows("select id, status from jobs where id in ('g1','g2')")}
res.append(ok(_closed == {'g1': 'new', 'g2': 'closed'}, f'closed postings leave the queue {_closed}'))
# regressions found in review: board-name collisions, rescans, BOM files, share-your-link questions, co-op seasons, imports
store.execute("insert or replace into jobs(id,source,company,title,url,apply_url,ats,found_at,fit,status) values('e1','greenhouse','Epic','Intern','https://boards.greenhouse.io/epicgames/jobs/1','','greenhouse',0,90,'new')")
with store.db() as _con:
    _src._retire(_con, 'greenhouse:ame', [{'id': 'zz'}])
    _st = {'fetched': 0, 'new': 0, 'matched': 0, 'errors': 0}
    _src._ingest(_con, [{'id': 'e1', 'source': 'greenhouse', 'company': 'Epic', 'title': 'Software Engineer Intern', 'location': 'Cary, NC',
                         'url': 'https://boards.greenhouse.io/epicgames/jobs/1', 'apply_url': '', 'ats': 'greenhouse', 'posted': '', 'description': 'x'}],
                 store.profile(), set(), _st, 0)
_epic = store.rows("select status from jobs where id='e1'")[0]['status']
open(store.path('bom.json'), 'w', encoding='utf-8-sig').write('{"a": 1}')
_bom = store.load('bom.json', {}).get('a') == 1
_share = _an.match('Please share your LinkedIn profile URL', _an.default_bank({'linkedin': 'linkedin.com/in/x'})).get('answer') == 'linkedin.com/in/x'
_coop = _m.fit({'title': 'Software Engineer Co-op - Fall 2026', 'company': 'X'}, {'search': {'kind': 'co-op', 'season': '', 'roles': []}})[0] > 0
_imp2 = _imp.parse('''Sam Park
sam@x.edu
Experience
Stripe, San Francisco, CA
Backend Engineering Intern, Jun 2025 – Aug 2025
• Shipped a dashboard for 12 teams
Acme, Austin, TX
Data Intern, Jan 2025 – May 2025
• Cleaned 3 years of sales data
''')
_orgs = [e.get('org') for e in _imp2['experience']]
res.append(ok(_epic == 'new' and _st['errors'] == 0 and _bom and _share and _coop and _orgs[:2] == ['Stripe', 'Acme'],
              f'review regressions stay fixed (board {_epic}, rescan errors {_st["errors"]}, bom {_bom}, share {_share}, co-op {_coop}, import {_orgs})'))
# graduation windows in postings, compared with the user's grad date (a window phrased any way students see it)
_gw = [('Candidates graduating Dec 2027 - Aug 2028.', '2028', 'May', True), ('Candidates graduating Dec 2027 - Aug 2028.', '2029', 'May', False),
       ('Candidates graduating Dec 2027-Aug 2028', '2027', 'May', False),
       ('Expected graduation between December 2027 and June 2028', '2027', 'December', True),
       ('Must have an expected graduation date of Fall 2027 or Spring 2028', '2028', 'Dec', False),
       ('graduation date between 12/2027 and 08/2028', '2028', '5', True), ('graduation date between 12/2027 and 08/2028', '2028', '09', False),
       ('You must graduate by May 2028', '2028', 'Aug', True), ('You must graduate by May 2028', '2029', 'May', False),
       ('Students graduating in 2028 or later', '2027', 'May', False), ('Students graduating in 2028 or later', '2030', 'May', True),
       ('Open to the Class of 2028', '2029', 'May', False), ('Open to the Class of 2028', '2027', 'Dec', True),
       ('Enrolled in a degree program during the 2027-2028 academic year', '2030', 'May', None),
       ('Python, SQL and a love of data.', '2028', 'May', None), ('Candidates graduating Dec 2027 - Aug 2028.', '', '', None)]
_gbad = [(t, y, mo, _m._grad_ok(t, y, mo)) for t, y, mo, want in _gw if _m._grad_ok(t, y, mo)[0] is not want]
_P2 = {'grad_year': '2029', 'grad_month': 'May', 'search': {'kind': 'internship', 'roles': [], 'exclude': []}}
_gj = {'title': 'Software Engineer Intern', 'company': 'X', 'description': 'Open to students graduating Dec 2027 - Aug 2028.'}
_ko = _m.knockouts(_gj, _P2)
_gf = _m.fit(_gj, _P2)
res.append(ok(not _gbad and _ko == ['Graduation window Dec 2027 - Aug 2028; you graduate May 2029'] and _gf[0] == 5 and 'May 2029' in _gf[1]
              and _m.knockouts({**_gj, 'description': 'Python.'}, _P2) == [],
              f'graduation windows are read and give an exact Skipped reason {_gbad or ""}'))
# statuses agents write every which way all land on the canonical ones, and a reason in the status moves to the notes
_ns = {('needs-user', ''): ('Needs User', ''), ('Skipped - grad window', ''): ('Skipped', 'grad window'),
       ('Ready to submit', ''): ('Needs User', 'ready to submit'), ('submitted', 'ok'): ('Applied', 'ok'),
       ('Not eligible (grad window)', ''): ('Skipped', 'Not eligible (grad window)'), ('Failed to submit', ''): ('Failed', 'Failed to submit'),
       ('Duplicate - already applied', ''): ('Skipped', 'Duplicate - already applied'), ('Online Assessment', ''): ('OA', 'Online Assessment'),
       ('Needs User', 'hCaptcha'): ('Needs User', 'hCaptcha'), ('Interview', ''): ('Interview', ''), ('Withdrawn', ''): ('Withdrawn', '')}
_nbad = {k: store.normalize_status(*k) for k, want in _ns.items() if store.normalize_status(*k) != want}
res.append(ok(not _nbad, f'log_application statuses are normalized {_nbad or ""}'))
# claims: parallel agents can't overrun the daily limit or a company cap, a run can re-claim its own job, a dead
# session's claim stops hiding its job, unknown ids are refused, and two sessions never finish one application at once
p0 = store.profile()
store.execute("delete from applications"); store.execute("delete from claims")
api.update_profile({**p0, 'apply': {**p0['apply'], 'daily_limit': 2, 'per_company_cap': 1}})
for _jid, _co, _t in (('c1', 'Alpha', 'Software Intern'), ('c2', 'Beta', 'Data Intern'), ('c3', 'Gamma', 'ML Intern'), ('c4', 'Alpha', 'Platform Intern')):
    store.execute("insert or replace into jobs(id,source,company,title,url,apply_url,ats,found_at,fit,status) values(?,?,?,?,?,?,?,?,?,'new')",
                  (_jid, 't', _co, _t, 'https://x/' + _jid, 'https://x/' + _jid, 'lever', 0, 95))
_c1 = api.claim('c1', who='run-a')['claimed']
_cap = api.claim('c4', who='run-b')['claimed'] is False          # Alpha's one slot is held by an unlogged claim
_c2 = api.claim('c2', who='run-b')['claimed']
_lim = api.claim('c3', who='run-c')['claimed'] is False          # 2 in progress = today's limit of 2
_again = api.claim('c1', who='run-a')['claimed'] and api.claim('c1', who='agent')['claimed'] is False
_unknown = api.claim('nope')['claimed'] is False
store.execute("update claims set at=? where job_id='c2'", (time.time() - store.CLAIM_TTL - 60,))   # run-b died hours ago
_nj = api.next_jobs(5)
_stale = store.latest_status('c2')['status'] == 'Needs User' and _nj['remaining_today'] == 1
_fin1 = api.claim('c2', who='run-d')['claimed']
_fin2 = api.claim('c2', who='run-e')['claimed'] is False          # run-d is finishing it
res.append(ok(_c1 and _cap and _c2 and _lim and _again and _unknown and _stale and _fin1 and _fin2,
              f'claims hold under parallel agents ({_c1}, {_cap}, {_c2}, {_lim}, {_again}, {_unknown}, {_stale}, {_fin1}, {_fin2})'))
# duplicates: a submitted application is never turned back into "not applied" by an agent, get_job warns about the same
# role at the same company, the same posting id under another listing is already done, and filled-then-skipped stops counting
api.log_application('c1', 'Applied', 'submitted', agent=True)
_down = api.log_application('c1', 'Skipped', 'duplicate', agent=True)
_kept = _down.get('ok') is False and store.latest_status('c1')['status'] == 'Applied'
store.execute("insert or replace into jobs(id,source,company,title,url,apply_url,ats,found_at,fit,status) values(?,?,?,?,?,?,?,?,?,'new')",
              ('c5', 'simplify', 'Alpha Inc.', 'Software Intern - Summer 2027', 'https://x/c5', 'https://x/c5', 'lever', 0, 95))
_orig = api.get_job
api.get_job = lambda jid, with_description=True: store.rows('select * from jobs where id=?', (jid,))[0]   # no network
try:
    _dup = api.job_for_agent('c5')['already_applied']
    _self = api.job_for_agent('c1')['already_applied']
finally:
    api.get_job = _orig
store.execute("insert or replace into jobs(id,source,company,title,url,apply_url,ats,found_at,fit,status) values(?,?,?,?,?,?,?,?,?,'new')",
              ('g7', 'greenhouse', 'Delta', 'Backend Intern', 'https://boards.greenhouse.io/delta/jobs/7001234', '', 'greenhouse', 0, 95))
api.log_application('g7', 'Applied')
_xl = api.already_done({'company': 'Delta', 'title': 'Software Engineering Intern (Backend)', 'url': 'https://simplify.jobs/x',
                        'apply_url': 'https://job-boards.greenhouse.io/embed/job_app?for=delta&token=7001234'})
_other = api.already_done({'company': 'Omega', 'title': 'Analyst', 'url': '', 'apply_url': 'https://job-boards.greenhouse.io/embed/job_app?for=omega&token=7001234'})
store.execute("delete from applications")
api.log_application('c3', 'Needs User', 'Filled; ready to submit')
_n1 = store.applied_count_today()
api.log_application('c3', 'Skipped', 'user decided not to')
_n0 = store.applied_count_today()
api.log_application('c4', 'Needs User', 'sign-in needed'); api.log_application('c4', 'Rejected')
_pend = not any(r['job_id'] == 'c4' for r in api.pending_jobs())
api.update_profile(p0)
res.append(ok(_kept and len(_dup) == 1 and _dup[0]['job_id'] == 'c1' and _self and _self[0]['status'] == 'Applied' and _xl and not _other
              and (_n1, _n0) == (1, 0) and _pend,
              f'no duplicate applications, honest counts ({_kept}, {_dup}, {bool(_self)}, {_xl}, {_other}, {_n1}/{_n0}, {_pend})'))
# answers: "How did you hear" picks the closest truthful option, AI interview consent is Yes, facts only the user knows
# (birth date, a recommender's name) are never filled from a near match
_hb = _an.default_bank({'name': 'Maya Chen', 'ai_review_ok': None})
_h1 = _an.match('How did you hear about us?', _hb, ['Select', 'LinkedIn', 'Indeed', 'Company Website', 'Employee Referral', 'Other'])['answer']
_h2 = _an.match('How did you hear about this position?', _hb, ['Career Fair', 'Employee Referral', 'Job Board', 'Other'])['answer']
_h3 = _an.match('How did you hear about this position?', _hb, ['Career Fair', 'Employee Referral'])
_ai = _an.match('Do you consent to participate in an AI-powered video interview?', _hb, ['Yes', 'No'])['answer']
_never = [_an.match(q, _hb)['answer'] for q in ('Date of Birth', 'Name of Recommender', 'Recommender email', 'Full name of your reference')]
_ref = _an.match('Were you referred by an employee?', _hb, ['Yes', 'No'])['answer']
res.append(ok(_h1 == 'Company Website' and _h2 == 'Job Board' and _h3['answer'] is None and not _h3['action'].startswith('ask') and _ai == 'Yes'
              and _never == [None] * 4 and _ref == 'No' and _an.match('Full name', _hb)['answer'] == 'Maya Chen',
              f'how-did-you-hear, AI interview consent and never-guess facts ({_h1}, {_h2}, {_ai}, {_never}, {_ref})'))
# every ATS playbook carries today's lessons, and the name can't be used to read other files
_pw, _pi, _po = api.playbook('workday'), api.playbook('icims'), api.playbook('oracle')
res.append(ok('click' in _pw and 'read the button' in _pw.lower() and 'DataTransfer' in _pi and 'contentDocument' in _pi
              and 'real key' in _po.lower() and all('already applied' in x and 'CAPTCHA' in x for x in (_pw, _pi, _po, api.playbook('lever')))
              and api.playbook('../../README') == api.playbook('general'), 'ATS playbooks carry the dropdown, iframe, Oracle and duplicate rules'))

# first-run and error-handling regressions (2026-10-31)
from applytwin import update as _up, server as _sv, cloud as _cl2, importer as _imp3
import base64 as _b64, sqlite3 as _sq, zipfile as _zf, io as _io
_wt = tempfile.mkdtemp()
open(os.path.join(_wt, '.git'), 'w').write('gitdir: /elsewhere/.git/worktrees/x\n')   # a git worktree: .git is a file
_app0 = _up.APP
_up.APP = _wt
_wt_ok = _up.is_checkout() and _up.check()['managed'] is False
_up.APP = _app0
_errs = [_sv.human_error(KeyError('url')), _sv.human_error(RuntimeError('')), _sv.human_error(AttributeError("'NoneType' object has no attribute 'get'")),
         _sv.human_error(_sq.OperationalError('database is locked')), _sv.human_error(ValueError("invalid literal for int() with base 10: 'abc'"))]
_err_ok = all(e and "'" not in e[:20] and 'NoneType' not in e for e in _errs) and 'url' in _errs[0] and 'busy' in _errs[3]
_bank0 = len(store.answers())
_refused = 0
for _bad in ({}, [], None, [{'answer': 'x'}]):
    try:
        api.save_answers(_bad)
    except RuntimeError:
        _refused += 1
_ans_ok = _refused == 4 and len(store.answers()) == _bank0 and api.save_answers(store.answers())['count'] == _bank0
_vault0 = json.dumps(store.resume(), sort_keys=True)
_buf = _io.BytesIO()
with _zf.ZipFile(_buf, 'w') as _z:
    _z.writestr('ppt/slides/slide1.xml', '<p/>')   # a .pptx dropped as a resume
_imp_msgs = []
for _nm, _data, _txt in (('scan.pdf', None, '   \n  '), ('deck.docx', _b64.b64encode(_buf.getvalue()).decode(), None),
                         ('photo.png', _b64.b64encode(b'\x89PNG\r\n\x1a\n' + bytes(range(256)) * 20).decode(), None),
                         ('broken.pdf', _b64.b64encode(b'%PDF-1.4 garbage').decode(), None)):
    try:
        _imp3.import_resume(_nm, _data, _txt)
        _imp_msgs.append(None)
    except RuntimeError as e:
        _imp_msgs.append(str(e))
_imp_ok = all(m and 'paste the text' in m for m in _imp_msgs) and json.dumps(store.resume(), sort_keys=True) == _vault0
_gone = []
for _f in (lambda: api.render_resume(job_id='no-such-job'), lambda: api.preview_html('classic', 'no-such-job')):
    try:
        _f()
    except RuntimeError as e:
        _gone.append('no longer in your list' in str(e))
os.environ['APPLYTWIN_SKIP_SIGNIN'] = '1'
_gate_ok = _cl2.status()['required'] is False
res.append(ok(_wt_ok and _err_ok and _ans_ok and _imp_ok and _gone == [True, True] and _gate_ok,
              f'worktrees never self-update ({_wt_ok}), errors read as sentences ({_err_ok}), answers never wiped ({_ans_ok}), '
              f'unreadable resumes say so ({_imp_ok}), gone jobs ({_gone}), dev runs skip sign-in ({_gate_ok})'))
# a setting changed while a scan runs (picking a term during setup) applies to the jobs that scan stores after the change
_prof0 = store.profile()['search'].get('season') or ''
api.update_profile({'search': {'season': 'Summer 2030'}})
_orig_scan2 = _srcs.scan


def _midscan(*a, **k):
    os.environ['APPLYTWIN_NO_RESCORE'] = '1'   # as if the settings rescore already ran before this job was stored
    api.update_profile({'search': {'season': 'Summer 2031'}})
    os.environ.pop('APPLYTWIN_NO_RESCORE')
    store.execute("insert or replace into jobs(id,source,company,title,url,apply_url,ats,found_at,fit,status) values('cyc1','greenhouse','CycCo',"
                  "'Software Engineer Intern - Summer 2030','https://x.com/1','','greenhouse',0,90,'new')")   # scored with the old term
    return {"new": 1, "matched": 1, "fetched": 1}


_srcs.scan = _midscan
api.scan()
_srcs.scan = _orig_scan2
_cyc = store.rows("select fit, fit_why from jobs where id='cyc1'")[0]
api.update_profile({'search': {'season': _prof0}})
res.append(ok(_cyc['fit'] == 0, f'settings changed mid-scan apply to what that scan found ({_cyc})'))
from applytwin import telemetry as _tm
res.append(ok(not _tm.enabled() and _tm.ping() is False and len(_tm.install_id()) == 36, 'install count is off in tests and uses only a random ID'))

# the local web server: other websites (cross-site requests), DNS rebinding and path tricks get nothing
import http.client, threading  # noqa: E401,E402
from http.server import ThreadingHTTPServer  # noqa: E402
from applytwin import server  # noqa: E402
_srv = ThreadingHTTPServer(('127.0.0.1', 0), server.H)
threading.Thread(target=_srv.serve_forever, daemon=True).start()
PORT = _srv.server_address[1]


def req(method, path, body=None, **headers):
    c = http.client.HTTPConnection('127.0.0.1', PORT, timeout=60)
    c.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
    headers.setdefault('Host', f'localhost:{PORT}')
    for k, v in headers.items():
        c.putheader(k.replace('_', '-'), v)
    data = (body or '').encode()
    c.putheader('Content-Length', str(len(data)))
    c.endheaders(data or None)
    r = c.getresponse()
    return r.status, r.read()


JSON, dump, me = 'application/json', '{"text": "pwned by another site"}', f'http://localhost:{PORT}'
before = api.get_dump()
res.append(ok(req('POST', '/api/dump', dump, Content_Type='text/plain')[0] == 403, 'POST with a text/plain body (no-cors fetch) refused'))
res.append(ok(req('POST', '/api/dump', 'text=x', Content_Type='application/x-www-form-urlencoded')[0] == 403, 'HTML form POST refused'))
res.append(ok(req('POST', '/api/dump', dump, Content_Type=JSON, Origin='https://evil.example')[0] == 403, 'POST from another website refused'))
res.append(ok(req('POST', '/api/dump', dump, Content_Type=JSON, Origin='null')[0] == 403, 'POST from a sandboxed (null) origin refused'))
res.append(ok(req('POST', '/api/dump', dump, Content_Type=JSON, Origin='http://localhost:3000')[0] == 403, 'POST from another local server refused'))
res.append(ok(req('POST', '/api/dump', dump, Content_Type=JSON, Referer='https://evil.example/x')[0] == 403, 'POST with a foreign Referer refused'))
res.append(ok(req('POST', '/api/dump', dump, Content_Type=JSON, Origin=me, Sec_Fetch_Site='cross-site')[0] == 403, 'POST marked cross-site refused'))
res.append(ok(api.get_dump() == before, 'refused requests changed nothing'))
res.append(ok(req('GET', '/api/state', Host='evil.example')[0] == 403, 'GET with a DNS-rebinding Host header refused'))
res.append(ok(req('GET', '/', Host=f'attacker.test:{PORT}')[0] == 403, 'page with a DNS-rebinding Host refused'))
res.append(ok(req('POST', '/api/dump', dump, Content_Type=JSON, Host=f'attacker.test:{PORT}', Origin=f'http://attacker.test:{PORT}')[0] == 403,
              'POST through DNS rebinding (Host and Origin both the attacker) refused'))
res.append(ok(req('GET', '/api/state', Origin='https://evil.example')[0] == 403, 'API GET from another website refused'))
res.append(ok(req('POST', '/api/inbox/1/resolve', '{}', Content_Type=JSON, Origin=me)[0] == 200, "the app's own JSON POST works"))
res.append(ok(req('POST', '/api/inbox/1/resolve', '{}', Content_Type=JSON, Host=f'127.0.0.1:{PORT}')[0] == 200,
              'a local JSON POST without Origin (CLI, scripts) works'))
res.append(ok(req('GET', '/', Sec_Fetch_Site='cross-site')[0] == 200, 'coming back from Google sign-in still opens the app'))
res.append(ok(req('GET', '/file?path=' + store.path('profile.json'))[0] == 403, '/file refuses data files outside resumes/'))
res.append(ok(req('GET', '/file?path=' + store.path('resumes', '..', 'auth.json'))[0] == 403, '/file refuses ../ out of resumes/'))
res.append(ok(req('GET', '/preview?job=../../x')[0] in (400, 500) and b'Traceback' not in req('GET', '/preview?job=../../x')[1],
              '/preview refuses a traversal job id'))
st, body = req('GET', '/api/auth/login?redirect=https://evil.example/')
res.append(ok(st == 500 and b'authorize' not in body, 'Google sign-in refuses to return to another site'))
res.append(ok(b'authorize' in req('GET', '/api/auth/login?redirect=' + me + '/')[1], 'Google sign-in back to this app works'))
st, body = req('POST', '/api/run', '{"agent": "bash", "n": 1}', Content_Type=JSON, Origin=me)
res.append(ok(st == 500 and b'unknown agent' in body, 'Autopilot runs only Claude Code or Codex'))
_xr = req('GET', '/export')
res.append(ok(_xr[0] == 200 and b'Company,Role' in _xr[1], f'/export downloads the CSV ({str(_xr)[:120]})'))
_srv.shutdown()

# open-issue fixes (2026-10-31, second pass)
import re as _re, threading as _th, logging as _lg
from applytwin import importer as _imp4, tailor as _tl4, agents as _ag4
_files = {n: store.load(n, None) for n in ('profile.json', 'answers.json', 'resume.json', 'learnings.json')}
# 1. signing in never overwrites setup done here: the cloud copy only fills blanks, and each changed file is backed up first
store.save('resume.json', store.DEFAULT_RESUME)
store.save('profile.json', {'phone': '555', 'search': {'season': 'Summer 2027', 'roles': []}, 'apply': {'daily_limit': 10}})
store.save('answers.json', [{'key': 'why_us', 'question': 'Why us?', 'answer': 'mine', 'source': 'user'}])
_row = {'vault': {'basics': {'name': 'Cloud Name'}, 'experience': [{'title': 'Intern', 'company': 'CloudCo', 'bullets': ['Did it']}]},
        'profile': {'phone': '111', 'name': 'Cloud Name', 'search': {'season': 'Fall 2026', 'roles': ['SWE']}, 'apply': {'daily_limit': 40}},
        'answers': [{'key': 'why_us', 'question': 'Why us?', 'answer': 'old', 'source': 'user'},
                    {'key': 'pets', 'question': 'Pets?', 'answer': 'cat', 'source': 'user'}], 'learnings': {'notes': ['short bullets']}}
_cl_orig = (_cl2.token, _cl2._session, _cl2._req)
_cl2.token, _cl2._session, _cl2._req = (lambda: 't'), (lambda: {'user': {'id': 'u'}}), (lambda *a, **k: [_row])
try:
    _restored = _cl2.pull()
finally:
    _cl2.token, _cl2._session, _cl2._req = _cl_orig
_pf, _an4 = store.load('profile.json', None), {r['key']: r['answer'] for r in store.load('answers.json', None)}
_bk = os.listdir(store.path('backups'))
_merge_ok = (_restored and _pf['phone'] == '555' and _pf['name'] == 'Cloud Name' and _pf['search'] == {'season': 'Summer 2027', 'roles': ['SWE']}
             and _pf['apply']['daily_limit'] == 10 and _an4 == {'why_us': 'mine', 'pets': 'cat'} and store.resume()['experience'][0]['company'] == 'CloudCo'
             and any(f.startswith('profile-') for f in _bk) and any(f.startswith('answers-') for f in _bk))
res.append(ok(_merge_ok, f'sign-in merges the cloud copy into local setup, never over it ({_pf.get("phone")}, {_an4}, backups {len(_bk)})'))
# 2. resume import: honest time left, Cancel stops the agent, and the built-in reader takes over with a clear message
_t0 = time.time()
_tl4._SINK.tag = 'kill-test'
_th.Timer(0.5, lambda: _tl4.cancel('kill-test')).start()
_r = _tl4._run([sys.executable, '-c', 'import time; time.sleep(30)'], '', 30)
_tl4._SINK.tag = None
_tl4.CANCELLED.discard('kill-test')
_killed = time.time() - _t0 < 10 and _r.returncode != 0
_seen = {}


def _slow_llm(text, timeout=600, fast=False, think=True):
    while 'import' not in _tl4.CANCELLED and time.time() - _t0 < 20:
        _seen.setdefault('progress', api.import_progress())
        if time.time() - _t0 > 0.4:   # the user presses Cancel (from another request, as the page does)
            _th.Thread(target=api.cancel_import).start()
        time.sleep(0.05)
    return None


_llm_orig, _ready_orig = _tl4.call_llm, _ag4.any_ready
_tl4.call_llm, _ag4.any_ready = _slow_llm, (lambda: True)
_t0 = time.time()
try:
    _ir = api.import_resume(text='Maya Chen\nmaya@example.com\nEXPERIENCE\nSoftware Intern, Acme  May 2025 - Aug 2025\n- Built a Python service used by 40 teams\n')
    _tl4.call_llm = lambda *a, **k: None   # an agent that fails outright
    _ir2 = api.import_resume(text='Maya Chen\nmaya@example.com\nPROJECTS\nTracker  2025\n- Built a React dashboard for 300 students\n')
finally:
    _tl4.call_llm, _ag4.any_ready = _llm_orig, _ready_orig
_pg = _seen.get('progress') or {}
_imp_ok = (_killed and _pg.get('running') and _pg.get('eta', 0) > 0 and _pg.get('limit', 0) >= 90 and time.time() - _t0 < 15
           and 'stopped your agent' in _ir['message'] and not _ir['ai'] and "couldn't read it" in _ir2['fallback']
           and api.import_progress() == {'running': False} and not _tl4.RUNNING)
res.append(ok(_imp_ok, f'resume import shows time left, Cancel kills the agent, built-in reader takes over ({_killed}, {_pg}, {_ir["message"][-60:]})'))
for _n, _v in _files.items():   # put this test file's setup back for the checks below
    if _v is None:
        os.remove(store.path(_n)) if os.path.exists(store.path(_n)) else None
    else:
        store.save(_n, _v)
# 3, 4. "switching versions" only while one is under way; restarts run `-m applytwin` from the install folder
_nf = _sv.not_found()
_sv._RESTARTING.append(1)
_nf2 = _sv.not_found()
_sv._RESTARTING.clear()
_cwd, _argv = _sv._restart_cmd()
res.append(ok('switching' not in _nf and 'switching' in _nf2, f'unknown requests say not-found unless an update is under way ({_nf[:40]})'))
res.append(ok(_cwd == store.HOME and os.path.isabs(_argv[0]) and _argv[1] == os.path.join(store.APP, 'bin', 'applytwin'),
              f'restart runs the install folder\'s app from outside it (Windows can\'t swap a folder in use) ({_argv[:2]})'))
# 5. a limit written in any spelling's posting caps the company (cache and lookup both by normalized name)
store.execute("insert or replace into jobs(id,source,company,title,url,apply_url,ats,description,found_at,fit,status) values('capx','t','Capco Holdings, Inc.',"
              "'Intern','u','u','lever','Candidates may apply to only one role this cycle.',0,90,'new')")
api._posted[0] = 0
api._limits.clear()
_cap = api.company_cap('Capco Holdings', 3)
res.append(ok(_cap == 1, f'company cap reads every spelling\'s postings by normalized name ({_cap})'))
# 6. the per-company cap counts this recruiting cycle only; the daily limit stays a rolling day
store.execute("insert into applications(job_id,company,title,url,status,notes,at) values('old1','Cyclco','Intern','u','Applied','',?)", (time.time() - 300 * 86400,))
_c_old = store.company_count('Cyclco')
store.execute("insert into applications(job_id,company,title,url,status,notes,at) values('new1','Cyclco Inc','Intern','u','Applied','',?)", (time.time() - 20 * 86400,))
_c_new = store.company_count('Cyclco')
res.append(ok(_c_old == 0 and _c_new == 1, f'per-company cap counts this recruiting cycle only ({_c_old}, {_c_new})'))
# 7. logging a job ApplyTwin doesn't have: the body's company/title, or a clear refusal (never a blank row)
_pat = r'/api/jobs/([\w-]+)/log'
_sv.POST[_pat](_re.fullmatch(_pat, '/api/jobs/nojob1/log'), {}, {'status': 'Applied', 'company': 'Newco', 'title': 'Data Intern'})
try:
    _sv.POST[_pat](_re.fullmatch(_pat, '/api/jobs/nojob2/log'), {}, {'status': 'Applied'})
    _refused2 = False
except RuntimeError as e:
    _refused2 = 'company and title' in str(e)
_nr = store.rows("select company, title from applications where job_id in ('nojob1','nojob2')")
res.append(ok(_nr == [{'company': 'Newco', 'title': 'Data Intern'}] and _refused2, f'logging an unknown job uses the given names or refuses ({_nr}, {_refused2})'))
store.execute("delete from applications where job_id in ('nojob1','old1','new1')")
# 8. a broken PDF is reported in our words only, without pypdf's "EOF marker not found" log line
_recs = []
_h = _lg.Handler()
_h.emit = _recs.append
_lg.getLogger('pypdf').addHandler(_h)
try:
    _imp4.extract_text('broken.pdf', _b64.b64encode(b'%PDF-1.4 garbage').decode())
except RuntimeError:
    pass
from applytwin import render as _rn4
_bp = os.path.join(tempfile.mkdtemp(), 'b.pdf')
open(_bp, 'wb').write(b'%PDF-1.4 garbage /Type /Page')
_pc = _rn4.page_count(_bp)
_lg.getLogger('pypdf').removeHandler(_h)
res.append(ok(not _recs and _pc == 1, f'broken PDFs log nothing from pypdf ({len(_recs)} records)'))


# ---- Windows (simulated here: os.name and a stand-in winreg) ----
import types as _types
from applytwin import update as _up, cli as _cli, install
_fakereg = _types.ModuleType('winreg')
_fakereg.HKEY_LOCAL_MACHINE, _fakereg.HKEY_CURRENT_USER = 'HKLM', 'HKCU'
_REG = {('HKLM', r'SYSTEM\CurrentControlSet\Control\Session Manager\Environment', 'Path'): r'C:\Windows\;C:\Program Files\nodejs',
        ('HKCU', 'Environment', 'Path'): r'C:\Users\José Ruiz\AppData\Roaming\npm;C:\Windows',
        ('HKCU', r'SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe', None): r'"D:\Apps\Chrome\chrome.exe"'}


class _Key:
    def __init__(self, root, key):
        if not any(k[:2] == (root, key) for k in _REG):
            raise OSError('no key')
        self.k = (root, key)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


_fakereg.OpenKey = _Key
_fakereg.QueryValueEx = lambda k, n: (_REG[k.k + (n,)], 2)
_fakereg.QueryValue = lambda k, n: _REG[k.k + (n,)]
_saved = (os.name, sys.modules.get('winreg'), os.environ.get('PATH'), os.environ.get('ProgramFiles'))
_calls = []
_real_run = subprocess.run
try:
    os.name, sys.modules['winreg'] = 'nt', _fakereg
    os.environ['PATH'] = r'C:\Windows;C:\Python312'
    os.environ['ProgramFiles'] = r'E:\Program Files'
    store.refresh_path()
    _wpath = os.environ['PATH']
    store.refresh_path()   # nothing new the second time
    _wpath2 = os.environ['PATH']
    _wb = render._win_browsers()
    subprocess.run = lambda *a, **k: _calls.append((a, k))
    from applytwin import twin as _tw
    _tw._close_other_windows()
finally:
    os.name = _saved[0]
    subprocess.run = _real_run
    for _k, _v in (('PATH', _saved[2]), ('ProgramFiles', _saved[3])):
        if _v is None:
            os.environ.pop(_k, None)
        else:
            os.environ[_k] = _v
    if _saved[1] is None:
        sys.modules.pop('winreg', None)
    else:
        sys.modules['winreg'] = _saved[1]
res.append(ok(_wpath == r'C:\Windows;C:\Python312;C:\Program Files\nodejs;C:\Users\José Ruiz\AppData\Roaming\npm' and _wpath2 == _wpath,
              f'Windows: Node/Claude installed after the app started are found without a restart ({_wpath})'))
res.append(ok(r'D:\Apps\Chrome\chrome.exe' in _wb and os.path.join(r'E:\Program Files', 'Google', 'Chrome', 'Application', 'chrome.exe') in _wb,
              'Windows: Chrome / Edge found on another drive and through App Paths'))
_ps = _calls[0][0][0] if _calls else ['', '', '', '']
res.append(ok(_calls and install.BROWSER_PROFILE not in _ps[3] and _calls[0][1].get('env', {}).get('APPLYTWIN_PROF') == install.BROWSER_PROFILE,
              "Windows: the twin's browser folder goes to PowerShell as data (a username like O'Brien can't break it)"))
_envs = {k: os.environ.get(k) for k in ('LOCALAPPDATA', 'USERPROFILE')}
os.environ['LOCALAPPDATA'], os.environ['USERPROFILE'] = r'C:\Users\José Ruiz\AppData\Local', r'C:\Users\José Ruiz'
_cp = [_up.cmd_path(r'C:\Users\José Ruiz\AppData\Local\Programs\Python\Python312\python.exe'), _up.cmd_path(r'C:\Python312\python.exe')]
for _k, _v in _envs.items():
    os.environ.pop(_k, None) if _v is None else os.environ.__setitem__(_k, _v)
res.append(ok(_cp == [r'%LOCALAPPDATA%\Programs\Python\Python312\python.exe', r'C:\Python312\python.exe'],
              f'Windows: the applytwin command works for accented usernames without 8.3 names ({_cp[0]})'))
# an update steps out of the app folder before swapping it, and waits out an antivirus lock
_appd = os.path.realpath(tempfile.mkdtemp())
_here = os.getcwd()
os.makedirs(os.path.join(_appd, 'sub'))
os.chdir(os.path.join(_appd, 'sub'))
_up._leave(_appd)
_left_ok = os.path.realpath(os.getcwd()) == os.path.dirname(_appd)
os.chdir(_here)
_tries = []
_real_rename = os.rename


def _flaky(a, b):
    _tries.append(1)
    if len(_tries) < 3:
        raise PermissionError(32, 'being used by another process')
    return _real_rename(a, b)


os.rename = _flaky
try:
    _up._rename(_appd, _appd + '-moved')
finally:
    os.rename = _real_rename
res.append(ok(_left_ok and len(_tries) == 3 and os.path.isdir(_appd + '-moved'),
              'Windows: an update leaves the app folder first and retries a rename antivirus blocks'))
# pythonw has no console: output goes to server.log instead of nowhere; piped output has no color codes
_so, _se = sys.stdout, sys.stderr
try:
    sys.stdout = None
    _cli._no_console()
    print('hello from pythonw')
    _logname = getattr(sys.stdout, 'name', '')
    sys.stdout.flush()
finally:
    if sys.stdout not in (None, _so):
        sys.stdout.close()
    sys.stdout, sys.stderr = _so, _se
res.append(ok(_logname == store.path('server.log') and 'hello from pythonw' in open(store.path('server.log'), encoding='utf-8').read(),
              'Windows: pythonw output and crashes land in server.log'))
_pp = _cli._paint(32, 'x')
res.append(ok(_pp == ('\033[32mx\033[0m' if sys.stdout.isatty() else 'x'), 'doctor prints no escape codes when piped (Windows installer)'))
# the MCP server reads the agent's UTF-8 even where the default encoding is a Windows code page
_mp = subprocess.run([sys.executable, os.path.join(ROOT, 'bin', 'applytwin'), 'mcp'],
                     input=(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "José"}}, ensure_ascii=False) + '\n').encode('utf-8'),
                     capture_output=True, env={**os.environ, 'PYTHONIOENCODING': 'cp1252'}, timeout=60)
res.append(ok('Jos\\u00e9' in _mp.stdout.decode('utf-8', 'replace'), f'MCP reads UTF-8 input under a cp1252 default ({_mp.stdout[:120]!r})'))
# resume_patterns.json: aggregate norms only. It ships in a public repo, so it must never carry contact details or links.
import re as _re
_pt = open(os.path.join(ROOT, 'applytwin', 'resume_patterns.json'), encoding='utf-8').read()
_pj = json.loads(_pt)
_pii = _re.findall(r'[\w.+-]+@[\w-]+\.[\w.]+|https?://\S+|www\.\S+|\b(?:linkedin|github)\.com/\S+|\(?\b\d{3}\)?[-. ]\d{3}[-. ]\d{4}\b|\+\d{1,3}[ -]\d{3,}', _pt)
res.append(ok(not _pii and len(_pj.get('profiles', {})) >= 5, f'resume_patterns.json loads ({len(_pj.get("profiles", {}))} profiles) with no emails, phones or URLs {_pii[:3]}'))
from applytwin import tailor as _tp
_prof = [_tp.pattern_profile({'company': c, 'title': t}, '', f)[0] for c, t, f in [
    ('Wellington Management', 'Equity Research Summer Associate', 'finance'), ('Morgan Stanley', 'Technology Summer Analyst', 'finance'),
    ('Jane Street', 'Quantitative Trading Intern', 'quant'), ('Google', 'Software Engineering Intern', 'software'),
    ('Lattice Labs (YC W26)', 'Founding Engineering Intern', 'software'), ('Evercore', 'Investment Banking Summer Analyst', 'finance'),
    ('Anduril Industries', 'Electrical Engineering Intern, Embedded Systems', 'hardware'), ('Pinterest', 'Machine Learning Intern', 'ml'),
    ('Two Sigma', 'Quantitative Researcher Intern', 'quant')]]
# Pinterest's applied ML role is not a research posting; the defense profile has not won its blind review (only the
# citizenship line shipped), so Anduril keeps the plain prompt rather than borrowing a neighbor's
res.append(ok(_prof == ['asset_mgmt_markets', None, 'quant_trading', 'bigtech_swe', 'startup', 'investment_banking', None, None, 'quant_research_dev'],
              f'posting -> resume profile ({_prof})'))
_fl = _tp.pattern_flags({'experience': [{'bullets': ['Worked on the backend for the payments team.', 'Built a cache in Go, cutting p99 latency 30%.']}]})
res.append(ok(any('weak opener' in f for f in _fl) and not any('Built' in f for f in _fl) and 'ASSET MANAGEMENT' in _tp.prompt(api.get_vault(), {'title': 'Equity Research Summer Associate', 'company': 'Wellington Management'}, 'stocks', {}),
              'recruiter-norms check flags filler openers; the plan prompt carries the posting\'s profile'))
# profiles still being measured ("shipped": false) stay off unless an eval switches them on; variants follow the title
_unshipped = [k for k, p in _pj['profiles'].items() if not p.get('shipped', True)]
os.environ['APPLYTWIN_TRY_PROFILES'] = 'all'
_try = [(_tp.pattern_profile({'company': c, 'title': t}, j, f)[0], (_tp.pattern_profile({'company': c, 'title': t}, j, f)[1] or {}).get('label'))
        for c, t, j, f in [('Hudson River Trading', 'Software Engineering Intern (C++)', '', 'software'),
                           ('Citadel', 'Quantitative Research Intern', '', 'quant'),
                           ('Northrop Grumman', 'GN&C / Flight Software Engineering Intern', 'U.S. citizenship required', 'software'),
                           ('Google DeepMind', 'Student Researcher', 'machine learning research with large language models', 'general'),
                           ('Pinterest', 'Machine Learning Intern', 'machine learning recommendation systems', 'ml'),
                           ('Google', 'Machine Learning Engineer Intern', 'deep learning models', 'ml')]]
os.environ.pop('APPLYTWIN_TRY_PROFILES')
res.append(ok(_try == [('quant_research_dev', 'quant developer / trading-systems engineering'), ('quant_research_dev', 'quant research'),
                       ('defense', 'defense tech'), ('ml_research', 'ML / AI research'), (None, None), (None, None)]
              and all(not _tp._live(k, _pj['profiles']) for k in _unshipped), f'measured profiles: variants and research-only ML detection ({_try})'))
_rs = {'basics': {}, 'education': [{'school': 'X'}], 'order': ['education', 'experience', 'leadership', 'skills', 'awards'],
       'experience': [{'org': 'Old Co', 'end': 'Aug 2025', 'bullets': ['Teach Excel labs to 40 students.', 'Built a DCF model', 'Wrote a 60-question guide.']},
                      {'org': 'New Co', 'end': 'Aug 2026', 'bullets': ['Built an LBO for a $65M add-on.']}],
       'skills': [{'label': 'Technical', 'items': ['DCF']}, {'label': 'Interests', 'items': ['Golf']}],
       'awards': ["Dean's List"]}
_rs['experience'][1]['bullets'].append('Built an LBO for a $65M add-on')   # differs only by the final period: one line after
_tp._house_rules(_rs, {'field': 'general', 'pattern': _pj['profiles']['investment_banking']})
_tp._same_punctuation(_rs)
_fl2 = _tp._profile_flags(_rs, ['tense'])
res.append(ok([e['org'] for e in _rs['experience']] == ['New Co', 'Old Co'] and _rs['titles'].get('skills') == 'Skills & Interests'
              and _rs['titles'].get('leadership') == 'Leadership & Activities' and all(b.endswith('.') for e in _rs['experience'] for b in e['bullets'])
              and len(_rs['experience'][0]['bullets']) == 1 and len(_fl2) == 1 and 'Teach' in _fl2[0],
              f'profile house rules: newest first, finance headings, one punctuation style, tense slips ({_fl2})'))
store.save('profile.json', {**store.profile(), 'citizenship': 'U.S. citizen'})
_rc = {'basics': {}}
_tp._status_line(_rc, 'Must be a U.S. person; eligible for a security clearance.')
_rn = {'basics': {}}
_tp._status_line(_rn, 'Build great software.')
store.save('profile.json', {**store.profile(), 'citizenship': ''})
_rx = {'basics': {}}
_tp._status_line(_rx, 'Must be a U.S. person.')
res.append(ok(_rc['basics'].get('status') == 'U.S. Citizen' and 'status' not in _rn['basics'] and 'status' not in _rx['basics']
              and 'U.S. Citizen' in render.build_html({'basics': {'name': 'A', 'status': 'U.S. Citizen'}}),
              'citizenship line only when the posting screens on it and the profile states it'))
# hardware postings: chip-design/verification and embedded/firmware titles get the hardware profile (variant by title), even
# at Tesla/NVIDIA; test/validation and mechanical titles keep robotics/hardware; a software title at Apple stays big-tech SWE
from applytwin import learn
_hw = [(lambda r: (r[0], (r[1] or {}).get('label')))(_tp.pattern_profile({'company': c, 'title': t}, '', learn.field_for({'title': t})))
       for c, t in [('NVIDIA', 'ASIC Design Verification Intern'), ('AMD', 'Design Verification Engineering Intern/Co-op'),
                    ('Figure AI', 'Embedded / Electrical Engineering Intern, Humanoid Robotics'), ('Tesla', 'Internship, Firmware Engineer, Vehicle Firmware'),
                    ('Rivian', 'Electrical Test & Validation Engineering Intern'), ('Ford', 'Mechanical Engineering Intern'),
                    ('Apple', 'Software Engineering Intern')]]
res.append(ok(_hw == [('hardware_eng', 'chip design / verification'), ('hardware_eng', 'chip design / verification'),
                      ('hardware_eng', 'embedded / firmware'), ('hardware_eng', 'embedded / firmware'),
                      ('robotics_hardware', 'robotics / hardware'), ('robotics_hardware', 'robotics / hardware'),
                      ('bigtech_swe', 'big-tech software engineering')] and learn.field_for({'title': 'Design Verification Intern'}) == 'hardware',
              f'hardware postings -> hardware profile and variant ({_hw})'))
# board-level electrical and avionics titles get the electrical/board profile, ahead of the firm's big-tech or defense routing;
# embedded, chip, test/validation and mechanical titles keep theirs (the validation variant didn't win its blind review)
_hb = [_tp.pattern_profile({'company': c, 'title': t}, j, learn.field_for({'title': t}))[0] for c, t, j in [
    ('Apple', 'Hardware Engineering Intern, Electrical Engineering', ''), ('SpaceX', 'Avionics Hardware Engineering Intern', 'ITAR'),
    ('Anduril Industries', 'Electrical Engineering Intern', 'U.S. person, ITAR'), ('Lucid Motors', 'Power Electronics Hardware Engineering Intern', ''),
    ('Rivian', 'Electrical Test & Validation Engineering Intern', ''), ('Intel', 'Silicon Validation / Post-Silicon Engineering Intern', ''),
    ('Figure AI', 'Embedded / Electrical Engineering Intern', ''), ('Ford', 'Mechanical Engineering Intern', '')]]
res.append(ok(_hb[:4] == ['hardware_board'] * 4 and _hb[4] == 'robotics_hardware' and _hb[5] != 'hardware_board'
              and _hb[6] == 'hardware_eng' and _hb[7] == 'robotics_hardware' and 'variants' not in _pj['profiles']['hardware_board'],
              f'electrical / board postings -> electrical/board profile ({_hb})'))
# round 5 (elite corpus): every shipped profile states its elite n; a job in India or continental Europe adds that region's
# overlay to the prompt on top of its profile (UK and US get none); India's overlay shows the vault's awards as a section
_shipped = [k for k, p in _pj['profiles'].items() if p.get('shipped', True)]
_ov = {loc: (_tp.region_overlay({'location': loc}) or {}).get('id') for loc in
       ('Bengaluru, Karnataka, India', 'Zurich, Switzerland', 'Berlin, Germany', 'London, UK', 'New York, NY', '')}
_pin = _tp.prompt({'basics': {}, 'experience': []}, {'title': 'Software Engineering Intern', 'company': 'Google', 'location': 'Hyderabad, India'}, 'C++ data structures', {})
_pus = _tp.prompt({'basics': {}, 'experience': []}, {'title': 'Software Engineering Intern', 'company': 'Google', 'location': 'Mountain View, CA'}, 'C++ data structures', {})
_vaw = {'awards': ['ICPC Regional, Rank 18', 'JEE Advanced, AIR 412', 'KVPY Fellowship']}
_pl_in = _tp._awards_rule({'awards': [2], 'order': ['education', 'experience']}, _vaw, {'region': _tp.region_overlay({'location': 'Pune, India'})})
_pl_us = _tp._awards_rule({'awards': [2], 'order': ['education']}, _vaw, {'region': None, 'pattern': _pj['profiles']['ml_research']})
res.append(ok(all(isinstance(_pj['profiles'][k].get('n'), int) and 'elite' in _pj['profiles'][k].get('basis', '') for k in _shipped)
              and _ov == {'Bengaluru, Karnataka, India': 'india', 'Zurich, Switzerland': 'europe', 'Berlin, Germany': 'europe',
                          'London, UK': None, 'New York, NY': None, '': None}
              and 'JOBS IN INDIA ALSO DO' in _pin and 'BIG-TECH' in _pin and 'ALSO DO' not in _pus
              and _pl_in['awards'] == [2, 0, 1] and _pl_in['order'][-1] == 'awards' and _pl_us['awards'] == [2],
              f'elite basis on shipped profiles; regional overlays ({_ov}); India awards section ({_pl_in.get("awards")})'))
# a rewrite can't add a hardware tool its role never lists (an interviewer tests every one); spellings of one part family match
_o = 'Built a UVM environment for an AHB-to-APB bridge; closed coverage from 71% to 98%.'
_w1 = _tp.check_rewrite(_o, 'Built a UVM environment for an AXI bridge in Xcelium, closing coverage from 71% to 98%.', '', '', _o)
_w2 = _tp.check_rewrite('Closed a 10 kHz torque loop on an STM32G4 under FreeRTOS.', 'Closed a 10 kHz FOC torque loop on an STM32 MCU under FreeRTOS.', '', '')
_tf = _tp._profile_flags({'experience': [{'org': 'Lab', 'tech': ['Altium Designer', 'TI C2000'], 'bullets': ['Designed a 1 kW power stage reaching 98% efficiency.']},
                                         {'org': 'Ford', 'tech': ['C', 'AUTOSAR'], 'bullets': ['Wrote C drivers for a battery ECU.']}]}, ['tools'])
res.append(ok(_w1 and 'axi' in _w1 and 'xcelium' in _w1 and _w2 is None and len(_tf) == 1 and 'Lab' in _tf[0],
              f'hardware fact guard: no invented tools ({_w1}); bullets that name none of their tools are flagged ({_tf})'))
# filler never pads a page: trainings are weak lines, and a store job or an all-filler entry is not added to fill space
_two = {'experience': [{'org': 'A'}, {'org': 'B'}]}
res.append(ok(_tp.weak('Completed ISO 26262 awareness training.') and _tp.weak('Completed ITAR and security training for flight work.')
              and _tp.weak('Filed paperwork and organized the document control room.')
              and not _tp.weak('Completed a 5-axis CAM program that cut machining time 30% on 12 parts.')
              and not _tp._can_pad({'org': 'H-E-B', 'title': 'Store Associate', 'bullets': ['Trained 3 new associates.']}, _two)
              and not _tp._can_pad({'name': 'Discord Bot', 'bullets': ['Made a Discord bot that plays music.']}, _two)
              and _tp._can_pad({'name': 'RISC-V CPU', 'bullets': ['Built a 5-stage RV32I pipeline on a Basys 3 FPGA at 100 MHz.']}, _two),
              'page filler skips trainings, service jobs and all-filler entries'))
# finance reads newest first, but an ongoing part-time campus role goes by its start date: it never sits above the internship
# that ended after it began (blind reviewers marked "Research Assistant, Sep 2025 - Present" above the summer internship down)
_fo = {'experience': [{'id': 'ra', 'title': 'Research Assistant to Finance Professor', 'start': 'Sep 2025', 'end': 'Present', 'bullets': ['x']},
                      {'id': 'wm', 'title': 'Summer Investment Analyst', 'start': 'Jun 2026', 'end': 'Aug 2026', 'bullets': ['x']},
                      {'id': 'svb', 'title': 'Equity Research Intern', 'start': 'May 2025', 'end': 'Aug 2025', 'bullets': ['x']},
                      {'id': 'pt', 'title': 'Part-time Investment Analyst', 'start': 'Jan 2026', 'end': 'Present', 'bullets': ['x']},
                      {'id': 'ta', 'title': 'Teaching Assistant', 'start': 'Sep 2026', 'end': 'Present', 'bullets': ['x']}],
       'leadership': [{'id': 'c1', 'title': 'Member', 'start': 'Sep 2024', 'end': 'Present'}, {'id': 'c2', 'title': 'Chair', 'start': 'Jan 2025', 'end': 'Dec 2025'}]}
_tp._house_rules(_fo, {'field': 'finance'})
res.append(ok([e['id'] for e in _fo['experience']] == ['pt', 'ta', 'wm', 'ra', 'svb'] and [e['id'] for e in _fo['leadership']] == ['c1', 'c2'],
              f"finance order: ongoing campus roles by start date, below the internship that ended after they began ({[e['id'] for e in _fo['experience']]})"))
# a section the plan left out still shows, but without the entries the plan cut, filler lines or all-filler club entries
_vu = {'basics': {'name': 'A'}, 'experience': [{'id': 'nasa', 'title': 'Intern', 'org': 'NASA', 'bullets': ['Ran 2,000 Monte Carlo cases on a lander model.']}],
       'leadership': [{'id': 'avi', 'title': 'Avionics Lead', 'org': 'Rocket Team', 'bullets': ['Lead 12 members across flight software and PCB design.']},
                      {'id': 'out', 'title': 'Outreach Chair', 'org': 'Club', 'bullets': ['Coordinated volunteers.']},
                      {'id': 'ws', 'title': 'Workshop Coordinator', 'org': 'IEEE', 'bullets': ['Ran soldering workshops for 40+ students.', 'Helped organize events.']},
                      ]}
_ru, _ = _tp.apply(_vu, {'experience': [{'id': 'nasa'}, {'id': 'avi'}], 'lead': {'entry': 'nasa'}}, '')
res.append(ok([e['id'] for e in _ru['experience']] == ['nasa', 'avi'] and [(e['id'], e['bullets']) for e in _ru['leadership']] == [('ws', ['Ran soldering workshops for 40+ students.'])],
              f"a section the plan left out keeps no filler lines or all-filler entries ({[(e['id'], e['bullets']) for e in _ru['leadership']]})"))
_sk = _tp._pick_skills([{'label': 'Software & Lab', 'items': ['Python', 'Oscilloscopes']}, {'label': 'Embedded', 'items': ['C']}],
                       [{'label': 'Software & Lab', 'items': ['Python']}, {'label': 'Lab & Test', 'items': ['Oscilloscopes']},
                        {'label': 'Software & Lab', 'items': ['C']}])
_sk2 = _tp._pick_skills([{'label': 'Modeling', 'items': ['MATLAB', 'Monte Carlo analysis']}, {'label': 'GN&C', 'items': ['EKF', 'HIL testing']}],
                        [{'label': 'Lab & Test', 'items': ['HIL testing', 'Monte Carlo analysis']}, {'label': 'GN&C & Modeling', 'items': ['EKF', 'MATLAB']}])
res.append(ok([s['label'] for s in _sk2] == ['Lab & Test', 'GN&C'], f"skills: no heading that reads as another one printed twice ({[s['label'] for s in _sk2]})"))
res.append(ok([s['label'] for s in _sk] == ['Software & Lab', 'Lab & Test'] and _sk[0]['items'] == ['Python', 'C'],
              f'skills: a split vault line keeps its own heading, never two lines under one heading ({_sk})'))
_h = render.build_html({'basics': {'name': 'A'}, 'order': ['education'], 'education': [
    {'school': 'Indiana University', 'degree': 'Bachelor of Science in Business, Finance and Accounting', 'minor': 'Economics', 'gpa': '3.89/4.00', 'honors': ["Dean's List"]}]})
res.append(ok('<span class="nb">GPA: 3.89/4.00</span> · Dean' in _h, 'a long degree line moves the GPA (never split) to the honors line'))

# Help answers right away even mid-run: its own short agent session beside Autopilot, never queued behind it
import shutil as _sh
import tempfile as _tf
_fd = _tf.mkdtemp()
if os.name == 'nt':
    _fake = os.path.join(_fd, 'claude.cmd')
    open(_fake, 'w').write('@echo off\r\nmore > nul\r\necho Your vault has 2 roles and nothing is broken.\r\n')
else:
    _fake = os.path.join(_fd, 'claude')
    open(_fake, 'w').write('#!/bin/sh\ncat > /dev/null\necho "Your vault has 2 roles and nothing is broken."\n')
    os.chmod(_fake, 0o755)
_busy = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
_saved = (api._agent, api.agents.status, _sh.which, api._run['proc'])
api._agent, api.agents.status, _sh.which = (lambda: 'claude'), (lambda n, fresh=False: {'signed_in': True, 'label': 'Claude Code'}), (lambda n, *a, **k: _fake)
api._run['proc'] = _busy
try:
    _fq = len(store.load('followups.json', []))
    _ht = api.message('help', 'is my setup ok?')['thread']
    _hp = api._help['help']
    _hp.wait(timeout=30)
    for _ in range(40):
        if any('nothing is broken' in r['text'] for r in api.thread('help')):
            break
        time.sleep(0.25)
    _ans = [r['text'] for r in api.thread('help') if r['role'] == 'twin']
    # a question about one application mid-run is answered now too, and nothing is queued for the browser
    store.execute("insert or replace into jobs(id, company, title, location, url, status) values('jq1', 'Visa', 'Software Engineer Intern', 'Austin, TX', 'https://visa.wd5.myworkdayjobs.com/x/job/1', 'new')")
    api.message('jq1', 'what resume did you use?')
    api._help['jq1'].wait(timeout=30)
    for _ in range(40):
        if any('nothing is broken' in r['text'] for r in api.thread('jq1')):
            break
        time.sleep(0.25)
    _jans = [r['text'] for r in api.thread('jq1') if r['role'] == 'twin']
    _jq = len(store.load('followups.json', []))
finally:
    api._agent, api.agents.status, _sh.which, api._run['proc'] = _saved
    _busy.kill()
res.append(ok(len(store.load('followups.json', [])) == _fq and _ans[0].startswith('Looking into it now') and 'nothing is broken' in _ans[-1],
              f'Help answers during a run instead of queuing ({_ans})'))
res.append(ok(_jq == _fq and _jans and not any(x.startswith('Queued') for x in _jans) and 'nothing is broken' in _jans[-1],
              f'a question about one job is answered mid-run, not queued ({_jans})'))
# export: one row per job at its latest status, as CSV a spreadsheet opens, with formula-looking cells defused
store.execute("insert or replace into jobs(id, company, title, location, url, status) values('exp1', 'Acme', '=HYPERLINK(1)', 'Remote', 'https://acme.test/1', 'applied')")
store.log_application('exp1', 'Needs User', 'sign in')
store.log_application('exp1', 'Applied', 'done')
_cb, _ct, _cn = api.export_applications()
_csv = _cb.decode('utf-8-sig')
_jb = json.loads(api.export_applications('json')[0])
_er = [r for r in _jb if r['company'] == 'Acme']
res.append(ok(_ct == 'text/csv' and _cn.endswith('.csv') and _csv.startswith('Company,Role,Status') and "'=HYPERLINK(1)" in _csv
              and len(_er) == 1 and _er[0]['status'] == 'Applied' and _er[0]['url'] == 'https://acme.test/1', f'export CSV/JSON of applications ({_er})'))
# ---- apply mechanism, from real outcomes: skip early, never park non-user problems in "Needs you", batch what is the user's
from applytwin import blockers as _bk, answers as _an
_notes = {'Workday sign-in required at https://acme.wd5.myworkdayjobs.com/x': 'signin', 'Account creation required; left Create Account page open': 'account',
          "The page you are looking for doesn't exist. Tab 3 open.": 'closed', 'Posting URL returns 404 (Page not found)': 'closed',
          'Queue link opens the corporate homepage, not the job posting': 'broken_link',
          'Browser access blocked: browser host unavailable and Computer Use denied Google Chrome': 'browser',
          'Playwright reports profile /x/.applytwin/browser already in use': 'browser', 'Filled; awaiting GH code; tab open': 'email_code',
          'hCaptcha on submit': 'captcha', 'The Workday application page stopped responding during page load': 'transient',
          'Ready to submit (auto_submit off), tab open': 'ready', 'required question: SAT score': 'question',
          'duplicate: already applied on Ashby': 'duplicate', 'Required arbitration agreement checkbox': 'agreement'}
_bad = {n: _bk.classify(n) for n, c in _notes.items() if _bk.classify(n) != c}
res.append(ok(not _bad, f'blocker notes are classified (sign-in, closed, homepage, browser, code, captcha, timeout...) {_bad}'))
_hp = [_bk.homepage_link(u) for u in ('https://www.riotgames.com', 'https://acme.com/careers/', 'https://acme.com/en-us/jobs',
                                       'https://acme.com/careers/job/123', 'https://boards.greenhouse.io/acme', 'https://acme.com/careers?gh_jid=4567',
                                       'https://jobs.lever.co/acme')]
res.append(ok(_hp == [True, True, True, False, False, False, False], f'homepage-only links are told apart from postings and ATS boards {_hp}'))
api.update_profile({'apply': {'daily_limit': 500, 'per_company_cap': 10}, 'search': {'companies_skip': []}})
store.execute("update jobs set status='zz-old' where status='new'")
store.execute('delete from claims')
store.save('run_health.json', {})
store.save('retries.json', {})


def _mkjob(jid, company, url, ats='greenhouse', title='Software Engineer Intern', loc='Austin, TX', source='t', fit=90):
    store.execute("insert or replace into jobs(id,source,company,title,location,url,apply_url,ats,found_at,fit,status) values(?,?,?,?,?,?,?,?,?,?,'new')",
                  (jid, source, company, title, loc, url, url, ats, time.time(), fit))


_mkjob('hp1', 'Homepage Co', 'https://www.homepageco.com/', ats='other')
_mkjob('hp2', 'Homepage Manual', 'https://www.manualco.com/', ats='other', source='manual')
_mkjob('ok1', 'Good Co', 'https://job-boards.greenhouse.io/embed/job_app?for=good&token=111111')
_nj = [j['id'] for j in api.next_jobs(10)['jobs']]
_cl = api.claim('hp1')
res.append(ok('hp1' not in _nj and 'ok1' in _nj and 'hp2' in _nj and _cl['claimed'] is False and store.latest_status('hp1')['status'] == 'Skipped',
              f'homepage links never reach the agent (a hand-added one does), and claiming one files it Skipped ({_nj}, {_cl.get("reason", "")[:40]})'))
# a US-only role for someone abroad without US work authorization is a knockout before any page is opened
_pf = {'work_authorized_us': False, 'location': 'Mumbai, India', 'willing_to_relocate': False, 'search': {}}
_kq = (match.quick_knockouts({'title': 'Data Intern', 'location': 'Remote - USA'}, _pf), match.quick_knockouts({'title': 'Data Intern', 'location': 'Bengaluru, India'}, _pf),
       match.quick_knockouts({'title': 'Data Intern', 'location': 'Remote - USA'}, {**_pf, 'work_authorized_us': True}))
res.append(ok(_kq[0] and not _kq[1] and not _kq[2], f'US-only role for a non-authorized user abroad is a quick knockout {_kq}'))
# closed postings and duplicates logged as Needs User are filed Skipped (nothing for the user to do)
_mkjob('cl1', 'Closed Co', 'https://closed.wd5.myworkdayjobs.com/en-US/ext/job/123', ats='workday')
api.claim('cl1')
_lc = api.log_application('cl1', 'Needs User', "Workday page says the page you are looking for doesn't exist", agent=True)
res.append(ok(_lc['status'] == 'Skipped' and store.latest_status('cl1')['notes'].startswith('closed:') and
              not any(r['job_id'] == 'cl1' for r in api.pending_jobs()), f'a closed posting logged Needs User is filed Skipped ({_lc})'))
# the agent's own browser failing: the job goes back to the queue, and after two the run is told to stop
_mkjob('br1', 'Browser Co', 'https://jobs.lever.co/browserco/1', ats='lever')
_mkjob('br2', 'Browser Two', 'https://jobs.lever.co/browsertwo/2', ats='lever')
api.claim('br1')
_b1 = api.log_application('br1', 'Needs User', 'Browser access blocked: browser host unavailable; Computer Use denied Google Chrome.', agent=True)
_q1 = 'br1' in [j['id'] for j in api.next_jobs(10)['jobs']]
api.claim('br2')
_b2 = api.log_application('br2', 'Failed', 'Playwright reports the ApplyTwin browser profile already in use', agent=True)
_nj2, _c2 = api.next_jobs(10), api.claim('ok1')
res.append(ok(_b1.get('requeued') and not _b1.get('stop') and store.latest_status('br1') is None and _q1 and _b2.get('stop') and _nj2.get('stop')
              and _nj2['jobs'] == [] and _c2['claimed'] is False, f'browser failures requeue the job unlogged and stop the run after two ({_b2.get("note", "")[:50]})'))
store.save('run_health.json', {})
# a page error gets one retry, later; the second one is logged
_mkjob('tr1', 'Transient Co', 'https://jobs.lever.co/transient/1', ats='lever')
api.claim('tr1')
_t1 = api.log_application('tr1', 'Failed', 'The application page stopped responding during page load', agent=True)
_held = 'tr1' not in [j['id'] for j in api.next_jobs(10)['jobs']]
store.update('retries.json', lambda r: {**r, 'tr1': {**r['tr1'], 'at': time.time() - 3600}}, {})
_back = 'tr1' in [j['id'] for j in api.next_jobs(10)['jobs']]
api.claim('tr1')
_t2 = api.log_application('tr1', 'Failed', 'The application page stopped responding during page load', agent=True)
res.append(ok(_t1.get('requeued') and _held and _back and _t2.get('status') == 'Failed', f'a page error is retried once, 30+ minutes later, then logged ({_t2})'))
# a site waiting for the user's sign-in: its other jobs wait too, the user gets one alert, and one action unblocks the group
_mkjob('wd1', 'Nvidia', 'https://nvidia.wd5.myworkdayjobs.com/ext/job/1', ats='workday')
_mkjob('wd2', 'Nvidia', 'https://nvidia.wd5.myworkdayjobs.com/ext/job/2', ats='workday', title='Hardware Engineer Intern')
api.claim('wd1')
_n1 = api.notify('Sign in needed for Nvidia', 'Workday sign-in required', url='https://nvidia.wd5.myworkdayjobs.com/ext/job/1', job_id='wd1')
api.log_application('wd1', 'Needs User', 'Workday sign-in required at https://nvidia.wd5.myworkdayjobs.com/ext/job/1', agent=True)
_n2 = api.notify('Sign in needed for Nvidia', 'Workday sign-in required', url='https://nvidia.wd5.myworkdayjobs.com/ext/job/2', job_id='wd2')
_wn = api.next_jobs(10)
_ny = api.needs_you()
_grp = next((g for g in _ny['groups'] if g['site'] == 'nvidia.wd5.myworkdayjobs.com'), {})
_gj = api.job_for_agent('wd1')
res.append(ok('wd2' not in [j['id'] for j in _wn['jobs']] and _wn.get('waiting_on_you', [{}])[0].get('site') == 'nvidia.wd5.myworkdayjobs.com'
              and not _n1.get('batched') and _n2.get('batched') and _grp.get('blocker') == 'signin' and 'Sign in once' in _grp.get('action', '')
              and _gj.get('resume_from', {}).get('blocker') == 'signin',
              f'one sign-in wall holds back that site, alerts once, and groups in needs_you ({_wn.get("waiting_on_you")}, {_grp.get("action", "")[:40]})'))
for _r in api.inbox():
    if _r['job_id'] in ('wd1', 'wd2'):
        api.resolve(_r['id'])
res.append(ok('wd2' in [j['id'] for j in api.next_jobs(10)['jobs']], 'resolving the sign-in releases the site\'s other jobs'))
# the agent's browser failing is one plain card with a fix, never a pile of raw tool errors; old ones are cleared on start
_b1 = api.notify('ApplyTwin browser unavailable', 'The browser access host is unavailable')
_b2 = api.notify('Email browser access needed', 'Browser access is currently unavailable: Chrome computer access was not approved.')
_bi = [r for r in api.inbox() if 'browser' in (r['title'] + r['message']).lower()]
res.append(ok(len(_bi) == 1 and _bi[0]['title'] == "Your twin's browser didn't start" and 'access host' not in _bi[0]['message']
              and _b2.get('batched'), f"browser failures make one clear card ({[(r['title'], r['message'][:50]) for r in _bi]})"))
store.execute('insert into inbox(kind,title,message,url,job_id,at) values(?,?,?,?,?,?)',
              ('needs_you', 'ApplyTwin browser unavailable', 'The browser access host is unavailable', '', '', time.time()))
api.tidy_inbox()
res.append(ok(not [r for r in api.inbox() if 'browser' in (r['title'] + r['message']).lower()], 'old browser errors are cleared on start'))
# graduate programs never reach an undergrad: "Undergraduate" once read as "graduate", "Systems" as an M.S., and banks'
# "Summer Associate" (the MBA/MS/PhD program) slipped through; a master's student still sees MS/PhD roles
_ug = {'degree': 'Bachelor of Science in Information Systems', 'class_standing': 'Undergraduate'}
_ms = {'degree': 'MS Computer Science', 'class_standing': 'Graduate student'}
_gt = ['2027 Quantitative Research Summer Associate - Masters/PhD', 'Software Engineer Program - Summer Associate (Master\'s)',
       'Data Science Summer Associate - Graduate Students']
_ok = ['2027 Investment Banking Summer Analyst', 'Systems Engineering Intern', 'Intern - BS/MS Software', 'Mastercard Software Intern']
_f = lambda t, p: match.fit({'title': t, 'company': 'JPMorgan Chase', 'description': ''}, p)[0]
res.append(ok(match.student_level(_ug) == 'undergrad' and all(_f(t, _ug) == 0 for t in _gt) and all(_f(t, _ug) > 0 for t in _ok)
              and _f(_gt[0], _ms) > 0 and bool(match.level_gate({'title': 'Quant Intern', 'description': "Must be pursuing a Master's or PhD."}, _ug)),
              'graduate-only roles are kept from undergrads, and MS/PhD roles still reach master\'s students'))
# the live preview shows the resume this run built for the job it's on, never one from an older run
os.makedirs(store.path('resumes', 'pv1'), exist_ok=True)
_pv = store.path('resumes', 'pv1', 'R.pdf'); open(_pv, 'wb').write(b'%PDF-1.4')
json.dump({"result": {"pdf": _pv, "score": 81, "pages": 1, "rewrites": [{}, {}]}}, open(store.path('resumes', 'pv1', 'tailor.json'), 'w'))
_b = api.built_resume('pv1', 0)
res.append(ok(_b and _b['pdf'] == _pv and _b['rewrites'] == 2 and api.built_resume('pv1', time.time() + 60) is None and api.built_resume('nope') is None,
              f'the live resume preview is this run\'s build ({_b})'))
# trimming a skills line cuts the one the posting cares least about, not whichever came last
from applytwin import render as _rd, tailor as _tl
_sk = {'skills': [{'label': 'Hardware', 'items': ['Soldering', 'Oscilloscopes']}, {'label': 'AI and ML', 'items': ['PyTorch', 'pandas', 'scikit-learn']},
                  {'label': 'Tools', 'items': ['Git']}, {'label': 'Languages', 'items': ['Python', 'SQL']}, {'label': 'Cloud', 'items': ['AWS']}]}
_jd = 'Data science intern: Python, SQL, pandas, scikit-learn and PyTorch for machine learning models.'
_cut = _rd._drop_one(_sk, _tl.trim_worth(_sk, _ats.keywords(_jd), _jd))
res.append(ok(_cut and 'AI and ML' not in _cut and 'AI and ML' in [x['label'] for x in _sk['skills']],
              f'a long page drops the least relevant skills line ({_cut})'))
# a rewrite that keeps a project's name but drops its link gets the link back instead of being thrown out
_kl = _tl._keep_links('Built [Deja View](https://devpost.com/x) in 36 hours', 'Shipped Deja View, a WebXR app, in 36 hours')
res.append(ok(_kl == 'Shipped [Deja View](https://devpost.com/x), a WebXR app, in 36 hours'
              and _tl.check_rewrite('Built [Deja View](https://devpost.com/x) in 36 hours', _kl, '', '') is None, f'dropped links are restored ({_kl})'))
# Needs you is a short list of things to do: every site's sign-in in one row, questions in one row, closed postings hidden
for _jid, _co, _u, _note in [('td1', 'Booz Allen', 'https://bah.wd1.myworkdayjobs.com/x/1', 'sign-in required at https://bah.wd1.myworkdayjobs.com/x/1'),
                             ('td2', 'Booz Allen', 'https://bah.wd1.myworkdayjobs.com/x/2', 'account required at https://bah.wd1.myworkdayjobs.com/x/2'),
                             ('td3', 'Visa', 'https://visa.wd5.myworkdayjobs.com/x/3', 'sign-in required at https://visa.wd5.myworkdayjobs.com/x/3'),
                             ('td4', 'Gone Co', 'https://gone.test/4', 'closed: the page does not exist')]:
    store.execute("insert or replace into jobs(id, company, title, location, url, status) values(?, ?, 'Intern', 'Remote', ?, 'new')", (_jid, _co, _u))
    store.log_application(_jid, 'Needs User', _note)
_td = api.todo()
_sites = next((g for g in _td if g['kind'] == 'sites'), {})
res.append(ok(_sites.get('title', '').startswith('Sign in to') and {s['site'] for s in _sites.get('sites', [])} >= {'bah.wd1.myworkdayjobs.com', 'visa.wd5.myworkdayjobs.com'}
              and next(s for s in _sites['sites'] if s['site'] == 'bah.wd1.myworkdayjobs.com')['count'] == 2
              and not any(e['job_id'] == 'td4' for g in _td for e in g['entries']) and api.inbox_poll()['count'] == len(_td),
              f"Needs you groups into a few rows ({[(g['title'], g['count']) for g in _td]})"))
for _jid in ('td1', 'td2', 'td3', 'td4'):
    api.skip_job(_jid)
# signing in for the user: off by default, the password lives only in secrets.json (never the synced profile, never a
# tool result), and the playbook tells the agent to call applytwin_fill_password instead of typing it
_ac0 = api.accounts_status()
_off = api.fill_password('https://x.wd1.myworkdayjobs.com/login')
try:
    api.set_accounts(enabled=True)
    _noset = False
except RuntimeError:
    _noset = True
_ac = api.set_accounts(enabled=True, email='me@school.edu', password='Job$ites-2027')
_prof = json.dumps(store.profile())
_fp = api.fill_password('https://x.wd1.myworkdayjobs.com/login')
_pb = api.playbook('workday')
_sso = api.fill_password('https://accounts.google.com/v3/signin/identifier')
res.append(ok(not _ac0['enabled'] and _off['filled'] == 0 and 'No job-site password' in _off['note'] and not _noset and _ac['enabled'] and _ac['password_set']
              and _sso['filled'] == 0 and 'never typed there' in _sso['note'] and 'Continue with Google' in _pb
              and 'Job$ites-2027' not in _prof and 'Job$ites-2027' not in json.dumps(_fp) and 'Job$ites-2027' not in _pb
              and 'applytwin_fill_password' in _pb and 'me@school.edu' in _pb and store.load('secrets.json', {}).get('account_password') == 'Job$ites-2027',
              f'sign-in for you: opt-in, password kept out of the profile, tools and playbook ({_fp})'))
api.set_accounts(enabled=True, google=False)
_pbg = api.playbook('workday')
try:
    store.save('secrets.json', {})
    api.set_accounts(enabled=True, google=False)
    _need = False
except RuntimeError:
    _need = True
api.set_accounts(enabled=False, google=True)
res.append(ok('Continue with Google' not in _pbg and _need and 'applytwin_fill_password' not in api.playbook('workday'),
              'Google off: email only; no password and no Google: refused; turned off: nothing about signing in'))
# a rewrite for a posting never loses one of its keywords that the original had ("convolutional neural network" -> "model"
# cost a Deep Learning match and the tailored page scored below the untailored one); CNN counts as deep learning
_jdml = 'Requirements: Python, PyTorch, convolutional neural networks, deep learning.'
_orig = 'Trained a convolutional neural network in PyTorch to spot 5 leaf diseases from photos, 92% test accuracy'
res.append(ok('Deep Learning' in (_tl.check_rewrite(_orig, 'Trained a PyTorch model to classify 5 leaf diseases from photos, reaching 92% test accuracy', '', _jdml) or '')
              and _tl.check_rewrite(_orig, 'Trained a PyTorch CNN to classify 5 leaf diseases from photos, reaching 92% test accuracy', '', _jdml) is None,
              'rewrites keep the posting keywords the original had'))
# resume import: "B.S. Computer Science" splits into degree and major; "Austin, TX" means the US; tool words count toward roles
from applytwin import importer as _imp
_dm = _imp.DEGREE_FIELD.match('B.S. Computer Science')
res.append(ok(_dm and _dm.group(2) == 'Computer Science' and not _imp.DEGREE_FIELD.match('Bachelor of Science')
              and _imp.DEGREE_FIELD.match('BA, Economics').group(2) == 'Economics', 'degree lines without "in" still give the major'))
_rl = [r for r, syn in match.ROLE_SYNONYMS.items() if any(_re.search(r'\b' + _re.escape(x), 'built a react app; trained pytorch models; pandas dashboards') for x in syn)]
res.append(ok({'software engineer', 'machine learning', 'data science'} <= set(_rl) and 'biology' not in
              [r for r, syn in match.ROLE_SYNONYMS.items() if any(_re.search(r'\b' + _re.escape(x), 'human-centered computing lab') for x in syn)],
              f'role guesses come from real evidence, not the word "lab" ({_rl})'))
# Finish on the Gmail sign-in the email-history search stopped at (no job): it starts that search again and clears the item
store.execute("insert into inbox(kind,title,message,url,job_id,at) values('needs_you','Sign in to your email in your twin''s browser','sign-in required','https://mail.google.com/mail/u/0/','',?)", (time.time(),))
_runs, _sr = [], api.start_run
api.start_run = lambda agent='claude', n=25, model=None, prompt=None, restarts=0: (_runs.append(prompt), {"running": True})[1]
try:
    _fs = api.finish_site('mail.google.com')
    _fs2 = api.finish_site('nothing.example.com')
finally:
    api.start_run = _sr
res.append(ok(_runs and 'applytwin-history' in (_runs[0] or '') and _fs.get('running') and not _fs.get('done')
              and not [r for r in api.inbox() if 'mail.google.com' in (r['url'] or '')] and _fs2.get('done'),
              f'Finish on the email sign-in restarts the email search ({_fs}, {_fs2})'))
# Greenhouse jobs are spaced apart in a batch (rapid Greenhouse submits trigger emailed security codes)
_pc = [j['ats'] for j in api.pace([{'ats': 'greenhouse'}, {'ats': 'greenhouse'}, {'ats': 'lever'}, {'ats': 'greenhouse'}, {'ats': 'ashby'}])]
res.append(ok(_pc == ['greenhouse', 'lever', 'greenhouse', 'ashby', 'greenhouse'], f'Greenhouse jobs never back to back when there is other work {_pc}'))
# answers: company-aware, form options that rule the user out, strict school/major/degree picks, dates in every format
_bank = _an.default_bank({'grad_month': 'May', 'grad_year': '2029', 'email': 'a@ufl.edu', 'start_month': 'August', 'start_year': '2025',
                          'major': 'Computer Engineering', 'degree': 'Bachelor of Science', 'school': 'University of Florida'})
_m = lambda q, o=None, c=None: _an.match(q, _bank, o, c or {})
_ans = [
    _m('What is your graduation year?', ['2026', '2027', '2028']).get('action') == 'knockout',
    _m('Expected graduation date', ['May 2027', 'May 2028', 'Other']).get('answer') == 'Other',
    _m('Graduation year', ['2028', '2029', '2030']).get('answer') == '2029',
    _m('Expected graduation date').get('formats', {}).get('MM/YYYY') == '05/2029',
    _m('University start date').get('answer') == 'August 2025',
    _m('Are you currently enrolled in a degree program?').get('key') == 'enrolled',
    _m('High school graduation year').get('key') == 'hs_grad_year' and _m('High school graduation year').get('answer') is None,
    _m('School email address').get('answer') == 'a@ufl.edu',
    _m('Discipline', ['Computer Science', 'Aerospace Engineering', 'Engineering', 'Other']).get('answer') == 'Engineering',
    _m('Discipline', ['Computer Science', 'Aerospace Engineering']).get('answer') is None,
    _m('Major', ['Electrical and Computer Engineering', 'Computer Science']).get('answer') == 'Electrical and Computer Engineering',
    _m('Degree', ["Bachelor's Degree", "Master's Degree"]).get('answer') == "Bachelor's Degree",
    _m('School', ['UF', 'FSU']).get('answer') == 'UF',
    _m('Have you ever worked for Acme?', None, {'worked_here': True}).get('answer') == 'Yes',
    _m('Have you ever worked for Acme?', None, {'worked_here': False}).get('answer') == 'No',
    _m('Have you previously applied to Acme?', None, {'applied_before': True}).get('answer') == 'Yes',
    _m('Have you previously applied to Acme?').get('answer') is None,
    _m('Before submitting your application, please acknowledge the privacy policy').get('key') == 'privacy',
    _m('Do you have any relatives employed by Acme?').get('key') == 'knows_employee',
    _m('How did you hear about us? (friend, employee, website)', ['Company website', 'Friend']).get('answer') == 'Company website',
]
res.append(ok(all(_ans), f'answers: grad-option knockouts, dates, school/major/degree never a sibling, company-aware facts {_ans}'))
_sp = _an.pick_option('No', ['I will require sponsorship', 'I will not require sponsorship'])
res.append(ok(_sp == 'I will not require sponsorship', f'Yes/No onto options that only differ by a negation ({_sp})'))
# with a job, "Have you worked for <company>?" is checked against the vault (Northwind Labs is in the example vault)
_mkjob('nw1', 'Northwind Labs', 'https://jobs.lever.co/northwind/1', ats='lever')
_nw = api.answer_questions(['Have you ever been employed by Northwind Labs?'], job_id='nw1', notify_user=False)[0]
_ok1 = api.answer_questions(['Have you ever been employed by Good Co?'], job_id='ok1', notify_user=False)[0]
res.append(ok(_nw['answer'] == 'Yes' and _ok1['answer'] == 'No', f'prior-employer questions answered from the vault ({_nw["answer"]}, {_ok1["answer"]})'))
_pb = api.playbook('oraclecloud')
res.append(ok('Oracle Recruiting Cloud' in _pb and 'remove it, upload' in _pb and 'knockout' in api.playbook('greenhouse'),
              'Oracle has its own playbook; every playbook carries the re-upload and closed-posting rules'))
_rp = api.run_prompt(5)
res.append(ok('about:blank' in _rp and 'applytwin_needs_you' in _rp and "closed: " in _rp and 'never log jobs as blocked because your browser' in _rp,
              'Autopilot instructions: browser check first, closed = Skipped, batched needs-you at the end'))
from applytwin import mcp as _mcp
res.append(ok('applytwin_needs_you' in _mcp.BY and 'waiting_on_you' in _mcp.BY['applytwin_next_jobs'][1], 'MCP exposes the batched needs-you list'))
# international: location parsing, regions, work rights, answers, CV conventions, A4 (kept in its own file)
exec(compile(open(os.path.join(ROOT, 'tests', 'smoke_intl.py'), encoding='utf-8').read(), 'smoke_intl.py', 'exec'))

# an agent installed where the app's login-time PATH doesn't reach (native installer, nvm, Homebrew) is still found
from applytwin import agents as _ag
_th = _tf.mkdtemp()
os.makedirs(os.path.join(_th, '.local', 'bin'))
_fa = os.path.join(_th, '.local', 'bin', 'atfakeagent' + ('.cmd' if os.name == 'nt' else ''))
open(_fa, 'w').write('@echo off\r\n' if os.name == 'nt' else '#!/bin/sh\n')
os.chmod(_fa, 0o755)
_env = {k: os.environ.get(k) for k in ('HOME', 'USERPROFILE', 'PATH')}
os.environ.update(HOME=_th, USERPROFILE=_th, PATH=os.pathsep.join(p for p in (os.environ.get('SystemRoot'), '/usr/bin', '/bin') if p))
try:
    _found = _ag.exe('atfakeagent')
finally:
    for _k, _v in _env.items():
        if _v is None:
            os.environ.pop(_k, None)
        else:
            os.environ[_k] = _v
res.append(ok(bool(_found) and os.path.dirname(_found) == os.path.dirname(_fa), f'agents found in ~/.local/bin with a short PATH ({_found})'))

print(f'\n{sum(res)}/{len(res)} passed')
sys.exit(0 if all(res) else 1)
