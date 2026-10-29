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


DEFAULT_PROFILE = {
    "name": "", "email": "", "phone": "", "location": "", "linkedin": "", "github": "", "website": "",
    "school": "", "degree": "Bachelor of Science", "major": "", "minor": "", "gpa": "",
    "grad_month": "May", "grad_year": "", "start_year": "", "class_standing": "",
    "work_authorized_us": True, "needs_sponsorship": False, "citizenship": "",
    "willing_to_relocate": True, "earliest_start": "May 2027",
    "eeo": {"gender": "Decline to self-identify", "race": "Decline to self-identify",
            "hispanic": "Decline to self-identify", "veteran": "I am not a protected veteran",
            "disability": "I do not want to answer", "pronouns": ""},
    "search": {
        "kind": "internship",                       # internship | new-grad | full-time
        "season": "Summer 2027",
        "roles": ["software engineer", "machine learning", "data science", "quant"],
        "include": [], "exclude": ["phd", "mba", "master", "senior", "staff", "principal", "manager"],
        "locations": ["United States", "Remote"],
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


def profile():
    return load('profile.json', DEFAULT_PROFILE)


def resume():
    return load('resume.json', DEFAULT_RESUME)


def answers():
    from . import answers as ans
    return load('answers.json', None) or ans.default_bank(profile())


def companies():
    user = path('companies.json')
    src = user if os.path.exists(user) else os.path.join(APP, 'data', 'companies.json')
    with open(src) as f:
        return json.load(f)


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
    return rows("select count(*) n from applications where status='Applied' and lower(company)=lower(?)",
                (company,))[0]['n']
