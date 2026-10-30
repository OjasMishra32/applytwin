"""Local storage. Everything lives in APPLYTWIN_HOME (default ~/.applytwin) so the user owns their data.

profile.json   who you are + preferences (filters, caps, auto-submit policy)
resume.json    your master resume, structured (see examples/resume.example.json)
answers.json   your application-question answer bank
applytwin.db        jobs found by the scrapers + applications you sent
"""
import copy
import json
import os
import sqlite3
import threading
import time

HOME = os.environ.get('APPLYTWIN_HOME') or os.path.expanduser('~/.applytwin')
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_lock = threading.Lock()


def path(*parts):
    os.makedirs(HOME, exist_ok=True)
    return os.path.join(HOME, *parts)


DEFAULT_PROFILE = {   # nothing about the person is assumed: unanswered fields stay blank and the user is asked
    "name": "", "email": "", "phone": "", "location": "", "linkedin": "", "github": "", "website": "",
    "school": "", "degree": "", "major": "", "minor": "", "gpa": "",
    "grad_month": "", "grad_year": "", "start_year": "", "class_standing": "",
    "work_authorized_us": None, "needs_sponsorship": None, "citizenship": "",
    "willing_to_relocate": None, "onsite_ok": None, "earliest_start": "",
    "over_18": None, "background_check_ok": None, "has_noncompete": None, "government_employee": None,
    "salary_expectation": "", "sms_ok": None, "ai_review_ok": None,
    "eeo": {"gender": "", "race": "", "hispanic": "", "veteran": "", "disability": "", "pronouns": ""},
    "search": {
        "kind": "",                                 # internship | co-op | new-grad | full-time (asked in setup)
        "season": "",                               # one or more terms, e.g. "Summer 2027, Fall 2027"
        "roles": [], "arrangement": [],
        "include": [], "exclude": ["phd", "mba", "master", "senior", "staff", "principal", "manager"],
        "locations": [],
        "min_fit": 65,
        "companies_priority": [], "companies_skip": [],
    },
    "apply": {
        "auto_submit": False,                       # False = agent fills, you click Submit
        "daily_limit": 40,
        "per_company_cap": 3,
        "tailor_every_resume": True,
        "template": "classic",
        "stop_on": ["password", "captcha", "arbitration", "essay>150 words", "assessment"],
        "email_codes": "notify",                    # notify = ping you; agent = your agent reads the code from your email
        "notify_desktop": True,
    },
}

DEFAULT_RESUME = {
    "basics": {"name": "", "email": "", "phone": "", "location": "", "links": [], "headline": []},
    "education": [], "experience": [], "projects": [], "research": [], "leadership": [],
    "skills": [], "awards": [], "certifications": [], "volunteering": [],
    "order": ["education", "experience", "projects", "research", "leadership", "volunteering", "skills", "certifications", "awards"],
}


def _merge(base, over):
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load(name, default=None):
    p = path(name)
    if not os.path.exists(p):
        return copy.deepcopy(default)
    with open(p) as f:
        data = json.load(f)
    return _merge(default, data) if isinstance(default, dict) else data


def save(name, obj):
    with _lock:
        tmp = path(name + '.tmp')
        with open(tmp, 'w') as f:
            json.dump(obj, f, indent=1, ensure_ascii=False)
        os.replace(tmp, path(name))
    return obj


def next_summer():
    """The internship cycle students are recruiting for right now (from August on, it's next summer)."""
    t = time.gmtime()
    return t.tm_year + (1 if t.tm_mon >= 8 else 0)


def profile():
    p = load('profile.json', DEFAULT_PROFILE)
    p.setdefault('search', {})
    return p


def resume():
    return load('resume.json', DEFAULT_RESUME)


def answers():
    """Profile-backed answers always come from the current profile (so a Settings change reaches every form), then
    anything you wrote or edited yourself on top."""
    from . import answers as ans
    base = ans.default_bank(profile())
    saved = load('answers.json', None) or []
    mine = {r.get('key'): r for r in saved if r.get('source') == 'user' and r.get('key')}
    out = [mine.pop(r['key'], r) for r in base]
    keys = {r['key'] for r in base}
    return out + [r for r in saved if r.get('key') not in keys and r.get('source') == 'user'] + list(mine.values())


def companies():
    """Built-in boards + your own additions + boards discovered from job trackers (all merged, so updates reach everyone)."""
    with open(os.path.join(APP, 'data', 'companies.json')) as f:
        out = json.load(f)
    for extra in (path('companies.json'), path('discovered.json')):
        if os.path.exists(extra):
            try:
                for k, v in json.load(open(extra)).items():
                    out[k] = list(dict.fromkeys(out.get(k, []) + v))
            except (ValueError, OSError):
                pass
    return out


SCHEMA = """
create table if not exists jobs(
  id text primary key, source text, company text, title text, location text,
  url text, apply_url text, ats text, posted text, description text,
  found_at real, fit real default 0, fit_why text, status text default 'new');
create index if not exists jobs_status on jobs(status);
create table if not exists applications(
  id integer primary key autoincrement, job_id text, company text, title text, url text,
  status text, resume_path text, notes text, at real);
create table if not exists claims(job_id text primary key, who text, at real);
create table if not exists inbox(id integer primary key autoincrement, kind text, title text, message text, url text, job_id text,
  at real, resolved real);
"""


def db():
    con = sqlite3.connect(path('applytwin.db'), timeout=30)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def rows(sql, args=()):
    with db() as con:
        return [dict(r) for r in con.execute(sql, args)]


def execute(sql, args=()):
    with _lock, db() as con:
        cur = con.execute(sql, args)
        return cur.rowcount


def log_application(job_id, status, notes='', resume_path=''):
    j = (rows('select * from jobs where id=?', (job_id,)) or [{}])[0]
    execute('insert into applications(job_id,company,title,url,status,resume_path,notes,at) values(?,?,?,?,?,?,?,?)',
            (job_id, j.get('company', ''), j.get('title', ''), j.get('apply_url') or j.get('url', ''),
             status, resume_path, notes, time.time()))
    execute('update jobs set status=? where id=?', (status.lower(), job_id))
    return {"ok": True, "job": j.get('title'), "company": j.get('company'), "status": status}


def claim(job_id, who='agent'):
    """Atomic claim so two parallel agents never apply to the same job."""
    with _lock, db() as con:
        try:
            con.execute('insert into claims(job_id,who,at) values(?,?,?)', (job_id, who, time.time()))
            return True
        except sqlite3.IntegrityError:
            return False


def applied_count_today():
    start = time.time() - 86400
    return rows("select count(*) n from applications where status='Applied' and at>?", (start,))[0]['n']


def company_count(company):
    from .match import company_key
    k = company_key(company)
    return sum(r['n'] for r in rows("select company, count(*) n from applications where status='Applied' group by company")
               if company_key(r['company']) == k)
