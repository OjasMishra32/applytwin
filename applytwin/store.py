"""Local storage. Everything lives in APPLYTWIN_HOME (default ~/.applytwin) so the user owns their data.

profile.json   who you are + preferences (filters, caps, auto-submit policy)
resume.json    your master resume, structured (see examples/resume.example.json)
answers.json   your application-question answer bank
applytwin.db        jobs found by the scrapers + applications you sent
"""
import contextlib
import copy
import json
import re
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
    try:
        with open(p, encoding='utf-8-sig') as f:   # -sig: Notepad / PowerShell 5 add a byte-order mark
            data = json.load(f)
    except UnicodeDecodeError:   # written by an older version in the Windows code page; read it once, save as UTF-8
        with open(p, encoding='cp1252', errors='replace') as f:
            data = json.load(f)
        save(name, data)
    except ValueError:   # damaged (a crash mid-write on an old version): keep a copy aside and carry on with the default
        try:
            os.replace(p, f"{p}.damaged-{time.strftime('%Y%m%d-%H%M%S')}")
        except OSError:
            pass
        return copy.deepcopy(default)
    return _merge(default, data) if isinstance(default, dict) else data


def replace(src, dst, tries=6):
    """os.replace that waits out Windows' share lock: another process (the app, the agent's MCP server) reading the
    target at that instant makes the replace fail with PermissionError for a few milliseconds."""
    for i in range(tries):
        try:
            return os.replace(src, dst)
        except PermissionError:
            if i == tries - 1:
                raise
            time.sleep(0.05)


def kill_tree(p):
    """Stop a child process and everything it started. On Windows, killing a .cmd wrapper (npm's claude.cmd) or Chrome
    leaves node.exe / Chrome's helpers running and holding pipes and folders open."""
    import subprocess
    if p.poll() is not None:
        return
    if os.name == 'nt':
        subprocess.run(['taskkill', '/F', '/T', '/PID', str(p.pid)], capture_output=True, **NOWIN)
    else:
        p.kill()


def _has_content(v):
    return bool(isinstance(v, dict) and (v.get('experience') or v.get('projects') or v.get('education') or v.get('research')))


def backup_vault():
    """Keep the vault as it is right now (the last 30 versions) before anything replaces it: a stale editor tab or a bad
    import must never be able to lose someone's resume."""
    cur = path('resume.json')
    if not os.path.exists(cur):
        return
    try:
        old = json.load(open(cur, encoding='utf-8'))
    except (OSError, ValueError):
        return
    if not _has_content(old):
        return
    d = path('backups')
    os.makedirs(d, exist_ok=True)
    import shutil
    shutil.copy2(cur, os.path.join(d, time.strftime('resume-%Y%m%d-%H%M%S.json')))
    keep = sorted(f for f in os.listdir(d) if f.startswith('resume-'))
    for f in keep[:-30]:
        try:
            os.remove(os.path.join(d, f))
        except OSError:
            pass


def backup_file(name):
    """A copy of any data file (profile, answers, learnings) in backups/ before something replaces it (last 30 kept)."""
    if name == 'resume.json':
        return backup_vault()
    cur = path(name)
    if not os.path.exists(cur):
        return
    import shutil
    d = path('backups')
    os.makedirs(d, exist_ok=True)
    stem = os.path.splitext(name)[0]
    shutil.copy2(cur, os.path.join(d, stem + time.strftime('-%Y%m%d-%H%M%S.json')))
    for f in sorted(f for f in os.listdir(d) if f.startswith(stem + '-'))[:-30]:
        try:
            os.remove(os.path.join(d, f))
        except OSError:
            pass


@contextlib.contextmanager
def quiet_pypdf():
    """pypdf logs "EOF marker not found" and the like for every damaged PDF it's handed; callers report those themselves."""
    import logging
    lg = logging.getLogger('pypdf')
    old = lg.level
    lg.setLevel(logging.CRITICAL)
    try:
        yield
    finally:
        lg.setLevel(old)


def vault_backups():
    d = path('backups')
    out = []
    for f in sorted(os.listdir(d), reverse=True) if os.path.isdir(d) else []:
        if f.startswith('resume-'):
            try:
                v = json.load(open(os.path.join(d, f), encoding='utf-8'))
                out.append({"file": f, "at": os.path.getmtime(os.path.join(d, f)),
                            "experience": len(v.get('experience', [])), "projects": len(v.get('projects', []))})
            except (OSError, ValueError):
                continue
    return out


def save(name, obj):
    import tempfile
    if name == 'resume.json':
        backup_vault()
    with _lock:
        # a temp file of its own: the app, the agent's MCP server and the CLI all save, sometimes at the same moment
        fd, tmp = tempfile.mkstemp(prefix='.' + os.path.basename(name) + '.', suffix='.tmp', dir=os.path.dirname(path(name)))
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(obj, f, indent=1, ensure_ascii=False)
            replace(tmp, path(name))
        except BaseException:
            try:
                os.remove(tmp)
            except OSError:
                pass
            raise
    return obj


class file_lock:
    """A lock shared by every ApplyTwin process (app, MCP server, CLI), for read-modify-write of a JSON file."""
    def __init__(self, name):
        self.p = path(name + '.lock')

    def __enter__(self):
        self.f = open(self.p, 'a+', encoding='utf-8')
        if os.name == 'nt':
            import msvcrt
            import time
            while True:
                try:
                    self.f.seek(0)
                    msvcrt.locking(self.f.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    time.sleep(0.05)
        else:
            import fcntl
            fcntl.flock(self.f.fileno(), fcntl.LOCK_EX)
        return self

    def __exit__(self, *a):
        try:
            if os.name == 'nt':
                import msvcrt
                self.f.seek(0)
                msvcrt.locking(self.f.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.f.fileno(), fcntl.LOCK_UN)
        finally:
            self.f.close()


def update(name, fn, default=None):
    """Read a JSON file, change it with fn, write it back, with no other process able to interleave."""
    with file_lock(name):
        cur = load(name, copy.deepcopy(default))
        new = fn(cur)
        save(name, cur if new is None else new)
        return cur if new is None else new


def next_summer():
    """The internship cycle students are recruiting for right now (from August on, it's next summer)."""
    t = time.gmtime()
    return t.tm_year + (1 if t.tm_mon >= 8 else 0)


def profile():
    p = load('profile.json', DEFAULT_PROFILE)
    p.setdefault('search', {})
    return p


LIST_FIELDS = ('bullets', 'tech', 'alts', 'coursework', 'items', 'links', 'headline', 'honors')


def clean(x):
    """Resume data from any importer or model, made safe to render: null text becomes '', null lists become [], numbers
    (a GPA of 3.86) become text, and a list that arrived as one comma-separated string is split."""
    if isinstance(x, dict):
        out = {}
        for k, v in x.items():
            if k in LIST_FIELDS:
                if v is None:
                    v = []
                elif isinstance(v, str):
                    v = [s.strip() for s in re.split(r'[,;]\s*' if k != 'bullets' else r'\n+', v) if s.strip()]
                out[k] = [clean(i) for i in v if i not in (None, '')] if isinstance(v, list) else v
            else:
                out[k] = clean(v)
        return out
    if isinstance(x, list):
        return [clean(i) for i in x if i is not None]
    if x is None:
        return ''
    if isinstance(x, bool):
        return x
    if isinstance(x, (int, float)):
        return ('%.2f' % x).rstrip('0').rstrip('.') if isinstance(x, float) and x != int(x) else (('%.1f' % x) if isinstance(x, float) else str(x))
    return x


def resume():
    return clean(load('resume.json', DEFAULT_RESUME))


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
    with open(os.path.join(APP, 'data', 'companies.json'), encoding='utf-8') as f:
        out = json.load(f)
    for extra in (path('companies.json'), path('discovered.json')):
        if os.path.exists(extra):
            try:
                for k, v in json.load(open(extra, encoding='utf-8')).items():
                    out[k] = list(dict.fromkeys(out.get(k, []) + v))
            except (ValueError, OSError):
                pass
    return out


# Windows: start helper programs without a console window (the app runs in the background with pythonw; a window would
# flash up, and closing it would kill an Autopilot run)
NOWIN = {'creationflags': 0x08000000} if os.name == 'nt' else {}


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
create table if not exists thread(id integer primary key autoincrement, job_id text, role text, text text, at real);
create index if not exists thread_job on thread(job_id);
"""


_ready = set()   # database files whose schema and journal mode are set up in this process


@contextlib.contextmanager
def db():
    """A connection for one block: commits (or rolls back) and always CLOSES at the end. sqlite3's own `with con:` only
    commits, so every request used to leave a connection (two open files with WAL) behind until the app hit the
    open-file limit and every page failed with "Too many open files"."""
    f = path('applytwin.db')
    con = sqlite3.connect(f, timeout=30)
    try:
        con.row_factory = sqlite3.Row
        if f not in _ready:
            try:   # readers never wait for a writer (a scan or rescore used to freeze every page for seconds)
                con.execute('pragma journal_mode=wal')
            except sqlite3.Error:
                pass
            con.executescript(SCHEMA)
            _ready.add(f)
        with con:
            yield con
    finally:
        con.close()


def rows(sql, args=()):
    with db() as con:
        return [dict(r) for r in con.execute(sql, args)]


def execute(sql, args=()):
    with _lock, db() as con:
        cur = con.execute(sql, args)
        return cur.rowcount


STATUSES = {'applied': 'Applied', 'submitted': 'Applied', 'complete': 'Applied', 'completed': 'Applied', 'done': 'Applied',
            'needs user': 'Needs User', 'needs_user': 'Needs User', 'needs you': 'Needs User', 'blocked': 'Needs User',
            'skipped': 'Skipped', 'skip': 'Skipped', 'failed': 'Failed', 'error': 'Failed', 'interview': 'Interview',
            'oa': 'OA', 'offer': 'Offer', 'rejected': 'Rejected'}
# agents write statuses many ways ("needs-user", "Skipped - grad window", "Ready to submit", "Online assessment")
STATUS_WORDS = [(r'\bneeds?\b|blocked|waiting|\bready\b|pending|manual', 'Needs User'),
                (r'skip|ineligible|not eligible|duplicate|already applied|closed|no longer|not appl', 'Skipped'), (r'fail|error|crash', 'Failed'),
                (r'reject|declin|not selected|not moving forward', 'Rejected'), (r'interview|phone screen|superday', 'Interview'),
                (r'\boa\b|online assessment|assessment|hackerrank|codesignal', 'OA'), (r'offer', 'Offer'), (r'appl(y|ied)|submit', 'Applied')]
OUTCOMES = ('Applied', 'Interview', 'OA', 'Offer', 'Rejected')   # it was submitted


def normalize_status(status, notes=''):
    """(canonical status, notes). A reason written into the status ("Skipped - grad window") moves into the notes."""
    raw = (status or 'Applied').strip()
    key = re.sub(r'[\s_-]+', ' ', raw.lower()).strip()
    if key in STATUSES:
        return STATUSES[key], notes
    parts = re.split(r'\s*[:(–—,]\s*|\s+-\s+', raw, maxsplit=1)
    head = re.sub(r'[\s_-]+', ' ', parts[0].lower()).strip()
    st = STATUSES.get(head) or next((s for pat, s in STATUS_WORDS if re.search(pat, key)), raw[:40])
    if head in STATUSES:
        rest = parts[1].strip(' -:()–—,') if len(parts) > 1 else ''
    else:   # the whole phrase is the reason ("Not eligible - grad window")
        rest = raw if st != raw[:40] else ''
    if st == 'Needs User' and re.search(r'\bready\b', key) and 'ready to submit' not in (notes or '').lower():
        rest = 'ready to submit' + ('; ' + rest if rest and not re.search(r'\bready\b', rest.lower()) else '')
    return st, '; '.join(x for x in (rest, notes) if x)


# what counts toward the daily limit and per-company cap: submitted, plus filled and waiting only for your Submit click
# (unless it was skipped or failed after that)
COUNTED = ("(status='Applied' or (status='Needs User' and lower(coalesce(notes,'')) like '%ready to submit%' and not exists ("
           "select 1 from applications later where later.job_id=applications.job_id and later.at>applications.at "
           "and later.status in ('Skipped','Failed'))))")


def latest_status(job_id):
    return (rows('select status, notes, at from applications where job_id=? order by at desc, id desc limit 1', (job_id,)) or [None])[0]


def log_application(job_id, status, notes='', resume_path='', agent=False, company='', title=''):
    status, notes = normalize_status(status, notes or '')
    if agent and status in ('Needs User', 'Skipped', 'Failed'):
        # an agent re-opening a submitted application (a refill, a duplicate posting) never turns it back into "not applied"
        last = latest_status(job_id)
        if last and last['status'] in OUTCOMES:
            return {"ok": False, "status": last['status'], "note": f"Already {last['status']} on "
                    f"{time.strftime('%Y-%m-%d', time.localtime(last['at']))}; kept. Never submit this one again."}
    j = (rows('select * from jobs where id=?', (job_id,)) or [{}])[0]
    if not j:   # not in the job list (added elsewhere, or removed since): the caller's names, else its last application's
        prev = (rows('select company, title, url from applications where job_id=? order by at desc, id desc limit 1', (job_id,)) or [{}])[0]
        j = {'company': company or prev.get('company') or '', 'title': title or prev.get('title') or '', 'url': prev.get('url') or ''}
        if not (j['company'] or j['title']):
            raise RuntimeError(f"ApplyTwin doesn't know job {job_id}. Add it first, or send its company and title with the log.")
    execute('insert into applications(job_id,company,title,url,status,resume_path,notes,at) values(?,?,?,?,?,?,?,?)',
            (job_id, j.get('company', ''), j.get('title', ''), j.get('apply_url') or j.get('url', ''),
             status, resume_path, notes, time.time()))
    execute('update jobs set status=? where id=?', (status.lower(), job_id))
    execute('delete from claims where job_id=?', (job_id,))   # logged: the claim did its job
    if status in ('Applied', 'Skipped'):   # nothing left for the user to do on this one
        execute('update inbox set resolved=? where job_id=? and resolved is null', (time.time(), job_id))
    return {"ok": True, "job": j.get('title'), "company": j.get('company'), "status": status}


CLAIM_TTL = 3 * 3600   # a claim nobody logged in this long belongs to a session that died


def claim(job_id, who='agent'):
    """Atomic claim so two parallel agents never apply to the same job. The same Autopilot run claiming again keeps it
    (interactive sessions all claim as 'agent', so for them a second claim is refused)."""
    with _lock, db() as con:
        try:
            con.execute('insert into claims(job_id,who,at) values(?,?,?)', (job_id, who, time.time()))
            return True
        except sqlite3.IntegrityError:
            if who and who != 'agent':
                return con.execute('update claims set at=? where job_id=? and who=?', (time.time(), job_id, who)).rowcount > 0
            return False


def live_claims(company=None):
    """Claims still being worked on (not logged yet, not stale): they count toward today's limit and the company cap, so
    parallel agents can't all pass the check at once."""
    rs = rows('select c.job_id, j.company from claims c left join jobs j on j.id=c.job_id where c.at>? and not exists '
              '(select 1 from applications a where a.job_id=c.job_id and a.at>=c.at)', (time.time() - CLAIM_TTL,))
    if company is None:
        return len(rs)
    from .match import company_key
    k = company_key(company)
    return sum(1 for r in rs if company_key(r['company'] or '') == k)


def applied_count_today():
    start = time.time() - 86400
    return rows(f"select count(distinct job_id) n from applications where {COUNTED} and at>?", (start,))[0]['n']


CYCLE_SECS = 270 * 86400   # one recruiting cycle (~9 months): last season's applications don't use up this season's cap


def company_counts():
    """company key -> applications that count toward its cap in the current recruiting cycle."""
    from .match import company_key
    out = {}
    for r in rows(f"select company, count(distinct job_id) n from applications where {COUNTED} and at>? group by company",
                  (time.time() - CYCLE_SECS,)):
        k = company_key(r['company'] or '')
        out[k] = out.get(k, 0) + r['n']
    return out


def company_count(company):
    from .match import company_key
    return company_counts().get(company_key(company or ''), 0)
