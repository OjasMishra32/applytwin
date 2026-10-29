"""One API used by the web app, the MCP server (Claude Code / Codex) and the CLI."""
import json
import os
import re
import threading
import time

from . import answers as ans
from . import agents, ats, learn, match, render, sources, store, tailor

APP = store.APP
_scan = {"running": False, "stats": None, "started": None, "finished": None}


# ------------------------------------------------------------------ profile, vault, answers

def get_profile():
    return store.profile()


def update_profile(patch):
    p = store._merge(store.profile(), patch or {})
    store.save('profile.json', p)
    # keep profile-derived answers in sync unless the user overrode them
    bank = store.answers()
    fresh = {r['key']: r for r in ans.default_bank(p)}
    for r in bank:
        if r.get('source') == 'profile' and r['key'] in fresh:
            r['answer'] = fresh[r['key']]['answer']
    store.save('answers.json', bank)
    from . import cloud
    cloud.sync_soon()
    return p


def get_vault():
    return tailor.ensure_ids(store.resume())


def save_vault(vault):
    v = store._merge(store.DEFAULT_RESUME, vault or {})
    for sec in tailor.ENTRY_SECS:
        for e in v.get(sec, []):
            e['bullets'] = [b for b in e.get('bullets', []) if b and b.strip()]
    tailor.ensure_ids(v)
    store.save('resume.json', v)
    from . import cloud
    cloud.sync_soon()
    return {"ok": True, "counts": {k: len(v.get(k, [])) for k in ('experience', 'projects', 'research', 'leadership', 'skills', 'awards')}}


def save_dump(text):
    """Raw brain-dump text (old resumes, LinkedIn, notes). An agent turns it into the structured vault."""
    with open(store.path('dump.md'), 'a') as f:
        f.write(f'\n\n<!-- {time.strftime("%Y-%m-%d %H:%M")} -->\n{text.strip()}\n')
    return {"ok": True, "chars": len(text), "next": "Ask your agent: 'twin: structure my dump into my vault' (skill applytwin-onboard)"}


def get_dump():
    p = store.path('dump.md')
    return open(p).read() if os.path.exists(p) else ''


def get_answers():
    return store.answers()


def save_answer(question, answer, key=None):
    bank = ans.upsert(store.answers(), question, answer, key)
    store.save('answers.json', bank)
    return {"ok": True, "count": len(bank)}


def answer_questions(questions, job_id=None):
    """questions: list of strings or {question, options}. Returns an answer (or 'ask') for each."""
    bank = store.answers()
    out = []
    for q in questions or []:
        if isinstance(q, dict):
            out.append(ans.match(q.get('question') or q.get('label', ''), bank, q.get('options')))
        else:
            out.append(ans.match(q, bank))
    return out


# ------------------------------------------------------------------ jobs

def scan(sources_list=None, background=False):
    if _scan['running']:
        return {"running": True, "stats": _scan['stats']}

    def run():
        _scan.update(running=True, started=time.time(), stats={})
        try:
            _scan['stats'] = sources.scan(sources_list, on_progress=lambda s: _scan.update(stats=s))
        finally:
            _scan.update(running=False, finished=time.time())
    if background:
        threading.Thread(target=run, daemon=True).start()
        return {"running": True}
    run()
    return _scan['stats']


def scan_status():
    return dict(_scan)


def list_jobs(query='', status='new', min_fit=None, limit=100, ats_filter=None, order='fit'):
    p = store.profile()
    min_fit = p['search'].get('min_fit', 65) if min_fit is None else min_fit
    sql = 'select id,source,company,title,location,url,apply_url,ats,posted,found_at,fit,fit_why,status from jobs where fit>=?'
    args = [min_fit]
    if status and status != 'all':
        sql += ' and status=?'
        args.append(status)
    if ats_filter:
        sql += ' and ats=?'
        args.append(ats_filter)
    if query:
        sql += ' and (title like ? or company like ? or location like ?)'
        args += [f'%{query}%'] * 3
    sql += ' order by ' + ('found_at desc, fit desc' if order == 'new' else 'fit desc, found_at desc') + ' limit ?'
    args.append(int(limit) * 3)
    out, seen = [], set()
    for j in store.rows(sql, args):  # the same role posted in many cities shows once
        k = (j['company'].lower(), re.sub(r'\s*[-(,].*$', '', j['title'].lower()))
        if k in seen:
            continue
        seen.add(k)
        out.append(j)
        if len(out) >= int(limit):
            break
    return out


def get_job(job_id, with_description=True):
    r = store.rows('select * from jobs where id=?', (job_id,))
    if not r:
        return None
    j = r[0]
    if with_description and len(j.get('description') or '') < 400:
        j['description'] = sources.fetch_description(j)
    return j


def set_job_status(job_id, status):
    store.execute('update jobs set status=? where id=?', (status, job_id))
    return {"ok": True}


def add_job(url, title='', company='', description=''):
    """Track a job the scrapers didn't find (paste any URL + description)."""
    j = sources.job('manual', url, company or re.sub(r'^https?://(www\.)?|/.*$', '', url), title or 'Untitled role', '', url,
                    url, time.strftime('%Y-%m-%d'), description, ats=sources.detect_ats(url))
    fit, why = match.fit(j, store.profile())
    store.execute('insert or replace into jobs(id,source,company,title,location,url,apply_url,ats,posted,description,found_at,fit,fit_why)'
                  ' values(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                  (j['id'], 'manual', j['company'], j['title'], '', url, url, j['ats'], j['posted'], description, time.time(),
                   max(fit, store.profile()['search'].get('min_fit', 65) + 10), why or 'added by you'))  # you added it: it always makes the queue
    return get_job(j['id'], with_description=not description)


def job_questions(job_id):
    """Greenhouse exposes an application's questions publicly; pre-answer them from the bank."""
    j = get_job(job_id, with_description=False)
    if not j:
        return []
    m = re.search(r'for=([^&]+)&token=(\d+)', j.get('apply_url') or '')
    if not m:
        return {"note": "Questions are only pre-fetchable for Greenhouse; read them from the form instead."}
    d = sources.get(f'https://boards-api.greenhouse.io/v1/boards/{m.group(1)}/jobs/{m.group(2)}?questions=true')
    qs = []
    for q in d.get('questions', []) + d.get('location_questions', []):
        opts = [v.get('label') for f in q.get('fields', []) for v in (f.get('values') or [])]
        qs.append({"question": q.get('label'), "required": q.get('required'), "options": opts,
                   "type": (q.get('fields') or [{}])[0].get('type')})
    bank = store.answers()
    for q in qs:
        q['suggested'] = ans.match(q['question'], bank, q['options'] or None)
    return qs


def next_jobs(n=10):
    """The apply queue: best-fit unapplied jobs, respecting the daily limit and per-company caps."""
    p = store.profile()
    left = max(0, p['apply'].get('daily_limit', 40) - store.applied_count_today())
    cap = p['apply'].get('per_company_cap', 3)
    out, per, done = [], {}, done_roles()
    for j in list_jobs(status='new', limit=400):
        if already_done(j, done):
            continue
        c = j['company'].lower()
        if store.company_count(c) + per.get(c, 0) >= cap:
            continue
        if store.rows('select 1 from claims where job_id=?', (j['id'],)):
            continue
        per[c] = per.get(c, 0) + 1
        out.append(j)
        if len(out) >= min(n, left):
            break
    return {"remaining_today": left, "jobs": out}


STOP = {'the', 'a', 'an', 'and', 'of', 'for', 'to', 'in', 'at', 'hq', 'remote', 'hybrid', 'onsite', 'us', 'usa'}


def role_key(company, title):
    """Same role at the same company, however a board spells it: 'Software Engineer Intern (First Play) - Summer 2027
    (Mountain View, CA)' and 'Software Engineer Intern, First Play' are one job."""
    c = re.sub(r'[^a-z]+', '', (company or '').lower())
    t = (title or '').lower()
    t = re.sub(r'\([^)]*,[^)]*\)', ' ', t)                                  # (Mountain View, CA)
    t = re.sub(r'\b(summer|fall|spring|winter|autumn)\b|\b20\d\d\b', ' ', t)
    toks = frozenset(w for w in re.split(r'[^a-z0-9+#]+', t) if w and w not in STOP)
    return c, toks


def done_roles():
    """Every role you've already applied to, are mid-way through, or skipped, from any source."""
    rows = store.rows("select company, title from jobs where status not in ('new')")
    rows += store.rows("select company, title from applications")
    return {role_key(r['company'], r['title']) for r in rows}


def already_done(job, done=None):
    return role_key(job['company'], job['title']) in (done if done is not None else done_roles())


def claim(job_id, who='agent'):
    j = (store.rows('select id, company, title, status from jobs where id=?', (job_id,)) or [None])[0]
    if j and (j['status'] != 'new' or already_done(j)):
        return {"claimed": False, "reason": "You already applied to this role (or a listing of the same role). Skip it."}
    return {"claimed": store.claim(job_id, who)}


def log_application(job_id, status='Applied', notes='', resume_path=''):
    out = store.log_application(job_id, status, notes, resume_path)
    from . import cloud
    if cloud.status()['signed_in']:
        threading.Thread(target=lambda: cloud._safe(cloud.push_applications), daemon=True).start()
    return out


def applications(limit=500):
    return store.rows('select * from applications order by at desc limit ?', (limit,))


def stats():
    r = store.rows("select status, count(*) n from jobs group by status")
    a = store.rows("select status, count(*) n from applications group by status")
    week = store.rows("select count(*) n from applications where status='Applied' and at>?", (time.time() - 7 * 86400,))[0]['n']
    return {"jobs": {x['status']: x['n'] for x in r}, "applications": {x['status']: x['n'] for x in a},
            "applied_7d": week, "applied_today": store.applied_count_today(),
            "matched": store.rows('select count(*) n from jobs where status="new" and fit>=?',
                                  (store.profile()['search'].get('min_fit', 65),))[0]['n']}


# ------------------------------------------------------------------ resumes

def templates():
    return [{"id": k, **v} for k, v in render.TEMPLATES.items()]


def preview_html(template='classic', job_id=None, plan=None):
    v = get_vault()
    saved = store.path('resumes', job_id or '_', 'tailor.json')
    if job_id and not plan and os.path.exists(saved):
        res = json.load(open(saved))['resume']
    elif job_id:
        j = get_job(job_id)
        res, _ = tailor.apply(v, plan or tailor.heuristic_plan(v, j.get('description', ''), title=j.get('title', ''),
                                                             ctx=learn.context_for(j)), j.get('description', ''))
    else:
        res = v
    return render.build_html(res, template)


def render_resume(template=None, job_id=None, one_page=True):
    p = store.profile()
    template = template or p['apply'].get('template', 'classic')
    v = get_vault()
    name = re.sub(r'[^A-Za-z]+', '_', v['basics'].get('name') or 'Resume').strip('_') + '_Resume.pdf'
    if job_id:
        j = get_job(job_id)
        return tailor.tailor(v, j, j.get('description', ''), mode='heuristic', style=template)
    out = store.path('resumes', 'master', name)
    r = render.render(v, template, out, one_page)
    txt = render.pdf_text(out)
    rep = ats.report(v, '', r['pages'], txt)
    return {**r, "score": rep['score'], "lint": rep['lint']}


def ats_report(job_id=None, jd_text=None, resume=None):
    v = resume or get_vault()
    jd = jd_text or (get_job(job_id) or {}).get('description', '') if (job_id or jd_text) else ''
    return ats.report(v, jd or '')


def tailor_prompt(job_id):
    j = get_job(job_id)
    if not j:
        return {"error": "unknown job"}
    return {"job": {k: j[k] for k in ('id', 'company', 'title', 'location', 'apply_url')},
            "prompt": tailor.prompt(get_vault(), j, j.get('description', ''), learn.context_for(j)),
            "template": learn.context_for(j)['template'],
            "then": "call applytwin_tailor_apply(job_id, plan) with the JSON plan"}


def tailor_apply(job_id, plan=None, template=None, mode='auto'):
    j = get_job(job_id)
    if not j:
        return {"error": "unknown job"}
    if isinstance(plan, str):
        plan = json.loads(plan)
    return tailor.tailor(get_vault(), j, j.get('description', ''), mode=mode, plan=plan, style=template)


def remember(note=None, pin=None, avoid=None, field=None, template=None):
    return learn.remember(note, pin, avoid, field, template)


def forget(note=None, pin=None, avoid=None):
    return learn.forget(note, pin, avoid)


def insights():
    return {"preferences": learn.prefs(), "outcomes": learn.outcomes()}


def suggest_template(job):
    p = store.profile()
    t = f"{job.get('title', '')} {job.get('company', '')}".lower()
    if re.search(r'invest|banking|private equity|asset management|wealth|equity research|capital markets', t):
        return 'finance'
    if re.search(r'consult|strategy|government|policy', t):
        return 'harvard'
    return p['apply'].get('template', 'classic')


PLAYBOOK_ALIAS = {'jobvite': 'others', 'workable': 'others', 'rippling': 'others', 'paylocity': 'others', 'pinpoint': 'others',
                  'gem': 'others', 'oracle': 'others', 'taleo': 'others', 'eightfold': 'others', 'successfactors': 'others',
                  'community': 'general', 'manual': 'general', 'other': 'general'}


def playbook(ats_name):
    name = (ats_name or 'general').lower()
    f = os.path.join(APP, 'playbooks', f'{PLAYBOOK_ALIAS.get(name, name)}.md')
    if not os.path.exists(f):
        f = os.path.join(APP, 'playbooks', 'general.md')
    return open(f).read()


def setup_status():
    p, v = store.profile(), store.resume()
    steps = [
        ("profile", bool(p.get('name') and p.get('email') and p.get('school')), "Fill in your profile"),
        ("vault", len(v.get('experience', [])) + len(v.get('projects', [])) >= 2, "Add your experience and projects to the vault"),
        ("skills", bool(v.get('skills')), "Add your skills"),
        ("search", bool(p['search'].get('roles')), "Choose the roles you want"),
        ("scan", bool(store.rows('select 1 from jobs limit 1')), "Run your first job scan"),
    ]
    try:
        render.chrome()
        chrome = True
    except Exception:
        chrome = False
    steps.append(("chrome", chrome, "Install Google Chrome (used to make PDFs)"))
    return [{"id": a, "done": b, "label": c} for a, b, c in steps]


# ------------------------------------------------------------------ import, queue, autopilot

def import_resume(name='', data=None, text=None):
    from . import importer
    return importer.import_resume(name, data, text)


def queue(n=50):
    """Everything worth applying to, in order: dream companies first, then by fit. Respects caps and the skip list."""
    p = store.profile()
    dream = {c.lower() for c in p['search'].get('companies_priority', [])}
    cap = p['apply'].get('per_company_cap', 3)
    rows = list_jobs(status='new', limit=20000)
    applied = {r['c']: r['n'] for r in store.rows("select lower(company) c, count(*) n from applications where status='Applied' group by lower(company)")}
    claimed = {r['job_id'] for r in store.rows('select job_id from claims')}
    out, per, done = [], {}, done_roles()
    for j in rows:
        c = j['company'].lower()
        if already_done(j, done) or j['id'] in claimed or applied.get(c, 0) + per.get(c, 0) >= cap:
            continue
        per[c] = per.get(c, 0) + 1
        j['dream'] = any(d in c for d in dream)
        out.append(j)
    out.sort(key=lambda j: (not j['dream'], -j['fit']))
    left = max(0, p['apply'].get('daily_limit', 40) - store.applied_count_today())
    return {"total": len(out), "dream": sum(j['dream'] for j in out), "remaining_today": left, "jobs": out[:int(n)]}


_run = {"proc": None, "agent": None, "log": None}


def run_prompt(n):
    return (f"Use the applytwin-apply skill. Apply to the next {n} jobs in my ApplyTwin queue (applytwin_queue / applytwin_next_jobs), "
            "dream companies first. For every job: claim it, tailor a resume (applytwin_tailor_prompt then applytwin_tailor_apply), "
            "open the application in the browser, follow applytwin_playbook for its ATS, answer from applytwin_answer_questions, "
            "submit only if my profile allows auto_submit, and log the result with applytwin_log_application. "
            "If a site asks for an emailed verification code: if my profile.apply.email_codes is 'agent', read the newest code from that company "
            "in my email (your email/Gmail tool, or my webmail tab in the browser) and enter it; otherwise call applytwin_notify and move on. "
            "For sign-ins, passwords, CAPTCHAs or anything only I can do: applytwin_notify, log Needs User, leave the tab open, continue. "
            "At the end, check applytwin_pending_jobs and finish any I have unblocked. Judge class-year and start-date requirements by my standing DURING the internship (applytwin_get_profile class_standing: a sophomore now is a rising junior next summer); skip only when I am clearly ineligible, and when unsure, apply. Never invent facts. Give a 1-line update every 5 jobs.")


def doctor():
    return agents.doctor()


def agent_status():
    return {n: agents.status(n) for n in agents.NAMES}


def start_run(agent='claude', n=25, model=None):
    import shutil
    import subprocess
    if _run['proc'] and _run['proc'].poll() is None:
        return run_status()
    exe = shutil.which(agent)
    if not exe:
        raise RuntimeError(f"{'Claude Code' if agent == 'claude' else 'Codex'} is not installed or not on PATH")
    st = agents.status(agent, fresh=True)
    if not st['signed_in']:
        raise RuntimeError(f"{st['label']} is signed out. Run `{agents.LOGIN[agent]}` in a terminal, then press Launch again.")
    prompt = run_prompt(n)
    if agent == 'claude':
        # runs on the user's own Claude subscription; only ApplyTwin's tools and a browser are pre-approved, so it never stalls on a prompt
        tools = ('mcp__plugin_applytwin_applytwin,mcp__applytwin,mcp__playwright,mcp__claude-in-chrome,'
                 'Read,Write,Bash(ls:*),Bash(open:*)')
        cmd = [exe, '-p', prompt, '--allowedTools', tools, '--permission-mode', 'acceptEdits', '--output-format', 'text']
    else:
        cmd = [exe, 'exec', '--skip-git-repo-check', '-s', 'workspace-write', '-c', 'approval_policy="never"', *(['-m', model] if model else agents.codex_model_args()), prompt]
    logf = store.path('autopilot.log')
    f = open(logf, 'w')
    f.write(f"$ {' '.join(os.path.basename(c) if i == 0 else c for i, c in enumerate(cmd[:-1]) if c != prompt)} … apply to {n} jobs\n")
    f.flush()
    # run from the data folder, not the repo, so the agent loads the installed plugin rather than the repo's dev .mcp.json
    proc = subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, cwd=store.HOME)
    _run.update(proc=proc, agent=agent, log=logf)
    import threading
    threading.Thread(target=_watch_run, args=(proc, agent, logf, n, model), daemon=True).start()
    return run_status()


AUTH_ERRORS = ('failed to authenticate', 'oauth session expired', 'not logged in', 'please run /login', 'invalid api key',
               'unauthorized', 'status 401')


def _watch_run(proc, agent, logf, n, model):
    # when the agent exits early because its own sign-in lapsed, tell the user how to fix it instead of failing silently
    proc.wait()
    tail = open(logf).read()[-3000:].lower() if os.path.exists(logf) else ''
    name = 'Claude Code' if agent == 'claude' else 'Codex'
    if agent == 'codex' and 'model_not_found' in tail and not model:
        # the configured model isn't on this plan or CLI: retry once on one the CLI lists
        agents.FALLBACK_MODEL[0] = True
        fb = (agents.codex_model_args() or [None, 'gpt-5.6-sol'])[1]
        return start_run(agent, n, model=fb)
    if any(e in tail for e in AUTH_ERRORS):
        fix = 'run `claude` in a terminal and type /login' if agent == 'claude' else 'run `codex login` in a terminal'
        notify(f'Sign in to {name}', f'Your {name} login expired: {fix}, then press Launch again.', kind='signin')
    elif proc.returncode:
        notify(f'{name} stopped early', f'Exit code {proc.returncode}. The last lines are in the Autopilot log.', kind='error')


def stop_run():
    if _run['proc'] and _run['proc'].poll() is None:
        _run['proc'].terminate()
    return run_status()


def run_status():
    p = _run['proc']
    log = ''
    if _run['log'] and os.path.exists(_run['log']):
        log = open(_run['log']).read()[-6000:]
    return {"running": bool(p and p.poll() is None), "agent": _run['agent'], "log": log,
            "exit": None if not p or p.poll() is None else p.returncode}


# ------------------------------------------------------------------ inbox: things only the user can do

def notify(title, message='', url='', job_id='', kind='needs_you'):
    """Tell the user something needs them (a code, a sign-in, a CAPTCHA, a question). Desktop notification + in-app inbox."""
    store.execute('insert into inbox(kind,title,message,url,job_id,at) values(?,?,?,?,?,?)', (kind, title, message, url, job_id, time.time()))
    if store.profile()['apply'].get('notify_desktop', True):
        from .install import notify as desk
        desk('ApplyTwin: ' + title, message or url)
    return {"ok": True}


def inbox(include_resolved=False):
    sql = 'select * from inbox' + ('' if include_resolved else ' where resolved is null') + ' order by at desc limit 200'
    return store.rows(sql)


def resolve(item_id):
    store.execute('update inbox set resolved=? where id=?', (time.time(), int(item_id)))
    return {"ok": True}


def pending_jobs():
    """Jobs your agent stopped on (Needs User) that are not finished yet: come back to these after the user acts."""
    rows = store.rows("select a.job_id, a.company, a.title, a.url, a.notes, a.at from applications a where a.status='Needs User' and "
                      "not exists (select 1 from applications b where b.job_id=a.job_id and b.at>a.at and b.status in ('Applied','Skipped','Failed')) "
                      "order by a.at desc")
    seen, out = set(), []
    for r in rows:
        if r['job_id'] not in seen:
            seen.add(r['job_id'])
            out.append(r)
    return out


def import_history(csv_path):
    """Mark jobs you already applied to elsewhere (a CSV with company,title,url,status columns, e.g. a spreadsheet tracker)
    so your twin never applies twice. Matches by ATS job id in the URL, then by company + title."""
    import csv
    ids, names = {}, {}
    with open(csv_path, newline='') as f:
        for row in csv.reader(f):
            if len(row) < 4 or row[0].lower() == 'company':
                continue
            company, title, url, status = row[0], row[1], row[2], row[3]
            if not status.strip():
                continue
            st = 'applied' if status.lower().startswith('applied') else 'skipped'  # anything you already touched stays out of the queue
            for m in re.findall(r'(?:token=|/jobs/|/)([0-9a-f]{8}-[0-9a-f-]{27}|\d{5,})', url or ''):
                ids[m] = st
            names[(company.lower().strip(), title.lower().strip())] = st
    n = 0
    for j in store.rows('select id, company, title, url, apply_url from jobs where status="new"'):
        st = None
        for m in re.findall(r'(?:token=|/jobs/|/)([0-9a-f]{8}-[0-9a-f-]{27}|\d{5,})', (j['apply_url'] or '') + ' ' + (j['url'] or '')):
            st = st or ids.get(m)
        st = st or names.get((j['company'].lower().strip(), j['title'].lower().strip()))
        if st:
            store.execute('update jobs set status=? where id=?', (st, j['id']))
            n += 1
    return {"matched": n, "known_applications": len(names)}


def rescore():
    """Re-run fit scoring on every stored job (after profile or matcher changes), no network needed."""
    from . import ats
    prof = store.profile()
    vt = ats.resume_text(store.resume())
    terms = {t for t, pat in ats.PATTERNS.items() if pat.search(vt)}
    n = 0
    with store.db() as con:
        for j in [dict(r) for r in con.execute('select * from jobs')]:
            f, why = match.fit(j, prof, terms)
            con.execute('update jobs set fit=?, fit_why=? where id=?', (f, why, j['id']))
            n += 1
    return {"rescored": n}
