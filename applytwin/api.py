"""One API used by the web app, the MCP server (Claude Code / Codex) and the CLI."""
import functools
import json
import os
import re
import threading
import time

from . import answers as ans
from . import agents, ats, blockers, learn, match, render, sources, store, tailor

APP = store.APP
_scan = {"running": False, "stats": None, "started": None, "finished": None}


# ------------------------------------------------------------------ profile, vault, answers

def get_profile():
    return store.profile()


def update_profile(patch):
    # read-change-write under a lock shared with the agent's MCP process, so neither overwrites the other's change
    p = store.update('profile.json', lambda cur: store._merge(store.profile(), patch or {}), {})

    def sync(bank):   # keep profile-derived answers in sync unless the user overrode them
        bank = bank or store.answers()
        fresh = {r['key']: r for r in ans.default_bank(p)}
        for r in bank:
            if r.get('source') == 'profile' and r['key'] in fresh:
                r['answer'] = fresh[r['key']]['answer']
        return bank
    store.update('answers.json', sync, [])
    from . import cloud
    cloud.sync_soon()
    if 'search' in (patch or {}) and not os.environ.get('APPLYTWIN_NO_RESCORE'):   # new roles, places or skip list apply now
        rescore_soon()
    return p


_rescoring = {"running": False, "again": False}


def rescore_soon():
    """One rescore at a time: saving Settings five times in a row runs it once more at the end, not five at once (each
    holds a write over the whole jobs table, and a pile of them locked the database for everyone)."""
    if _rescoring['running']:
        _rescoring['again'] = True
        return

    def go():
        try:
            while True:
                _rescoring['again'] = False
                try:
                    rescore()
                except Exception:
                    pass
                if not _rescoring['again']:
                    break
        finally:
            _rescoring['running'] = False
    _rescoring['running'] = True
    threading.Thread(target=go, daemon=True).start()


def get_vault():
    return tailor.ensure_ids(store.resume())


def save_vault(vault, force=False):
    old = store.resume()
    if not force and store._has_content(old) and not store._has_content(vault or {}):
        # an editor showing an empty or stale copy must never wipe the real vault; a backup is kept for every save anyway
        raise RuntimeError("That save would have erased your whole resume, so nothing was changed. Reload the page to see your saved resume.")
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


def save_answers(bank):
    """The whole answer bank from the Answers page. Anything but a list of answers is refused: a stray {} or [] used to
    replace every answer you'd written with the defaults."""
    if not isinstance(bank, list) or not bank or not all(isinstance(r, dict) and r.get('question') for r in bank):
        raise RuntimeError('That save would have erased your answers, so nothing was changed. Reload the page and try again.')
    store.update('answers.json', lambda cur: bank, [])
    return {"ok": True, "count": len(bank)}


def save_answer(question, answer, key=None):
    bank = store.update('answers.json', lambda cur: ans.upsert(cur or store.answers(), question, answer, key), [])
    return {"ok": True, "count": len(bank)}


def answer_questions(questions, job_id=None, notify_user=True):
    """questions: list of strings or {question, options}. Returns an answer (or 'ask') for each. When a form asks
    something you haven't told ApplyTwin, you get a 'Needs you' item saying exactly what to add (once per question)."""
    bank = store.answers()
    ctx = answer_context(job_id)
    out = []
    for q in questions or []:
        if isinstance(q, dict):
            out.append(ans.match(q.get('question') or q.get('label', ''), bank, q.get('options'), ctx))
        else:
            out.append(ans.match(q, bank, None, ctx))
    profile_keys = {r['key'] for r in ans.default_bank(store.profile())}
    for r in out:
        if notify_user and r.get('answer') is None and (r.get('action') or '').startswith('ask'):   # open-ended ones the agent writes; never ask
            known = r.get('key') in profile_keys
            title = f"Add your answer: {r['question'][:300]}"
            if not store.rows('select 1 from inbox where title=? and resolved is null', (title,)):
                notify(title, ("Forms keep asking this and it's blank in your profile. Add it in Settings so your twin never "
                               "has to guess." if known else "A form asked this and ApplyTwin doesn't know your answer yet. "
                               "Answer it on the Answers page; your twin reuses it everywhere."),
                       job_id=job_id or '', kind='question')
    return out


def answer_context(job_id):
    """What ApplyTwin itself knows about the user and this job's company, for company-specific questions: whether the
    vault lists a job there ("Have you worked for X?") and whether ApplyTwin's records show an application there."""
    j = (store.rows('select company from jobs where id=?', (job_id,)) or [None])[0] if job_id else None
    if not j or not j.get('company'):
        return {}
    co = j['company']
    vault = store.resume()
    orgs = [e.get('org') or e.get('company') or '' for e in (vault.get('experience') or [])]
    applied = any(match.same_company(r['company'] or '', co) for r in store.rows(
        "select company from applications where job_id!=? and status in ('Applied','Interview','OA','Offer','Rejected')", (job_id,)))
    applied = applied or any(match.same_company(r.get('company') or '', co) for r in applied_elsewhere())
    ctx = {"company": co, "applied_before": applied}
    if orgs:   # without a vault there is nothing to check against: the bank's answer stands
        ctx['worked_here'] = any(o and match.same_company(o, co) for o in orgs)
    return ctx


def profile_questions():
    p = store.profile()
    return {"questions": ans.questions(), "missing": ans.gaps(p)}


# ------------------------------------------------------------------ jobs

def scan(sources_list=None, background=False):
    if _scan['running']:
        return {"running": True, "stats": _scan['stats']}

    # marked running BEFORE the thread starts: the page asks "still running?" right after pressing Scan, and used to hear
    # "no" (the thread hadn't begun) and report "0 new jobs" for every scan while the real one ran on unseen
    _scan.update(running=True, started=time.time(), stats={})

    def run():
        try:
            _scan['stats'] = sources.scan(sources_list, on_progress=lambda s: _scan.update(stats=s))
            store.save('last_scan.json', {"at": time.time(), "stats": _scan['stats']})
            # the scan scored with the profile as it was when it started; setup or Settings changed it since (picking a term
            # mid-scan left last cycle's roles in the queue), so score again before anyone reads the queue
            pf = store.path('profile.json')
            if os.path.exists(pf) and os.path.getmtime(pf) >= _scan['started']:
                rescore(force=True)
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
    for j in store.rows(sql, args):  # the same role posted in many cities shows once (different roles never merge)
        k = role_key(j['company'], j['title'])
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
        d = sources.fetch_description(j)
        if d and len(d) > len(j.get('description') or ''):   # keep it: it was being downloaded again on every view
            store.execute('update jobs set description=? where id=?', (d, job_id))
        j['description'] = d or j.get('description') or ''
    return j


def job_for_agent(job_id):
    """get_job for the agent: the posting plus what it must check before filling anything. knockouts are requirements the
    full description states that rule the user out (the scan often scored the job before the description was fetched);
    already_applied lists earlier applications to the same role or the same posting id at this company."""
    j = get_job(job_id)
    if not j:
        return {"error": f"No job {job_id}. Use an id from applytwin_next_jobs, or applytwin_add_job(url)."}
    j['knockouts'] = match.knockouts(j, store.profile())
    if j['knockouts']:
        j['knockouts_note'] = ("The posting rules the user out: applytwin_log_application(job_id, 'Skipped', '<the knockout above>') "
                               "and move on. If the posting clearly says otherwise elsewhere, apply.")
    key, ids = role_key(j['company'], j['title']), set(URL_ID.findall(f"{j.get('apply_url') or ''} {j.get('url') or ''}"))
    seen = []
    for a in store.rows("select job_id, company, title, url, status, at from applications where job_id!=? order by at desc", (job_id,)):
        if a['status'] in ('Skipped', 'Failed') or not match.same_company(a['company'] or '', j['company']):
            continue
        if role_key(a['company'], a['title']) == key or ids & set(URL_ID.findall(a.get('url') or '')):
            seen.append({"job_id": a['job_id'], "title": a['title'], "status": a['status'],
                         "on": time.strftime('%Y-%m-%d', time.localtime(a['at']))})
    j['already_applied'] = seen[:5]
    last = store.latest_status(job_id)
    if last and last['status'] in store.OUTCOMES:
        j['already_applied'].insert(0, {"job_id": job_id, "title": j['title'], "status": last['status'],
                                        "on": time.strftime('%Y-%m-%d', time.localtime(last['at']))})
    if last and last['status'] == 'Needs User':   # coming back to one: pick up where it stopped instead of starting over
        j['resume_from'] = {"blocker": blockers.classify(last.get('notes')), "notes": (last.get('notes') or '')[:400],
                            "how": "Continue this application where it stopped: reuse the open tab if it is still there, keep "
                                   "what is filled, fix only what is missing. If the site now shows it as submitted, log Applied "
                                   "(never submit twice)."}
    h = blockers.host(j.get('apply_url') or j.get('url'))
    if h and h in blocked_hosts() and not j.get('resume_from'):
        j['site_waiting'] = (f"Another application on {h} is waiting for the user to sign in. If this one asks for a sign-in too, "
                             "don't stop to report it separately: log Needs User 'sign-in required at <url> (same site)', and move on.")
    if blockers.homepage_link(j.get('apply_url') or j.get('url')):
        j['link_warning'] = ("This link only opens the company homepage. Look for this exact role on the company's careers page "
                             "once; if it isn't there, log Skipped 'Broken link: listing points to the company homepage'.")
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
    bank, ctx = store.answers(), answer_context(job_id)
    for q in qs:
        q['suggested'] = ans.match(q['question'], bank, q['options'] or None, ctx)
    return qs


_limits = {}   # company key -> (when read, limit or None)


def company_cap(company, cap):
    """Your per-company cap, or the company's own limit when it takes fewer applications per candidate (Jane Street, Akuna;
    or a posting that says 'apply to only one role'). The queue is fit-ordered, so the best-fitting role gets the slot."""
    k = match.company_key(company or '')
    hit = _limits.get(k)
    if not hit or time.time() - hit[0] > 600:
        lim, n = match.application_limit(company), _posting_limits().get(k)
        hit = _limits[k] = (time.time(), min(lim, n) if lim and n else (lim or n))
    return min(cap, hit[1]) if hit[1] else cap


_posted = [0.0, {}]   # (when read, company key -> the lowest limit any of its postings states)


def _posting_limits():
    """Limits written in postings, by company KEY (every spelling: "Jane Street", "Jane Street Capital, LLC"), read in one
    pass every 10 minutes instead of one query per company."""
    if time.time() - _posted[0] > 600:
        out = {}
        for r in store.rows("select company, description from jobs where description like '%only one%' or description like "
                            "'%no more than%' or description like '%per candidate%' or description like '%maximum of%' or description "
                            "like '%single role%' or description like '%one role%' or description like '%per applicant%'"):
            n, k = match.application_limit('', r['description']), match.company_key(r['company'] or '')
            if n:
                out[k] = min(out.get(k, n), n)
        _posted[:] = [time.time(), out]
    return _posted[1]


def next_jobs(n=10):
    """The apply queue: best-fit unapplied jobs, respecting the daily limit and per-company caps."""
    p = store.profile()
    release_claims(older_than=store.CLAIM_TTL)   # a session that died hours ago no longer hides its jobs (they go to Needs you)
    left = max(0, p['apply'].get('daily_limit', 40) - store.applied_count_today() - store.live_claims())
    cap = p['apply'].get('per_company_cap', 3)
    out, per, done, ids = [], {}, done_roles(), done_url_ids()
    if left <= 0:
        return {"remaining_today": 0, "jobs": [], "note": "Today's limit is reached (counting applications in progress). Stop here."}
    for r in store.rows('select j.company from claims c join jobs j on j.id=c.job_id where c.at>?', (time.time() - store.CLAIM_TTL,)):
        per[match.company_key(r['company'] or '')] = per.get(match.company_key(r['company'] or ''), 0) + 1   # in progress counts too
    down = browser_down()
    if down:
        return {"remaining_today": left, "jobs": [], "stop": True, "note": down}
    skip, applied = p['search'].get('companies_skip', []), store.company_counts()
    waiting, later, deferred = blocked_hosts(), retry_later(), {}
    for j in list_jobs(status='new', limit=400):
        if already_done(j, done, ids) or any(match.same_company(s, j['company']) for s in skip):
            continue
        if not_applyable(j, p) or j['id'] in later:   # a homepage link, a clear knockout, or a page error retried later
            continue
        h = blockers.host(j.get('apply_url') or j.get('url'))
        if h in waiting:   # this site is waiting for the user's sign-in: its other jobs would stop at the same wall
            deferred[h] = deferred.get(h, 0) + 1
            continue
        c = match.company_key(j['company'])
        if applied.get(c, 0) + per.get(c, 0) >= company_cap(j['company'], cap):
            continue
        if store.rows('select 1 from claims where job_id=?', (j['id'],)):
            continue
        per[c] = per.get(c, 0) + 1
        out.append(j)
        if len(out) >= min(n, left):
            break
    out = pace(out)
    res = {"remaining_today": left, "jobs": out}
    if deferred:
        res['waiting_on_you'] = [{"site": h, "jobs": k, "blocker": waiting[h]} for h, k in deferred.items()]
        res['note'] = ("Jobs on sites waiting for the user's sign-in or account are held back (waiting_on_you); they continue "
                       "after the user signs in. Don't open them now.")
    return res


# ------------------------------------------------------------------ what real runs taught: skip early, wait smart

def not_applyable(job, prof=None):
    """Why the agent should never be handed this job, or '': its link is only a company homepage (no posting to apply to),
    or its title/location rule the user out. Cheap: no description fetch. A job the user added by hand always goes through."""
    if job.get('source') == 'manual':
        return ''
    if blockers.homepage_link(job.get('apply_url') or job.get('url')):
        return 'Broken link: listing points to the company homepage, not the job posting.'
    k = match.quick_knockouts(job, prof or store.profile())
    return k[0] if k else ''


def blocked_hosts():
    """Sites (host -> blocker) where an application is waiting for the user's sign-in or account right now. Cleared when
    the user resolves its Needs-you item, or once any application on that site goes through."""
    out = {}
    resolved = {r['job_id'] for r in store.rows('select job_id from inbox where resolved is not null and job_id is not null')}
    open_items = {r['job_id'] for r in store.rows('select job_id from inbox where resolved is null and job_id is not null')}
    since = time.time() - 24 * 3600
    pend = pending_jobs()
    for r in pend:
        if r['at'] < since or (r['job_id'] in resolved and r['job_id'] not in open_items):
            continue
        cat = blockers.classify(r.get('notes'))
        if cat in ('signin', 'account'):
            h = blockers.host(r.get('url'))
            if h:
                out.setdefault(h, cat)
    if out:   # a later success on the site means the user is signed in there now
        for r in store.rows("select url, at from applications where status='Applied' and at>?", (since,)):
            h = blockers.host(r['url'])
            if h in out and any(blockers.host(p['url']) == h and p['at'] < r['at'] for p in pend):
                out.pop(h, None)
    return out


RETRY_AFTER = 30 * 60   # a page that errored gets one more try, at least this much later


def retry_later():
    """Job ids that hit a page error or timeout and wait for their one retry."""
    now = time.time()
    return {k for k, v in (store.load('retries.json', {}) or {}).items() if now - v.get('at', 0) < RETRY_AFTER and v.get('n', 0) <= 1}


def browser_down():
    """The agent reported its browser tools unusable this run (twice): a note saying so, or ''."""
    h = store.load('run_health.json', {}) or {}
    if h.get('browser_failures', 0) >= 2 and time.time() - h.get('at', 0) < 3600:
        return ("The browser tools failed twice in this run, so no more jobs are handed out (each would fail the same way). "
                "Stop now: call applytwin_notify once with the browser error, then end the run. Jobs stay in the queue.")
    return ''


def pace(jobs):
    """Order a batch so Greenhouse submits are spaced out: Greenhouse starts asking for emailed security codes after a few
    rapid submits (the most common 'Needs you' in real runs). Two Greenhouse jobs never sit back to back when there is
    anything else to do in between, and the first is pushed back if Greenhouse was just used."""
    gh = lambda j: (j.get('ats') or '').lower() == 'greenhouse'
    recent = store.rows("select url from applications where at>? order by at desc limit 3", (time.time() - 300,))
    last_gh = bool(recent) and 'greenhouse' in (recent[0].get('url') or '')
    rest, out = list(jobs), []
    while rest:
        pick = next((j for j in rest if not (last_gh and gh(j))), rest[0])
        rest.remove(pick)
        out.append(pick)
        last_gh = gh(pick)
    return out


STOP = {'the', 'a', 'an', 'and', 'of', 'for', 'to', 'in', 'at', 'hq', 'remote', 'hybrid', 'onsite', 'us', 'usa'}


@functools.lru_cache(maxsize=65536)   # pure, and asked about the same few thousand roles on every queue read
def role_key(company, title):
    """Same role at the same company, however a board spells it: 'Software Engineer Intern (First Play) - Summer 2027
    (Mountain View, CA)' and 'Software Engineer Intern, First Play' are one job."""
    c = match.company_key(company)
    t = title or ''
    # a trailing place is not part of the role: "Software Engineer Intern - New York" == "... - Seattle"
    parts = re.split(r'\s+[-–—|]\s+|\s*,\s*(?=[A-Z][a-z]+(?:\s[A-Z][a-z]+)?,?\s*(?:[A-Z]{2})?$)', t)
    while len(parts) > 1 and (match.place(parts[-1]) != 'unknown' or match.US.search(parts[-1]) and len(parts[-1]) < 30):
        parts.pop()
    t = ' '.join(parts).lower()
    t = re.sub(r'\([^)]*,[^)]*\)', ' ', t)                                  # (Mountain View, CA)
    t = re.sub(r'\binternships?\b', 'intern', t)
    t = re.sub(r'\bengineering\b', 'engineer', t)
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
    """Posting ids (Greenhouse/Lever/Ashby ids in URLs) already applied to: from your history (any company), and from
    ApplyTwin's own applications as (company, id), so the same posting found under another listing is never applied twice."""
    out = {m for r in applied_elsewhere() for m in URL_ID.findall(r.get('url') or '')}
    for r in store.rows("select company, url from applications where status not in ('Skipped','Failed')"):
        out |= {(match.company_key(r['company'] or ''), m) for m in URL_ID.findall(r.get('url') or '')}
    return out


def already_done(job, done=None, ids=None):
    if role_key(job['company'], job['title']) in (done if done is not None else done_roles()):
        return True
    ids = ids if ids is not None else done_url_ids()
    c = match.company_key(job.get('company') or '')
    return any(m in ids or (c, m) in ids for m in URL_ID.findall(f"{job.get('apply_url') or ''} {job.get('url') or ''}"))


def claim(job_id, who='agent'):
    """The one gate every application passes: never twice, never a skipped company, never past today's limit or a
    company's cap."""
    j = (store.rows('select id, company, title, status, url, apply_url, source from jobs where id=?', (job_id,)) or [None])[0]
    if not j:
        return {"claimed": False, "reason": "No job with that id. Use an id from applytwin_next_jobs, or applytwin_add_job(url) first."}
    if j['status'] in ('needs user', 'failed'):
        last = store.latest_status(job_id)
        if last and last['status'] in store.OUTCOMES:   # it was submitted after all (status columns can disagree)
            return {"claimed": False, "reason": f"Already {last['status']}. Never submit it again. Skip it."}
        # still take the claim, so two sessions never finish the same application at once
        if not store.claim(job_id, who):
            if store.rows('select 1 from claims where job_id=? and at>?', (job_id, time.time() - store.CLAIM_TTL)):
                return {"claimed": False, "reason": "Another session is finishing this application right now. Skip it."}
            store.execute('update claims set who=?, at=? where job_id=?', (who, time.time(), job_id))   # a dead session's claim
        return {"claimed": True, "reason": "Already in progress: continue this application (check first that it wasn't submitted)."}
    if j and (j['status'] != 'new' or already_done(j)):
        return {"claimed": False, "reason": "You already applied to this role (or a listing of the same role). Skip it."}
    down = browser_down()
    if down:
        return {"claimed": False, "stop": True, "reason": down}
    if blockers.homepage_link(j.get('apply_url') or j.get('url')) and j['source'] != 'manual':
        log_application(job_id, 'Skipped', 'Broken link: listing points to the company homepage, not the job posting.')
        return {"claimed": False, "reason": "This listing's link is only the company homepage, so there is no posting to apply to. "
                                            "Logged Skipped; take the next job."}
    p = store.profile()
    if j and any(match.same_company(s, j['company']) for s in p['search'].get('companies_skip', [])):
        return {"claimed": False, "reason": "The user asked never to apply to this company. Skip it."}
    if who and who != 'agent' and store.rows('select 1 from claims where job_id=? and who=?', (job_id, who)):
        store.claim(job_id, who)   # this run's own claim: refresh it
        return {"claimed": True, "reason": "You already claimed this one: continue it."}
    limit, cap = p['apply'].get('daily_limit', 40), p['apply'].get('per_company_cap', 3)
    # checks and claim under one lock shared by every process: parallel agents can't all pass the limit check at once
    with store.file_lock('claims'):
        if store.applied_count_today() + store.live_claims() >= limit:
            return {"claimed": False, "reason": "Today's application limit is reached (counting applications in progress). Stop the run here."}
        if j and store.company_count(j['company']) + store.live_claims(j['company']) >= company_cap(j['company'], cap):
            lim = _limits.get(match.company_key(j['company']), (0, None))[1]
            return {"claimed": False, "reason": (f"{j['company']} takes only {lim} application(s) per candidate and that's used. Skip it."
                                                 if lim and lim < cap else
                                                 "The per-company cap for this company is reached (counting applications in progress). Skip it.")}
        ok = store.claim(job_id, who)
    if ok:
        pretailor(job_id)   # the resume is written while the agent opens and fills the application
    return {"claimed": ok} if ok else {"claimed": False, "reason": "Another session claimed it. Skip it."}


_tailoring = {}   # job_id -> {"thread", "result", "error", "vault"}: dedicated resume builds running in the background
_tlock = threading.Lock()
_builders = threading.BoundedSemaphore(2)   # several agents claiming at once never start a crowd of Claude processes


def _vault_stamp():
    try:
        return os.path.getmtime(store.path('resume.json'))
    except OSError:
        return 0


def pretailor(job_id):
    """Start the full resume pipeline for a job in the background (a focused AI plan, honesty check, page fit), unless
    one is already running or a current resume exists. The agent picks it up with applytwin_tailor_apply(job_id)."""
    with _tlock:
        t = _tailoring.get(job_id)
        if t and (t['thread'].is_alive() or (t.get('result') and t.get('vault') == _vault_stamp())):
            return   # building now, or built from the current vault
        _tailoring.pop(job_id, None)
        return _start_build(job_id)


def _start_build(job_id):
    saved = store.path('resumes', job_id, 'tailor.json')
    try:
        d = json.load(open(saved, encoding='utf-8'))
        if d.get('pipeline', 0) >= tailor.PIPELINE and d.get('mode') == 'api' and os.path.getmtime(saved) >= _vault_stamp():
            return   # a current resume, built after the last vault edit
    except Exception:
        pass
    slot = {"result": None, "error": None, "vault": _vault_stamp()}

    def work():
        try:
            with _builders:
                j = get_job(job_id)
                if not j:
                    raise RuntimeError('That job is no longer in your list (it may have closed). Reload the page.')
                slot['result'] = tailor.tailor(get_vault(), j, j.get('description', ''), mode='auto')
        except Exception as e:
            slot['error'] = str(e)
    slot['thread'] = threading.Thread(target=work, daemon=True)
    _tailoring[job_id] = slot
    slot['thread'].start()


def on_start():
    """After the app (re)starts: unfinished claims from a run that died go to Needs you, and work you queued during a run
    still happens."""
    release_claims(older_than=3 * 3600)
    try:   # progress files of builds that were killed with the app
        for f in os.listdir(store.path('progress')) if os.path.isdir(store.path('progress')) else []:
            if time.time() - os.path.getmtime(store.path('progress', f)) > 60:
                os.unlink(store.path('progress', f))
    except OSError:
        pass
    try:
        refresh_resumes()
    except Exception:
        pass
    try:   # a location imported with the name in front of it ('JANE DOE West Lafayette, IN') is cleaned once
        from .importer import clean_location
        v = store.resume()
        b = v.get('basics') or {}
        fixed = clean_location(b.get('location', ''), b.get('name', ''))
        if b.get('location') and fixed != b['location']:
            b['location'] = fixed
            store.save('resume.json', v)
        p = store.profile()
        if p.get('location') and clean_location(p['location'], p.get('name') or b.get('name', '')) != p['location']:
            store.update('profile.json', lambda cur: {**cur, 'location': clean_location(cur.get('location', ''), cur.get('name') or b.get('name', ''))}, {})
    except Exception:
        pass
    try:   # descriptions saved from a page's code (an older text extractor kept its CSS/JS) are fetched again, cleanly
        store.execute("update jobs set description='' where description like '%@font-face%' or description like '%font-family:%' "
                      "or description like '%function(%' or description like '%{display:%'")
    except Exception:
        pass
    threading.Thread(target=_hydrate_loop, daemon=True).start()
    time.sleep(20)
    if not (_run['proc'] and _run['proc'].poll() is None):
        _next_followup()


def hydrate_descriptions(limit=20, pause=1.5):
    """Fetch the full posting for your best-matching queued jobs that only came with a one-line summary (the community
    lists), a few at a time and slowly, so fit scores and resumes use the real requirements instead of a title."""
    p = store.profile()
    rows = store.rows("select * from jobs where status='new' and fit>=? and length(coalesce(description,''))<400 "
                      "order by fit desc limit ?", (p['search'].get('min_fit', 65), limit))
    n = 0
    for j in rows:
        try:
            d = sources.fetch_description(j)
            if d and len(d) >= 400:
                f, why = match.fit({**j, 'description': d}, p)
                store.execute('update jobs set fit=?, fit_why=? where id=?', (f, why, j['id']))
                n += 1
        except Exception:
            pass
        time.sleep(pause)
    return n


def _hydrate_loop():
    while True:
        try:
            if hydrate_descriptions() == 0:
                time.sleep(3600)   # nothing left to fill in: look again in an hour
            else:
                time.sleep(600)
        except Exception:
            time.sleep(3600)


def refresh_resumes():
    """Resumes built by an older, weaker pipeline for jobs not yet submitted are rebuilt from their saved plan with the
    current one (no AI call), so Needs you and the previews never hand out a page we've since fixed. Submitted ones stay
    exactly as sent."""
    root = store.path('resumes')
    sent = {r['job_id'] for r in store.rows("select job_id from applications where status='Applied'")}
    n = 0
    for jid in os.listdir(root) if os.path.isdir(root) else []:
        f = os.path.join(root, jid, 'tailor.json')
        if jid in sent or jid in ('master', 'general', '_') or not os.path.isfile(f):
            continue
        try:
            d = json.load(open(f, encoding='utf-8'))
            if d.get('pipeline', 0) >= tailor.PIPELINE or not d.get('plan'):
                continue
            j = get_job(jid)
            if not j:
                continue
            tailor.tailor(get_vault(), j, j.get('description', ''), plan=d['plan'], style=d.get('style'), out_dir=os.path.dirname(f))
            n += 1
        except Exception:
            continue
    return n


def release_claims(since=0.0, older_than=None, who=None):
    """Jobs a run claimed but never logged (it was stopped, crashed, or the app restarted). They go to Needs you with an
    honest note instead of vanishing from the queue forever."""
    q = 'select c.job_id, c.at from claims c where not exists (select 1 from applications a where a.job_id=c.job_id and a.at>=c.at)'
    q = q.replace('select c.job_id, c.at', 'select c.job_id, c.at, c.who')
    for r in store.rows(q):
        if who and r.get('who') != who:   # only this run's claims; another session may still be working on its own
            continue
        if r['at'] < since or (older_than and time.time() - r['at'] < older_than):
            continue
        try:
            store.log_application(r['job_id'], 'Needs User', 'The run ended before this one was finished. Check whether it was '
                                                             'submitted; if not, press Refill or tell your twin to finish it.')
        except RuntimeError:   # the job is gone from the list: nothing to show, just drop the claim
            store.execute('delete from claims where job_id=?', (r['job_id'],))


def triage(job_id, status, notes, agent=False):
    """Read an agent's Needs User / Failed log the way real outcomes showed it should be read. Returns (status, notes, action)
    where action is None (log it as given), 'requeue' (don't log: the job goes back to the queue) or 'skip' (re-filed as
    Skipped). Only the user's real to-dos stay in Needs you:
    - the posting is closed / the page doesn't exist / the link is a homepage / already applied -> Skipped (nothing to do)
    - the agent's own browser tools failed -> back to the queue untouched, and after two the run is told to stop
    - a page error or timeout (not on the submit step) -> back to the queue once, retried at least 30 minutes later."""
    st, nt = store.normalize_status(status, notes or '')
    if st not in ('Needs User', 'Failed'):
        return st, nt, None
    cat = blockers.classify(nt)
    if cat in ('closed', 'broken_link', 'duplicate'):
        prefix = {'closed': 'closed', 'broken_link': 'broken link', 'duplicate': 'duplicate'}[cat]
        return 'Skipped', nt if nt.lower().startswith(prefix) else f'{prefix}: {nt}', 'skip'
    if not agent:
        return st, nt, None
    if cat == 'browser':
        return st, nt, 'requeue'
    if cat == 'transient' and not re.search(r'submit|confirm|thank', nt, re.I) and \
            (store.load('retries.json', {}) or {}).get(job_id, {}).get('n', 0) < 1:
        return st, nt, 'requeue'
    return st, nt, None


def _requeue(job_id, cat, notes):
    store.execute('delete from claims where job_id=?', (job_id,))
    if cat == 'browser':
        store.update('run_health.json', lambda h: {"browser_failures": (h or {}).get('browser_failures', 0) + 1, "at": time.time(),
                                                   "last": (notes or '')[:300]}, {})
        down = browser_down()
        return {"ok": True, "status": "requeued", "requeued": True, "stop": bool(down),
                "note": down or ("Your browser tools failed, which is not the user's to fix per job, so this job went back to the "
                                 "queue unlogged. Check your browser tool once (open about:blank). If it works, continue; if it fails "
                                 "again, log the next job the same way and ApplyTwin will tell you to stop.")}

    def bump(r):
        r = r or {}
        r[job_id] = {"n": r.get(job_id, {}).get('n', 0) + 1, "at": time.time(), "why": (notes or '')[:200]}
        return r
    store.update('retries.json', bump, {})
    return {"ok": True, "status": "requeued", "requeued": True,
            "note": "A page error or timeout: this job goes back to the queue for one more try in 30+ minutes (not logged). Move on."}


def log_application(job_id, status='Applied', notes='', resume_path='', agent=False, company='', title=''):
    st, nt, action = triage(job_id, status, notes, agent)
    if action == 'requeue' and store.rows('select 1 from jobs where id=?', (job_id,)):
        last = store.latest_status(job_id)
        if not (last and last['status'] in store.OUTCOMES):
            return _requeue(job_id, blockers.classify(nt), nt)
    if action == 'skip':
        status, notes = st, nt
    out = store.log_application(job_id, status, notes, resume_path, agent=agent, company=company, title=title)
    if not out.get('ok'):
        return out
    if action == 'skip':
        out['note'] = "Filed as Skipped: nothing here for the user to do (closed posting, broken link or already applied)."
    elif out['status'] == 'Needs User' and agent:
        out['blocker'] = blockers.classify(notes)
    if agent and out['status'] in ('Needs User', 'Skipped', 'Failed') and not store.normalize_status(status, notes or '')[1].strip():
        out['warning'] = ("Log it again with notes saying exactly why (e.g. 'Workday sign-in required at <url>', 'hCaptcha on submit', "
                          "'graduation window Dec 2027 - Aug 2028; user graduates May 2029'), so the user knows what to do.")
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


def export_applications(fmt='csv'):
    """Everything you've applied to (and everything waiting on you), for your own spreadsheet or tracker."""
    import csv
    import io
    from datetime import datetime
    jobs = {j['id']: j for j in store.rows('select id, location, ats, source, apply_url from jobs')}
    rows, seen = [], set()
    for a in applications(limit=100000, history=True):   # newest first: one row per job, at its latest status
        if a['job_id'] in seen:
            continue
        seen.add(a['job_id'])
        j = jobs.get(a['job_id']) or {}
        rows.append({"company": a['company'] or '', "role": a['title'] or '', "status": a['status'] or '',
                     "date": datetime.fromtimestamp(a['at']).strftime('%Y-%m-%d %H:%M') if a.get('at') else '',
                     "location": j.get('location') or '', "url": a['url'] or j.get('apply_url') or '',
                     "site": j.get('ats') or j.get('source') or '', "notes": a['notes'] or '',
                     "resume": os.path.basename(a['resume_path'] or '')})
    if fmt == 'json':
        return json.dumps(rows, indent=2).encode(), 'application/json', 'applytwin-applications.json'
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(['Company', 'Role', 'Status', 'Date', 'Location', 'Link', 'Site', 'Notes', 'Resume'])
    for r in rows:
        # a cell starting with = + - @ is a formula to Excel and Sheets: a job title can't be allowed to run as one
        w.writerow(["'" + v if v[:1] in ('=', '+', '-', '@', '\t', '\r') else v for v in map(str, r.values())])
    return ('\ufeff' + out.getvalue()).encode('utf-8'), 'text/csv', 'applytwin-applications.csv'   # BOM: Excel reads it as UTF-8


def stats():
    r = store.rows("select status, count(*) n from jobs group by status")
    a = store.rows("select status, count(*) n from applications group by status")
    week = store.rows("select count(*) n from applications where status='Applied' and at>?", (time.time() - 7 * 86400,))[0]['n']
    return {"jobs": {x['status']: x['n'] for x in r}, "applications": {x['status']: x['n'] for x in a},
            "applied_7d": week, "applied_today": store.applied_count_today(),
            # what pages show as "Applied today": since midnight here, submitted only (the daily limit above is the last 24
            # hours and counts ones waiting at review; showing that as "today" said 2 on one page and 0 on another)
            "applied_day": store.rows("select count(distinct job_id) n from applications where status='Applied' and at>=?",
                                      (time.mktime(time.localtime()[:3] + (0, 0, 0, 0, 0, -1)),))[0]['n'],
            "matched": store.rows("select count(*) n from jobs where status='new' and fit>=?",
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
        if not j:
            raise RuntimeError('That job is no longer in your list (it may have closed). Reload the page.')
        res, _ = tailor.apply(v, plan or tailor.heuristic_plan(v, j.get('description', ''), title=j.get('title', ''),
                                                             ctx=learn.context_for(j)), j.get('description', ''))
    else:
        res = v
    return render.build_html(res, template)


def render_resume(template=None, job_id=None, one_page=True):
    p = store.profile()
    template = template or p['apply'].get('template', 'classic')
    v = get_vault()
    name = (re.sub(r'[^\w]+', '_', v['basics'].get('name') or 'Resume' or '', flags=re.UNICODE).strip('_') or 'Resume') + '_Resume.pdf'
    if job_id:
        j = get_job(job_id)
        if not j:
            raise RuntimeError('That job is no longer in your list (it may have closed). Reload the page.')
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
            "then": "Usually skip this: applytwin_tailor_apply(job_id) with no plan returns the dedicated writer's resume, which "
                    "is better. Write a plan only if the user asked you to change something specific."}


def last_resume(job_id):
    """The resume last built for this job (what the job panel shows when you open it again), if its PDF still exists."""
    if not re.fullmatch(r'[\w-]+', job_id or ''):
        return {"result": None}
    try:
        d = json.load(open(store.path('resumes', job_id, 'tailor.json'), encoding='utf-8'))
        r = d.get('result')
        return {"result": r if r and os.path.exists(r.get('pdf', '')) else None}
    except (OSError, ValueError):
        return {"result": None}


def built_resume(job_id, since=0):
    """The resume this run built for the job it's applying to: a small summary for the live preview, or None."""
    r = last_resume(job_id)['result']
    try:
        if not r or os.path.getmtime(store.path('resumes', job_id, 'tailor.json')) < since:
            return None
    except OSError:
        return None
    return {"pdf": r['pdf'], "score": r.get('score'), "pages": r.get('pages'), "rewrites": len(r.get('rewrites') or []),
            "positioning": (r.get('positioning') or '')[:160] if isinstance(r.get('positioning'), str) else ''}


def tailor_progress(job_id):
    """What the resume build for this job is doing now and about how long is left (None when nothing is building)."""
    return {"progress": tailor.progress(job_id)}


def tailor_apply(job_id, plan=None, template=None, mode='auto', fresh=False):
    """The tailored resume for a job. Without a plan: the dedicated writer's build (started at claim; waited for if still
    running), which is the best quality. With a plan: built from that plan."""
    j = get_job(job_id)
    if not j:
        return {"error": "unknown job"}
    if isinstance(plan, str):
        plan = json.loads(plan)
    if fresh and plan is None and mode in ('auto', 'api'):   # Rebuild: a new plan, not the saved one
        slot = _tailoring.get(job_id)
        if slot and slot['thread'].is_alive():
            slot['thread'].join(timeout=420)
        _tailoring.pop(job_id, None)
        return tailor.tailor(get_vault(), j, j.get('description', ''), mode=mode, style=template)
    if plan is None and mode in ('auto', 'api'):
        pretailor(job_id)
        slot = _tailoring.get(job_id)
        if slot:
            slot['thread'].join(timeout=900)   # longer than the slowest build: never start a second one alongside it
            if slot['thread'].is_alive():
                return {"error": "Your resume is still being written. It will be ready here in a moment."}
            if slot.get('result') and slot.get('vault') == _vault_stamp() and (not template or slot['result'].get('style') == template):
                return slot['result']
        try:   # a current dedicated build is saved: show it (in another template, the same plan re-set, no new AI plan)
            d = json.load(open(store.path('resumes', job_id, 'tailor.json'), encoding='utf-8'))
            if (d.get('pipeline', 0) >= tailor.PIPELINE and d.get('mode') in ('api', 'agent') and d.get('plan')
                    and os.path.getmtime(store.path('resumes', job_id, 'tailor.json')) >= _vault_stamp()):
                return tailor.tailor(get_vault(), j, j.get('description', ''), plan=d['plan'], style=template or d.get('style'), mode='agent')
        except (OSError, ValueError):
            pass
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
                  'gem': 'others', 'oraclecloud': 'oracle', 'oraclehcm': 'oracle', 'taleo': 'others',
                  'eightfold': 'others', 'successfactors': 'others', 'avature': 'others',
                  'community': 'general', 'manual': 'general', 'other': 'general'}

# appended to every ATS playbook: agents often fetch only the one for the form in front of them
ALWAYS = """
## Every ATS
- Pick dropdown options by clicking the exact option text, then read the selected value back. Typeaheads that ignore
  script need real keystrokes; forms in same-origin iframes are reached via `iframe.contentDocument` (file inputs there:
  upload to a top-level temporary input and copy it over with a DataTransfer).
- Before Submit: `applytwin_get_job` showed no `already_applied` and the site doesn't say "already applied". Duplicate =
  log Skipped "duplicate: <what you saw>".
- Never type passwords, never solve CAPTCHAs, never type emailed codes unless `email_codes` is `agent`, never create an
  account, never invent a fact (birth date, a recommender's name): fill everything else first, `applytwin_notify`, then log
  Needs User with notes that START with the blocker ("sign-in required at <url>", "emailed code at <url>", "hCaptcha on
  submit", "required question: <text>").
- A resume already attached (from the site's profile or an earlier application) is not the tailored one: remove it, upload
  the tailored PDF, and confirm the shown file name.
- "Page doesn't exist", 404, "no longer accepting applications" = log Skipped "closed: <what you saw>", never Needs User.
  A page error or timeout: reload once; still broken = log Failed with the error (ApplyTwin retries it later).
- A graduation dropdown whose options all end before the user's grad year is the posting's graduation window:
  `applytwin_answer_questions` returns `action: "knockout"` with a `skip_reason` to log as Skipped.
"""


def playbook(ats_name):
    name = re.sub(r'[^a-z0-9]', '', (ats_name or 'general').lower()) or 'general'   # never a path
    name = PLAYBOOK_ALIAS.get(name, name)
    f = os.path.join(APP, 'playbooks', f'{name}.md')
    if not os.path.exists(f):
        f, name = os.path.join(APP, 'playbooks', 'general.md'), 'general'
    text = open(f, encoding='utf-8').read()
    return (text if name == 'general' else text.rstrip() + '\n' + ALWAYS) + account_rules()


# ------------------------------------------------------------------ accounts: the twin signs in, never seeing the password

def _secrets():
    return store.load('secrets.json', {}) or {}


def accounts_status(check_google=True):
    from . import twin
    a = store.profile()['apply'].get('accounts') or {}
    google = a.get('google', True) is not False
    return {"enabled": bool(a.get('enabled')), "email": a.get('email') or '', "password_set": bool(_secrets().get('account_password')),
            "google": google, "google_signed_in": bool(check_google and google and a.get('enabled') and twin.google_signed_in())}


def set_accounts(enabled=None, email=None, password=None, google=None):
    """Turn on signing in / creating accounts for you. The password stays in secrets.json on this computer (never synced,
    never shown to the AI): ApplyTwin types it into the page itself when the agent asks."""
    if password is not None:
        if password and len(password) < 8:
            raise RuntimeError('Use at least 8 characters (most job sites ask for 8 or more, with a number and a symbol).')
        sec = _secrets()
        sec['account_password'] = password
        store.save('secrets.json', sec)
        try:
            os.chmod(store.path('secrets.json'), 0o600)
        except OSError:
            pass
    p = store.profile()
    a = dict(p['apply'].get('accounts') or {})
    if enabled is not None:
        a['enabled'] = bool(enabled)
    if email is not None:
        a['email'] = email.strip()
    if google is not None:
        a['google'] = bool(google)
    if a.get('enabled') and not _secrets().get('account_password') and a.get('google', True) is False:
        raise RuntimeError('Set the password your twin should use, or let it use Sign in with Google.')
    p['apply']['accounts'] = a
    store.save('profile.json', p)
    return accounts_status()


def sign_in_google():
    """Open Google's sign-in in the twin's browser, so "Continue with Google" on job sites needs no password later."""
    from . import twin
    return twin.open_tab('https://accounts.google.com/ServiceLogin?continue=https%3A%2F%2Fmyaccount.google.com%2F')


# the job-site password is never typed into an identity provider's own page (that would be a different account's password)
SSO_HOSTS = re.compile(r'(^|\.)(google\.com|googleusercontent\.com|microsoftonline\.com|live\.com|microsoft\.com|apple\.com|'
                       r'linkedin\.com|facebook\.com|okta\.com|auth0\.com)$', re.I)


def fill_password(url):
    """The agent is on a sign-in or create-account page: type the saved password into its password boxes. The agent gets
    a count back, never the password."""
    from . import twin
    st = accounts_status(check_google=False)
    if not st['enabled'] or not st['password_set']:
        return {"filled": 0, "note": "No job-site password is saved (signing in by email is off). Use Continue with Google if the "
                                     "page offers it and the rules allow it; otherwise leave the tab on this page, applytwin_notify, "
                                     "and log Needs User 'sign-in required at <url>'."}
    if SSO_HOSTS.search(twin.site_of(url)):
        return {"filled": 0, "note": "That is a Google / Microsoft / Apple / LinkedIn sign-in page. The saved password is only for job "
                                     "sites and is never typed there. If it asks for a password, the user must sign in to that "
                                     "account once in the twin's browser: applytwin_notify them and move on."}
    if not twin.alive():
        return {"filled": 0, "note": "This only works in the twin's browser (the Playwright tools). Notify the user instead."}
    n = twin.fill_password(url, _secrets()['account_password'])
    return {"filled": n, "email": st['email'] or (store.resume().get('basics') or {}).get('email', ''),
            "note": ("Filled the password box(es). Click the sign-in / create-account button and check the page for an error."
                     if n else "No password box was found on that page. Open the sign-in or create-account form first, then call this again.")}


def account_rules():
    """What the agent may do about sign-ins, read into every playbook and run."""
    st = accounts_status(check_google=False)
    if st['enabled'] and st['google']:
        st = accounts_status()   # only then is the browser asked whether it's signed in to Google
    google, pw = st['enabled'] and st['google'], st['enabled'] and st['password_set']
    if not (google or pw):
        return ''
    email = st['email'] or (store.resume().get('basics') or {}).get('email', '')
    out = "\n## Signing in and creating accounts (the user turned this on)\n"
    out += ("- A site that needs an account: sign in, or CREATE the account if there isn't one yet. Don't stop and notify for an "
            "account wall you can handle with the steps below.\n")
    if google:
        out += (f"- If the page offers \"Sign in with Google\" / \"Continue with Google\", use it first. In Google's window pick the account "
                f"{email or 'the user uses'} (or the only one listed). If Google asks to share name, email address and profile picture "
                "with the site, press Continue / Allow. If it asks for anything more (Gmail, Drive, contacts, calendar), press Cancel "
                "and use email sign-in instead. " + ("The twin's browser is signed in to Google. " if st['google_signed_in'] else
                "The twin's browser may not be signed in to Google yet. ") +
                "If Google asks for a password, a code or 2-step verification, never type anything: go back and use email sign-in"
                + (", or " if pw else "; if that isn't possible, ") + "applytwin_notify 'Sign in to Google once in your twin's browser "
                "(Settings, Sign in to Google)' and log Needs User.\n")
    if pw:
        out += (f"- Email sign-in / create account: use the email {email}. Never type a password yourself: call "
                "`applytwin_fill_password(url)` with the page's URL and ApplyTwin types the user's job-site password into every "
                "password box (including \"confirm password\"). Then click Sign in / Create account and read the page for errors.\n"
                "- \"Already have an account\" or \"email in use\" on create: switch to sign in. \"Wrong password\" or locked out: stop on "
                "that site, applytwin_notify, log Needs User 'sign-in failed at <url>' (never guess another password, never use "
                "\"forgot password\").\n")
    out += ("- Creating a candidate account may need ticking the site's account terms / privacy checkbox: allowed. Never accept an "
            "arbitration or other legal agreement beyond that: notify the user.\n"
            "- A verification email: if email_codes is 'agent', open it in the user's email and click the link or type the code; "
            "otherwise applytwin_notify and move on.\n- CAPTCHAs are still the user's: never solve one.\n")
    return out


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

def vault_backups():
    return {"backups": store.vault_backups()[:30]}


def restore_vault(file=None):
    """Put a backed-up vault back (the newest one with content, or the one named)."""
    bs = store.vault_backups()
    pick = next((b for b in bs if b['file'] == file), None) if file else next((b for b in bs if b['experience'] or b['projects']), None)
    if not pick or not re.fullmatch(r'resume-[\d-]+\.json', pick['file']):
        raise RuntimeError('No saved version to restore.')
    v = json.load(open(store.path('backups', pick['file']), encoding='utf-8'))
    store.save('resume.json', v)
    from . import cloud
    cloud.sync_soon()
    return {"ok": True, "vault": get_vault(), "restored": pick}


def import_resume(name='', data=None, text=None):
    from . import importer
    return importer.import_resume(name, data, text)


def import_progress():
    from . import importer
    return importer.import_progress()


def cancel_import():
    from . import importer
    return importer.cancel_import()


def queue(n=50, for_agent=False):
    """Everything worth applying to, in order: dream companies first, then by fit. Respects caps and the skip list."""
    p = store.profile()
    dream = p['search'].get('companies_priority', [])
    cap = p['apply'].get('per_company_cap', 3)
    rows = list_jobs(status='new', limit=20000)
    applied = store.company_counts()   # this recruiting cycle's applications, by company key
    claimed = {r['job_id'] for r in store.rows('select job_id from claims')}
    out, per, done, ids = [], {}, done_roles(), done_url_ids()
    skip = p['search'].get('companies_skip', [])
    for j in rows:
        c = match.company_key(j['company'])
        if (already_done(j, done, ids) or j['id'] in claimed or applied.get(c, 0) + per.get(c, 0) >= company_cap(j['company'], cap)
                or any(match.same_company(s, j['company']) for s in skip) or not_applyable(j, p)):
            continue
        per[c] = per.get(c, 0) + 1
        j['dream'] = any(match.same_company(d, j['company']) for d in dream)
        out.append(j)
    out.sort(key=lambda j: (not j['dream'], j.get('source') != 'manual', -j['fit']))   # dream companies, then jobs you added, then fit
    left = max(0, p['apply'].get('daily_limit', 40) - store.applied_count_today() - store.live_claims())
    return {"total": len(out), "dream": sum(j['dream'] for j in out), "remaining_today": left,
            "jobs": out[:min(int(n), left)] if for_agent else out[:int(n)]}


_run = {"proc": None, "agent": None, "log": None, "stopped": False}


def run_prompt(n):
    return (f"Use the applytwin-apply skill. Apply to the next {n} jobs in my ApplyTwin queue (applytwin_queue / applytwin_next_jobs), "
            "dream companies first. Use the Playwright browser tools (browser_navigate etc.): that is the twin's browser ApplyTwin set up, "
            "with my sign-ins saved. Don't use Claude in Chrome, computer use or a built-in Chrome/browser tool: they need approvals "
            "nobody is there to give. If any other browser tool fails, switch to the Playwright tools before giving up. "
            "FIRST check your browser tool works (open about:blank in your own tab); if it can't connect, call applytwin_open_browser "
            "and try once more. The twin's window stays open between runs, so tabs from earlier runs may still be there: reuse a "
            "job's tab if it's already open. If Playwright doesn't work either, call "
            "applytwin_notify once with the exact error and stop: never log jobs as blocked because your browser is down. "
            "For every job: claim it, get its tailored resume with applytwin_tailor_apply(job_id) and NO plan (a dedicated writer builds it while you open the application), "
            "open the application in the browser, follow applytwin_playbook for its ATS, answer from applytwin_answer_questions (pass job_id, and the "
            "options of every dropdown/radio), submit only if my profile allows auto_submit, and log the result with applytwin_log_application. "
            "If a site asks for an emailed verification code: if my profile.apply.email_codes is 'agent', read the newest code from that company "
            "in my email (your email/Gmail tool, or my webmail tab in the browser) and enter it; otherwise call applytwin_notify and move on. "
            "For sign-ins, passwords, CAPTCHAs or anything only I can do: fill everything you can first (on a no-account form fill the whole form; "
            "where an account is required, leave the tab on the sign-in / create-account page), then applytwin_notify, log Needs User with notes that "
            "START with the blocker ('sign-in required at <url>', 'account required at <url>', 'emailed code at <url>', 'hCaptcha on submit', "
            "'required question: <exact text>'), leave the tab open, and go straight to the next job. Tabs close when the run ends, so in what "
            "you tell me never say a tab is open: say what I need to do (sign in at <site>, answer <question> in ApplyTwin), and "
            "that pressing Finish in ApplyTwin fills the application again from where it stopped. Never create an account or type a password. "
            "applytwin_next_jobs holds back other jobs on a site that is waiting for my sign-in (waiting_on_you): don't go looking for them. "
            "A posting that is closed or says the page doesn't exist: log Skipped 'closed: <what you saw>' (never Needs User). "
            "A page error or timeout: reload once; if it persists, log Failed with the error (ApplyTwin retries it later by itself). "
            "If a resume is already attached from an earlier application, remove it and upload the tailored PDF, then check the shown file name. "
            "Never wait for me and never retry a blocked page more than twice: anything that is not moving in a few minutes gets logged and skipped. "
            "If a tool result says stop, stop the run. "
            "At the end, call applytwin_needs_you and tell me, grouped, what only I can do (one sign-in per site unblocks all its jobs); then "
            "check applytwin_pending_jobs and finish any I have unblocked, continuing each where it stopped (applytwin_get_job resume_from). "
            "Judge class-year and start-date requirements by my standing DURING the internship (applytwin_get_profile class_standing: a sophomore now is a rising junior next summer); skip only when I am clearly ineligible, and when unsure, apply. "
            "A graduation window in the posting (applytwin_get_job knockouts, or text like 'graduating Dec 2027 - Aug 2028'), or a graduation dropdown "
            "whose options all end before my grad date (applytwin_answer_questions says knockout), that my grad date is outside of IS clearly ineligible: log Skipped with that exact reason. "
            "If applytwin_get_job shows already_applied, or the site says I already applied, log Skipped as a duplicate and never submit twice. "
            "Never invent facts (no guessed birth dates or recommender names: log Needs User with the exact question). Give a 1-line update every 5 jobs.")


def doctor():
    return agents.doctor()


def agent_status():
    return {n: {**agents.status(n, fresh=bool(_connecting.get(n))), "connecting": _connect_view(n)} for n in agents.NAMES}


_connecting = {}   # name -> {"step": "installing" | "signing_in" | "failed", "at", "error", "proc"}
LOGIN_CMD = {'claude': ['auth', 'login', '--claudeai'], 'codex': ['login']}
NPM_PKG = {'claude': '@anthropic-ai/claude-code', 'codex': '@openai/codex'}


def _connect_view(name):
    c = _connecting.get(name)
    if not c:
        return None
    if c['step'] == 'signing_in' and agents.status(name, fresh=True)['signed_in']:
        _connecting.pop(name, None)   # done: the browser sign-in finished
        return None
    if time.time() - c['at'] > 900 and c['step'] != 'failed':   # nobody finished in 15 minutes: stop waiting
        _kill_connect(c)
        _connecting.pop(name, None)
        return None
    return {k: c.get(k) for k in ('step', 'error', 'at')}


def _kill_connect(c):
    p = c.get('proc')
    if p and p.poll() is None:
        try:
            store.kill_tree(p)
        except Exception:
            pass


def connect_agent(name):
    """Get Claude Code or Codex ready without a terminal: install it if it's missing (npm), then start its sign-in, which
    opens the browser on Claude's or ChatGPT's own login page. The app notices the moment it's done."""
    import shutil
    import subprocess
    if name not in agents.NAMES:
        raise ValueError('unknown agent')
    if agents.status(name, fresh=True)['signed_in']:
        return {"ok": True, "signed_in": True}
    old = _connecting.get(name)
    if old and old['step'] in ('installing', 'signing_in') and time.time() - old['at'] < 900:
        return {"ok": True, "connecting": _connect_view(name)}
    if old:
        _kill_connect(old)
    c = {"step": "installing", "at": time.time(), "error": None, "proc": None}
    _connecting[name] = c

    def work():
        log = open(store.path(f'connect-{name}.log'), 'w', encoding='utf-8')
        try:
            if not agents.exe(name) and name == 'claude' and not agents.exe('npm'):
                # no Node.js: Claude Code's own installer needs none (it puts claude in ~/.local/bin, which exe() looks in)
                cmd = (['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', 'irm https://claude.ai/install.ps1 | iex']
                       if os.name == 'nt' else ['bash', '-c', 'curl -fsSL https://claude.ai/install.sh | bash'])
                subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, timeout=600, **store.NOWIN)
                agents._cache.pop(name, None)
            if not agents.exe(name):
                npm = agents.exe('npm')
                if not npm:
                    c.update(step='failed', error="Node.js isn't installed, so it can't be installed for you. Get it from nodejs.org, "
                                                  "then press this again.")
                    return
                r = subprocess.run([npm, 'install', '-g', NPM_PKG[name]], stdout=log, stderr=subprocess.STDOUT, timeout=600, **store.NOWIN)
                agents._cache.pop(name, None)
                if r.returncode != 0 or not agents.exe(name):
                    c.update(step='failed', error=f"Installing {agents.NAMES[name]} didn't finish. Run: npm install -g {NPM_PKG[name]}")
                    return
            c.update(step='signing_in', at=time.time())
            c['proc'] = subprocess.Popen([agents.exe(name), *LOGIN_CMD[name]], stdin=subprocess.DEVNULL, stdout=log,
                                         stderr=subprocess.STDOUT, cwd=store.HOME, **store.NOWIN)
        except Exception as e:
            c.update(step='failed', error=str(e)[:200])
        finally:
            log.close()
    threading.Thread(target=work, daemon=True).start()
    return {"ok": True, "connecting": _connect_view(name)}


def finish_prompt(job_ids, submit=False):
    rows = [store.rows('select id, company, title, apply_url, url from jobs where id=?', (j,)) for j in job_ids]
    lines = '; '.join(f"{r[0]['company']} {r[0]['title']} (job {r[0]['id']}, {r[0]['apply_url'] or r[0]['url']})" for r in rows if r)
    act = ("SUBMIT each one: I reviewed them and asked you to submit these specific applications, so submit once, confirm the "
           "success page, and log it Applied." if submit else
           "Stop on the review screen with everything filled and leave that tab open for me; log Needs User with 'ready to submit'.")
    return ("Use the applytwin-apply skill. Finish these specific applications only, in your browser: " + lines + ". "
            "For each: the job is already claimed; reuse its tailored resume (applytwin_get_job shows it; if there is none, "
            "applytwin_tailor_apply(job_id) with no plan), open the application, follow applytwin_playbook "
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
        f = {"job_ids": list(job_ids), "submit": bool(submit), "agent": agent}
        store.update('followups.json', lambda later: None if any(
            x.get('job_ids') == f['job_ids'] and x.get('submit') == f['submit'] and not x.get('prompt') for x in later) else later.append(f), [])
        return {"queued": True, "running": True}
    return start_run(agent, len(job_ids), prompt=finish_prompt(job_ids, submit))


def _agent():
    """The agent to use: the one chosen in Settings if it's signed in, otherwise whichever one is."""
    ready = agents.preferred(store.profile())
    return ready[0] if ready else (store.profile()['apply'].get('agent') or 'claude')


def _next_followup():
    """Start the next queued finish request (from a button pressed while a run was going). Returns True if one started."""
    while True:
        with store.file_lock('followups.json'):
            later = store.load('followups.json', [])
            if not later:
                return False
            f = later.pop(0)
            store.save('followups.json', later)
        try:
            r = start_run(f['agent'], len(f['job_ids']), prompt=f.get('prompt') or finish_prompt(f['job_ids'], f['submit']))
            if r.get('busy'):   # something else started first: put it back for the next opening
                store.update('followups.json', lambda later: later.insert(0, f), [])
                return False
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


HELP = 'help'   # the thread for "something's wrong / help me" about the app in general, not one application


def help_prompt(text):
    """Everything your agent needs to understand a problem with the app and fix what it can, without asking you."""
    from . import update
    p, v = store.profile(), store.resume()
    last = (store.load('last_scan.json', {}) or {})
    errs = ''
    try:
        errs = ''.join(open(store.path('llm.log'), encoding='utf-8', errors='replace').readlines()[-4:])[-1200:]
    except OSError:
        pass
    needs = store.rows("select a.job_id, j.company, j.title, a.notes from applications a join jobs j on j.id=a.job_id "
                       "where a.status='Needs User' order by a.at desc limit 5")
    convo = '\n'.join(f"{'User' if r['role'] == 'you' else 'You'}: {r['text']}" for r in thread(HELP)[-10:])
    waiting = '; '.join(f"{r['company']} {r['title']}: {r['notes']}" for r in needs)
    return ("You are the user's ApplyTwin assistant, running on their computer through their own agent. They wrote to you "
            "from the app's Help chat about a problem or a request. Understand it, then FIX it yourself with your ApplyTwin "
            "tools (applytwin_*): read and update their profile, vault, answers and preferences; restore their resume with "
            "applytwin_vault_backups / applytwin_restore_vault if it was lost; scan for jobs; rebuild a resume; skip or finish "
            "an application. Don't edit ApplyTwin's own program files. If the problem is a bug in ApplyTwin itself, say so "
            "plainly and include a short bug report they can paste to the developer (what happened, what they expected, "
            "version). Never invent facts, never type passwords.\n\n"
            f"Facts about their setup: ApplyTwin {update.check().get('current') or ''}, agent {p['apply'].get('agent') or 'claude'}; "
            f"vault has {len(v.get('experience', []))} roles, {len(v.get('projects', []))} projects, "
            f"{len(store.vault_backups())} backups saved; looking for {', '.join(p['search'].get('roles', [])[:6])} "
            f"({p['search'].get('kind', 'internship')}, {p.get('class_standing', '')} {p.get('degree', '')}); "
            f"last job scan: {last.get('stats') or 'never'}; waiting on them: "
            f"{waiting or 'nothing'}.\n"
            f"Recent errors from their agent calls: {errs or 'none'}\n\n"
            f"The conversation so far:\n{convo}\n\n"
            "Do what their last message asks. Then answer with applytwin_reply('help', text): two or three plain sentences on "
            "what you found and what you did, and anything they still need to do. Plain words, no em dashes, no markdown.")


def message(job_id, text):
    """You wrote to your twin about one application. Simple things are handled right away; anything else goes to the
    agent for that application, and its answer shows up in the same conversation."""
    text = (text or '').strip()
    if not text:
        return {"thread": thread(job_id)}
    if job_id == HELP:   # the general help chat: its own agent right away, never waiting behind an Autopilot run
        _say(HELP, 'you', text)
        try:
            start_help()
            _say(HELP, 'twin', "Looking into it now. I'll answer here in a minute.")
        except Exception as e:
            _say(HELP, 'twin', f"I can't answer right now: {e}")
        return {"thread": thread(HELP)}
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
        busy = bool(_run['proc'] and _run['proc'].poll() is None)
        if busy and not submit:
            # mid-run, an answer can't wait for the run to end ("what resume did you use?" sat behind 25 applications):
            # a side agent answers now from ApplyTwin's data; anything that needs the browser is queued for after the run
            queued = not _question(text)
            if queued:
                _run_or_queue(job_id, message_prompt(job_id, text))
            try:
                start_help(job_id, queued=queued)
                _say(job_id, 'twin', "Looking into it now.")
            except Exception as e:
                _say(job_id, 'twin', f"I can't answer right now: {e}")
            return {"thread": thread(job_id)}
        r = finish_jobs([job_id], submit=True) if submit else _run_or_queue(job_id, message_prompt(job_id, text))
        _say(job_id, 'twin', ("Already submitted, nothing to do." if r.get('done') else
                              "Queued. I'm in the middle of a run and will do this right after, then reply here." if r.get('queued')
                              else ("Submitting it now. I'll reply here when it's done." if submit else "On it. I'll reply here when it's done.")))
    return {"thread": thread(job_id)}


def _question(text):
    """A question to answer, not something to do in the browser."""
    t = (text or '').strip().lower()
    return t.endswith('?') or bool(re.match(r"(what|which|why|how|when|where|who|did|does|do|is|are|was|were|can|could|have|has|show|tell)\b", t))


def job_answer_prompt(job_id, queued):
    j = (store.rows('select id, company, title, apply_url, url from jobs where id=?', (job_id,)) or [{}])[0]
    a = _latest(job_id) or {}
    convo = '\n'.join(f"{'User' if r['role'] == 'you' else 'You'}: {r['text']}" for r in thread(job_id)[-8:])
    return (f"The user is asking about ONE application: {j.get('company')} {j.get('title')} (job {job_id}). "
            f"Its latest status: {a.get('status', 'not started')}: {a.get('notes') or ''}\n"
            f"Conversation so far:\n{convo}\n\n"
            "Answer their last message from ApplyTwin's tools (applytwin_get_job, applytwin_list_jobs, applytwin_get_vault, "
            "applytwin_get_profile). An Autopilot run is using the browser right now: don't open a browser, don't claim, "
            "apply or start a run. " + ("What they asked needs the browser, so it is queued and happens right after the current "
            "run; tell them that. " if queued else "") +
            "Reply with applytwin_reply(job_id, text): one to three plain sentences, no markdown, no em dashes, never a file "
            "path (the resume opens from the link the app shows under your reply). Never invent facts.")


_help = {}   # thread id -> the side agent answering it
_HELP_LOCK = threading.Lock()


def start_help(tid=None, queued=False):
    """Answer the Help chat with a second, short agent session that runs beside any Autopilot run. It gets ApplyTwin's
    tools but no browser, so it never fights the run for the twin's browser. A newer message replaces one still being
    worked on: the new session sees the whole conversation, so nothing is lost."""
    import shutil
    import subprocess
    agent = _agent()
    exe = shutil.which(agent) or agents.exe(agent)
    if not exe or not os.path.exists(str(exe)):
        raise RuntimeError('Claude Code or Codex needs to be installed first (Settings shows how).')
    if not agents.status(agent)['signed_in']:
        raise RuntimeError(f"{'Claude Code' if agent == 'claude' else 'Codex'} is signed out. Press Sign in on the Autopilot page.")
    tid = tid or HELP
    busy = bool(_run['proc'] and _run['proc'].poll() is None)
    prompt = job_answer_prompt(tid, queued) if tid != HELP else help_prompt(_help_latest()) + (
        "\n\nAn Autopilot run is going right now in the twin's browser: don't open a browser, don't start a run, and "
        "don't claim or apply to jobs. Answer from ApplyTwin's tools and data." if busy else
        "\n\nAnswer from ApplyTwin's tools and data; don't open a browser or start an Autopilot run.")
    if agent == 'claude':
        cmd = [exe, '-p', '--allowedTools', 'mcp__plugin_applytwin_applytwin,mcp__applytwin,Read', '--permission-mode', 'acceptEdits',
               '--output-format', 'text']
    else:
        cmd = [exe, 'exec', '--skip-git-repo-check', '-s', 'workspace-write', '-c', 'approval_policy=never', *agents.codex_model_args(),
               '--output-last-message', store.path(f'help-{tid}.last'), '-']   # its log is full of tool chatter; this is just the answer
    with _HELP_LOCK:
        old = _help.get(tid)
        if old and old.poll() is None:
            _kill(old)
        logf = store.path(f'help-{tid}.log')
        try:
            os.remove(store.path(f'help-{tid}.last'))
        except OSError:
            pass
        f = open(logf, 'w', encoding='utf-8')
        proc = subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.PIPE, cwd=store.HOME, text=True, encoding='utf-8',
                                errors='replace', env={**os.environ, 'APPLYTWIN_RUN_ID': f'help-{int(time.time())}'},
                                **(store.NOWIN if os.name == 'nt' else {'start_new_session': True}))
        f.close()
        proc.stdin.write(prompt)
        proc.stdin.close()
        _help[tid] = proc
    threading.Thread(target=_watch_help, args=(proc, logf, time.time(), tid), daemon=True).start()
    return {"started": True}


def _help_latest():
    mine = [r['text'] for r in thread(HELP) if r['role'] == 'you']
    return mine[-1] if mine else ''


def _watch_help(proc, logf, started, tid=HELP):
    """If the agent answered with applytwin_reply, that's in the chat already; otherwise post what it printed."""
    try:
        proc.wait(timeout=600)
    except Exception:
        _kill(proc)
        if _help.get(tid) is proc:
            _say(tid, 'twin', "That took too long, so I stopped. Try asking again, or in fewer words.")
        return
    if _help.get(tid) is not proc:   # replaced by a newer message
        return
    if store.rows("select 1 from thread where job_id=? and role='twin' and at>? and text not like 'Looking into it now%'", (tid, started)):
        return
    out = ''
    for f in (store.path(f'help-{tid}.last'), logf):
        try:
            out = open(f, encoding='utf-8', errors='replace').read().strip()
        except OSError:
            continue
        if out:
            break
    low = out.lower()
    if not out or proc.returncode and ('not logged in' in low or 'login' in low and 'please' in low):
        _say(tid, 'twin', "I couldn't get an answer from your agent. Check that it's signed in on the Autopilot page, then ask again.")
    else:
        _say(tid, 'twin', out[-1800:])


def _run_or_queue(job_id, prompt):
    agent = _agent()
    if _run['proc'] and _run['proc'].poll() is None:
        store.update('followups.json', lambda later: later.append({"job_ids": [] if job_id == HELP else [job_id], "submit": False,
                                                                  "agent": agent, "prompt": prompt}), [])
        return {"queued": True}
    return start_run(agent, 1, prompt=prompt)


def skip_job(job_id, why='Skipped by you'):
    """Never apply to this one (the Skip button on anything that needs you)."""
    _todo_cache['v'] = None
    store.execute("update jobs set status='skipped' where id=?", (job_id,))
    store.execute('update inbox set resolved=? where job_id=? and resolved is null', (time.time(), job_id))
    if any(r['job_id'] == job_id for r in pending_jobs()):   # it was waiting on you: close that out too
        store.log_application(job_id, 'Skipped', why)
    return {"ok": True}


def open_in_twin_browser(url):
    """Open a page in the twin's own browser profile, so a sign-in you do there is the one the twin uses."""
    if not re.match(r'https?://[^\s]+$', url or '', re.I):   # a web page, never a Chrome command-line flag
        raise RuntimeError('That is not a web link.')
    from . import twin
    return twin.open_tab(url)   # a tab in the twin's own window (mid-run too): the sign-in you do there is the one it uses


_RUN_LOCK = threading.Lock()


def pick_agent(agent):
    """The agent to run: the one asked for if it's installed and signed in, otherwise whichever one is (someone with only
    Codex pressing 'Find them in my email' got 'Claude Code is not installed')."""
    ready = lambda a: bool(agents.exe(a)) and agents.status(a, fresh=True)['signed_in']
    if ready(agent):
        return agent
    return next((a for a in agents.NAMES if a != agent and ready(a)), agent)


def start_run(agent='claude', n=25, model=None, prompt=None, restarts=0):
    if agent not in agents.NAMES:   # only ever Claude Code or Codex, never another program named in a request
        raise ValueError('unknown agent')
    with _RUN_LOCK:   # two clicks at once must never start two agents on one browser
        return _start_run(agent, n, model, prompt, restarts)


def _start_run(agent, n, model, prompt, restarts):
    import shutil
    import subprocess
    if _run['proc'] and _run['proc'].poll() is None:
        return {**run_status(), "busy": True}
    if prompt is None and store.applied_count_today() >= store.profile()['apply'].get('daily_limit', 40):
        raise RuntimeError(f"You've reached today's limit of {store.profile()['apply'].get('daily_limit', 40)} applications. "
                           "Raise it in Settings, or your twin continues tomorrow.")
    picked = pick_agent(agent)
    if picked != agent:
        agent, model = picked, None
    exe = shutil.which(agent) or agents.exe(agent)
    if not exe or not os.path.exists(str(exe)):
        raise RuntimeError(f"{'Claude Code' if agent == 'claude' else 'Codex'} is not installed. Install Claude Code or Codex "
                           f"(Settings shows how), sign in once, then try again.")
    st = agents.status(agent, fresh=True)
    if not st['signed_in']:
        raise RuntimeError(f"{st['label']} is signed out. Press Sign in on the Autopilot page, finish in your browser, then press Start again.")
    from . import cloud
    if not (cloud.status()['signed_in'] or os.environ.get('APPLYTWIN_SKIP_SIGNIN') or os.environ.get('CI')):
        raise RuntimeError('Sign in first: open ApplyTwin (type applytwin in a terminal) and continue with Google.')
    prompt = prompt or run_prompt(n)
    if account_rules() and 'applytwin_fill_password' not in prompt:
        prompt += "\n\nThe user turned on signing in for them. This overrides 'never type a password or create an account' above, for candidate accounts only:" + account_rules()
    if agent == 'codex':
        # in `codex exec` any message that isn't a tool call ends the whole run: an "update every 5 jobs" stopped it after 5
        prompt = prompt.replace(' Give a 1-line update every 5 jobs.', '') + (
            "\n\nYou are running unattended: nobody reads messages until the end. Don't stop to report progress or ask "
            "anything; keep calling tools until every job is handled or a tool result says stop. Your one final message ends the run.")
    store.save('run_health.json', {})   # a new run gets a fresh chance at its browser
    from . import install
    install.ensure_browser(agent)
    if not install.has_browser(agent) and not shutil.which('npx'):
        raise RuntimeError("Your twin's browser needs Node.js. Install it from nodejs.org, then press Start again.")
    if agent == 'claude':
        # runs on the user's own Claude subscription; only ApplyTwin's tools and a browser are pre-approved, so it never stalls on a prompt
        tools = ('mcp__plugin_applytwin_applytwin,mcp__applytwin,mcp__playwright,mcp__claude-in-chrome,'
                 'Read,Write,Bash(ls:*),Bash(open:*)')
        cmd = [exe, '-p', '--allowedTools', tools, '--permission-mode', 'acceptEdits', '--output-format', 'text']
    else:
        cmd = [exe, 'exec', '--skip-git-repo-check', '-s', 'workspace-write', '-c', 'approval_policy=never', *(['-m', model] if model else agents.codex_model_args()),
               *agents.codex_browser_args(exe), '-']
    logf = store.path('autopilot.log')
    keep = os.path.exists(logf) and os.path.getsize(logf) < 2_000_000 and restarts   # a continuation adds to its run's log
    f = open(logf, 'a' if keep else 'w', encoding='utf-8')
    f.write(f"$ {' '.join(os.path.basename(c) if i == 0 else c for i, c in enumerate(cmd))} … apply to {n} jobs\n")
    f.flush()
    from . import twin
    if not twin.ensure():   # the twin's own window, kept open between runs so half-filled forms are still there
        f.close()
        raise RuntimeError("Couldn't open your twin's browser. ApplyTwin needs Google Chrome (or Chromium/Edge) installed.")
    # run from the data folder, not the repo, so the agent loads the installed plugin rather than the repo's dev .mcp.json
    # the instructions go in on stdin: on Windows, claude/codex are .cmd wrappers and cmd.exe would mangle quotes in a long argument
    run_id = f'run-{int(time.time() * 1000)}'
    env = {**os.environ, 'APPLYTWIN_RUN_ID': run_id}   # the agent's ApplyTwin tools tag their claims with this run
    proc = subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.PIPE, cwd=store.HOME, text=True, encoding='utf-8', env=env,
                            errors='replace', **(store.NOWIN if os.name == 'nt' else {'start_new_session': True}))   # its own group: Stop ends its browser too
    f.close()   # the agent has its own handle to the log; keeping ours open leaked one file per run
    proc.stdin.write(prompt)
    proc.stdin.close()
    _run.update(proc=proc, agent=agent, log=logf, started=time.time(), stopped=False, id=run_id)
    import threading
    threading.Thread(target=_watch_run, args=(proc, agent, logf, n, model, prompt, restarts, run_id), daemon=True).start()
    return run_status()


AUTH_ERRORS = ('failed to authenticate', 'oauth session expired', 'not logged in', 'please run /login', 'invalid api key',
               'unauthorized', 'status 401')


def _kill(proc):
    """Stop the agent and everything it started. On Windows, claude/codex are .cmd wrappers: killing only the wrapper
    would leave the real agent running in the background."""
    if os.name == 'nt':
        import subprocess
        subprocess.run(['taskkill', '/T', '/F', '/PID', str(proc.pid)], capture_output=True, **store.NOWIN)
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


def _watch_run(*a, **k):
    """One error in the watcher (a locked database, an unreadable log) used to end it silently: stuck runs were never
    skipped, claims never released and queued follow-ups never started until the app restarted."""
    try:
        return _watch_run_body(*a, **k)
    except Exception as e:
        try:
            print(f'Autopilot watcher error: {e}')
            release_claims(who=k.get('run_id') or (a[6] if len(a) > 6 else None))
            if not (_run['proc'] and _run['proc'].poll() is None):
                _next_followup()
        except Exception:
            pass


def _watch_run_body(proc, agent, logf, n, model, prompt=None, restarts=0, run_id=None):
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
        release_claims(since=started, who=run_id)
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
    if agent == 'codex' and 'model_not_found' in tail and restarts < 8 and agents.reject_model(tail):
        # that model isn't on this plan: continue on the next one the CLI lists (remembered for every later run)
        fb = (agents.codex_model_args() or [None, None])[1]
        if fb:
            return start_run(agent, n, model=fb, prompt=prompt, restarts=restarts + 1)
    if (proc.returncode == 0 and prompt is None and not _run.get('stopped') and restarts < 5 and not browser_down()
            and not any(e in tail for e in AUTH_ERRORS)):
        # the agent wrapped up before doing them all (Codex ends a run on its first progress message): carry on with the rest,
        # as long as this leg got something done and there is work and room left today
        done = len(store.rows('select 1 from applications where at >= ?', (started,)))
        left = n - done
        room = store.profile()['apply'].get('daily_limit', 40) - store.applied_count_today()
        if done and left > 0 and room > 0 and next_jobs(1).get('jobs'):
            release_claims(since=started, who=run_id)
            try:
                return start_run(agent, left, model=model, restarts=restarts + 1)
            except Exception:
                pass
    if any(e in tail for e in AUTH_ERRORS):
        fix = 'press Sign in on the Autopilot page'
        notify(f'Sign in to {name}', f'Your {name} login expired: {fix}, then press Launch again.', kind='signin')
    elif proc.returncode and not _run.get('stopped'):
        notify(f'{name} stopped early', f'Exit code {proc.returncode}. The last lines are in the Autopilot log.', kind='error')
    release_claims(since=started, who=run_id)
    if not _run.get('stopped'):
        _next_followup()
    _run['stopped'] = False


def stop_run():
    if _run['proc'] and _run['proc'].poll() is None:
        _run['stopped'] = True   # you pressed Stop: don't start queued work either, and forget it
        store.save('followups.json', [])
        _kill(_run['proc'])
    return run_status()


def _safe(f):
    """The extras on the status (resume progress, the preview) must never break it: a crash there made the page think
    no run was going while the twin was mid-application, and it showed "Ready" with nothing to explain why."""
    try:
        return f()
    except Exception:
        import traceback
        traceback.print_exc()
        return None


def run_status():
    p = _run['proc']
    log = ''
    if _run['log'] and os.path.exists(_run['log']):
        log = open(_run['log'], encoding='utf-8', errors='replace').read()[-6000:]
    now = None
    a = store.load('activity.json', {}) or {}
    if p and p.poll() is None and a.get('at', 0) >= _run.get('started', 0):
        j = (store.rows('select company, title, apply_url, url from jobs where id=?', (a.get('job_id') or '',)) or [{}])[0]
        now = {"step": a.get('step'), "company": j.get('company', ''), "title": j.get('title', ''), "url": j.get('apply_url') or j.get('url') or '', "at": a['at'],
               "resume": _safe(lambda: tailor.progress(a.get('job_id') or '')),   # this job's resume being written, if it is
               "built": _safe(lambda: built_resume(a.get('job_id') or '', _run.get('started', 0)))}   # and once it's done, the page itself
    return {"running": bool(p and p.poll() is None), "agent": _run['agent'], "log": log, "now": now,
            "exit": None if not p or p.poll() is None else p.returncode}


# ------------------------------------------------------------------ inbox: things only the user can do

_app_seen = [0.0]   # last time the app (open in a browser tab) checked its inbox


def notify(title, message='', url='', job_id='', kind='needs_you'):
    """Tell the user something needs them (a code, a sign-in, a CAPTCHA, a question). In-app inbox, plus a notification:
    the open app shows its own (click it to answer); if the app isn't open, a system notification says where to go."""
    # one ping per site and blocker: five NVIDIA jobs waiting on one Workday sign-in are one thing to do, not five alerts
    cat = blockers.classify(f'{title}. {message}')
    if cat == 'browser':   # the agent's own tooling, not something on a site: one plain card with the fix, never a pile of raw errors
        title, message, url, job_id = "Your twin's browser didn't start", browser_fix(f'{title}. {message}'), '', ''
        if store.rows("select id from inbox where resolved is null and title=?", (title,)):
            return {"ok": True, "batched": True, "note": "The user already has a browser item. Stop the run now."}
    h = blockers.host(url or ((store.rows('select apply_url, url from jobs where id=?', (job_id,)) or [{}])[0].get('apply_url') or ''))
    repeat = False
    if h and cat in ('signin', 'account', 'email_code', 'captcha'):
        for r in store.rows('select title, message, url, job_id from inbox where resolved is null and at>?', (time.time() - 6 * 3600,)):
            ru = r['url'] or ((store.rows('select apply_url from jobs where id=?', (r['job_id'] or '',)) or [{}])[0].get('apply_url') or '')
            if blockers.host(ru) == h and blockers.classify(f"{r['title']}. {r['message']}") == cat:
                repeat = True
                break
    store.execute('insert into inbox(kind,title,message,url,job_id,at) values(?,?,?,?,?,?)', (kind, title, message, url, job_id, time.time()))
    _say(job_id, 'twin', f"{title}. {message}".strip(' .') + '.' if message else title)
    if repeat:
        return {"ok": True, "batched": True, "note": f"The user already has a {blockers.LABELS.get(cat, cat).lower()} item for {h}; "
                                                       "this one is grouped with it (no second alert). Log Needs User and move on."}
    if store.profile()['apply'].get('notify_desktop', True) and time.time() - _app_seen[0] > 60:
        from .install import notify as desk
        desk('ApplyTwin: ' + title, 'Open ApplyTwin (localhost:4747) to handle it. ' + (message or url))
    return {"ok": True}


def tidy_inbox():
    """On start: clear browser errors left by earlier runs. They were the agent's own tooling failing (now set up on
    start), never something the user had to do on a site."""
    for r in store.rows('select id, title, message from inbox where resolved is null'):
        if r['title'] == "Your twin's browser didn't start" or blockers.classify(f"{r['title']}. {r['message']}") == 'browser':
            store.execute('update inbox set resolved=? where id=?', (time.time(), r['id']))


def browser_fix(err=''):
    """What the user should do when the agent's browser didn't start, in plain words."""
    import shutil
    from . import install
    if not shutil.which('npx'):
        return "It needs Node.js. Install it from nodejs.org, then press Start again."
    if re.search(r'already in use|profile', err, re.I):
        return "Another Chrome was using your twin's profile. Restart ApplyTwin and press Start again; your sign-ins are kept."
    if not any(install.has_browser(a) for a in agents.NAMES):
        return "It wasn't set up yet. Restart ApplyTwin (it sets it up on start), then press Start again."
    return "Press Start again. If it happens again, restart ApplyTwin; your jobs stay in the queue."


_todo_cache = {"at": 0.0, "v": None}


def inbox_poll():
    """What the bell and Needs you show, polled every few seconds by every open window: the grouped list plus just enough
    of each new message for a desktop notification (it used to resend every message and every waiting job, 90 KB a poll)."""
    _app_seen[0] = time.time()
    if time.time() - _todo_cache['at'] > 3 or _todo_cache['v'] is None:   # two windows polling at once share one build
        _todo_cache.update(at=time.time(), v=todo())
    t = _todo_cache['v']
    items = [{"id": i['id'], "title": i['title'], "message": (i.get('message') or '')[:200]} for i in inbox()[:50]]
    return {"items": items, "groups": t, "count": len(t)}


HIDE = {'closed', 'duplicate', 'broken_link', 'transient'}   # handled by ApplyTwin itself: never a thing for the user to do
ORDER = ['question', 'ready', 'captcha', 'email_code', 'signin', 'account', 'agreement', 'assessment', 'upload', 'eligibility',
         'dropdown', 'browser', 'other']


def todo():
    """Everything waiting on the user as a short list of things to do, not one card per message: five Workday jobs behind
    one sign-in are one row, every unanswered question is one row, and what ApplyTwin handles itself (closed postings,
    retries) never shows. 70 separate cards with five buttons each read like an alarm going off."""
    if _run['proc'] and _run['proc'].poll() is None:   # a run is going, so its browser started: old browser errors are stale
        for r in store.rows('select id, title, message from inbox where resolved is null'):
            if r['title'] == "Your twin's browser didn't start" or blockers.classify(f"{r['title']}. {r['message']}") == 'browser':
                store.execute('update inbox set resolved=? where id=?', (time.time(), r['id']))
    jobs = {}
    def job(jid):
        if jid and jid not in jobs:
            jobs[jid] = (store.rows('select company, title, apply_url, url from jobs where id=?', (jid,)) or [{}])[0]
        return jobs.get(jid) or {}
    entries = []
    for i in inbox():
        j = job(i.get('job_id'))
        cat = 'question' if i.get('kind') == 'question' else 'browser' if i['title'] == "Your twin's browser didn't start" \
            else blockers.classify(f"{i['title']}. {i.get('message') or ''}")
        if cat == 'browser' and i['at'] < (_run.get('started') or 0):   # a run started since, so its browser worked
            store.execute('update inbox set resolved=? where id=?', (time.time(), i['id']))
            continue
        entries.append({"item_id": i['id'], "job_id": i.get('job_id') or '', "company": j.get('company') or '', "title": j.get('title') or '',
                        "url": i.get('url') or j.get('apply_url') or j.get('url') or '', "text": i['title'],
                        "note": (i.get('message') or '')[:300], "cat": cat})
    covered = {e['job_id'] for e in entries if e['job_id']}
    for p in pending_jobs():
        if p['job_id'] not in covered:
            entries.append({"item_id": None, "job_id": p['job_id'], "company": p.get('company') or '', "title": p.get('title') or '',
                            "url": p.get('url') or '', "text": '', "note": (p.get('notes') or '')[:300], "cat": blockers.classify(p.get('notes'))})
    groups = {}
    for e in entries:
        cat = 'ready' if e['cat'] == 'captcha' else e['cat']
        if cat in HIDE:
            continue
        h = blockers.host(e['url'])
        key = f"{cat}|{h}" if cat in ('signin', 'account', 'email_code') else cat
        g = groups.setdefault(key, {"key": key, "kind": cat, "site": h if cat in ('signin', 'account', 'email_code') else '', "entries": []})
        if not any(x['job_id'] and x['job_id'] == e['job_id'] for x in g['entries']):   # one row per job, however many messages
            g['entries'].append(e)
    out = []
    for g in groups.values():
        n, names = len(g['entries']), []
        for e in g['entries']:
            c = re.sub(r'^\W+', '', e['company'] or '')
            if c and c not in names:
                names.append(c)
        who = names[0] if len(names) == 1 else (', '.join(names[:2]) + (f' +{len(names) - 2}' if len(names) > 2 else '')) if names else g['site']
        g['title'] = {
            'question': f"Answer {n} question{'s' if n > 1 else ''} only you know",
            'ready': f"Review and submit {n} application{'s' if n > 1 else ''}",
            'email_code': f"Type the emailed code for {who}",
            'signin': f"Sign in to {who}",
            'account': f"Create your {who} account",
            'agreement': f"Accept {who}'s agreement yourself",
            'assessment': f"Take {who}'s assessment",
            'upload': f"Add a file {who} asks for",
            'eligibility': f"Check you qualify for {who}",
            'dropdown': f"Pick an answer {who}'s form wouldn't take",
            'browser': "Your twin's browser didn't start",
        }.get(g['kind'], f"Finish {who}" if names else "Something needs a look")
        g['detail'] = (blockers.ACTIONS.get(g['kind'], '').format(host=g['site'] or 'the site', n=n) if g['kind'] in blockers.ACTIONS
                       else browser_fix() if g['kind'] == 'browser' else (g['entries'][0]['note'] or g['entries'][0]['text'])[:160])
        g['count'] = n
        out.append(g)
    out.sort(key=lambda g: (ORDER.index(g['kind']) if g['kind'] in ORDER else len(ORDER), -g['count']))
    # every site waiting on a sign-in, an account or an emailed code is one row with the sites inside it
    sites = {}
    for g in out:
        if g['kind'] in ('signin', 'account', 'email_code'):
            s2 = sites.setdefault(g['site'], {**g, "entries": []})
            s2['entries'] += [e for e in g['entries'] if not any(x['job_id'] == e['job_id'] for x in s2['entries'])]
            s2['count'] = len(s2['entries'])
            if g['kind'] == 'account':
                s2['kind'], s2['title'] = 'account', g['title']
    rest = [g for g in out if g['kind'] not in ('signin', 'account', 'email_code')]
    if sites:
        rows = sorted(sites.values(), key=lambda g: -g['count'])
        jobs_n = sum(g['count'] for g in rows)
        sec = {"key": 'sites', "kind": 'sites', "site": '', "count": jobs_n, "sites": rows, "entries": [],
               "title": f"Sign in to {len(rows)} site{'s' if len(rows) > 1 else ''}" if len(rows) > 1 else rows[0]['title'],
               "detail": (f"{jobs_n} application{'s' if jobs_n > 1 else ''} stopped at a sign-in. Signing in for you is on now: press "
                          "Finish on a site and your twin signs in (or makes the account) and finishes every job there."
                          if accounts_status(check_google=False)['enabled'] else
                          f"{jobs_n} application{'s' if jobs_n > 1 else ''} are filled up to a sign-in. Sign in once per site in your "
                          "twin's browser and it finishes every job there, or turn on Sign in and create accounts for me in Settings.")}
        rest.insert(next((i for i, g in enumerate(rest) if g['kind'] not in ('question', 'ready')), len(rest)), sec)
    return rest


def inbox(include_resolved=False):
    sql = 'select * from inbox' + ('' if include_resolved else ' where resolved is null') + ' order by at desc limit 200'
    return store.rows(sql)


def resolve(item_id):
    _todo_cache['v'] = None
    store.execute('update inbox set resolved=? where id=?', (time.time(), int(item_id)))
    return {"ok": True}


def pending_jobs():
    """Jobs your agent stopped on (Needs User) that are not finished yet: come back to these after the user acts."""
    release_claims(older_than=store.CLAIM_TTL)
    # anything logged after it (Applied, Skipped, Failed, or an outcome like Rejected the user recorded) means it's finished
    rows = store.rows("select a.job_id, a.company, a.title, a.url, a.notes, a.at from applications a where a.status='Needs User' and "
                      "not exists (select 1 from applications b where b.job_id=a.job_id and ((b.at>a.at and b.status!='Needs User') or "
                      "b.status in ('Applied','Interview','OA','Offer','Rejected'))) "
                      "order by a.at desc")
    seen, out = set(), []
    for r in rows:
        if r['job_id'] not in seen:
            seen.add(r['job_id'])
            out.append(r)
    return out


def needs_you():
    """Everything waiting on the user, batched so each thing is done once: one sign-in per site unblocks all of that site's
    applications, one Answers-page visit covers every question. Groups are ordered by how many applications they unblock."""
    groups = {}
    for r in pending_jobs():
        cat = blockers.classify(r.get('notes'))
        h = blockers.host(r.get('url'))
        key = (cat, h if cat in ('signin', 'account', 'email_code') else '')
        g = groups.setdefault(key, {"blocker": cat, "label": blockers.LABELS.get(cat, cat), "site": key[1], "jobs": []})
        g['jobs'].append({"job_id": r['job_id'], "company": r['company'], "title": r['title'], "url": r['url'],
                          "notes": (r.get('notes') or '')[:240]})
    out = []
    for g in sorted(groups.values(), key=lambda g: -len(g['jobs'])):
        g['count'] = len(g['jobs'])
        g['action'] = blockers.ACTIONS.get(g['blocker'], 'Open each one and finish it ({n}).').format(host=g['site'] or 'the site', n=g['count'])
        out.append(g)
    return {"total": sum(g['count'] for g in out), "groups": out,
            "how": "After the user handles a group (e.g. signs in to a site), finish that group's jobs with finish_jobs / "
                   "applytwin_pending_jobs: each continues where it stopped (applytwin_get_job shows resume_from)."}


def finish_site(site, submit=False, agent=None):
    """The user signed in to one site: continue every application that was waiting on it, in one run."""
    ids = [j['job_id'] for g in needs_you()['groups'] if g['site'] == site for j in g['jobs']]
    if not ids:
        return {"done": True, "note": f"Nothing is waiting on {site}."}
    store.execute('update inbox set resolved=? where resolved is null and job_id in (%s)' % ','.join('?' * len(ids)), (time.time(), *ids))
    return finish_jobs(ids, submit, agent)


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
        # intent first: "To apply", "Want to apply", "Not applied", "Interested" are plans, not applications
        if re.search(r"\bnot\b|n't|\bto apply|want|plan|interested|saved|wishlist|bookmark|considering|maybe|later|draft", status, re.I):
            continue   # never applied: leave it in the queue
        st = 'applied' if not status or re.search(r'appl|submit|interview|offer|reject|\boa\b|assessment|screen|ghost|declin', status, re.I) else 'skipped'
        for m in re.findall(r'(?:token=|/jobs/|/)([0-9a-f]{8}-[0-9a-f-]{27}|\d{5,})', url or ''):
            ids[m] = st
        names[role_key(company, title)] = st
        found.append({"company": company, "title": title, "url": url, "status": status or 'Applied', "source": 'tracker'})
    remember_applied(found)
    n = 0
    for j in store.rows("select id, company, title, url, apply_url from jobs where status='new'"):
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
    added = [0]

    def add(cur):
        seen = {role_key(r['company'], r['title']) for r in cur}
        for it in items or []:
            c, t = (it.get('company') or '').strip(), (it.get('title') or '').strip()
            if not c or not t or role_key(c, t) in seen:
                continue
            seen.add(role_key(c, t))
            cur.append({"company": c, "title": t, "url": it.get('url') or '', "status": it.get('status') or 'Applied',
                        "date": it.get('date') or '', "source": it.get('source') or 'import', "at": time.time()})
            added[0] += 1
    store.update('applied_elsewhere.json', add, [])   # the email-history run and a CSV import can write at once
    return added[0]


def import_applied(items, source='email'):
    """What your agent found (e.g. confirmation emails): [{company, title, url?, date?, status?}]. Remembered forever and
    applied to the current queue, so none of these roles is applied to again."""
    added = remember_applied([{**i, "source": source} for i in items or []])
    done, ids = done_roles(), done_url_ids()
    n = 0
    for j in store.rows("select id, company, title, url, apply_url from jobs where status='new'"):
        if already_done(j, done, ids):
            store.execute("update jobs set status='applied' where id=?", (j['id'],))
            n += 1
    return {"added": added, "known": len(applied_elsewhere()), "matched_in_queue": n}


def email_history_prompt():
    return ("Use the applytwin-history skill. Find every job I already applied to by reading my email in your browser, and "
            "record them with applytwin_import_applied so ApplyTwin never applies to them again. Use the Playwright browser tools "
            "(the twin's browser), not Claude in Chrome or computer use. Open my webmail (Gmail, "
            "Outlook, or my school email; if I'm not signed in, applytwin_notify me to sign in in your browser and wait for "
            "me, never type a password). Search the last 12 months for application confirmations: \"thank you for applying\", "
            "\"application received\", \"we received your application\", \"your application was sent\" (LinkedIn), and mail from "
            "greenhouse.io, lever.co, ashbyhq.com, myworkday.com, icims.com, smartrecruiters.com, jobvite.com, workable.com. "
            "Read company and role from each (rejections and interview invites count too, with that status; skip job alerts "
            "and newsletters), and record them in batches of about 25. Only record what an email shows; never guess. "
            "Finish with how many you found.")


def rescore(force=False):
    """Re-run fit scoring on every stored job (after profile or matcher changes), no network needed. Skipped when nothing
    that scoring depends on has changed since the last time (it ran on every start, slowing the app for seconds)."""
    import hashlib
    from . import ats
    prof = store.profile()
    vt = ats.resume_text(store.resume())
    terms = {t for t, pat in ats.PATTERNS.items() if pat.search(vt)}
    here = os.path.dirname(os.path.abspath(__file__))
    code = b''.join(open(os.path.join(here, f), 'rb').read() for f in ('match.py', 'sources.py'))
    keys = ('search', 'grad_year', 'grad_month', 'needs_sponsorship', 'citizenship', 'school', 'earliest_start', 'class_standing', 'degree')
    mark = hashlib.sha1(json.dumps([{k: prof.get(k) for k in keys}, sorted(terms)], sort_keys=True, default=str).encode() + code).hexdigest()
    if not force and (store.load('rescore.json', {}) or {}).get('mark') == mark:
        return {"rescored": 0, "unchanged": True}
    n = 0
    with store.db() as con:
        for j in [dict(r) for r in con.execute('select * from jobs')]:
            name = sources.clean_company(j['company'])   # older scans kept tracker decorations like '🔥 Tesla'
            if name and name != j['company']:
                j['company'] = name
                con.execute('update jobs set company=? where id=?', (name, j['id']))
            f, why = match.fit(j, prof, terms)
            if j.get('source') == 'manual':   # a job you added yourself stays in your queue, whatever the matcher thinks
                f, why = max(f, prof['search'].get('min_fit', 65) + 10), why or 'added by you'
            con.execute('update jobs set fit=?, fit_why=? where id=?', (f, why, j['id']))
            n += 1
    store.save('rescore.json', {"mark": mark, "at": time.time()})
    return {"rescored": n}
