"""Job scrapers. Every source is a public, no-login endpoint, so scanning never touches anyone's account.

  greenhouse       boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true
  lever            api.lever.co/v0/postings/{company}?mode=json
  ashby            api.ashbyhq.com/posting-api/job-board/{org}
  smartrecruiters  jobs.smartrecruiters.com/sr-jobs/search  (live feed of every company, newest first)
  workday          {tenant}.{wdN}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs  (POST)
  community lists  SimplifyJobs / vanshb03 internship listings.json on GitHub
"""
import hashlib
import html
import json
import re
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

from . import store

UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36'

COMMUNITY_LISTS = [
    'https://raw.githubusercontent.com/SimplifyJobs/Summer2027-Internships/dev/.github/scripts/listings.json',
    'https://raw.githubusercontent.com/SimplifyJobs/Summer2026-Internships/dev/.github/scripts/listings.json',
    'https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/dev/.github/scripts/listings.json',
    'https://raw.githubusercontent.com/vanshb03/Summer2027-Internships/dev/.github/scripts/listings.json',
]


def get(url, data=None, timeout=20):
    headers = {'User-Agent': UA, 'Accept': 'application/json'}
    body = None
    if data is not None:
        body = json.dumps(data).encode()
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8', 'replace'))


def strip_html(s):
    s = html.unescape(s or '')
    s = re.sub(r'<(br|/p|/li|/h\d)[^>]*>', '\n', s, flags=re.I)
    s = re.sub(r'<li[^>]*>', '\n- ', s, flags=re.I)
    s = re.sub(r'<[^>]+>', ' ', s)
    s = html.unescape(s)
    return re.sub(r'[ \t\r\f\v]+', ' ', re.sub(r'\n\s*\n+', '\n', s)).strip()


def jid(source, key):
    return source[:2] + '_' + hashlib.sha1(f'{source}:{key}'.encode()).hexdigest()[:12]


CO_NOISE = re.compile(r"\s*(?:[-|:(]\s*)?\b(?:early\s*careers?|careers?(?:'s)?\s*page|careers?|campus(?:\s*recruiting)?|university(?:\s*(?:job|recruiting))?s?|"
                      r"internships?|interns?|student\s*programs?|recruiting|jobs?)\b\)?\s*$", re.I)


def clean_company(name):
    n = (name or '').strip()
    for _ in range(3):
        n2 = CO_NOISE.sub('', n).strip(' -|:')
        if n2 == n or not n2:
            break
        n = n2
    if n and n == n.lower():  # board slugs like "notion", "bedrock-robotics"
        n = ' '.join(w.capitalize() for w in re.split(r'[-_]+', n))
    return n


def job(source, key, company, title, location, url, apply_url=None, posted='', description='', ats=None):
    return {"id": jid(source, key), "source": source, "company": clean_company(company), "title": (title or '').strip(),
            "location": (location or '').strip(), "url": url, "apply_url": apply_url or url,
            "ats": ats or source, "posted": posted or '', "description": description or ''}


def greenhouse(token):
    d = get(f'https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true')
    name = token
    try:
        name = get(f'https://boards-api.greenhouse.io/v1/boards/{token}').get('name') or token
    except Exception:
        pass
    for j in d.get('jobs', []):
        yield job('greenhouse', j['id'], name, j.get('title'), (j.get('location') or {}).get('name', ''),
                  j.get('absolute_url'), f'https://job-boards.greenhouse.io/embed/job_app?for={token}&token={j["id"]}',
                  j.get('updated_at', ''), strip_html(j.get('content', '')))


def lever(company):
    for j in get(f'https://api.lever.co/v0/postings/{company}?mode=json'):
        cat = j.get('categories') or {}
        desc = (j.get('descriptionPlain') or '') + '\n' + '\n'.join(
            f"{l.get('text', '')}\n{strip_html(l.get('content', ''))}" for l in j.get('lists', []))
        yield job('lever', j['id'], company, j.get('text'), cat.get('location', ''), j.get('hostedUrl'),
                  j.get('applyUrl'), time.strftime('%Y-%m-%d', time.gmtime((j.get('createdAt') or 0) / 1000)), desc)


def ashby(org):
    d = get(f'https://api.ashbyhq.com/posting-api/job-board/{org}?includeCompensation=true')
    for j in d.get('jobs', []):
        if not j.get('isListed', True):
            continue
        yield job('ashby', j['id'], org, j.get('title'), j.get('location', ''), j.get('jobUrl'),
                  j.get('applyUrl') or (j.get('jobUrl', '') + '/application'), j.get('publishedAt', ''),
                  j.get('descriptionPlain') or strip_html(j.get('descriptionHtml', '')))


def smartrecruiters_feed(keywords=('intern', 'internship', 'co-op', 'new grad', 'software engineer')):
    seen = set()
    for kw in keywords:
        d = get('https://jobs.smartrecruiters.com/sr-jobs/search?' + urllib.parse.urlencode({'keyword': kw}))
        for j in d.get('content', []):
            if j['id'] in seen:
                continue
            seen.add(j['id'])
            loc = j.get('location') or {}
            where = ', '.join(x for x in (loc.get('city'), loc.get('region'), (loc.get('country') or '').upper()) if x)
            if loc.get('remote'):
                where += ' (Remote)'
            yield job('smartrecruiters', j['id'], j['company']['name'], j.get('name'), where, j.get('applyUrl'),
                      j.get('applyUrl'), j.get('releasedDate', ''), '')


def smartrecruiters_company(company):
    d = get(f'https://api.smartrecruiters.com/v1/companies/{company}/postings?limit=100')
    for j in d.get('content', []):
        loc = j.get('location') or {}
        yield job('smartrecruiters', j['id'], (j.get('company') or {}).get('name', company), j.get('name'),
                  loc.get('fullLocation') or loc.get('city', ''),
                  f"https://jobs.smartrecruiters.com/{company}/{j['id']}", None, j.get('releasedDate', ''))


def workday(spec, search='intern'):
    """spec = 'tenant.wd5/Site_Name', optionally '|Company Name' (tenant codes like 'ghr' or 'ms' aren't names)"""
    spec, _, name = spec.partition('|')
    host, site = spec.split('/', 1)
    tenant = host.split('.')[0]
    base = f'https://{host}.myworkdayjobs.com'
    off = 0
    while off < 200:
        d = get(f'{base}/wday/cxs/{tenant}/{site}/jobs',
                {"appliedFacets": {}, "limit": 20, "offset": off, "searchText": search})
        posts = d.get('jobPostings', [])
        for p in posts:
            url = f"{base}/en-US/{site}{p.get('externalPath', '')}"
            yield job('workday', url, name or tenant.capitalize(), p.get('title'), p.get('locationsText', ''), url,
                      url + '/apply', p.get('postedOn', ''), '')
        if len(posts) < 20:
            break
        off += 20


def community():
    out, seen = [], set()
    for url in COMMUNITY_LISTS:
        try:
            items = get(url, timeout=40)
        except Exception:
            continue
        for it in items:
            if not it.get('active', True) or not it.get('is_visible', True):
                continue
            key = it.get('url') or it.get('id')
            if key in seen:
                continue
            seen.add(key)
            locs = it.get('locations') or []
            out.append(job('community', key, it.get('company_name', ''), it.get('title', ''), '; '.join(locs[:3]),
                           it.get('url'), it.get('url'),
                           time.strftime('%Y-%m-%d', time.gmtime(it.get('date_posted') or it.get('date_updated') or 0)),
                           ' '.join(it.get('terms') or []) + ' ' + (it.get('sponsorship') or ''),
                           ats=detect_ats(it.get('url', ''))))
    return out


def detect_ats(url):
    for k, pat in (('greenhouse', 'greenhouse.io'), ('lever', 'lever.co'), ('ashby', 'ashbyhq.com'),
                   ('workday', 'myworkdayjobs.com'), ('smartrecruiters', 'smartrecruiters.com'),
                   ('icims', 'icims.com'), ('taleo', 'taleo.net'), ('oracle', 'oraclecloud.com'),
                   ('successfactors', 'successfactors'), ('eightfold', 'eightfold.ai'), ('jobvite', 'jobvite.com'),
                   ('workable', 'workable.com'), ('linkedin', 'linkedin.com')):
        if pat in (url or ''):
            return k
    return 'other'


def scan(sources=None, on_progress=None, workers=16):
    """Run every enabled source in parallel, score each job against the profile, upsert into applytwin.db."""
    from . import match
    sources = sources or ['community', 'smartrecruiters', 'greenhouse', 'lever', 'ashby', 'workday']
    comp = store.companies()
    tasks = []
    if 'community' in sources:
        tasks.append(('community', community, ()))
    if 'smartrecruiters' in sources:
        sp = store.profile()['search']
        kind = {'internship': ['intern', 'internship'], 'new-grad': ['new grad', 'entry level'], 'full-time': []}.get(sp.get('kind'), [])
        kws = tuple(dict.fromkeys(kind + [f'{r} {kind[0]}' if kind else r for r in sp.get('roles', [])[:8]] + ['co-op']))
        tasks.append(('smartrecruiters feed', lambda kws=kws: list(smartrecruiters_feed(kws)), ()))
        tasks += [(f'smartrecruiters:{c}', lambda c=c: list(smartrecruiters_company(c)), ()) for c in comp.get('smartrecruiters', [])]
    for src, fn in (('greenhouse', greenhouse), ('lever', lever), ('ashby', ashby), ('workday', workday)):
        if src in sources:
            tasks += [(f'{src}:{c}', lambda fn=fn, c=c: list(fn(c)), ()) for c in comp.get(src, [])]
    prof = store.profile()
    from . import ats, tailor
    vt = ats.resume_text(store.resume())
    vault_terms = {t for t, pat in ats.PATTERNS.items() if pat.search(vt)}
    stats = {"sources": len(tasks), "done": 0, "fetched": 0, "new": 0, "matched": 0, "errors": 0}
    now = time.time()
    with ThreadPoolExecutor(workers) as ex, store.db() as con:
        futs = {ex.submit(fn, *a): name for name, fn, a in tasks}
        for f in as_completed(futs):
            stats['done'] += 1
            try:
                jobs = f.result()
            except Exception:
                stats['errors'] += 1
                if on_progress:
                    on_progress(dict(stats))
                continue
            for j in jobs:
                stats['fetched'] += 1
                fit, why = match.fit(j, prof, vault_terms)
                cur = con.execute('select status from jobs where id=?', (j['id'],)).fetchone()
                if fit < 1:
                    if cur:
                        con.execute('update jobs set fit=0, fit_why=? where id=?', (why, j['id']))
                    continue
                if cur:
                    con.execute('update jobs set fit=?, fit_why=?, company=?, description=coalesce(nullif(?,""),description) where id=?',
                                (fit, why, j['company'], j['description'], j['id']))
                    continue
                stats['new'] += 1
                stats['matched'] += fit >= prof['search'].get('min_fit', 65)
                con.execute('insert into jobs(id,source,company,title,location,url,apply_url,ats,posted,description,found_at,fit,fit_why)'
                            ' values(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                            (j['id'], j['source'], j['company'], j['title'], j['location'], j['url'], j['apply_url'],
                             j['ats'] if j['ats'] != 'community' else detect_ats(j['apply_url']), j['posted'],
                             j['description'], now, fit, why))
            if on_progress:
                on_progress(dict(stats))
    return stats


def fetch_description(j):
    """Fill in a missing job description on demand (SmartRecruiters / Workday / community rows)."""
    if j.get('description') and len(j['description']) > 400:
        return j['description']
    url = j.get('url') or ''
    try:
        m = re.search(r'jobs\.smartrecruiters\.com/([^/]+)/(\d+)', url)
        if m:
            d = get(f'https://api.smartrecruiters.com/v1/companies/{m.group(1)}/postings/{m.group(2)}')
            secs = (d.get('jobAd') or {}).get('sections') or {}
            text = '\n'.join(strip_html((secs.get(k) or {}).get('text', '')) for k in
                             ('companyDescription', 'jobDescription', 'qualifications', 'additionalInformation'))
        elif 'myworkdayjobs.com' in url:
            m = re.match(r'https://([^/]+)/(?:[a-z]{2}-[A-Z]{2}/)?([^/]+)(/job/.+)', url)
            host, site, ext = m.groups()
            tenant = host.split('.')[0]
            d = get(f'https://{host}/wday/cxs/{tenant}/{site}{ext}')
            text = strip_html((d.get('jobPostingInfo') or {}).get('jobDescription', ''))
        else:
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=20) as r:
                raw = r.read().decode('utf-8', 'replace')
            m = re.search(r'"description"\s*:\s*"((?:[^"\\]|\\.){200,})"', raw)  # JSON-LD JobPosting
            text = strip_html(json.loads('"' + m.group(1) + '"')) if m else strip_html(raw)[:12000]
    except Exception:
        return j.get('description') or ''
    if text:
        store.execute('update jobs set description=? where id=?', (text, j['id']))
    return text
