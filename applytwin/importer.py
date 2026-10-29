"""Import any resume (PDF, DOCX, LaTeX, TXT/MD, pasted LinkedIn text) into the Career Vault.

Works with no AI at all: a section/entry/bullet parser that handles the usual resume shapes. If an API key is
set it asks the model to structure it instead (better), and an agent can always refine it from the dump.
"""
import base64
import io
import json
import os
import re
import zipfile

from . import store

HEAD = {
    'education': r'education|academic', 'experience': r'(work |professional |relevant )?experience|employment|work history|internships?',
    'projects': r'projects?|personal projects|selected projects|projects and competitions|portfolio',
    'research': r'research|publications?|papers', 'leadership': r'leadership|activities|extracurricular|involvement|organizations',
    'volunteering': r'volunteer(ing)?( experience)?|community service', 'skills': r'(technical )?skills|technologies|tools|languages and tools',
    'awards': r'awards?|honors?|achievements|awards and honors', 'certifications': r'certifications?|licenses?( and certifications)?',
    'summary': r'summary|profile|objective|about( me)?',
}
MONTH = r'(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?'
DATE = rf'(?:{MONTH}\s+)?(?:19|20)\d\d|present|current|now'
RANGE = re.compile(rf'({DATE})\s*(?:-|–|—|to|until)\s*({DATE})', re.I)
ONE = re.compile(rf'\b({MONTH}\s+(?:19|20)\d\d|(?:19|20)\d\d)\b', re.I)
BULLET = re.compile(r'^\s*(?:[•●▪◦‣∙·\-\*–]|\d+[.)])\s+')
EMAIL = re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+')
PHONE = re.compile(r'(?:\+?\d{1,2}[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}')
URL = re.compile(r'(?:https?://)?(?:www\.)?(?:linkedin\.com/in/[\w-]+|github\.com/[\w-]+|[\w-]+\.(?:me|dev|io|com|org|net|ai|app)(?:/[\w./-]*)?)', re.I)


def extract_text(name='', data=None, text=None):
    if text:
        return text, None
    raw = base64.b64decode(data or '')
    low = (name or '').lower()
    if low.endswith('.pdf') or raw[:4] == b'%PDF':
        try:
            from pypdf import PdfReader
            return '\n'.join(p.extract_text() or '' for p in PdfReader(io.BytesIO(raw)).pages), None
        except ImportError:
            import shutil
            import subprocess
            import tempfile
            if shutil.which('pdftotext'):
                with tempfile.NamedTemporaryFile(suffix='.pdf') as f:
                    f.write(raw)
                    f.flush()
                    return subprocess.run(['pdftotext', '-layout', f.name, '-'], capture_output=True, text=True).stdout, None
            raise RuntimeError('Reading PDFs needs pypdf: run  python3 -m pip install pypdf  (or paste the text instead)')
    if low.endswith('.docx') or raw[:2] == b'PK':
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            x = z.read('word/document.xml').decode('utf8', 'replace')
        x = re.sub(r'</w:p>', '\n', x)
        return re.sub(r'<[^>]+>', '', x), None
    s = raw.decode('utf8', 'replace')
    if low.endswith('.tex') or '\\documentclass' in s:
        return tex_to_text(s), s
    return s, None


def tex_to_text(s):
    s = s[s.find('\\begin{document}'):] if '\\begin{document}' in s else s
    s = re.sub(r'(?m)(?<!\\)%.*$', '', s)
    s = re.sub(r'\\begin\{[^}]*\}(\[[^\]]*\])?|\\end\{[^}]*\}', '\n', s)
    s = re.sub(r'\\par\b|\\\\(\[[^\]]*\])?|\\newline\b', '\n', s)
    s = re.sub(r'\\sep\b|\$\|\$|\\textbar\{\}', ' | ', s)
    s = re.sub(r'\{\\bfseries\s+([^{}]*)\}', r'**\1**', s)
    for _ in range(3):
        s = re.sub(r'\\textbf\{([^{}]*)\}', r'**\1**', s)
        s = re.sub(r'\\href\{([^{}]*)\}\{([^{}]*)\}', r'[\2](\1)', s)

    def entry(m):  # any \macro{a}{b}{c}{d} entry heading (resumeSubheading, custom \job, \project...)
        a = re.findall(r'\{([^{}]*)\}', m.group(1))
        if len(a) >= 4:
            return f'\n{a[0]} | {a[3]}\n{a[1]} | {a[2]}\n'
        if len(a) == 3:
            return f'\n{a[0]} | {a[2]}\n{a[1]}\n'
        return f'\n{a[0]} | {a[1]}\n'
    s = re.sub(r'\\(?!textbf|href|textit|emph|section)[a-zA-Z]+\s*((?:\{[^{}]*\}\s*){2,4})', entry, s)
    s = re.sub(r'\\(?:section|ressection)\*?\{([^}]*)\}', r'\n\1\n', s)
    s = re.sub(r'\\(?:resume)?item\s*', '\n• ', s)
    s = re.sub(r'\\resumeSubheading\s*\{([^}]*)\}\s*\{([^}]*)\}\s*\{([^}]*)\}\s*\{([^}]*)\}', r'\n\1 | \2\n\3 | \4\n', s)
    s = re.sub(r'\\textbf\{([^}]*)\}', r'**\1**', s)
    s = re.sub(r'\\(?:textit|emph|underline|small|large|Large|Huge|scshape)\{?([^}]*)\}?', r'\1', s)
    s = re.sub(r'\\[a-zA-Z]+\*?(\[[^\]]*\])?', ' ', s).replace('{', '').replace('}', '').replace('\\\\', '\n').replace('$|$', '|')
    s = s.replace('\\&', '&').replace('\\%', '%').replace('\\$', '$').replace('\\#', '#').replace('\\_', '_').replace('--', '–')
    return re.sub(r'[ \t]+', ' ', s)


def _head(line):
    raw = line.strip()
    t = re.sub(r'[^a-z& ]', '', raw.lower()).strip()
    if not t or len(t) > 45 or len(t.split()) > 5 or re.search(r'\d', raw):
        return None
    headingish = raw.isupper() or raw.endswith(':') or len(t.split()) <= 3
    for k, pat in HEAD.items():
        if re.fullmatch(pat, t) or (headingish and re.match(rf'^(?:{pat})\b', t)):
            return k
    return None


def _dates(s):
    m = RANGE.search(s)
    if m:
        return m.group(1).strip().title(), m.group(2).strip().title(), s[:m.start()] + s[m.end():]
    ms = list(ONE.finditer(s))
    if ms:
        m = ms[-1]  # the date is usually at the end of the line
        return '', m.group(1).title(), s[:m.start()] + s[m.end():]
    return '', '', s


def _clean(s):
    return re.sub(r'\s+', ' ', re.sub(r'\s*[|,;·–-]\s*$', '', s.strip(' |·,-–'))).strip()


CITY2 = {'san', 'los', 'new', 'las', 'salt', 'st.', 'st', 'saint', 'fort', 'ft.', 'ann', 'palo', 'mountain', 'santa', 'long', 'baton', 'grand',
         'kansas', 'oklahoma', 'jersey', 'el', 'la', 'menlo', 'foster', 'redwood', 'white', 'west', 'east', 'north', 'south', 'chapel',
         'college', 'iowa', 'carson', 'cedar', 'colorado', 'corpus', 'des', 'beverly', 'boca', 'cape', 'coral', 'daly', 'half', 'state'}
LOC_END = re.compile(r'^(.*?)\s+((?:([A-Z][\w.]+)\s+)?([A-Z][\w.]+),\s*([A-Z]{2}|[A-Z][a-z]+)|Remote(?:,? [A-Z][\w ]+)?)$')


def split_loc(s):
    """'Software Engineering Intern Seattle, WA' -> ('Software Engineering Intern', 'Seattle, WA')"""
    m = LOC_END.match(s.strip())
    if not m:
        return s, ''
    head, loc = m.group(1), m.group(2)
    if m.group(3) and m.group(3).lower() not in CITY2:
        head, loc = head + ' ' + m.group(3), loc[len(m.group(3)):].strip()
    return head.strip(' |·,'), loc


def unspace_caps(s):
    """small-caps PDFs extract as 'E DUCATION' / 'A LEX  R IVERA'"""
    return re.sub(r'\b([A-Z]) ([A-Z]{2,})\b', r'\1\2', s)


def parse(text):
    lines = [unspace_caps(l.replace('\xa0', ' ')).rstrip() for l in text.replace('\r', '').split('\n')]
    lines = [l for l in lines if l.strip()]
    v = {"basics": {"name": "", "email": "", "phone": "", "location": "", "links": [], "headline": []},
         "education": [], "experience": [], "projects": [], "research": [], "leadership": [], "volunteering": [], "skills": [],
         "awards": [], "certifications": [], "order": []}
    head_txt = ' '.join(lines[:8])
    b = v['basics']
    if lines:
        first = re.sub(r'\s*[|·].*$', '', lines[0]).strip()
        if 1 <= len(first.split()) <= 5 and not EMAIL.search(first):
            b['name'] = re.sub(r'\s+', ' ', first.title() if first.isupper() else first)
    m = EMAIL.search(head_txt)
    b['email'] = m.group() if m else ''
    m = PHONE.search(head_txt)
    b['phone'] = m.group().strip() if m else ''
    m = re.search(r'\b([A-Z][a-zA-Z .]+, [A-Z]{2})\b', head_txt)
    b['location'] = m.group(1) if m else ''
    for u in dict.fromkeys(URL.findall(head_txt)):
        if '@' in u or u.lower() == b['email'].split('@')[-1]:
            continue
        b['links'].append({"label": re.sub(r'^https?://(www\.)?', '', u), "url": u if u.startswith('http') else 'https://' + u})
    sec, cur = None, None
    for line in lines[1:]:
        h = _head(line)
        if h:
            sec, cur = h, None
            if h not in v['order'] and h != 'summary':
                v['order'].append(h)
            continue
        if sec is None or sec == 'summary':
            continue
        s = line.strip()
        is_b = bool(BULLET.match(s))
        s2 = BULLET.sub('', s)
        if sec == 'skills':
            if ':' in s2:
                lab, items = s2.split(':', 1)
                v['skills'].append({"label": _clean(lab).replace('**', ''), "items": [i.strip(' *') for i in re.split(r',|;|·|\|', items) if i.strip(' *')]})
            elif s2:
                v['skills'].append({"label": "Skills", "items": [i.strip() for i in re.split(r',|;|·|\|', s2) if i.strip()]})
            continue
        if sec in ('awards', 'certifications', 'research'):
            if sec == 'research':
                v['research'].append({"title": s2})
            else:
                v[sec].append(s2)
            continue
        if sec == 'education':
            if is_b and cur:
                cur.setdefault('honors', []).append(s2)
                continue
            a, z, rest = _dates(s2)
            gpa = re.search(r'gpa[:\s]*([0-9.]+(?:\s*/\s*[0-9.]+)?)', s2, re.I)
            if cur is None or (not is_b and re.search(r'universit|college|school|institute|academy', s2, re.I) and cur.get('degree')):
                sch, loc = split_loc(_clean(re.sub(r'gpa.*', '', rest.replace('**', ''), flags=re.I)))
                cur = {"school": sch, "location": loc, "degree": "", "major": "", "start": a, "end": z}
                v['education'].append(cur)
            else:
                d = _clean(re.sub(r'gpa.*', '', rest, flags=re.I))
                d = re.split(r';', d)[0]
                if re.match(r'(relevant )?coursework', d, re.I):
                    cur['coursework'] = [c.strip() for c in re.split(r',', d.split(':', 1)[-1]) if c.strip()]
                    continue
                m = re.search(r'bachelor|master|\bb\.?s\.?\b|\bb\.?a\.?\b|\bm\.?s\.?\b|ph\.?d|associate|\bbsn\b|\bbba\b|\bmba\b', d, re.I)
                if m and not cur.get('degree'):
                    deg, _, maj = d.partition(' in ')
                    cur['degree'], cur['major'] = _clean(deg), _clean(maj)
                    minor = re.search(r'minor in ([^;,]+)', s2, re.I)
                    if minor:
                        cur['minor'] = _clean(minor.group(1))
                elif d:
                    cur.setdefault('honors', []).append(d)
                cur['end'] = cur.get('end') or z
                cur['start'] = cur.get('start') or a
            if gpa:
                cur['gpa'] = gpa.group(1).replace(' ', '')
            continue
        # experience-like sections
        if is_b:
            if cur is None:
                cur = {"org": "", "title": "", "bullets": []}
                v[sec].append(cur)
            cur.setdefault('bullets', []).append(s2)
            continue
        if cur is not None and cur.get('bullets') and not RANGE.search(s2) and not ONE.search(s2[-12:]) and not split_loc(s2)[1]:
            cur['bullets'][-1] += ' ' + s2  # a bullet that wrapped onto the next line
            continue
        a, z, rest = _dates(s2)
        parts = [p.strip() for p in re.split(r'\s+[|·]\s+|\s{3,}|\t', rest) if p.strip()]
        link = re.match(r'\*{0,2}\[([^\]]+)\]\(([^)]+)\)\*{0,2}(.*)', rest.strip())
        url = None
        if link:
            url, rest = link.group(2), link.group(1) + link.group(3)
            parts = [p.strip() for p in re.split(r'\s+[|·]\s+|\s{3,}|\t', rest) if p.strip()]
        if cur is None or cur.get('bullets') or (cur.get('title') and cur.get('org')):
            cur = {"bullets": []}
            v[sec].append(cur)
            if url:
                cur['url'] = url
            if sec == 'projects':
                cur['name'] = _clean(parts[0] if parts else rest).replace('**', '')
                cur['tagline'] = _clean(' | '.join(parts[1:]))
                cur['date'] = z
            else:
                org, loc = split_loc(_clean(parts[0] if parts else rest).replace('**', ''))
                cur['org'] = org
                if loc:
                    cur['location'] = loc
                if len(parts) > 1:
                    cur['location'] = _clean(parts[-1]) if re.search(r', [A-Z]{2}\b|remote', parts[-1], re.I) else ''
                    if not cur['location']:
                        cur['title'] = _clean(parts[1])
                cur['start'], cur['end'] = a, z
        else:
            if sec != 'projects':
                if not cur.get('title'):
                    t, loc = split_loc(_clean(parts[0] if parts else rest))
                    cur['title'] = t
                    if loc and not cur.get('location'):
                        cur['location'] = loc
                if len(parts) > 1 and not cur.get('location'):
                    cur['location'] = _clean(parts[-1])
                if a or z:
                    cur['start'], cur['end'] = cur.get('start') or a, cur.get('end') or z
    for sec in ('experience', 'projects', 'leadership', 'volunteering'):
        v[sec] = [e for e in v[sec] if e.get('bullets') or e.get('org') or e.get('name')]
    if 'education' in v['order']:
        v['order'] = ['education'] + [s for s in v['order'] if s != 'education']
    return v


def merge(old, new):
    """Add new entries to the existing vault without duplicating ones already there."""
    if not (old.get('experience') or old.get('projects') or old.get('education')):
        keep = {k: old['basics'][k] for k in old.get('basics', {}) if old['basics'][k]}
        new['basics'] = {**new.get('basics', {}), **keep}
        return new
    out = json.loads(json.dumps(old))
    for k, val in new.get('basics', {}).items():
        if val and not out['basics'].get(k):
            out['basics'][k] = val
    for sec in ('education', 'experience', 'projects', 'research', 'leadership', 'volunteering'):
        have = {(e.get('org') or e.get('name') or e.get('school') or e.get('title') or '').lower() for e in out.get(sec, [])}
        for e in new.get(sec, []):
            key = (e.get('org') or e.get('name') or e.get('school') or e.get('title') or '').lower()
            if key and key not in have:
                out.setdefault(sec, []).append(e)
            elif key:
                tgt = next(x for x in out[sec] if (x.get('org') or x.get('name') or x.get('school') or x.get('title') or '').lower() == key)
                for bl in e.get('bullets', []):
                    if bl not in tgt.get('bullets', []):
                        tgt.setdefault('bullets', []).append(bl)
    labels = {s['label'].lower(): s for s in out.get('skills', [])}
    for s in new.get('skills', []):
        t = labels.get(s['label'].lower())
        if t:
            t['items'] += [i for i in s['items'] if i not in t['items']]
        else:
            out.setdefault('skills', []).append(s)
    for k in ('awards', 'certifications'):
        out[k] = out.get(k, []) + [x for x in new.get(k, []) if x not in out.get(k, [])]
    for s in new.get('order', []):
        if s not in out.get('order', []):
            out.setdefault('order', []).append(s)
    return out


LLM_PROMPT = """Turn this resume text into JSON for a Career Vault. Copy facts EXACTLY; never invent or embellish.
Schema: {"basics":{"name","email","phone","location","links":[{"label","url"}]},
"education":[{"school","location","degree","major","minor","gpa","start","end","coursework":[],"honors":[]}],
"experience":[{"org","title","location","start","end","url","bullets":[]}], "projects":[{"name","tagline","tech":[],"date","url","bullets":[]}],
"research":[{"title","venue","role","url"}], "leadership":[same as experience], "volunteering":[same as experience],
"skills":[{"label","items":[]}], "awards":[strings], "certifications":[strings], "order":[section names in the resume's order]}
Dates like "Jun 2025". Use **bold** only where the original bolded. Return only JSON.

RESUME:
"""


def import_resume(name='', data=None, text=None):
    from . import match, tailor
    txt, source_tex = extract_text(name, data, text)
    if source_tex:
        with open(store.path('source.tex'), 'w') as f:
            f.write(source_tex)
    from . import api
    api.save_dump(f'# imported: {name or "pasted text"}\n{txt}')
    structured, parsed = False, None
    from . import agents
    if os.environ.get('ANTHROPIC_API_KEY') or os.environ.get('OPENAI_API_KEY') or agents.any_ready():
        try:
            parsed = tailor.call_llm(LLM_PROMPT + txt[:24000])
            structured = bool(parsed)
        except Exception:
            parsed = None
    if not parsed:
        parsed = parse(txt)
    vault = merge(store.resume(), parsed)
    tailor.ensure_ids(vault)
    store.save('resume.json', vault)
    p = store.profile()
    b = vault.get('basics', {})
    patch = {k: b[k] for k in ('name', 'email', 'phone', 'location') if b.get(k) and not p.get(k)}
    for l in b.get('links', []):
        for site in ('linkedin', 'github'):
            if site in l.get('url', '') and not p.get(site):
                patch[site] = l['url']
    edu = (vault.get('education') or [{}])[0]
    if edu.get('school') and not p.get('school'):
        patch.update(school=edu['school'], degree=edu.get('degree', ''), major=edu.get('major', ''), gpa=edu.get('gpa', ''))
        m = re.search(rf'({MONTH})?\s*((?:19|20)\d\d)', edu.get('end', ''), re.I)
        if m:
            patch.update(grad_year=m.group(2), grad_month=(m.group(1) or 'May').title()[:3])
    if patch:
        api.update_profile(patch)
    low = txt.lower()
    roles = sorted(((sum(low.count(x) for x in syn), r) for r, syn in match.ROLE_SYNONYMS.items()), reverse=True)
    suggest = [r for n, r in roles if n >= 2][:4]
    counts = {k: len(vault.get(k, [])) for k in ('experience', 'projects', 'education', 'skills', 'awards', 'research')}
    found = ', '.join(f'{n} {k}' for k, n in counts.items() if n)
    return {"structured": True, "ai": structured, "vault": vault, "counts": counts, "name": b.get('name', ''), "suggest_roles": suggest,
            "latex_source": bool(source_tex),
            "message": f"Found {found or 'your details'}." + ('' if structured else ' Check it in Resume Studio; your agent can polish it.')}
