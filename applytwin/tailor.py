"""Per-job resume tailoring from the Career Vault.

The vault (resume.json) holds EVERYTHING the user has done: more roles, projects and bullets than fit on a page,
with as many alternate phrasings per bullet as they like. Tailoring = pick the strongest, most relevant subset,
order it for this posting, mirror the posting's vocabulary only where the vault already proves it, fit one page.

Three ways to tailor, same output:
  heuristic  no AI at all: ranks entries/bullets by posting keyword overlap        (always available)
  agent      Claude Code / Codex writes the plan from prompt()                     (best quality, uses your plan)
  api        an LLM writes the plan: the user's own Claude Code / Codex subscription, or an API key if one is set

The fact guard rejects any rewrite that adds numbers, names, links or skills that are not in the vault.
"""
import copy
import json
import os
import re

from . import ats

GUIDE = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'docs', 'RESUME_GUIDE.md')).read() \
    if os.path.exists(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'docs', 'RESUME_GUIDE.md')) else ''
ENTRY_SECS = ('experience', 'projects', 'leadership', 'volunteering')


def slug(s):
    return re.sub(r'[^a-z0-9]+', '', (s or '').lower())[:14] or 'x'


def ensure_ids(v):
    """Give every entry a stable id so plans can reference it ('acme', 'acme.0' = first bullet)."""
    used = set()
    for sec in ENTRY_SECS + ('research',):
        for e in v.get(sec, []):
            if not e.get('id'):
                base = slug(e.get('org') or e.get('name') or e.get('title'))
                i, n = base, 2
                while i in used:
                    i, n = f'{base}{n}', n + 1
                e['id'] = i
            used.add(e['id'])
    return v


def words(s):
    return set(re.findall(r'[A-Za-z][A-Za-z0-9+#.\-]*[A-Za-z0-9+#]|[A-Za-z]', s))


def nums(s):
    return set(re.findall(r'\d+(?:[.,]\d+)?', s))


def vault_text(v):
    return json.dumps(v, ensure_ascii=False)


MAGNITUDE = re.compile(r'\b(thousand|million|billion|trillion|\d+[kmb]\b|\d+x\b|percent)', re.I)


def check_rewrite(orig, new, vault_txt, jd, entry_txt=None):
    """Return None if the rewrite is truthful, else the reason it was rejected.
    entry_txt = all text of the same role/project: new numbers and tools must come from THAT entry."""
    o, n = ats.plain(orig), ats.plain(new)
    scope = ats.plain(entry_txt or orig)
    if len(n) < 25:
        return 'too short'
    if len(n) > max(len(o) * 1.25, len(o) + 40):
        return 'much longer than the original'
    extra_nums = nums(n) - nums(scope)
    if extra_nums:
        return 'adds numbers not in this entry: ' + ', '.join(sorted(extra_nums))
    mags = {x.lower() for x in MAGNITUDE.findall(n)} - {x.lower() for x in MAGNITUDE.findall(scope)}
    if mags:
        return 'adds a scale claim not in this entry: ' + ', '.join(sorted(mags))
    for term, pat in ats.PATTERNS.items():
        if term not in ats.SOFT and pat.search(n) and not pat.search(scope):
            return f'claims {term}, which this entry never mentions'
    vw = words(vault_txt)
    stems = {w[:6].lower() for w in vw if len(w) >= 6}
    vlow = {w.lower() for w in vw}
    caps = {w for w in words(n) - vw if w[0].isupper() and w.lower() not in vlow and w.lower() not in ats.ACTION_VERBS}
    caps = {w for w in caps if not (len(w) >= 6 and w[:6].lower() in stems)}
    if caps:
        return 'adds names/tools not in your vault: ' + ', '.join(sorted(caps))
    jdw = {w.lower() for w in words(jd)}
    stuffed = {w for w in {x.lower() for x in words(n)} - vlow if w in jdw and not (len(w) >= 6 and w[:6] in stems)}
    stuffed -= ats.ACTION_VERBS | {'and', 'the', 'for', 'with', 'to', 'of', 'in', 'on', 'a', 'an', 'by', 'via', 'using', 'across'}
    if len(stuffed) > 1:
        return 'stuffs posting keywords the vault does not back: ' + ', '.join(sorted(stuffed))
    for link in re.findall(r'\]\(([^)]+)\)', orig):
        if link not in new:
            return 'dropped a link'
    if re.search('[–—]', n) and not re.search('[–—]', o):
        return 'adds dashes'
    return None


# ---------------------------------------------------------------- heuristic tailor (no AI)

IMPACT = re.compile(r'\b(1st|2nd|3rd|first place|second place|winner|won|finalist|champion|gold|top \d+%?|1 of \d+|'
                    r'published|first author|patent|acquired|funded|raised|record|co-?founder|founded|founding|'
                    r'\d[\d,.]*\+?\s*(?:k\s*)?(?:users|customers|downloads|members|students|teams))\b', re.I)
OLD = re.compile(r'\b(high school|middle school|secondary school)\b', re.I)  # or set "high_school": true on a vault entry


def _kw_score(text, kws):
    s = 0.0
    for term, w, _ in kws:
        if ats.PATTERNS[term].search(text):
            s += w
    return s


def heuristic_plan(v, jd, max_bullets=None, title='', ctx=None):
    v = ensure_ids(copy.deepcopy(v))
    ctx = ctx or {}
    pins, avoid, wins = set(ctx.get('pins', [])), set(ctx.get('avoid', [])), set(ctx.get('winning_bullets', []))
    kws = ats.keywords(jd)
    max_bullets = max_bullets or {'experience': 3, 'projects': 2, 'leadership': 1, 'volunteering': 1}
    plan = {"order": [], "bullets": {}, "skills": [], "headline": v.get('basics', {}).get('headline', [])}
    from .match import ROLE_SYNONYMS
    head = (title or jd[:160]).lower()
    want = [r for r, syn in ROLE_SYNONYMS.items() if any(re.search(r'\b' + re.escape(x), head) for x in syn)]

    def role_fit(text):
        t = text.lower()
        if not want:
            return 0
        if any(re.search(r'\b' + re.escape(x), t) for r in want for x in ROLE_SYNONYMS[r]):
            return 2.0
        return -1.0 if any(re.search(r'\b' + re.escape(x), t) for r, syn in ROLE_SYNONYMS.items() if r not in want for x in syn) else 0
    sec_rel = {}
    for sec in ENTRY_SECS:
        ranked, items = [], v.get(sec, [])
        texts = [ats.plain(' '.join([e.get('title', ''), e.get('org', ''), e.get('name', ''), e.get('tagline', ''),
                                     ' '.join(e.get('tech', []))] + e.get('bullets', []))) for e in items]
        kw_max = max([_kw_score(t, kws) for t in texts] + [1])
        for idx, e in enumerate(items):
            raw = ' '.join([e.get('tagline', '')] + e.get('bullets', []))
            # relevance to this posting (0-6) + impact a recruiter sees (0-3) + recency (vault order is newest first, 0-2)
            impact = min(3.0, 0.4 * raw.count('**') / 2 + 1.5 * len(IMPACT.findall(raw)) + 0.15 * len(nums(raw)))
            rel = (6 * _kw_score(texts[idx], kws) / kw_max + impact + 2 * (1 - idx / max(1, len(items)))
                   + role_fit(' '.join([e.get('title', ''), e.get('org', ''), e.get('name', '')] + e.get('bullets', []))))
            if e.get('high_school') or OLD.search(texts[idx]):
                rel -= 2.5
            if e['id'] in avoid:
                continue
            if e['id'] in pins:
                rel += 100  # the user said: always include this
            rel += 1.5 * sum(b in wins for b in e.get('bullets', []))
            bl = sorted(range(len(e.get('bullets', []))), key=lambda i: -(_kw_score(ats.plain(e['bullets'][i]), kws)
                                                                             + (0.6 if re.search(r'\d', e['bullets'][i]) else 0)
                                                                             + 0.3 * e['bullets'][i].count('**') / 2
                                                                             + (2 if e['bullets'][i] in wins else 0)
                                                                             + (100 if f"{e['id']}.{i}" in pins else 0)
                                                                             - (100 if f"{e['id']}.{i}" in avoid else 0)
                                                                             - i * 0.25))
            ranked.append((rel, e['id'], bl[:max_bullets.get(sec, 2)]))
        ranked.sort(key=lambda x: -x[0])
        keep = ranked[:{'experience': 6, 'projects': 4, 'leadership': 3, 'volunteering': 2}[sec]]
        plan[sec] = [{"id": i, "bullets": [f'{i}.{b}' for b in sorted(bl)]} for _, i, bl in keep]
        sec_rel[sec] = sum(r for r, _, _ in keep[:3])
    lines = []
    for s in v.get('skills', []):
        items = sorted(s.get('items', []), key=lambda it: -_kw_score(it, kws))
        lines.append({"label": s.get('label'), "items": items[:16], "rel": _kw_score(' '.join(items), kws)})
    lines.sort(key=lambda s: -s['rel'])
    keep = [l for l in lines if l['rel'] > 0][:5] or lines[:3]
    if len(keep) < 3:
        keep += [l for l in lines if l not in keep][:3 - len(keep)]
    for l in keep:
        l.pop('rel')
    plan['skills'] = keep
    field_order = (ctx.get('rules') or {}).get('order')
    base = [s for s in (field_order or v.get('order') or []) if s != 'education']
    base += [s for s in (v.get('order') or []) if s not in base and s != 'education']
    if sec_rel.get('projects', 0) > sec_rel.get('experience', 0) * 1.3 and 'projects' in base and 'experience' in base:
        base.remove('projects')
        base.insert(base.index('experience'), 'projects')
    plan['order'] = ['education'] + base
    plan['notes'] = f"{ctx.get('field', 'general')} resume: " + (ctx.get('rules') or {}).get('emphasize', '')
    return plan


# ---------------------------------------------------------------- agent / LLM tailor

def prompt(v, job, jd, ctx=None):
    v = ensure_ids(copy.deepcopy(v))
    ctx = ctx or {}
    rules = ctx.get('rules') or {}
    you = ''
    if ctx.get('notes'):
        you += 'THE CANDIDATE TOLD US (always follow):\n' + '\n'.join('- ' + n for n in ctx['notes']) + '\n'
    if ctx.get('pins'):
        you += 'ALWAYS INCLUDE these entries/bullets: ' + ', '.join(ctx['pins']) + '\n'
    if ctx.get('avoid'):
        you += 'NEVER INCLUDE: ' + ', '.join(ctx['avoid']) + '\n'
    if ctx.get('winning_bullets'):
        you += 'BULLETS THAT GOT THIS CANDIDATE INTERVIEWS BEFORE (prefer them when relevant):\n' + '\n'.join('- ' + b for b in ctx['winning_bullets'][:8]) + '\n'
    return f"""You are an elite recruiter and resume writer for the {ctx.get('field', 'general')} field. Build the strongest possible ONE-PAGE resume for this
specific posting, using ONLY facts in the candidate's Career Vault. The vault holds more than fits; your job is to choose.

RULES (hard):
- Never invent: no new numbers, employers, tools, skills, titles, dates, awards or links. A fact guard rejects violations.
- REWRITE every bullet you keep into its strongest truthful form for THIS posting: lead with the result, mirror the
  posting's exact terms where the bullet already proves them, cut filler, keep every fact. Keep **bold** on the 1-3
  most impressive facts per entry. No em/en dashes. No first person.
- Each bullet: past-tense action verb first (present tense for current roles), 80-200 characters, ideally a number.
- Choose 2-4 bullets per relevant role, 1-3 per project; drop entries that do not help this posting.
- Order sections for this reader. Ideal order for this field: {', '.join(rules.get('order', []))}.
- What hiring managers in this field look for first: {rules.get('emphasize', 'the posting requirements and measurable results')}.
{you}

OUTPUT: only a JSON object:
{{"headline": [strings from vault basics.headline, reordered/subset],
  "order": ["education", "experience", "projects", ...],
  "experience": [{{"id": "<entry id>", "bullets": ["<id>.<n>" or {{"from": "<id>.<n>", "text": "<reworded bullet>"}}]}}],
  "projects": [same shape], "leadership": [same shape],
  "research": ["<research id>", ...], "awards": [<indexes>],
  "skills": [{{"label": "...", "items": [subset/reorder of that label's items]}}],
  "notes": "one line on the strategy"}}

RESUME WRITING GUIDE (follow it):
{GUIDE[:6000]}

POSTING: {job.get('title', '')} at {job.get('company', '')} ({job.get('location', '')})
{jd[:9000]}

CAREER VAULT (entry ids are the "id" fields; bullet n is the nth item of "bullets"):
{json.dumps({k: v[k] for k in v if k not in ('titles',)}, ensure_ascii=False)[:30000]}
"""


def agent_llm(text, timeout=600):
    """Run one prompt on the user's own Claude Code or Codex subscription (no API key). Returns the reply text or None."""
    import subprocess
    import tempfile
    from . import agents, store
    for name in agents.preferred(store.profile()):
        try:
            if name == 'claude':
                # a one-shot plan doesn't need the biggest model; Sonnet is several times faster for this
                r = subprocess.run([agents.exe('claude'), '-p', '--model', 'sonnet', '--output-format', 'text', '--tools', ''], input=text, capture_output=True,
                                   text=True, timeout=timeout, cwd=store.HOME)
                if r.returncode == 0 and r.stdout.strip():
                    return r.stdout
            else:
                for _ in range(2):
                    with tempfile.NamedTemporaryFile('r', suffix='.txt', delete=False) as f:
                        out = f.name
                    cmd = [agents.exe('codex'), 'exec', '--skip-git-repo-check', '--ephemeral', '-s', 'read-only', '-o', out,
                           *agents.codex_model_args(), '-']
                    r = subprocess.run(cmd, input=text, capture_output=True, text=True, timeout=timeout, cwd=store.HOME)
                    reply = open(out).read() if os.path.exists(out) else ''
                    if os.path.exists(out):
                        os.unlink(out)
                    if reply.strip():
                        return reply
                    if 'model_not_found' not in r.stdout + r.stderr or agents.FALLBACK_MODEL[0]:
                        break
                    agents.FALLBACK_MODEL[0] = True   # the configured model isn't on this plan: retry on one the CLI lists
        except Exception:
            continue
    return None


def call_llm(text, timeout=600):
    key = os.environ.get('ANTHROPIC_API_KEY')
    import urllib.request
    if key:
        body = {"model": os.environ.get('APPLYTWIN_MODEL', 'claude-sonnet-5-5'), "max_tokens": 6000,
                "messages": [{"role": "user", "content": text}]}
        req = urllib.request.Request('https://api.anthropic.com/v1/messages', data=json.dumps(body).encode(),
                                     headers={'x-api-key': key, 'anthropic-version': '2023-06-01', 'content-type': 'application/json'})
        with urllib.request.urlopen(req, timeout=180) as r:
            out = json.load(r)['content'][0]['text']
    elif os.environ.get('OPENAI_API_KEY'):
        body = {"model": os.environ.get('APPLYTWIN_OPENAI_MODEL', 'gpt-5'), "messages": [{"role": "user", "content": text}]}
        req = urllib.request.Request('https://api.openai.com/v1/chat/completions', data=json.dumps(body).encode(),
                                     headers={'Authorization': 'Bearer ' + os.environ['OPENAI_API_KEY'], 'content-type': 'application/json'})
        with urllib.request.urlopen(req, timeout=180) as r:
            out = json.load(r)['choices'][0]['message']['content']
    else:
        out = agent_llm(text, timeout=timeout)
        if not out:
            return None
    m = re.search(r'\{.*\}', out, re.S)
    return json.loads(m.group()) if m else None


# ---------------------------------------------------------------- apply a plan

def apply(v, plan, jd=''):
    """Vault + plan -> concrete resume dict, plus a report of accepted/rejected rewrites."""
    v = ensure_ids(copy.deepcopy(v))
    vt = vault_text(v)
    out = {"basics": copy.deepcopy(v.get('basics', {})), "titles": v.get('titles', {})}
    rep = {"rewrites": [], "rejected": [], "notes": plan.get('notes', '')}
    head = v.get('basics', {}).get('headline', [])
    if plan.get('headline'):
        out['basics']['headline'] = [h for h in plan['headline'] if h in head] or head
    out['education'] = v.get('education', [])
    for sec in ENTRY_SECS:
        byid = {e['id']: e for e in v.get(sec, [])}
        chosen = plan.get(sec)
        if chosen is None:
            out[sec] = v.get(sec, [])
            continue
        lst = []
        for c in chosen:
            cid = c['id'] if isinstance(c, dict) else c
            e = byid.get(cid)
            if not e:
                continue
            e2 = {k: e[k] for k in e if k != 'bullets'}
            bl = []
            for ref in (c.get('bullets') if isinstance(c, dict) and c.get('bullets') is not None else
                        [f'{cid}.{i}' for i in range(len(e.get('bullets', [])))]):
                src_id, text = (ref.get('from'), ref.get('text')) if isinstance(ref, dict) else (ref, None)
                m = re.match(r'(.+)\.(\d+)$', str(src_id or ''))
                if not m or m.group(1) not in byid or int(m.group(2)) >= len(byid[m.group(1)].get('bullets', [])):
                    continue
                orig = byid[m.group(1)]['bullets'][int(m.group(2))]
                if text and text.strip() != orig:
                    src = byid[m.group(1)]
                    etxt = ' '.join([src.get('title', ''), src.get('org', ''), src.get('name', ''), src.get('tagline', ''),
                                     ' '.join(src.get('tech', []))] + src.get('bullets', []) + src.get('alts', []))
                    why = check_rewrite(orig, text, vt, jd, etxt)
                    if why:
                        rep['rejected'].append({"bullet": src_id, "reason": why, "text": text})
                        text = None
                    else:
                        rep['rewrites'].append({"bullet": src_id, "from": orig, "to": text})
                bl.append(text or orig)
            e2['bullets'] = bl
            lst.append(e2)
        out[sec] = lst
    rid = {p.get('id'): p for p in v.get('research', [])}
    out['research'] = [rid[i] for i in plan.get('research', []) if i in rid] if 'research' in plan else v.get('research', [])
    aw = v.get('awards', [])
    out['awards'] = [aw[i] for i in plan.get('awards', []) if isinstance(i, int) and i < len(aw)] if 'awards' in plan else aw
    out['certifications'] = v.get('certifications', [])
    labels = {s.get('label'): s.get('items', []) for s in v.get('skills', [])}
    if plan.get('skills'):
        sk = []
        for s in plan['skills']:
            items = [i for i in s.get('items', []) if i in labels.get(s.get('label'), [])]
            if items:
                sk.append({"label": s['label'], "items": items})
        out['skills'] = sk or v.get('skills', [])
    else:
        out['skills'] = v.get('skills', [])
    order = [s for s in (plan.get('order') or v.get('order') or []) if out.get(s)]
    out['order'] = order + [s for s in (v.get('order') or []) if s not in order and out.get(s) and s not in ('research', 'awards')]
    return out, rep


def tailor(v, job, jd, mode='auto', plan=None, style=None, out_dir=None):
    """Full pipeline -> {pdf, pages, ats before/after, rewrites}."""
    from . import learn, render, store
    ctx = learn.context_for(job)
    style = style or ctx['template']
    if plan is None:
        if mode in ('auto', 'api'):
            try:
                plan = call_llm(prompt(v, job, jd, ctx), timeout=150)   # never leave someone waiting: past this, the built-in writer takes over
            except Exception:
                plan = None
        if plan is None:
            plan = heuristic_plan(v, jd, title=job.get('title', ''), ctx=ctx)
            mode = 'heuristic'
        else:
            mode = 'api'
    else:
        mode = 'agent'
    res, rep = apply(v, plan, jd)
    out_dir = out_dir or store.path('resumes', job.get('id', 'general'))
    name = re.sub(r'[^A-Za-z]+', '_', res['basics'].get('name', 'Resume')).strip('_') + '_Resume.pdf'
    pdf = os.path.join(out_dir, name)
    r = render.render(res, style, pdf)
    from . import latex
    with open(pdf[:-4] + '.tex', 'w') as f:  # every tailored resume also ships as editable LaTeX
        f.write(latex.build_tex(res))
    txt = render.pdf_text(pdf)
    before = ats.report(v, jd)
    after = ats.report(res, jd, r['pages'], txt)
    json.dump({"plan": plan, "resume": res, "report": rep, "render": r, "mode": mode, "style": style, "field": ctx['field']},
              open(os.path.join(out_dir, 'tailor.json'), 'w'), indent=1, ensure_ascii=False)
    return {"pdf": pdf, "tex": pdf[:-4] + '.tex', "pages": r['pages'], "dropped": r['dropped'], "mode": mode, "style": style,
            "coverage_vault": before.get('coverage'), "coverage": after.get('coverage'), "score": after['score'],
            "missing": [m['term'] for m in after.get('missing', []) if m['hard']][:12],
            "rewrites": len(rep['rewrites']), "rejected": rep['rejected'], "notes": rep['notes'], "field": ctx['field']}
