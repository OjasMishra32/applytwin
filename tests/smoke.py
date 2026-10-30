"""End-to-end smoke test on a throwaway APPLYTWIN_HOME: vault -> render every template -> tailor + fact guard -> answers -> MCP."""
import json, os, subprocess, sys, tempfile
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
print(f'\n{sum(res)}/{len(res)} passed')
sys.exit(0 if all(res) else 1)
