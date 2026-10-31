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

GUIDE = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'docs', 'RESUME_GUIDE.md'), encoding='utf-8').read() \
    if os.path.exists(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'docs', 'RESUME_GUIDE.md')) else ''
ENTRY_SECS = ('experience', 'projects', 'leadership', 'volunteering')
# raise when how a plan becomes a page gets meaningfully better: saved resumes from older versions are rebuilt from their plan
PIPELINE = 3


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


IRREGULAR_PAST = set('''ran led built won wrote made grew taught drove began held found took gave cut set sold spent brought bought
chose drew flew fought kept lost met paid rode rose saw sent shot spoke stood struck thought threw understood wore became
broke dealt fed felt hit hung knew laid left lent let meant put read sought shut sat slept split spread stuck swept told
withdrew undertook oversaw overcame upheld'''.split())


def _forms(w):
    """Inflections of a verb, to recognise 'Ship' as 'shipped' or 'Build' as 'built' in the vault."""
    irregular = {'build': ['built'], 'lead': ['led'], 'run': ['ran'], 'write': ['wrote', 'written'], 'win': ['won'],
                 'make': ['made'], 'drive': ['drove'], 'teach': ['taught'], 'grow': ['grew'], 'find': ['found'],
                 'take': ['took'], 'give': ['gave'], 'hold': ['held'], 'cut': ['cut'], 'set': ['set'], 'begin': ['began']}
    out = {w + 'ed', w + 'd', w + 's', w + 'es', w + 'ing', w + w[-1:] + 'ed', w + w[-1:] + 'ing', w[:-1] + 'ied',
           w[:-1] + 'ing', w[:-1] + 'ed'} | set(irregular.get(w, []))
    return out


def check_rewrite(orig, new, vault_txt, jd, entry_txt=None):
    """Return None if the rewrite is allowed, else the reason it was rejected. Numbers are locked: every number must come from
    the same role/project (entry_txt) and keep its meaning; a scale claim can't grow. Wording, tools and outcomes can move."""
    o, n = ats.plain(orig), ats.plain(new)
    scope = ats.plain(entry_txt or orig)
    if len(n) < 25:
        return 'too short'
    if len(n) > max(240, len(o) + 40):   # length is about fitting two lines, not truth: facts are checked below
        return 'longer than two lines'
    extra_nums = nums(n) - nums(scope)
    if extra_nums:
        return 'adds numbers not in this entry: ' + ', '.join(sorted(extra_nums))
    # a number keeps its meaning: "40K events/sec" can't become "40K users"
    for num, unit in re.findall(r'(\d[\d,.]*\+?(?:\s*[kKmMbB%](?![A-Za-z]))?)\s*\+?\s*([A-Za-z][a-z]{2,})', n):
        key = re.escape(num.strip()) + r'\s*\+?\s*'
        if unit.lower() in ('to', 'and', 'the', 'of', 'in', 'on', 'at', 'per', 'for', 'by', 'from', 'with'):
            continue
        before = re.search(r'([A-Za-z][\w.+#-]*)\s+' + re.escape(num.strip()), n)
        if before and re.search(re.escape(before.group(1)) + r'\s+' + re.escape(num.strip()), scope):
            continue   # a version or a name with a number ("Ubuntu 24.04", "Python 3.12"), same as in the original
        if not re.search(key + r'(?:[A-Za-z-]+\s+){0,2}' + re.escape(unit[:5]), scope, re.I) and \
                not re.search(re.escape(unit[:5]) + r'[a-z]*\s+(?:of\s+)?' + re.escape(num.strip()), scope, re.I):
            return f'uses {num.strip()} for {unit}, but in this entry it counts something else'
    mags = {x.lower() for x in MAGNITUDE.findall(n)} - {x.lower() for x in MAGNITUDE.findall(scope)}
    if mags:
        return 'adds a scale claim not in this entry: ' + ', '.join(sorted(mags))
    # tools, methods and outcomes may be framed toward the posting (the user's call); numbers, scale and links may not.
    # Titles, employers, awards and team leadership are checked by the honesty read (audit), which understands context.
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
# bullets a recruiter skips: no scope, no result, chores. Never kept when the same entry has a stronger true one unused.
WEAK = re.compile(r'^\W*(help(ed|s|ing)?|assist(ed|s|ing)?|attend(ed|s)?|participat(ed|es)|complet(ed|es) (training|onboarding)|'
                  r'responsible for|worked on|did|cleaned|created some|made some|was part of|took part|shadow(ed|s)|learn(ed|s|ing)|'
                  r'maintain(ed|s)? (shop|lab|the)|answer(ed|s|ing)? (\w+ )?questions|checked out|stock(ed|ing) shelves|cashier|present(ed|s) (my |our |a |the )?final|'
                  r'organiz(ed|es) (events|socials)|supported (vehicle )?teardowns|gained|exposed to|familiariz)\b'
                  r'|\b(ITAR|safety|compliance|onboarding|orientation) training\b|\bintern (events?|socials?)\b|'
                  r'\bagile ceremonies\b|\bad[- ]hoc requests\b', re.I)


def weak(b):
    """Filler a recruiter skips: a chore or vague verb, or a short line with no number ('Graded homework.', 'Made the slides.')."""
    t = ats.plain(b)
    return bool(WEAK.search(t) or (len(t) < 55 and not re.search(r'\d', t)) or
                re.match(r'^\W*(grad(ed|es|ing)|read papers|sold|ran (philanthropy|events?)|made (the|a|an|some))\b', t, re.I))


def strength(b, kws=()):
    """How hard a bullet works on the page: a measured result and the posting's words count, filler and chores don't."""
    t = ats.plain(b)
    return ((3 if re.search(r'\d', t) else 0) + (2 if IMPACT.search(t) else 0) + min(len(t), 160) / 80
            + (_kw_score(t, kws) if kws else 0) - (6 if weak(t) else 0))


def _upgrade(bl, src, avoid, kws, least=1):
    """Swap each weak bullet for the entry's strongest unused one (a real, unchosen vault bullet), never adding length."""
    used = set(bl)
    spare = sorted((b for i, b in enumerate(src.get('bullets', [])) if b not in used and f"{src['id']}.{i}" not in avoid
                    and not weak(b) and not any(_closest([b], x)[1] > 0.5 for x in bl)),
                   key=lambda b: -strength(b, kws))
    out = []
    for b in bl:
        t = ats.plain(b)
        if spare and weak(t) and strength(spare[0], kws) > strength(b, kws):
            out.append(spare.pop(0))
        elif spare and not re.search(r'\d', t) and re.search(r'\d', ats.plain(spare[0])) and strength(spare[0], kws) >= strength(b, kws) + 3:
            out.append(spare.pop(0))   # the entry's measured result beats an unmeasured line
        else:
            out.append(b)
    keep = [b for b in out if not (weak(b) and not re.search(r'\d', ats.plain(b)))]   # measured lines stay
    return keep if len(keep) >= least else out


SERVICE = re.compile(r'\b(lifeguard|cashier|barista|waiter|waitress|hostess|busser|dishwasher|line cook|'
                     r'sales associate|retail associate|crew member|camp counselor|caddie|delivery driver|valet|'
                     r'stocker|front desk|circulation desk|babysitter|nanny|dog walker)\b', re.I)
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
    return f"""You are an elite recruiter and resume writer for the {ctx.get('field', 'general')} field. Make this candidate read as the obvious
hire for THIS specific posting, on ONE page, using ONLY facts in their Career Vault. The vault holds more than fits; your job
is to choose and to frame.

FIRST, POSITION (think it through before writing anything):
1. What does this hiring manager screen for, in order? Name the top 3 requirements from the posting.
2. What one-line story makes this candidate the obvious fit for exactly this role? (e.g. "a quant researcher who ships
   production ML systems", "a robotics engineer who has run real hardware end to end").
3. Which 2-3 entries prove that story best, and which single bullet proves requirement #1?
THEN BUILD THE PAGE AROUND IT so a recruiter skimming for 6 seconds sees those three things in the top third:
- The first entry in the first section, and its first bullet, prove requirement #1.
- Headline tags are the first thing read. The FIRST tag names the identity this posting hires, in its terms where the vault
  backs them ("Recommendation Systems", "Vehicle Hardware", "Python & TypeScript"); drop vault tags that point at a different
  job ("Semiconductors" for a vehicle-hardware role, "Vehicle Dynamics" for robot enclosures).
- Frame every bullet in this role's language without changing a fact: the same work reads as latency and systems for a
  quant/infra role, as perception and models for an ML role, as hardware and validation for a robotics role.
- Skills: the line and the items this role cares about come first.

RULES (hard):
- Every research/publication entry in the vault appears on the page (you choose where the section goes; put it high when
  the role values research). Never spend a bullet restating a paper the research section already lists.
- Locked: numbers and metrics, employers, titles, dates, degrees, awards and links. A fact guard rejects any change.
- REWRITE every bullet you keep into its strongest form for THIS posting: lead with the result, mirror the posting's
  exact terms, cut filler, keep every number exactly. Keep **bold** on the 1-3
  most impressive facts per entry. No em/en dashes. No first person.
- Each bullet: past-tense action verb first (present tense for current roles), 80-200 characters, ideally a number.
- Fill one page with the strongest material: usually 4-6 entries and 14-18 bullets. 2-4 bullets per relevant role, 1-2 per
  project or leadership entry; drop entries that do not help this posting.
- Every entry you keep shows its single most impressive measured result (the bullet with the biggest number, scale or
  outcome), even if its wording is less on-topic: reframe it for this role rather than dropping it.
- Never spend a line on filler ("helped with", "attended", "participated in", trainings, ad-hoc requests, intern events,
  generic duties) when the vault has a stronger true bullet for that entry or a stronger entry left out.
- No fact twice: an honor in education is not repeated in awards, a placement in a bullet is not repeated in awards.
- No orphan section: a section with one entry and one short bullet either earns a second bullet or gives way to a
  stronger entry.
- Reframe toward the posting: stronger verbs, the purpose and outcome of the work, the posting's vocabulary, and closely
  related tools or methods. Numbers are locked (never a new or changed number, metric or scale), and so are titles,
  employers, degrees, awards and placements; never claim leading people they didn't lead.
- Refer to bullets by the exact ids shown in the vault ("drift.0"). A number keeps its meaning ("40K events/sec" never
  becomes "40K users").
- A titled technical role on a student design team, lab or club ("Avionics Subteam Lead", "Electrical Lead") may go under
  "experience" (use its leadership id there) when it is the strongest proof for this posting; it then leaves leadership.
- Order sections for this reader. Ideal order for this field: {', '.join(rules.get('order', []))}.
- What hiring managers in this field look for first: {rules.get('emphasize', 'the posting requirements and measurable results')}.
{you}

OUTPUT: only a JSON object, written in THIS order (decide the strategy first, then build the page from it):
{{"requirements": ["requirement 1 (what this hiring manager screens for first)", "requirement 2", "requirement 3"],
  "positioning": "the one-line story that makes this candidate the obvious hire for THIS role",
  "lead": {{"entry": "<id of the entry that best proves requirement 1>", "bullet": "<its id.n that proves it>",
           "cut": ["<ids of entries that don't help this posting>"]}},
  "headline": [2-4 short identity tags naming THIS role's identity in its terms (vault words; "Avionics Hardware",
               "Recommender Systems", "Developer Tooling"); drop tags that point at a different job],
  "order": ["education", "experience", "projects", ...],
  "experience": [{{"id": "<entry id>", "bullets": ["<id>.<n>" or {{"from": "<id>.<n>", "text": "<reworded bullet>"}}]}}],
  "projects": [same shape], "leadership": [same shape],
  "research": ["<research id>", ...], "awards": [<indexes>],
  "skills": [{{"label": "...", "items": [subset/reorder of that label's items]}}],
  "notes": "one line on the strategy"}}
The "lead" entry goes first in its section (a design-team or lab role may sit in experience) with the "lead" bullet first,
unless a strictly chronological field convention says otherwise; the "cut" entries stay off the page.

RESUME WRITING GUIDE (follow it):
{GUIDE[:6000]}

POSTING: {job.get('title', '')} at {job.get('company', '')} ({job.get('location', '')})
{jd[:9000]}

CAREER VAULT (entry ids are the "id" fields; every bullet is shown with its exact id, like "drift.0": use those ids as given.
"posting_fit" on each entry and "fit" on each bullet measure how much of THIS posting's vocabulary they share: start from the
high ones, lead with them, and give a low one page space only when it is the candidate's best proof of something the posting
needs. Retail, food service and unrelated part-time jobs go only if nothing stronger is left):
{_vault_for_prompt(v, jd=jd)}
"""


_SINK = __import__('threading').local()   # where a running build wants live "characters written" counts
# a job that can be stopped from another request (resume import): _SINK.tag names it, its agent process is RUNNING[tag],
# and a tag in CANCELLED stops the agent and skips the next one; _SINK.deadline caps all tries together
RUNNING, CANCELLED = {}, set()


def _started(p):
    tag = getattr(_SINK, 'tag', None)
    if tag:
        RUNNING[tag] = p
        if tag in CANCELLED:   # cancelled while it was starting
            from . import store
            store.kill_tree(p)


def _ended(p):
    tag = getattr(_SINK, 'tag', None)
    if tag and RUNNING.get(tag) is p:
        RUNNING.pop(tag, None)


def _left(timeout):
    """Seconds this agent call may take, or 0 when the job was cancelled or its time is up."""
    if getattr(_SINK, 'tag', None) in CANCELLED:
        return 0
    dl = getattr(_SINK, 'deadline', None)
    return timeout if dl is None else max(0, min(timeout, dl - __import__('time').time()))


def cancel(tag):
    """Stop a running agent job now (its caller falls back to the built-in way)."""
    from . import store
    CANCELLED.add(tag)
    p = RUNNING.get(tag)
    if p:
        store.kill_tree(p)
    return {"cancelled": bool(p)}


def _run(cmd, text, timeout, env=None):
    """subprocess.run(input=text, capture_output=True, timeout=...) that cancel() can stop."""
    import subprocess
    from . import store
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8',
                         errors='replace', cwd=store.HOME, env=env, **store.NOWIN)
    _started(p)
    try:
        out, err = p.communicate(text, timeout=timeout)
    except subprocess.TimeoutExpired:
        store.kill_tree(p)
        p.communicate()
        raise
    finally:
        _ended(p)
    return subprocess.CompletedProcess(cmd, p.returncode, out, err)


def _claude_stream(cmd, text, timeout, env, sink):
    """Run Claude Code with streamed output, reporting how much of the reply is written so far. Returns (ok, reply, err)."""
    import subprocess
    import tempfile
    import threading
    from . import store
    # stderr goes to a file, not a pipe: a pipe nobody reads fills (4 KB on Windows) and stalls the reply mid-stream
    errf = tempfile.TemporaryFile(mode='w+', encoding='utf-8', errors='replace')
    p = subprocess.Popen(cmd + ['--output-format', 'stream-json', '--verbose', '--include-partial-messages'], stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=errf, text=True, encoding='utf-8', errors='replace',
                         cwd=store.HOME, env=env, **store.NOWIN)
    _started(p)
    killer = threading.Timer(timeout, lambda: store.kill_tree(p))
    killer.start()
    parts, result, n = [], None, 0
    try:
        try:
            p.stdin.write(text)
            p.stdin.close()
        except OSError:   # it exited before reading (signed out, an old CLI): its error is in errf
            pass
        for line in p.stdout:
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get('type') == 'stream_event':
                d = (e.get('event') or {}).get('delta') or {}
                if d.get('type') == 'text_delta':
                    parts.append(d.get('text', ''))
                    n += len(d.get('text', ''))
                    sink(n, parts)
            elif e.get('type') == 'result':
                result = e.get('result') if not e.get('is_error') else None
    finally:
        killer.cancel()
        store.kill_tree(p)   # no-op when it finished; never leaves a zombie or an orphaned node.exe
        _ended(p)
        p.wait()
        p.stdout.close()
        errf.seek(0)
        err = errf.read()[-600:]
        errf.close()
    reply = result or ''.join(parts)
    return p.returncode == 0 and bool(reply.strip()), reply, err


def agent_llm(text, timeout=600, fast=False, think=True):
    """Run one prompt on the user's own Claude Code or Codex subscription (no API key). Returns the reply text or None.
    fast: a short checking job, so Claude uses its quickest model. think=False: no extended thinking (a resume plan is as
    good without it and takes ~20 seconds instead of ~2 minutes); careful checks keep it."""
    import tempfile
    from . import agents, store
    if os.environ.get('APPLYTWIN_NO_AGENT'):   # tests: the same result on a laptop with Claude as on CI without it
        return None
    for name in agents.preferred(store.profile()):
        timeout = _left(timeout)
        if not timeout:   # cancelled, or out of time: the caller uses its built-in fallback
            return None
        try:
            if name == 'claude':
                # a one-shot plan doesn't need the biggest model; Sonnet is several times faster for this
                base = [agents.exe('claude'), '-p', '--model', 'haiku' if fast else os.environ.get('APPLYTWIN_PLAN_MODEL', 'sonnet'), '--tools', '']
                env = {**os.environ, **({} if think else {'MAX_THINKING_TOKENS': '0'})}
                sink = getattr(_SINK, 'fn', None)
                if sink:   # a build is showing progress: stream, so the timer follows the reply as it's written
                    ok, reply, err = _claude_stream(base, text, timeout, env, sink)
                    if ok:
                        return reply
                    _llm_log('claude', type('R', (), {'returncode': 1, 'stderr': err, 'stdout': ''})())
                    continue
                r = _run(base + ['--output-format', 'text'], text, timeout, env)
                if r.returncode == 0 and r.stdout.strip():
                    return r.stdout
                _llm_log('claude', r)
            else:
                for _ in range(8):   # each refused model is remembered, so this walk happens once per machine
                    if not _left(timeout):
                        return None
                    with tempfile.NamedTemporaryFile('r', suffix='.txt', delete=False) as f:
                        out = f.name
                    cmd = [agents.exe('codex'), 'exec', '--skip-git-repo-check', '--ephemeral', '-s', 'read-only', '-o', out,
                           *agents.codex_model_args(), '-']
                    try:
                        r = _run(cmd, text, _left(timeout))
                        reply = open(out, encoding='utf-8').read() if os.path.exists(out) else ''
                    finally:   # also when it timed out: a temp file per call otherwise piles up
                        if os.path.exists(out):
                            os.unlink(out)
                    if reply.strip():
                        return reply
                    _llm_log('codex', r)
                    if 'model_not_found' not in r.stdout + r.stderr or not agents.reject_model(r.stdout + r.stderr):
                        break   # anything but "that model isn't on your plan" won't be fixed by retrying; that one moves to the next model
        except Exception:
            continue
    return None


def _llm_log(name, r):
    """Why a call to the user's agent came back empty, for 'why did my resume use the built-in writer?'."""
    try:
        from . import store
        with open(store.path('llm.log'), 'a', encoding='utf-8') as f:
            f.write(f"{__import__('time').strftime('%Y-%m-%d %H:%M:%S')} {name} rc={r.returncode} {(r.stderr or r.stdout or '')[-600:]!r}\n")
    except Exception:
        pass


def call_llm(text, timeout=600, fast=False, think=True):
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
        out = agent_llm(text, timeout=timeout, fast=fast, think=think)
        if not out:
            return None
    return _first_json(out)


def _first_json(out):
    """The first JSON object in a model's reply, even with prose or code fences around it."""
    dec = json.JSONDecoder()
    for m in re.finditer(r'\{', out or ''):
        try:
            obj, _ = dec.raw_decode(out[m.start():])
            if isinstance(obj, dict):
                return obj
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------- apply a plan

def _with_bullet_ids(v):
    """The vault as the model sees it: each bullet labeled with its id, so nobody has to count (counting from 1 instead of 0
    once shifted every bullet on a resume)."""
    out = {k: v[k] for k in v if k != 'titles'}
    for sec in ENTRY_SECS:
        out[sec] = [{**e, 'bullets': [{'id': f"{e['id']}.{i}", 'text': b} for i, b in enumerate(e.get('bullets', []))]}
                    for e in v.get(sec, [])]
    return out


_COMMON = set("""a an and are as at be by for from has have in is it its of on or our that the this to we will with you your
    who what when where which while their they them using use used work working team teams role roles intern interns internship
    experience skills ability strong including include such other into about across more than also must able well new
    help helps support responsible responsibilities requirements qualifications preferred minimum summer 2026 2027 2028
    students student candidates candidate applicants year years please equal opportunity""".split())


def _jd_words(jd):
    """The posting's own vocabulary, weighted by how often it uses each word (generic and HR words left out)."""
    from collections import Counter
    c = Counter(w for w in re.findall(r'[a-z][a-z0-9+#./-]{2,}', (jd or '').lower()) if w not in _COMMON)
    return {w: min(n, 4) for w, n in c.items()}


def relevance(text, kws, jdw):
    """How directly a line speaks to this posting: its skill terms plus the posting's own words it shares."""
    t = ats.plain(text)
    return _kw_score(t, kws) + 0.35 * sum(jdw.get(w, 0) for w in set(re.findall(r'[a-z][a-z0-9+#./-]{2,}', t.lower())))


def _annotate_fit(full, jd):
    """Mark every entry and bullet 'high'/'medium'/'low' for this posting, so the model starts from what the posting asks for
    (it still decides: a hint, not a rule)."""
    kws, jdw = ats.keywords(jd), _jd_words(jd)
    ents = [(e, relevance(json.dumps(e, ensure_ascii=False), kws, jdw)) for sec in ENTRY_SECS for e in full.get(sec, [])]
    if not ents:
        return
    ranked = sorted(s for _, s in ents)
    lo, hi = ranked[len(ranked) // 3], ranked[(2 * len(ranked)) // 3]
    for e, s in ents:
        e['posting_fit'] = 'high' if s >= hi and s > 0 else 'low' if s <= lo else 'medium'
        bs = [relevance(b['text'], kws, jdw) for b in e.get('bullets', [])]
        top = max(bs, default=0)
        for b, s2 in zip(e.get('bullets', []), bs):
            b['fit'] = (e['posting_fit'] if len(bs) == 1 else
                        'high' if top and s2 >= 0.7 * top else 'low' if s2 <= 0.3 * top else 'medium')


def _vault_for_prompt(v, limit=40000, jd=''):
    """The vault as JSON, short sections (skills, awards, education) first so nothing important is cut off, and alternate
    phrasings dropped before any real content if it's too long."""
    full = _with_bullet_ids(v)
    if jd:
        _annotate_fit(full, jd)
    first = ['basics', 'skills', 'awards', 'education', 'research', 'certifications']
    ordered = {k: full[k] for k in first if k in full}
    ordered.update({k: full[k] for k in full if k not in ordered})
    out = json.dumps(ordered, ensure_ascii=False)
    if len(out) > limit:
        for sec in ENTRY_SECS:
            for e in ordered.get(sec, []):
                e.pop('alts', None)
        out = json.dumps(ordered, ensure_ascii=False)
    return out[:limit]


def _words(s):
    return set(re.findall(r'[a-z0-9]+', (s or '').lower()))


def _closest(bullets, text):
    """Index of the vault bullet a rewrite came from, by shared words (ids can be off by one; the words can't)."""
    w = _words(text)
    best, score = None, 0.0
    for i, b in enumerate(bullets):
        bw = _words(b)
        s = len(w & bw) / (len(w | bw) or 1)
        if s > score:
            best, score = i, s
    return best, score


def apply(v, plan, jd=''):
    """Vault + plan -> concrete resume dict, plus a report of accepted/rejected rewrites."""
    v = ensure_ids(copy.deepcopy(v))
    if isinstance(plan, dict) and len(plan) == 1 and isinstance(next(iter(plan.values())), dict):
        plan = next(iter(plan.values()))   # {"plan": {...}} from a chatty model
    plan = plan if isinstance(plan, dict) else {}
    vt = vault_text(v)
    out = {"basics": copy.deepcopy(v.get('basics', {})), "titles": v.get('titles', {})}
    rep = {"rewrites": [], "rejected": [], "notes": plan.get('notes', ''), "positioning": plan.get('positioning', ''),
           "requirements": plan.get('requirements', [])}
    avoid = set(learn_avoid(v))
    kws = ats.keywords(jd) if jd else []
    head = v.get('basics', {}).get('headline', [])
    if plan.get('headline'):
        stems = {w[:5] for w in _words(vt)}   # 'Recommendation Systems' is backed by a vault that says 'recommender system'
        ok = [h for h in plan['headline'] if isinstance(h, str) and (h in head or (
            len(h) <= 40 and _words(h) and all(w[:5] in stems or w in GENERIC_TAG for w in _words(h))))]
        out['basics']['headline'] = ok[:4] or head
    out['education'] = v.get('education', [])
    # a plan that numbers bullets from 1 never uses .0 and points one past the end somewhere: shift it back
    refs = [r for sec in ENTRY_SECS for c in (plan.get(sec) or []) if isinstance(c, dict) for r in (c.get('bullets') or [])]
    nums = [(m.group(1), int(m.group(2))) for r in refs
            for m in [re.match(r'(.+)\.(\d+)$', str(r.get('from') if isinstance(r, dict) else r))] if m]
    allb = {e['id']: len(e.get('bullets', [])) for sec in ENTRY_SECS for e in v.get(sec, [])}
    one_based = bool(nums) and all(n >= 1 for _, n in nums) and any(n == allb.get(i, -1) for i, n in nums)
    for sec in ENTRY_SECS:
        byid = {e['id']: e for e in v.get(sec, [])}
        if sec == 'experience':   # a titled role on a design team or club ("Avionics Subteam Lead") may count as experience
            byid.update({e['id']: e for e in v.get('leadership', []) if e.get('title') and e['id'] not in byid})
        chosen = plan.get(sec)
        if chosen is None:
            out[sec] = v.get(sec, [])
            continue
        lst = []
        for c in chosen:
            cid = c['id'] if isinstance(c, dict) else c
            e = byid.get(_near_id(cid, byid))
            if not e:
                continue
            e2 = {k: e[k] for k in e if k != 'bullets'}
            bl, used = [], set()
            for ref in (c.get('bullets') if isinstance(c, dict) and c.get('bullets') is not None else
                        [f'{cid}.{i}' for i in range(len(e.get('bullets', [])))]):
                src_id, text = (ref.get('from'), ref.get('text')) if isinstance(ref, dict) else (ref, None)
                m = re.match(r'(.+)\.(\d+)$', str(src_id or ''))
                owner = e   # a bullet only ever appears under its own role/project, whatever id the plan wrote
                obl = owner.get('bullets', [])
                if not obl:
                    continue
                k = (int(m.group(2)) - (1 if one_based else 0)) if m else -1
                if text:   # a rewrite: find the bullet it came from by its words
                    near, score = _closest(obl, text)
                    if near is not None and (not 0 <= k < len(obl) or score > len(_words(text) & _words(obl[k])) / (len(_words(text) | _words(obl[k])) or 1)):
                        k = near
                if m and _near_id(m.group(1), {e['id']}) != e['id'] and not text:
                    continue   # a bare reference to another entry's bullet: skip it rather than mislabel
                if not 0 <= k < len(obl):
                    continue
                orig = obl[k]
                if f"{e['id']}.{k}" in avoid:
                    continue   # the user said never to use this one
                src_id = f"{owner['id']}.{k}"
                if text and text.strip() != orig:
                    src = owner
                    etxt = ' '.join([src.get('title', ''), src.get('org', ''), src.get('name', ''), src.get('tagline', ''),
                                     ' '.join(src.get('tech', []))] + src.get('bullets', []) + src.get('alts', []))
                    why = check_rewrite(orig, text, vt, jd, etxt)
                    if why:
                        rep['rejected'].append({"bullet": src_id, "reason": why, "text": text})
                        text = None
                    else:
                        rep['rewrites'].append({"bullet": src_id, "from": orig, "to": text})
                if (text or orig) not in bl and k not in used:
                    bl.append(text or orig)
                    used.add(k)
            # never ship a thin entry: roles keep at least 2 bullets and projects/leadership at least 1 when the vault has
            # them (the renderer trims to one page afterwards, so this never overflows)
            # a section of one entry with one line reads as an afterthought: that entry gets a second line too
            least = 2 if sec == 'experience' or len(chosen) == 1 else 1
            for bi, b in enumerate(e.get('bullets', [])):
                if len(bl) >= least:
                    break
                if f"{e['id']}.{bi}" in avoid or bi in used or weak(b):
                    continue
                if b not in bl and not any(_closest([b], x)[1] > 0.5 for x in bl):
                    bl.append(b)
            e2['bullets'] = _one_per_fact(_upgrade(bl, e, avoid, kws, least))
            e2['_used'] = sorted(used | {i for i, b in enumerate(e.get('bullets', [])) if b in e2['bullets']})
            lst.append(e2)
        out[sec] = lst
    # a lifeguard or cashier job doesn't belong on an avionics resume when there's real material to show instead
    exp = out.get('experience', [])
    real = [e for e in exp if not SERVICE.search(f"{e.get('title', '')} {e.get('org', '')}")]
    if len(real) >= 2 and len(real) + len(out.get('projects', [])) >= 4:
        out['experience'] = [e for e in exp if e in real or SERVICE.search(jd or '') and
                             SERVICE.search(jd).group(0).lower() in f"{e.get('title', '')} {e.get('org', '')}".lower()]
    moved = {e.get('id') for e in out.get('experience', [])}
    if out.get('leadership'):
        out['leadership'] = [e for e in out['leadership'] if e.get('id') not in moved]   # never listed twice
    rid = {p.get('id'): p for p in v.get('research', [])}
    # publications and research always appear (the plan only orders them): for any student they're among the strongest lines
    # on the page, and a hiring manager never expects them cut. Trimming to one page removes them only as a last resort.
    picked = [rid[_near_id(i, rid)] for i in plan.get('research') or [] if _near_id(i, rid) in rid]
    out['research'] = picked + [p for p in v.get('research', []) if p not in picked]
    aw = v.get('awards', [])
    out['awards'] = _pick_awards(aw, plan['awards']) if 'awards' in plan else aw
    out['awards'] = _not_repeated(out['awards'], out)
    if len(out['awards']) == 1 and out['education'] and isinstance(out['awards'][0], str):
        # one award doesn't need a section of its own: it reads better beside the school's honors
        out['education'] = copy.deepcopy(out['education'])
        out['education'][0]['honors'] = list(out['education'][0].get('honors') or []) + out['awards']
        out['awards'] = []
    out['certifications'] = v.get('certifications', [])
    out['skills'] = _named_tools(_pick_skills(v.get('skills', []), plan.get('skills')), v, jd)
    out['education'] = [_courses_for(e, jd) for e in out['education']]
    # every section the plan selected is shown, education leads, and experience is newest first
    order = [s for s in (plan.get('order') or v.get('order') or []) if out.get(s)]
    order += [s for s in (v.get('order') or []) if s not in order and out.get(s) and s not in ('research', 'awards')]
    order += [s for s in ('research',) if s not in order and out.get(s)]
    order += [s for s in ('awards',) if s not in order and out.get(s) and s in plan]
    if 'education' in order and order[0] != 'education':
        order.remove('education')
        order.insert(0, 'education')
    tail = [s for s in ('skills', 'certifications', 'awards') if s in order]
    order = [s for s in order if s not in tail] + tail   # what you did leads; lists of skills and honors close the page
    out['order'] = order
    for sec in ('experience', 'leadership', 'volunteering'):
        if out.get(sec):
            out[sec] = sorted(out[sec], key=_recency, reverse=True)
    return out, rep


AUDIT = """You check resume rewrites. Each item has the candidate's ORIGINAL bullet (the truth) and a NEW version. Resumes
reframe work to fit a job, and that is fine: a stronger verb that still fits their role ("built" for "wrote", "ran" for
"analyzed"), the obvious purpose or audience of the work, the posting's vocabulary for the same work, and cutting minor
qualifiers. Flag ONLY claims a recruiter, interviewer or reference check would catch as false:
- a new or changed number, metric, percentage, team size, user count or dollar amount, or a number moved to a different thing
- a number, size or scale from the original dropped and replaced by a bigger claim ("1/5-scale car" -> "on-road vehicle",
  "regional finalist" -> "finalist", "estimated $310K" -> "$310K")
- a job title, employer, degree, award, rank/placement or date that differs from the original or the item's "entry"
- leading or managing people or teams they only joined or supported
New tools, methods, technologies, outcomes and purposes are ALLOWED (the candidate chose this); never flag them.
Reply with ONLY JSON: {"overclaims": [{"id": "<item id>", "why": "<short reason>"}]}

ITEMS:
"""


def audit(res, rep):
    """A second, quick read of every rewrite against its original: any that claims more than the vault says goes back to
    the user's own words (the fact checker catches new numbers and names, not a quietly upgraded verb or a dropped qualifier)."""
    ents = {e.get('id'): e for sec in ENTRY_SECS for e in res.get(sec, []) if e.get('id')}

    def entry(bid):   # the role/project the bullet belongs to: its tools and title back a rewrite too
        e = ents.get(str(bid).rsplit('.', 1)[0]) or {}
        return ' | '.join(x for x in [e.get('title', ''), e.get('org', '') or e.get('name', ''), e.get('tagline', ''),
                                       ', '.join(e.get('tech', []) or [])] if x)[:400]
    items = [{"id": str(i), "original": r['from'], "new": r['to'], "entry": entry(r['bullet'])} for i, r in enumerate(rep['rewrites'])]
    try:
        out = call_llm(AUDIT + json.dumps(items, ensure_ascii=False), timeout=120)   # Sonnet: Haiku let quiet overclaims through
    except Exception:
        out = None
    flagged = {str(x.get('id')): x.get('why', '') for x in (out or {}).get('overclaims', []) if isinstance(x, dict)}
    if not flagged:
        return 0
    keep = []
    for i, r in enumerate(rep['rewrites']):
        if str(i) not in flagged:
            keep.append(r)
            continue
        for sec in ENTRY_SECS:
            for e in res.get(sec, []):
                e['bullets'] = [r['from'] if b == r['to'] else b for b in e.get('bullets', [])]
        rep['rejected'].append({"bullet": r['bullet'], "reason": 'overclaims: ' + flagged[str(i)], "text": r['to']})
    rep['rewrites'] = keep
    return len(flagged)


def trim_worth(res, kws, jd):
    """What to keep when the page runs long: measured results, the posting's own words, and the order the plan chose within
    each entry (keyword overlap alone threw out 'Merged 5 PRs into kubectl' and kept 'Reviewed PRs and triaged issues')."""
    jdw = _jd_words(jd)
    rank = {}
    for sec in ENTRY_SECS:
        for e in res.get(sec, []):
            for i, b in enumerate(e.get('bullets', [])):
                rank.setdefault(b, i)
    return lambda b: strength(b, kws) + 0.35 * sum(jdw.get(w, 0) for w in set(re.findall(r'[a-z][a-z0-9+#./-]{2,}', ats.plain(b).lower()))) - 1.0 * rank.get(b, 0)


def _near_id(cid, ids):
    """The id the plan meant: models misspell the made-up ids now and then ('utaustinodinin' for 'utaustinodenin'), which
    silently dropped someone's best entry. Exact first, then the one clearly closest."""
    import difflib
    if not isinstance(cid, str) or cid in ids:
        return cid
    m = difflib.get_close_matches(cid, [i for i in ids if isinstance(i, str)], n=1, cutoff=0.8)
    return m[0] if m else cid


def _same_fact(a, b):
    """Two lines stating one fact: most words shared, or the same distinctive figure ('6x', '1e-12', '4B+') with real overlap."""
    wa, wb = _words(ats.plain(a)), _words(ats.plain(b))
    j = len(wa & wb) / (len(wa | wb) or 1)
    figs = lambda t: {m for m in re.findall(r'\d[\d.,]*\s*(?:x|%|[kmb]\+?|e-?\d+)\b|\d[\d.,]*\+?\s+[a-z][a-z-]{3,}', ats.plain(t).lower())}
    return j > 0.55 or (j > 0.25 and bool(figs(a) & figs(b)))


def _one_per_fact(bl):
    out = []
    for b in bl:
        if not any(_same_fact(b, x) for x in out):
            out.append(b)
    return out


def _fill_page(v, res, jd, style, probe, k=1.0):
    """A two-thirds-empty page reads as thin. While there's clear room, add the user's next strongest true bullets for
    this posting (from the same roles first, then roles/projects the plan left out), never past one page."""
    from . import render
    v = ensure_ids(copy.deepcopy(v))
    kws = ats.keywords(jd)
    avoid = set(learn_avoid(v))
    shown = {e.get('id') for sec in ENTRY_SECS for e in res.get(sec, [])}
    pick = trim_worth({}, kws, jd)   # the same measure trimming uses: results and the posting's words, not keywords alone
    cands = []
    for sec in ('experience', 'projects', 'leadership'):
        byid = {e['id']: e for e in v.get(sec, [])}
        for e in res.get(sec, []):
            src = byid.get(e.get('id'))
            for i, b in enumerate((src or {}).get('bullets', [])):
                if (f"{src['id']}.{i}" in avoid or i in e.get('_used', []) or weak(b)
                        or any(_closest([b], x)[1] > 0.45 or _same_fact(b, x) for x in e.get('bullets', []))):
                    continue
                cands.append((pick(b), 'bullet', sec, e.get('id'), b))
        for e in v.get(sec, []):
            if e['id'] not in shown and e.get('bullets') and not OLD.search(json.dumps(e)):
                cands.append((max(pick(b) for b in e['bullets']) - 1, 'entry', sec, e['id'], e))
    shown_skills = {s.get('label') for s in res.get('skills', [])}
    for s in v.get('skills', []):   # a skills line trimmed to fit is one short line: often exactly what a gap needs
        if s.get('label') not in shown_skills and s.get('items'):
            cands.append((_kw_score(ats.plain(' '.join(s['items'])), kws) + 1, 'skills', 'skills', s.get('label'), s))
    cands.sort(key=lambda c: -c[0])
    best, rest = cands[:8], sorted(cands[8:], key=lambda c: len(json.dumps(c[4])))   # strongest first, then the shortest
    added, misses = [], 0
    for score, kind, sec, eid, x in best + rest[:10]:
        if misses >= 6:   # six in a row didn't fit: the page is full
            break
        if kind == 'skills':
            res.setdefault('skills', []).append(x)
            undo = lambda: res['skills'].pop()
        elif kind == 'bullet':
            tgt = next(e for e in res[sec] if e.get('id') == eid)
            tgt['bullets'].append(x)
            undo = lambda: tgt['bullets'].pop()
            src_b = next((e for e in v[sec] if e['id'] == eid), {}).get('bullets', [])
            tgt.setdefault('_used', []).extend(j for j, b in enumerate(src_b) if b == x)
        else:
            e2 = {k: x[k] for k in x if k != 'bullets'}
            e2['bullets'] = [b for b in x['bullets'] if not weak(b)][:2] or x['bullets'][:1]
            res.setdefault(sec, []).append(e2)
            if sec not in res.get('order', []):   # a new section goes with the others, before skills/awards close the page
                o = res.setdefault('order', [])
                o.insert(next((i for i, s in enumerate(o) if s in ('skills', 'certifications', 'awards')), len(o)), sec)
            undo = lambda: res[sec].pop()
        if not render.fits(res, style, k, probe):
            undo()
            misses += 1
            continue   # too big for the space left: try the next, smaller candidate
        misses = 0
        added.append(f"{sec}: {ats.plain(x if isinstance(x, str) else x.get('org') or x.get('name') or x.get('label', ''))[:60]}")
    return added


MONTHS = {m: i for i, m in enumerate(['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'], 1)}


def _when(s):
    """'November 2025' -> 2025.83; 'Present' -> far future; unknown -> None."""
    s = (s or '').strip().lower()
    if not s:
        return None
    if re.search(r'present|current|now|ongoing', s):
        return 9999.0
    y = re.search(r'(19|20)\d\d', s)
    if not y:
        return None
    mo = next((v for k, v in MONTHS.items() if k in s), 6)
    return int(y.group(0)) + mo / 12


def _recency(e):
    """Sort key: current roles first, then by end date (resumes read newest first)."""
    dates = e.get('dates') or ' '.join(str(e.get(k, '')) for k in ('start', 'end'))
    parts = re.split(r'\s*[–—-]\s*|\s+to\s+', str(dates)) if dates else []
    end = _when(e.get('end')) or (_when(parts[-1]) if parts else None)
    start = _when(e.get('start')) or (_when(parts[0]) if parts else None)
    when = end or start or 0
    # anything current or finished in the last year is "recent": among those the plan's relevance order stands (sorted() is
    # stable), so this summer's internship isn't pushed under an older part-time role that happens to still be ongoing
    import time
    now = time.localtime()
    return 9999.0 if when >= now.tm_year + now.tm_mon / 12 - 1 else when


def _house_rules(res, ctx):
    """Field conventions a screener checks at a glance. Banking and finance read strict reverse-chronological order (a
    recent role listed below an older one looks like a formatting error), so relevance never reorders their roles."""
    if ctx.get('field') in ('finance', 'consulting'):
        for sec in ('experience', 'leadership'):
            if res.get(sec):
                res[sec] = sorted(res[sec], key=lambda e: _when_end(e), reverse=True)


def _when_end(e):
    dates = e.get('dates') or ' '.join(str(e.get(k, '')) for k in ('start', 'end'))
    parts = re.split(r'\s*[–—-]\s*|\s+to\s+', str(dates)) if dates else []
    return (_when(e.get('end')) or (_when(parts[-1]) if parts else None) or 0,
            _when(e.get('start')) or (_when(parts[0]) if parts else None) or 0)


def _not_repeated(awards, res):
    """An award already stated under education or in a bullet only takes a line twice."""
    seen = json.dumps([res.get('education', [])] + [[e.get(k) for k in ('org', 'name', 'title', 'tagline')] + e.get('bullets', [])
                                                     for sec in ENTRY_SECS for e in res.get(sec, [])], ensure_ascii=False)
    sw = _words(seen)
    keep = []
    for a in awards:
        txt = a if isinstance(a, str) else ' '.join(str(x) for x in a.values() if isinstance(x, str))
        w = _words(txt)
        name = re.split(r'\s*[,(;:]', txt.strip())[0].strip().lower()   # "Kelley Investment Banking Workshop, admitted 2026"
        if (len(w) >= 3 and len(w & sw) / len(w) >= 0.75) or (len(name) >= 12 and name in seen.lower()):
            continue
        keep.append(a)
    return keep


def _pick_awards(aw, picks):
    texts = [a if isinstance(a, str) else json.dumps(a) for a in aw]
    ints = [p for p in picks if isinstance(p, int)]
    shift = 1 if ints and min(ints) >= 1 and max(ints) == len(aw) else 0   # counted from 1
    out = []
    for p in picks:
        if isinstance(p, int) and 0 <= p - shift < len(aw):
            a = aw[p - shift]
        elif isinstance(p, str):
            i, score = _closest(texts, p)
            a = aw[i] if i is not None and score > 0.4 else None
        else:
            a = None
        if a is not None and a not in out:
            out.append(a)
    return out or aw


GENERIC_TAG = {'and', 'systems', 'system', 'engineering', 'engineer', 'development', 'design', 'analysis', 'research', 'methods',
               'tools', 'applications'}   # words that frame a tag without claiming anything


def _named_tools(skills, v, jd):
    """A tool the posting asks for by name ('Proficiency with Microsoft Excel') that the user really used (in a role's or
    project's tech or a bullet) belongs in the skills section, not only buried in a line of text."""
    if not jd or not skills:
        return skills
    shown = ats.plain(json.dumps(skills, ensure_ascii=False))
    tech = [t for sec in ENTRY_SECS for e in v.get(sec, []) for t in (e.get('tech') or []) if isinstance(t, str)]
    low = shown.lower()
    add = []
    for t, w, n in ats.keywords(jd)[:15]:
        hit = next((x for x in tech if ats.PATTERNS[t].search(x)), None)   # a tool listed on a real role or project
        if t not in ats.SOFT and hit and not ats.PATTERNS[t].search(shown) and hit.lower() not in low and hit not in add:
            add.append(hit)
    if not add:
        return skills
    skills = copy.deepcopy(skills)
    tgt = next((s for s in skills if re.search(r'tool|software|technolog|program|languag', s.get('label', ''), re.I)), skills[0])
    tgt['items'] = tgt.get('items', []) + add[:3]
    return skills


def _courses_for(e, jd):
    """Coursework this posting cares about first, at most six (a list of every class reads as filler)."""
    cw = e.get('coursework') or []
    if not jd or len(cw) <= 4:
        return e
    stems = {x[:5] for x in _jd_words(jd)}
    generic = {'analysis', 'real', 'topics', 'introduction', 'intro', 'principles', 'applications', 'fundamentals', 'advanced',
               'theory', 'methods', 'mathematics', 'engineering', 'science', 'design', 'systems', 'computation', 'structures'}
    score = lambda c: sum(1 for w in _words(c) if len(w) > 3 and w not in generic and w[:5] in stems)
    keep = sorted(range(len(cw)), key=lambda i: (-score(cw[i]), i))[:6]
    return {**e, 'coursework': [cw[i] for i in keep]}


def _pick_skills(vault_skills, picks):
    """Keep the plan's order and emphasis, but only real items, matched to the user's labels loosely ('Programming
    Languages' is 'Languages'), and never drop most of what the user knows."""
    if not picks:
        return vault_skills
    norm = lambda x: re.sub(r'[^a-z0-9+#]', '', (x or '').lower())
    allitems = {norm(i): i for s in vault_skills for i in s.get('items', [])}
    out, used = [], set()
    for s in picks:
        if not isinstance(s, dict):
            continue
        items = [allitems[norm(i)] for i in s.get('items', []) if norm(i) in allitems and norm(i) not in used]
        lab = next((vs['label'] for vs in vault_skills if norm(vs.get('label')) == norm(s.get('label'))), None) or \
            next((vs['label'] for vs in vault_skills if items and items[0] in vs.get('items', [])), s.get('label'))
        if items:
            used.update(norm(i) for i in items)
            out.append({"label": lab, "items": items})
    if sum(len(s['items']) for s in out) < 0.35 * len(allitems):   # a lost line, not a choice: add back the rest
        for vs in vault_skills:
            rest = [i for i in vs.get('items', []) if norm(i) not in used]
            if not rest:
                continue
            tgt = next((o for o in out if o['label'] == vs.get('label')), None)
            if tgt:
                tgt['items'] += rest
            else:
                out.append({"label": vs.get('label'), "items": rest})
            used.update(norm(i) for i in rest)
    return out or vault_skills


def learn_avoid(v):
    try:
        from . import learn
        return learn.context_for({}).get('avoid', [])
    except Exception:
        return []


# ---------------------------------------------------------------- live progress
# what a resume build is doing right now, per job, with a time-left estimate from how long each step has actually taken
# on this computer (Claude/Codex speed differs a lot between people and plans)
STAGES = [('plan', 'Writing your resume plan'), ('fix', 'Fixing lines the fact checker flagged'),
          ('audit', 'Checking every rewrite is true'), ('fit', 'Fitting one page and making the PDF')]
DEFAULT_SECS = {'plan': 25, 'fix': 22, 'audit': 25, 'fit': 15}   # Sonnet without extended thinking; each computer learns its own
PROGRESS = {}


def _timings():
    from . import store
    t = store.load('timings.json', {}) or {}
    # a step never measured on this computer uses the starting point, not whatever was stored before it ran once
    S = {'len': 4400.0, 'rate': 330.0, 'wait': 3.0}   # a plan's length, writing speed (chars/s) and wait before the first word
    return {k: {'avg': float((t.get(k) or {}).get('avg', d)) if int((t.get(k) or {}).get('n', 0)) else float(d),
                'n': int((t.get(k) or {}).get('n', 0)),
                **{x: float((t.get(k) or {}).get(x, S[x])) if int((t.get(k) or {}).get('sn', 0)) else S[x] for x in S},
                'sn': int((t.get(k) or {}).get('sn', 0)),
                'p': float((t.get(k) or {}).get('p', 0.6 if k == 'fix' else 1.0))} for k, d in DEFAULT_SECS.items()}


def _record(secs, stream=None):
    """Learn each step's typical length (and how often the optional fix step runs) from finished builds."""
    from . import store
    try:
        t = _timings()
        for k in DEFAULT_SECS:
            r = t[k]
            w = 0.5 if r['n'] < 3 else 0.25   # quick to learn this machine, then steady
            if k in secs:
                r['avg'] = (1 - w) * r['avg'] + w * secs[k] if r['n'] else secs[k]
                r['n'] += 1
            if k == 'fix' and 'plan' in secs:
                r['p'] = (1 - w) * r['p'] + w * (1.0 if 'fix' in secs else 0.0)
            if stream and k in stream:   # how long the reply was, how fast it came, how long before it started
                ws = 0.5 if r['sn'] < 3 else 0.25
                for x in ('len', 'rate', 'wait'):
                    r[x] = (1 - ws) * r[x] + ws * stream[k][x] if r['sn'] else stream[k][x]
                r['sn'] += 1
        store.save('timings.json', t)
    except Exception:
        pass


class _Track:
    def __init__(self, key, ai):
        import time
        self.key, self.t0, self.secs, self.cur, self.at = key, time.time(), {}, None, time.time()
        self.chars, self.first, self.stream = 0, None, {}
        self.skip = set() if ai else {'plan', 'fix'}
        PROGRESS[key] = self
        if ai:
            self.stage('plan')
        # Autopilot's tools run in another process than the app: publish progress to a file once a second so the app
        # can show it wherever the build runs
        self.live = True
        __import__('threading').Thread(target=self._publish, daemon=True).start()

    def _file(self):
        from . import store
        os.makedirs(store.path('progress'), exist_ok=True)
        return store.path('progress', re.sub(r'[^\w-]', '_', str(self.key)) + '.json')

    def _publish(self):
        import time
        from . import store
        while self.live:
            try:
                tmp = self._file() + '.tmp'
                with open(tmp, 'w', encoding='utf-8') as f:
                    json.dump(self.view(), f)
                store.replace(tmp, self._file())
            except Exception:
                pass
            time.sleep(1)
        try:
            os.unlink(self._file())
        except OSError:
            pass

    def written(self, n, parts=None):
        import time
        if self.first is None:
            self.first = time.time()
        self.chars = n
        if parts is not None and self.cur in ('plan', 'fix'):
            self.parts = parts   # the plan so far, for the live "watch it tailor" view (not the checker's own reply)

    def plan_ready(self, plan, v):
        """The finished plan (and each bullet's original wording), so the live view shows every rewrite even when the
        agent didn't stream (Codex)."""
        self.parts = [json.dumps(plan, ensure_ascii=False)]
        self.src = {f"{e['id']}.{i}": b for sec in ENTRY_SECS for e in ensure_ids(copy.deepcopy(v)).get(sec, [])
                    for i, b in enumerate(e.get('bullets', []))}

    def watch(self):
        """What the plan has decided so far, read from the reply as it streams: the requirements, the story and the
        rewrites (original -> new), so the user watches their resume being written instead of a spinner."""
        text = ''.join(getattr(self, 'parts', None) or [])
        if not text:
            return None
        s = lambda x: _unq(x)
        out = {}
        m = re.search(r'"requirements"\s*:\s*\[(.*?)(?:\]|$)', text, re.S)
        if m:
            out['requirements'] = [s(x) for x in re.findall(r'"((?:[^"\\]|\\.)*)"', m.group(1))][:3]
        m = re.search(r'"positioning"\s*:\s*"((?:[^"\\]|\\.)*)', text)
        if m:
            out['positioning'] = s(m.group(1))
        src = getattr(self, 'src', {}) or {}
        rw = []
        for fid, new in re.findall(r'\{\s*"from"\s*:\s*"([^"]+)"\s*,\s*"text"\s*:\s*"((?:[^"\\]|\\.)*)', text):
            rw.append({"from": ats.plain(src.get(fid, ''))[:600], "to": ats.plain(s(new))[:600]})
        out['rewrites'] = rw[-8:]
        prev = getattr(self, '_seen', {}) or {}   # a revision streams from the start: keep showing what was there until it catches up
        for k in ('requirements', 'positioning', 'rewrites'):
            if not out.get(k) or (k == 'rewrites' and len(out[k]) < len(prev.get(k) or [])):
                out[k] = prev.get(k) or out.get(k)
        self._seen = out
        return out

    def _close(self, now):
        if self.cur:
            self.secs[self.cur] = now - self.at
            if self.chars > 200 and self.first:
                self.stream[self.cur] = {'len': self.chars, 'rate': self.chars / max(0.5, now - self.first), 'wait': self.first - self.at}
        self.chars, self.first = 0, None

    def stage(self, name):
        import time
        now = time.time()
        self._close(now)
        for k, _ in STAGES:   # steps between the last one and this one didn't happen this time
            if k == name:
                break
            if k not in self.secs and k != self.cur:
                self.skip.add(k)
        self.cur, self.at = name, now

    def done(self):
        import time
        self._close(time.time())
        _record(self.secs, self.stream)
        self.stop()

    def stop(self):
        self.live = False
        if PROGRESS.get(self.key) is not self:   # a newer build for this job owns the timer now: leave it alone
            return
        PROGRESS.pop(self.key, None)
        try:
            os.unlink(self._file())
        except OSError:
            pass

    def view(self):
        import time
        now = time.time()
        if not getattr(self, '_t', None) or self._t[0] != self.cur:   # read the learned timings once per step, not every second
            self._t = (self.cur, _timings())
        t = self._t[1]
        order = [k for k, _ in STAGES]
        cur = self.cur or 'audit'   # a build from a ready plan starts at the checks
        i = order.index(cur)
        left = 0.0
        for k in order[i + 1:]:
            if k not in self.skip:
                left += t[k]['avg'] * (t[k]['p'] if k == 'fix' else 1)
        inside = now - self.at
        avg = t[cur]['avg']
        s = t[cur]
        if cur in ('plan', 'fix') and self.first:   # the reply is being written: time left from what's left to write
            rate = max(30.0, self.chars / max(0.5, now - self.first))
            here = max(s['len'] * 1.05 - self.chars, s['len'] * 0.04) / rate
            slow_now = False
        elif cur in ('plan', 'fix') and s['sn']:     # waiting for the first word, then the usual length at the usual speed
            here = max(s['wait'] - inside, 1.5) + s['len'] / s['rate']
            slow_now = inside > s['wait'] * 1.5 + 8
        else:   # past its usual length a step is nearly done, but never "0 seconds" while it is still running
            here = max(avg - inside, min(20.0, 0.15 * inside + 3))
            slow_now = inside > avg * 1.15 + 5
        left += here
        return {"stage": cur, "elapsed": round(now - self.t0, 1), "eta": round(left, 1), "slow": slow_now,
                "written": self.chars if cur in ('plan', 'fix') else 0, "live": self.watch(),
                "steps": [{"id": k, "label": lab, "state": 'done' if k in self.secs else 'now' if k == cur else
                           'skipped' if k in self.skip else 'next'} for k, lab in STAGES]}


def _unq(x):
    try:
        return json.loads('"' + x + '"')
    except ValueError:   # cut mid-escape while streaming
        return x.replace('\\"', '"').replace('\\n', ' ')


def progress(key):
    """The live view of a build for this job, from this process or (Autopilot's builds) the file another process keeps
    fresh. A file older than a few seconds belongs to a build that died."""
    import time
    p = PROGRESS.get(key)
    if p:
        return p.view()
    from . import store
    f = store.path('progress', re.sub(r'[^\w-]', '_', str(key)) + '.json')
    try:
        age = time.time() - os.path.getmtime(f)
        if age < 4:
            v = json.load(open(f, encoding='utf-8'))
            v['eta'] = max(1.0, v['eta'] - age)
            v['elapsed'] += age
            return v
    except (OSError, ValueError):
        pass
    return None


def tailor(v, job, jd, mode='auto', plan=None, style=None, out_dir=None):
    """Full pipeline -> {pdf, pages, ats before/after, rewrites}."""
    track = _Track(job.get('id', 'general'), ai=plan is None and mode in ('auto', 'api'))
    track.src = {f"{e['id']}.{i}": b for sec in ENTRY_SECS for e in ensure_ids(copy.deepcopy(v)).get(sec, [])
                 for i, b in enumerate(e.get('bullets', []))}
    _SINK.fn = track.written   # this thread's model calls report the reply as it's written
    try:
        r = _tailor(v, job, jd, mode, plan, style, out_dir, track)
        track.done()
        return r
    except Exception:
        track.stop()
        raise
    finally:
        _SINK.fn = None


def _tailor(v, job, jd, mode, plan, style, out_dir, track):
    from . import learn, render, store
    ctx = learn.context_for(job)
    style = style or ctx['template']
    if plan is None:
        if mode in ('auto', 'api'):
            import time
            t0 = time.time()
            for _ in range(2):   # a busy or rate-limited agent often answers on the second try; the built-in writer is a big step down
                left = 330 - (time.time() - t0)   # never leave someone waiting: past this, the built-in writer takes over
                if left < 90:
                    break
                try:
                    plan = call_llm(prompt(v, job, jd, ctx), timeout=min(200, left), think=False)   # ~20 s without extended thinking
                except Exception:
                    plan = None
                if plan:
                    break
        if plan is None:
            plan = heuristic_plan(v, jd, title=job.get('title', ''), ctx=ctx)
            mode = 'heuristic'
        else:
            mode = 'api'
            track.plan_ready(plan, v)
    else:
        mode = 'agent'
    res, rep = apply(v, plan, jd)
    _house_rules(res, ctx)
    if mode == 'api' and rep['rejected']:   # one revision: show the model exactly what the fact checker refused, and why
        track.stage('fix')
        fix = (prompt(v, job, jd, ctx) + '\n\nYOUR PREVIOUS PLAN:\n' + json.dumps(plan, ensure_ascii=False)[:12000] +
               '\n\nTHE FACT CHECKER REJECTED THESE REWRITES (bullet, reason, your text):\n' +
               '\n'.join(f"- {r['bullet']}: {r['reason']}: {r['text']}" for r in rep['rejected']) +
               '\n\nReturn the same JSON plan with each rejected rewrite fixed: keep its facts exactly as the vault states them '
               '(no new numbers, tools or claims), or use the bullet id as-is. Change nothing else.')
        try:
            plan2 = call_llm(fix, timeout=200, think=False)
            if plan2:
                res2, rep2 = apply(v, plan2, jd)
                _house_rules(res2, ctx)
                if len(rep2['rejected']) < len(rep['rejected']):
                    plan, res, rep = plan2, res2, rep2
        except Exception:
            pass
    if mode in ('api', 'agent') and rep['rewrites']:   # Autopilot's own plans get the same honesty check
        track.stage('audit')
        audit(res, rep)
    track.stage('fit')
    out_dir = out_dir or store.path('resumes', job.get('id', 'general'))
    name = (re.sub(r'[^\w]+', '_', res['basics'].get('name', 'Resume') or '', flags=re.UNICODE).strip('_') or 'Resume') + '_Resume.pdf'
    pdf = os.path.join(out_dir, name)
    kws = ats.keywords(jd)
    worth = trim_worth(res, kws, jd)
    r = render.render(res, style, pdf, worth=worth)
    if r['pages'] == 1 and style != 'latex':   # room left on the page (also after trimming a big item): fill it with real material
        base = r['resume'] if r['dropped'] else res
        added = _fill_page(v, base, jd, style, pdf + '.probe.pdf', k=r['scale'])
        if added:
            rep['added'] = added
            res = base
            first_cut = r['dropped']
            r = render.render(res, style, pdf, worth=worth)
            r['dropped'] = first_cut + [x for x in r['dropped'] if x not in first_cut]   # what the first fit cut stays reported
        if r['pages'] == 1 and r['scale'] < 1 and not r['dropped']:
            # the content is final: set the type as large as one page allows, so the page ends full instead of short
            k2 = next((k for k in (1.0, .99, .98, .97, .96) if k > r['scale'] and render.fits(res, style, k, pdf + '.probe.pdf')), None)
            if k2:
                render.fits(res, style, k2, pdf)
                r['scale'] = k2
        for f in (pdf + '.probe.pdf',):
            if os.path.exists(f):
                os.remove(f)
    from . import latex
    with open(pdf[:-4] + '.tex', 'w', encoding='utf-8') as f:  # every tailored resume also ships as editable LaTeX
        f.write(latex.build_tex(res))
    txt = render.pdf_text(pdf)
    before = ats.report(v, jd)
    after = ats.report(res, jd, r['pages'], txt)
    r.pop('resume', None)
    out = {"pdf": pdf, "tex": pdf[:-4] + '.tex', "pages": r['pages'], "dropped": r['dropped'], "mode": mode, "style": style,
           "coverage_vault": before.get('coverage'), "coverage": after.get('coverage'), "score": after['score'],
           "missing": [m['term'] for m in after.get('missing', []) if m['hard']][:12],
           "rewrites": len(rep["rewrites"]), "rejected": rep["rejected"], "notes": rep["notes"], "field": ctx["field"], "added": rep.get("added", []),
           "positioning": rep.get("positioning", ''), "requirements": rep.get("requirements", [])}
    with open(os.path.join(out_dir, 'tailor.json'), 'w', encoding='utf-8') as f:
        json.dump({"plan": plan, "resume": res, "report": rep, "render": r, "mode": mode, "style": style, "field": ctx['field'],
                   "pipeline": PIPELINE, "result": out}, f, indent=1, ensure_ascii=False)
    return out
