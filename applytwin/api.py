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
    with open(store.path('dump.md'), 'a', encoding='utf-8') as f:
        f.write(f'\n\n<!-- {time.strftime("%Y-%m-%d %H:%M")} -->\n{text.strip()}\n')
    return {"ok": True, "chars": len(text), "next": "Ask your agent: 'twin: structure my dump into my vault' (skill applytwin-onboard)"}


def get_dump():
    p = store.path('dump.md')
    return open(p, encoding='utf-8').read() if os.path.exists(p) else ''


def get_answers():
    return store.answers()


def save_answer(question, answer, key=None):
    bank = ans.upsert(store.answers(), question, answer, key)
    store.save('answers.json', bank)
    return {"ok": True, "count": len(bank)}


def answer_questions(questions, job_id=None):
    """questions: list of strings or {question, options}. Returns an answer (or 'ask') for each. When a form asks
    something you haven't told ApplyTwin, you get a 'Needs you' item saying exactly what to add (once per question)."""
    bank = store.answers()
    out = []
    for q in questions or []:
        if isinstance(q, dict):
            out.append(ans.match(q.get('question') or q.get('label', ''), bank, q.get('options')))
        else:
            out.append(ans.match(q, bank))
    profile_keys = {r['key'] for r in ans.default_bank(store.profile())}
    for r in out:
        if r.get('answer') is None and r.get('action') != 'write':   # open-ended ones the agent writes; never ask the user
            known = r.get('key') in profile_keys
            title = f"Add your answer: {r['question'][:300]}"
            if not store.rows('select 1 from inbox where title=? and resolved is null', (title,)):
                notify(title, ("Forms keep asking this and it's blank in your profile. Add it in Settings so your twin never "
                               "has to guess." if known else "A form asked this and ApplyTwin doesn't know your answer yet. "
                               "Answer it on the Answers page; your twin reuses it everywhere."),
                       job_id=job_id or '', kind='question')
    return out


def profile_questions():
    p = store.profile()
    return {"questions": ans.questions(), "missing": ans.gaps(p)}


# ------------------------------------------------------------------ jobs

def scan(sources_list=None, background=False):
    if _scan['running']:
        return {"running": True, "stats": _scan['stats']}

    def run():
        _scan.update(running=True, started=time.time(), stats={})
        try:
            _scan['stats'] = sources.scan(sources_list, on_progress=lambda s: _scan.update(stats=s))
            store.save('last_scan.json', {"at": time.time(), "stats": _scan['stats']})
        finally:
            _scan.update(running=False, finished=time.time())
    if background:
        threading.Thread(target=run, daemon=True).start()
        return {"running": True}
    run()
    return _scan['stats']


def scan_status():
    return {**_scan, "last": store.load('last_scan.json', {}).get('at')}


def scan_if_stale(hours=12):
    """Keep the job list fresh without anyone pressing Scan: rescan in the background when the last one is old."""
    last = store.load('last_scan.json', {}).get('at', 0)
    if time.time() - last > hours * 3600 and (store.resume().get('experience') or store.resume().get('projects')):
        return scan(background=True)
    return {"running": False, "fresh": True}


def update_status():
    from . import update
    return update.check()


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
    out, per, done, ids = [], {}, done_roles(), done_url_ids()
    if left <= 0:
        return {"remaining_today": 0, "jobs": [], "note": "Today's limit is reached. Stop here."}
    skip = p['search'].get('companies_skip', [])
    for j in list_jobs(status='new', limit=400):
        if already_done(j, done, ids) or any(match.same_company(s, j['company']) for s in skip):
            continue
        c = match.company_key(j['company'])
        if store.company_count(j['company']) + per.get(c, 0) >= cap:
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
    c = match.company_key(company)
    t = (title or '').lower()
    t = re.sub(r'\([^)]*,[^)]*\)', ' ', t)                                  # (Mountain View, CA)
    t = re.sub(r'\b(summer|fall|spring|winter|autumn)\b|\b20\d\d\b', ' ', t)
    toks = frozenset(w for w in re.split(r'[^a-z0-9+#]+', t) if w and w not in STOP)
    return c, toks


URL_ID = re.compile(r'(?:token=|/jobs/|/job/|/)([0-9a-f]{8}-[0-9a-f-]{27}|\d{5,})')


def applied_elsewhere():
    """Roles you applied to outside ApplyTwin (a tracker CSV, or confirmations found in your email). Kept forever, so a
    role that shows up in a later scan is still never applied to twice."""
    return store.load('applied_elsewhere.json', [])


def done_roles():
    """Every role you've already applied to, are mid-way through, or skipped, from any source."""
    rows = store.rows("select company, title from jobs where status not in ('new')")
    rows += store.rows("select company, title from applications")
    rows += applied_elsewhere()
    return {role_key(r['company'], r['title']) for r in rows if r.get('company') and r.get('title')}


def done_url_ids():
    return {m for r in applied_elsewhere() for m in URL_ID.findall(r.get('url') or '')}


def already_done(job, done=None, ids=None):
    if role_key(job['company'], job['title']) in (done if done is not None else done_roles()):
        return True
    ids = ids if ids is not None else done_url_ids()
    return any(m in ids for m in URL_ID.findall(f"{job.get('apply_url') or ''} {job.get('url') or ''}"))


def claim(job_id, who='agent'):
    """The one gate every application passes: never twice, never a skipped company, never past today's limit or a
    company's cap."""
    j = (store.rows('select id, company, title, status, url, apply_url from jobs where id=?', (job_id,)) or [None])[0]
    if j and j['status'] in ('needs user', 'failed'):
        return {"claimed": True, "reason": "Already in progress: continue this application."}
    if j and (j['status'] != 'new' or already_done(j)):
        return {"claimed": False, "reason": "You already applied to this role (or a listing of the same role). Skip it."}
    p = store.profile()
    if j and any(match.same_company(s, j['company']) for s in p['search'].get('companies_skip', [])):
        return {"claimed": False, "reason": "The user asked never to apply to this company. Skip it."}
    if store.applied_count_today() >= p['apply'].get('daily_limit', 40):
        return {"claimed": False, "reason": "Today's application limit is reached. Stop the run here."}
    if j and store.company_count(j['company']) >= p['apply'].get('per_company_cap', 3):
        return {"claimed": False, "reason": "The per-company cap for this company is reached. Skip it."}
    return {"claimed": store.claim(job_id, who)}


def on_start():
    """After the app (re)starts: unfinished claims from a run that died go to Needs you, and work you queued during a run
    still happens."""
    release_claims(older_than=3 * 3600)
    time.sleep(20)
    if not (_run['proc'] and _run['proc'].poll() is None):
        _next_followup()


def release_claims(since=0.0, older_than=None):
    """Jobs a run claimed but never logged (it was stopped, crashed, or the app restarted). They go to Needs you with an
    honest note instead of vanishing from the queue forever."""
    q = 'select c.job_id, c.at from claims c where not exists (select 1 from applications a where a.job_id=c.job_id and a.at>=c.at)'
    for r in store.rows(q):
        if r['at'] < since or (older_than and time.time() - r['at'] < older_than):
            continue
        store.log_application(r['job_id'], 'Needs User', 'The run ended before this one was finished. Check whether it was '
                                                         'submitted; if not, press Refill or tell your twin to finish it.')


def log_application(job_id, status='Applied', notes='', resume_path=''):
    out = store.log_application(job_id, status, notes, resume_path)
    from . import cloud
    if cloud.status()['signed_in']:
        threading.Thread(target=lambda: cloud._safe(cloud.push_applications), daemon=True).start()
    return out


def applications(limit=500, history=False):
    rows = store.rows('select * from applications order by at desc limit ?', (limit,))
    if history:   # roles applied to before ApplyTwin (imported from a tracker), so the board shows the whole search
        logged = {r['job_id'] for r in store.rows('select job_id from applications')}
        rows += [{"id": 'h' + j['id'], "job_id": j['id'], "company": j['company'], "title": j['title'], "url": j['url'], "status": 'Applied',
                  "resume_path": '', "notes": 'From your history', "at": j['found_at']}
                 for j in store.rows("select id, company, title, url, found_at from jobs where status='applied' order by found_at desc")
                 if j['id'] not in logged]
    return rows


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
    if job_id and not re.fullmatch(r'[\w-]+', job_id):
        raise ValueError('bad job id')
    saved = store.path('resumes', job_id or '_', 'tailor.json')
    if job_id and not plan and os.path.exists(saved):
        res = json.load(open(saved, encoding='utf-8'))['resume']
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
    return open(f, encoding='utf-8').read()


def setup_status():
    p, v = store.profile(), store.resume()
    steps = [
        ("profile", not ans.gaps(p), "Answer your application questions", f"{len(ans.gaps(p))} left" if ans.gaps(p) else ''),
        ("vault", len(v.get('experience', [])) + len(v.get('projects', [])) >= 2, "Add experience and projects", ''),
        ("skills", bool(v.get('skills')), "Add your skills", ''),
        ("search", bool(p['search'].get('roles')), "Choose the roles you want", ''),
        ("scan", bool(store.rows('select 1 from jobs limit 1')), "Run your first job scan", ''),
    ]
    try:
        render.chrome()
        chrome = True
    except Exception:
        chrome = False
    steps.append(("chrome", chrome, "Install Chrome (for PDFs)", ''))
    return [{"id": a, "done": b, "label": c, "detail": d} for a, b, c, d in steps]


# ------------------------------------------------------------------ import, queue, autopilot

def import_resume(name='', data=None, text=None):
    from . import importer
    return importer.import_resume(name, data, text)


def queue(n=50, for_agent=False):
    """Everything worth applying to, in order: dream companies first, then by fit. Respects caps and the skip list."""
    p = store.profile()
    dream = p['search'].get('companies_priority', [])
    cap = p['apply'].get('per_company_cap', 3)
    rows = list_jobs(status='new', limit=20000)
    applied = {}
    for r in store.rows(f"select company, count(distinct job_id) n from applications where {store.COUNTED} group by company"):
        k = match.company_key(r['company'])
        applied[k] = applied.get(k, 0) + r['n']
    claimed = {r['job_id'] for r in store.rows('select job_id from claims')}
    out, per, done, ids = [], {}, done_roles(), done_url_ids()
    skip = p['search'].get('companies_skip', [])
    for j in rows:
        c = match.company_key(j['company'])
        if (already_done(j, done, ids) or j['id'] in claimed or applied.get(c, 0) + per.get(c, 0) >= cap
                or any(match.same_company(s, j['company']) for s in skip)):
            continue
        per[c] = per.get(c, 0) + 1
        j['dream'] = any(match.same_company(d, j['company']) for d in dream)
        out.append(j)
    out.sort(key=lambda j: (not j['dream'], j.get('source') != 'manual', -j['fit']))   # dream companies, then jobs you added, then fit
    left = max(0, p['apply'].get('daily_limit', 40) - store.applied_count_today())
    return {"total": len(out), "dream": sum(j['dream'] for j in out), "remaining_today": left,
            "jobs": out[:min(int(n), left)] if for_agent else out[:int(n)]}


_run = {"proc": None, "agent": None, "log": None, "stopped": False}


def run_prompt(n):
    return (f"Use the applytwin-apply skill. Apply to the next {n} jobs in my ApplyTwin queue (applytwin_queue / applytwin_next_jobs), "
            "dream companies first. For every job: claim it, tailor a resume (applytwin_tailor_prompt then applytwin_tailor_apply), "
            "open the application in the browser, follow applytwin_playbook for its ATS, answer from applytwin_answer_questions, "
            "submit only if my profile allows auto_submit, and log the result with applytwin_log_application. "
            "If a site asks for an emailed verification code: if my profile.apply.email_codes is 'agent', read the newest code from that company "
            "in my email (your email/Gmail tool, or my webmail tab in the browser) and enter it; otherwise call applytwin_notify and move on. "
            "For sign-ins, passwords, CAPTCHAs or anything only I can do: applytwin_notify, log Needs User, leave the tab open, and go straight to the next job. "
            "Never wait for me and never retry a blocked page more than twice: anything that is not moving in a few minutes gets logged Needs User and skipped. "
            "At the end, check applytwin_pending_jobs and finish any I have unblocked. Judge class-year and start-date requirements by my standing DURING the internship (applytwin_get_profile class_standing: a sophomore now is a rising junior next summer); skip only when I am clearly ineligible, and when unsure, apply. Never invent facts. Give a 1-line update every 5 jobs.")


def doctor():
    return agents.doctor()


def agent_status():
    return {n: agents.status(n) for n in agents.NAMES}


def finish_prompt(job_ids, submit=False):
    rows = [store.rows('select id, company, title, apply_url, url from jobs where id=?', (j,)) for j in job_ids]
    lines = '; '.join(f"{r[0]['company']} {r[0]['title']} (job {r[0]['id']}, {r[0]['apply_url'] or r[0]['url']})" for r in rows if r)
    act = ("SUBMIT each one: I reviewed them and asked you to submit these specific applications, so submit once, confirm the "
           "success page, and log it Applied." if submit else
           "Stop on the review screen with everything filled and leave that tab open for me; log Needs User with 'ready to submit'.")
    return ("Use the applytwin-apply skill. Finish these specific applications only, in your browser: " + lines + ". "
            "For each: the job is already claimed; reuse its tailored resume (applytwin_get_job shows it; tailor with "
            "applytwin_tailor_prompt/applytwin_tailor_apply only if there is none), open the application, follow applytwin_playbook "
            "for its ATS, fill every field from applytwin_answer_questions, upload the resume. If a sign-in is still required, I signed "
            "in in your browser profile; if it still asks, applytwin_notify me and move on. " + act + " Never invent facts.")


def finish_jobs(job_ids, submit=False, agent=None):
    """Re-open and finish specific applications in the twin's browser (refill a form that was closed, continue after a
    sign-in, or submit one you approved)."""
    agent = agent or _agent()
    job_ids = [j for j in job_ids if ((_latest(j) or {}).get('status') != 'Applied')]   # never redo a submitted one
    if not job_ids:
        return {"done": True, "note": "Already submitted."}
    if _run['proc'] and _run['proc'].poll() is None:   # mid-run: do it right after, instead of silently doing nothing
        later = store.load('followups.json', [])
        f = {"job_ids": list(job_ids), "submit": bool(submit), "agent": agent}
        if not any(x.get('job_ids') == f['job_ids'] and x.get('submit') == f['submit'] and not x.get('prompt') for x in later):
            later.append(f)
            store.save('followups.json', later)
        return {"queued": True, "running": True}
    return start_run(agent, len(job_ids), prompt=finish_prompt(job_ids, submit))


def _agent():
    """The agent to use: the one chosen in Settings if it's signed in, otherwise whichever one is."""
    ready = agents.preferred(store.profile())
    return ready[0] if ready else (store.profile()['apply'].get('agent') or 'claude')


def _next_followup():
    """Start the next queued finish request (from a button pressed while a run was going). Returns True if one started."""
    later = store.load('followups.json', [])
    while later:
        f = later.pop(0)
        store.save('followups.json', later)
        try:
            start_run(f['agent'], len(f['job_ids']), prompt=f.get('prompt') or finish_prompt(f['job_ids'], f['submit']))
            return True
        except Exception as e:
            notify("Couldn't finish an application", str(e), kind='error')
    return False


# ------------------------------------------------------------------ talking to your twin about one application

def thread(job_id):
    return store.rows('select role, text, at from thread where job_id=? order by id', (job_id,))


def _say(job_id, role, text):
    if job_id and text:
        store.execute('insert into thread(job_id, role, text, at) values(?,?,?,?)', (job_id, role, text.strip()[:2000], time.time()))


def reply(job_id, text):
    """The agent answers the user about one application (shown under that item in Needs you)."""
    _say(job_id, 'twin', text)
    if store.profile()['apply'].get('notify_desktop', True) and time.time() - _app_seen[0] > 60:
        from .install import notify as desk
        j = (store.rows('select company from jobs where id=?', (job_id,)) or [{'company': ''}])[0]
        desk(f"ApplyTwin: {j['company']}".strip(), text[:180])
    return {"ok": True}


def _latest(job_id):
    return (store.rows('select status, notes, at from applications where job_id=? order by at desc limit 1', (job_id,)) or [None])[0]


def _status_answer(job_id):
    a = _latest(job_id)
    if not a:
        return "I haven't started this one yet."
    when = time.strftime('%b %-d at %-I:%M %p', time.localtime(a['at'])) if os.name != 'nt' else time.strftime('%b %d at %I:%M %p', time.localtime(a['at']))
    if a['status'] == 'Applied':
        return f"Yes. It was submitted {when}."
    if a['status'] == 'Skipped':
        return "No, it's skipped. Say \"apply to it\" if you want me to go back to it."
    why = (a['notes'] or '').strip()
    return ("No, it isn't submitted yet. " + (why + ' ' if why else '') +
            "If you submitted it yourself, say \"I submitted it\". To have me finish it, say \"submit it\".")


def message_prompt(job_id, text):
    j = (store.rows('select id, company, title, apply_url, url from jobs where id=?', (job_id,)) or [{}])[0]
    a = _latest(job_id) or {}
    convo = '\n'.join(f"{'User' if r['role'] == 'you' else 'You'}: {r['text']}" for r in thread(job_id)[-8:])
    return ("Use the applytwin-apply skill. This is about ONE application only: "
            f"{j.get('company')} {j.get('title')} (job {job_id}, {j.get('apply_url') or j.get('url')}). "
            f"Its latest status: {a.get('status', 'not started')}: {a.get('notes') or ''}\n"
            f"Your conversation with the user about it so far:\n{convo}\n\n"
            "The job is already claimed for you; do not claim it again. Do what the user's last message asks, for this application only. That can mean reopening it in your browser, "
            "changing or adding an answer, finishing it, or submitting it. Submit only if they clearly asked you to or "
            "profile.apply.auto_submit is true. Log the outcome with applytwin_log_application. Then answer them with "
            "applytwin_reply(job_id, text): one or two plain sentences on what you did and what, if anything, they still need "
            "to do. If you could not do it, say why in that reply. Never invent facts.")


def intent(text):
    """What a short message to the twin means, when it's one of the things the app can do instantly. Only whole, short
    phrasings count ("I submitted it"), so "Done, I signed in. Finish it" goes to the agent instead of being misread."""
    t = (text or '').strip().lower()
    asking = '?' in t
    t = re.sub(r'[.!\s]+$', '', t)
    if re.fullmatch(r"(so |wait |hey )?(did (you|it|this) (submit|apply|send|go through|finish)( it| this| yet)?|is (it|this) (submitted|done|in|sent)( yet)?|what'?s the status|status|where (are|is) (we|it|this)( at)?)\??", t):
        return 'status'
    if asking:
        return None
    if re.fullmatch(r"(ok |okay |yeah |yes )?(i('ve| have)? (already |just )?(submitted|applied|sent)( it| this| myself| it myself)?( already)?|(it'?s|its) (submitted|in|sent)|submitted( it)?|i applied myself)", t):
        return 'applied'
    if re.fullmatch(r"(please )?(skip( it| this( one)?)?|don'?t apply( to (it|this))?|not interested|forget (it|this( one)?))", t):
        return 'skip'
    if re.fullmatch(r"(please )?(submit|send|go ahead and submit|go ahead)( it| this)?( now)?", t):
        return 'submit'
    return None


def message(job_id, text):
    """You wrote to your twin about one application. Simple things are handled right away; anything else goes to the
    agent for that application, and its answer shows up in the same conversation."""
    text = (text or '').strip()
    if not text:
        return {"thread": thread(job_id)}
    _say(job_id, 'you', text)
    kind = intent(text)
    if kind == 'status':
        _say(job_id, 'twin', _status_answer(job_id))
    elif kind == 'applied':
        log_application(job_id, 'Applied', 'You submitted it yourself')
        _say(job_id, 'twin', 'Marked as applied.')
    elif kind == 'skip':
        skip_job(job_id)
        _say(job_id, 'twin', "Skipped. I won't apply to this one.")
    else:
        submit = kind == 'submit'
        r = finish_jobs([job_id], submit=True) if submit else _run_or_queue(job_id, message_prompt(job_id, text))
        _say(job_id, 'twin', ("Already submitted, nothing to do." if r.get('done') else
                              "Queued. I'm in the middle of a run and will do this right after, then reply here." if r.get('queued')
                              else ("Submitting it now. I'll reply here when it's done." if submit else "On it. I'll reply here when it's done.")))
    return {"thread": thread(job_id)}


def _run_or_queue(job_id, prompt):
    agent = _agent()
    if _run['proc'] and _run['proc'].poll() is None:
        later = store.load('followups.json', [])
        later.append({"job_ids": [job_id], "submit": False, "agent": agent, "prompt": prompt})
        store.save('followups.json', later)
        return {"queued": True}
    return start_run(agent, 1, prompt=prompt)


def skip_job(job_id, why='Skipped by you'):
    """Never apply to this one (the Skip button on anything that needs you)."""
    store.execute("update jobs set status='skipped' where id=?", (job_id,))
    store.execute('update inbox set resolved=? where job_id=? and resolved is null', (time.time(), job_id))
    if any(r['job_id'] == job_id for r in pending_jobs()):   # it was waiting on you: close that out too
        store.log_application(job_id, 'Skipped', why)
    return {"ok": True}


def open_in_twin_browser(url):
    """Open a page in the twin's own browser profile, so a sign-in you do there is the one the twin uses."""
    import subprocess
    from . import install
    if not re.match(r'https?://[^\s]+$', url or '', re.I):   # a web page, never a Chrome command-line flag
        raise RuntimeError('That is not a web link.')
    # mid-run this is fine too: Chrome passes the page to the twin's open window as a new tab in the same profile
    os.makedirs(install.BROWSER_PROFILE, exist_ok=True)
    # same keychain flags Playwright uses for this profile: with the real keychain Chrome can't read the logins the twin
    # saved (and macOS asks for keychain access)
    subprocess.Popen([render.chrome(), f'--user-data-dir={install.BROWSER_PROFILE}', '--no-first-run', '--no-default-browser-check',
                      '--use-mock-keychain', '--password-store=basic', url],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {"opened": True}


_RUN_LOCK = threading.Lock()


def start_run(agent='claude', n=25, model=None, prompt=None, restarts=0):
    with _RUN_LOCK:   # two clicks at once must never start two agents on one browser
        return _start_run(agent, n, model, prompt, restarts)


def _close_twin_windows():
    """A twin's-browser window you left open (from 'Open in twin's browser') holds its profile, and the agent's browser
    then can't start. Close it; your sign-ins are already saved in the profile."""
    import subprocess
    from . import install
    prof = install.BROWSER_PROFILE
    try:
        if os.name == 'nt':
            ps = ("Get-CimInstance Win32_Process -Filter \"Name='chrome.exe' or Name='msedge.exe'\" | "
                  f"Where-Object {{ $_.CommandLine -like '*{prof}*' }} | ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force }}")
            subprocess.run(['powershell', '-NoProfile', '-Command', ps], capture_output=True, timeout=20)
        else:
            subprocess.run(['pkill', '-f', f'--user-data-dir={prof}( |$)'], capture_output=True, timeout=10)
    except Exception:
        pass


def _start_run(agent, n, model, prompt, restarts):
    import shutil
    import subprocess
    if _run['proc'] and _run['proc'].poll() is None:
        return {**run_status(), "busy": True}
    if prompt is None and store.applied_count_today() >= store.profile()['apply'].get('daily_limit', 40):
        raise RuntimeError(f"You've reached today's limit of {store.profile()['apply'].get('daily_limit', 40)} applications. "
                           "Raise it in Settings, or your twin continues tomorrow.")
    exe = shutil.which(agent)
    if not exe:
        raise RuntimeError(f"{'Claude Code' if agent == 'claude' else 'Codex'} is not installed or not on PATH")
    st = agents.status(agent, fresh=True)
    if not st['signed_in']:
        raise RuntimeError(f"{st['label']} is signed out. Run `{agents.LOGIN[agent]}` in a terminal, then press Launch again.")
    from . import cloud
    if not (cloud.status()['signed_in'] or os.environ.get('APPLYTWIN_SKIP_SIGNIN') or os.environ.get('CI')):
        raise RuntimeError('Sign in first: open ApplyTwin (type applytwin in a terminal) and continue with Google.')
    prompt = prompt or run_prompt(n)
    if agent == 'claude':
        # runs on the user's own Claude subscription; only ApplyTwin's tools and a browser are pre-approved, so it never stalls on a prompt
        tools = ('mcp__plugin_applytwin_applytwin,mcp__applytwin,mcp__playwright,mcp__claude-in-chrome,'
                 'Read,Write,Bash(ls:*),Bash(open:*)')
        cmd = [exe, '-p', '--allowedTools', tools, '--permission-mode', 'acceptEdits', '--output-format', 'text']
    else:
        cmd = [exe, 'exec', '--skip-git-repo-check', '-s', 'workspace-write', '-c', 'approval_policy=never', *(['-m', model] if model else agents.codex_model_args()), '-']
    logf = store.path('autopilot.log')
    keep = os.path.exists(logf) and os.path.getsize(logf) < 2_000_000 and restarts   # a continuation adds to its run's log
    f = open(logf, 'a' if keep else 'w', encoding='utf-8')
    f.write(f"$ {' '.join(os.path.basename(c) if i == 0 else c for i, c in enumerate(cmd))} … apply to {n} jobs\n")
    f.flush()
    _close_twin_windows()
    # run from the data folder, not the repo, so the agent loads the installed plugin rather than the repo's dev .mcp.json
    # the instructions go in on stdin: on Windows, claude/codex are .cmd wrappers and cmd.exe would mangle quotes in a long argument
    proc = subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.PIPE, cwd=store.HOME, text=True, encoding='utf-8',
                            errors='replace', **({} if os.name == 'nt' else {'start_new_session': True}))   # its own group: Stop ends its browser too
    proc.stdin.write(prompt)
    proc.stdin.close()
    _run.update(proc=proc, agent=agent, log=logf, started=time.time(), stopped=False)
    import threading
    threading.Thread(target=_watch_run, args=(proc, agent, logf, n, model, prompt, restarts), daemon=True).start()
    return run_status()


AUTH_ERRORS = ('failed to authenticate', 'oauth session expired', 'not logged in', 'please run /login', 'invalid api key',
               'unauthorized', 'status 401')


def _kill(proc):
    """Stop the agent and everything it started. On Windows, claude/codex are .cmd wrappers: killing only the wrapper
    would leave the real agent running in the background."""
    if os.name == 'nt':
        import subprocess
        subprocess.run(['taskkill', '/T', '/F', '/PID', str(proc.pid)], capture_output=True)
    else:
        import signal
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)   # the agent, its browser tools and their Chrome
        except (ProcessLookupError, PermissionError, OSError):
            proc.terminate()


def _last_activity(since):
    """When the agent last made progress: claimed a job, logged one, or asked the user for something."""
    t = [since, (store.load('activity.json', {}) or {}).get('at', 0)]
    for q in ('select max(at) m from claims', 'select max(at) m from applications', 'select max(at) m from inbox'):
        t.append((store.rows(q) or [{}])[0].get('m') or 0)
    return max(t)


def _skip_stuck(since, minutes):
    """Log the application the agent was stuck on as Needs User, so the next run moves past it."""
    logged = {r['job_id'] for r in store.rows('select job_id from applications where at >= ?', (since,))}
    stuck = [r['job_id'] for r in store.rows('select job_id from claims where at >= ? order by at desc', (since,)) if r['job_id'] not in logged]
    a = store.load('activity.json', {}) or {}
    if a.get('job_id') and a.get('at', 0) >= since and a['job_id'] not in logged:   # the job it was actually on
        stuck = [a['job_id']] + [j for j in stuck if j != a['job_id']]
    for j in stuck[:1]:
        log_application(j, 'Needs User', f'Skipped after {minutes:g} minutes with no progress. Open it to finish by hand, or press Refill.')
    return stuck[:1]


def _watch_run(proc, agent, logf, n, model, prompt=None, restarts=0):
    # a run that makes no progress for apply.stuck_minutes is stuck on one application (waiting on a sign-in, a hung page):
    # skip that application and carry on with the rest instead of holding up the whole queue
    minutes = float(store.profile()['apply'].get('stuck_minutes') or 20)
    started, stuck = time.time(), False
    while proc.poll() is None:
        time.sleep(min(15, minutes * 15))
        if proc.poll() is None and time.time() - _last_activity(started) > minutes * 60:
            stuck = True
            _kill(proc)
            try:
                proc.wait(timeout=20)
            except Exception:
                proc.kill()
    if stuck:
        skipped = _skip_stuck(started, minutes)
        release_claims(since=started)
        done = len(store.rows('select 1 from applications where at >= ?', (started,)))
        left = n - done
        if skipped:
            j = (store.rows('select company, title from jobs where id=?', (skipped[0],)) or [{'company': '', 'title': ''}])[0]
            notify(f"{j['company']}: stuck, skipped for now", f"No progress for {minutes:g} minutes on {j['title']}, so your twin "
                   "moved on" + (f' and kept going with {left} more.' if left > 0 and prompt is None and restarts < 5 else '.')
                   + ' Press Refill to try it again.', job_id=skipped[0], kind='needs_you')
        else:
            notify('Your twin stopped', f'It made no progress for {minutes:g} minutes, so it was stopped. Nothing was lost.', kind='info')
        if left > 0 and prompt is None and restarts < 5:
            try:
                start_run(agent, left, model=model, restarts=restarts + 1)
            except Exception:
                pass
        else:
            _next_followup()
        return
    # when the agent exits early because its own sign-in lapsed, tell the user how to fix it instead of failing silently
    tail = open(logf, encoding='utf-8', errors='replace').read()[-3000:].lower() if os.path.exists(logf) else ''
    name = 'Claude Code' if agent == 'claude' else 'Codex'
    if agent == 'codex' and 'model_not_found' in tail and not model:
        # the configured model isn't on this plan or CLI: retry once on one the CLI lists
        agents.FALLBACK_MODEL[0] = True
        fb = (agents.codex_model_args() or [None, 'gpt-5.6-sol'])[1]
        return start_run(agent, n, model=fb, prompt=prompt)
    if any(e in tail for e in AUTH_ERRORS):
        fix = 'run `claude` in a terminal and type /login' if agent == 'claude' else 'run `codex login` in a terminal'
        notify(f'Sign in to {name}', f'Your {name} login expired: {fix}, then press Launch again.', kind='signin')
    elif proc.returncode and not _run.get('stopped'):
        notify(f'{name} stopped early', f'Exit code {proc.returncode}. The last lines are in the Autopilot log.', kind='error')
    release_claims(since=started)
    if not _run.get('stopped'):
        _next_followup()
    _run['stopped'] = False


def stop_run():
    if _run['proc'] and _run['proc'].poll() is None:
        _run['stopped'] = True   # you pressed Stop: don't start queued work either, and forget it
        store.save('followups.json', [])
        _kill(_run['proc'])
    return run_status()


def run_status():
    p = _run['proc']
    log = ''
    if _run['log'] and os.path.exists(_run['log']):
        log = open(_run['log'], encoding='utf-8', errors='replace').read()[-6000:]
    now = None
    a = store.load('activity.json', {}) or {}
    if p and p.poll() is None and a.get('at', 0) >= _run.get('started', 0):
        j = (store.rows('select company, title, apply_url, url from jobs where id=?', (a.get('job_id') or '',)) or [{}])[0]
        now = {"step": a.get('step'), "company": j.get('company', ''), "title": j.get('title', ''), "url": j.get('apply_url') or j.get('url') or '', "at": a['at']}
    return {"running": bool(p and p.poll() is None), "agent": _run['agent'], "log": log, "now": now,
            "exit": None if not p or p.poll() is None else p.returncode}


# ------------------------------------------------------------------ inbox: things only the user can do

_app_seen = [0.0]   # last time the app (open in a browser tab) checked its inbox


def notify(title, message='', url='', job_id='', kind='needs_you'):
    """Tell the user something needs them (a code, a sign-in, a CAPTCHA, a question). In-app inbox, plus a notification:
    the open app shows its own (click it to answer); if the app isn't open, a system notification says where to go."""
    store.execute('insert into inbox(kind,title,message,url,job_id,at) values(?,?,?,?,?,?)', (kind, title, message, url, job_id, time.time()))
    _say(job_id, 'twin', f"{title}. {message}".strip(' .') + '.' if message else title)
    if store.profile()['apply'].get('notify_desktop', True) and time.time() - _app_seen[0] > 60:
        from .install import notify as desk
        desk('ApplyTwin: ' + title, 'Open ApplyTwin (localhost:4747) to handle it. ' + (message or url))
    return {"ok": True}


def inbox_poll():
    _app_seen[0] = time.time()
    return {"items": inbox(), "pending": pending_jobs()}


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


HISTORY_COLS = {   # column names used by Simplify, Huntr, Teal, Notion, Google Sheets and hand-made trackers
    'company': ('company', 'company name', 'employer', 'organization', 'firm'),
    'title': ('title', 'job title', 'position', 'job position', 'role', 'job', 'job name'),
    'url': ('url', 'link', 'job url', 'job link', 'posting', 'posting url', 'application link', 'apply link'),
    'status': ('status', 'stage', 'list', 'application status', 'state', 'outcome'),
}


def import_history(csv_path=None, text=None):
    """Mark jobs you already applied to elsewhere so your twin never applies twice. Reads a CSV export from any tracker
    (Simplify, Huntr, Teal, Notion, a Google Sheet, or company,title,url,status columns); matches by the posting's job id
    in the URL, then by company + role."""
    import csv
    import io
    rows = list(csv.reader(io.StringIO(text) if text is not None else open(csv_path, newline='', encoding='utf-8-sig', errors='replace')))
    if not rows:
        return {"matched": 0, "known_applications": 0}
    head = [h.strip().lower() for h in rows[0]]
    idx = {k: next((i for i, h in enumerate(head) if h in names), None) for k, names in HISTORY_COLS.items()}
    if idx['company'] is None or idx['title'] is None:   # no header: company,title,url,status
        idx, body = {'company': 0, 'title': 1, 'url': 2, 'status': 3}, rows
    else:
        body = rows[1:]
    cell = lambda r, k: r[idx[k]].strip() if idx[k] is not None and idx[k] < len(r) else ''
    ids, names, found = {}, {}, []
    for r in body:
        company, title, url, status = cell(r, 'company'), cell(r, 'title'), cell(r, 'url'), cell(r, 'status')
        if not company or not title:
            continue
        if idx['status'] is not None and not status:
            continue   # a saved-but-not-applied row
        st = 'skipped' if re.search(r'saved|wishlist|bookmark|interested|to apply', status, re.I) and not re.search(r'appl', status, re.I) else \
             'applied' if not status or re.search(r'appl|interview|offer|reject|oa|assessment|screen', status, re.I) else 'skipped'
        if st == 'skipped' and re.search(r'saved|wishlist|bookmark|to apply', status, re.I):
            continue   # never applied: leave it in the queue
        for m in re.findall(r'(?:token=|/jobs/|/)([0-9a-f]{8}-[0-9a-f-]{27}|\d{5,})', url or ''):
            ids[m] = st
        names[role_key(company, title)] = st
        found.append({"company": company, "title": title, "url": url, "status": status or 'Applied', "source": 'tracker'})
    remember_applied(found)
    n = 0
    for j in store.rows('select id, company, title, url, apply_url from jobs where status="new"'):
        st = None
        for m in re.findall(r'(?:token=|/jobs/|/)([0-9a-f]{8}-[0-9a-f-]{27}|\d{5,})', (j['apply_url'] or '') + ' ' + (j['url'] or '')):
            st = st or ids.get(m)
        st = st or names.get(role_key(j['company'], j['title']))
        if st:
            store.execute('update jobs set status=? where id=?', (st, j['id']))
            n += 1
    return {"matched": n, "known_applications": len(names)}


def remember_applied(items):
    """Add roles applied to elsewhere to the permanent list (deduplicated by company + role)."""
    cur = applied_elsewhere()
    seen = {role_key(r['company'], r['title']) for r in cur}
    added = 0
    for it in items or []:
        c, t = (it.get('company') or '').strip(), (it.get('title') or '').strip()
        if not c or not t or role_key(c, t) in seen:
            continue
        seen.add(role_key(c, t))
        cur.append({"company": c, "title": t, "url": it.get('url') or '', "status": it.get('status') or 'Applied',
                    "date": it.get('date') or '', "source": it.get('source') or 'import', "at": time.time()})
        added += 1
    store.save('applied_elsewhere.json', cur)
    return added


def import_applied(items, source='email'):
    """What your agent found (e.g. confirmation emails): [{company, title, url?, date?, status?}]. Remembered forever and
    applied to the current queue, so none of these roles is applied to again."""
    added = remember_applied([{**i, "source": source} for i in items or []])
    done, ids = done_roles(), done_url_ids()
    n = 0
    for j in store.rows('select id, company, title, url, apply_url from jobs where status="new"'):
        if already_done(j, done, ids):
            store.execute("update jobs set status='applied' where id=?", (j['id'],))
            n += 1
    return {"added": added, "known": len(applied_elsewhere()), "matched_in_queue": n}


def email_history_prompt():
    return ("Use the applytwin-history skill. Find every job I already applied to by reading my email in your browser, and "
            "record them with applytwin_import_applied so ApplyTwin never applies to them again. Open my webmail (Gmail, "
            "Outlook, or my school email; if I'm not signed in, applytwin_notify me to sign in in your browser and wait for "
            "me, never type a password). Search the last 12 months for application confirmations: \"thank you for applying\", "
            "\"application received\", \"we received your application\", \"your application was sent\" (LinkedIn), and mail from "
            "greenhouse.io, lever.co, ashbyhq.com, myworkday.com, icims.com, smartrecruiters.com, jobvite.com, workable.com. "
            "Read company and role from each (rejections and interview invites count too, with that status; skip job alerts "
            "and newsletters), and record them in batches of about 25. Only record what an email shows; never guess. "
            "Finish with how many you found.")


def rescore():
    """Re-run fit scoring on every stored job (after profile or matcher changes), no network needed."""
    from . import ats
    prof = store.profile()
    vt = ats.resume_text(store.resume())
    terms = {t for t, pat in ats.PATTERNS.items() if pat.search(vt)}
    n = 0
    with store.db() as con:
        for j in [dict(r) for r in con.execute('select * from jobs')]:
            name = sources.clean_company(j['company'])   # older scans kept tracker decorations like '🔥 Tesla'
            if name and name != j['company']:
                j['company'] = name
                con.execute('update jobs set company=? where id=?', (name, j['id']))
            f, why = match.fit(j, prof, terms)
            con.execute('update jobs set fit=?, fit_why=? where id=?', (f, why, j['id']))
            n += 1
    return {"rescored": n}
