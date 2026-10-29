"""Fit score 0-100: how well a posting matches the user's profile and search preferences.

Fast and explainable on purpose (it runs on tens of thousands of postings per scan). The resume-vs-JD
keyword match lives in ats.py and runs only on jobs you actually look at.
"""
import re
import time

INTERN = re.compile(r'\b(intern|interns|internship|extern|externship|practicum|trainee|traineeship|co-?op|summer (?:analyst|associate|scholar|fellow)|'
                    r'student|apprentice|apprenticeship|'
                    r'fellow(?:ship)?|insight (?:day|days|week|program|series)|discovery (?:day|days|program|week)|sophomore|freshman|first[- ]year|'
                    r'early (?:career|talent) program)\b', re.I)
NEWGRAD = re.compile(r'\b(new grad|graduate|entry[- ]level|university grad|early career|junior|associate|analyst)\b', re.I)
SENIOR = re.compile(r'\b(senior|sr\.?|staff|principal|lead|manager|director|head of|vp|architect|distinguished|fellow engineer)\b', re.I)
US = re.compile(r'\b(united states|usa|u\.s\.|remote|[A-Z][a-z]+,? (?:AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|'
                r'LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|DC)\b|'
                r'new york|san francisco|seattle|boston|chicago|austin|los angeles|atlanta|denver|'
                r'mountain view|palo alto|sunnyvale|menlo park|cambridge|pittsburgh|philadelphia|miami)', re.I)
NO_SPONSOR = re.compile(r'(will not|won\'t|unable to|does not|not able to) (?:provide |offer )?sponsor|'
                        r'must be (?:a )?u\.?s\.? citizen|security clearance (?:is )?required|requires? (?:an? )?(?:active )?clearance|'
                        r'citizenship is required|does not offer sponsorship', re.I)
CITIZEN = re.compile(r'u\.?s\.? citizen(?:ship)? (?:is )?required|must be (?:a )?u\.?s\.? citizen|citizenship is required|'
                     r'(?:active|secret|ts/sci) (?:security )?clearance', re.I)
CANADA = re.compile(r'\b(canada|toronto|vancouver|montreal|ottawa|calgary|waterloo|ontario|quebec|british columbia|alberta)\b|,\s*(ON|BC|QC|AB|MB|NS)\b(?!\w)', re.I)
MONTHS = 'jan feb mar apr may jun jul aug sep oct nov dec'.split()

ROLE_SYNONYMS = {
    'software engineer': ['software', 'swe', 'sde', 'developer', 'backend', 'back-end', 'frontend', 'front-end', 'full stack',
                          'full-stack', 'mobile', 'ios', 'android', 'platform engineer', 'infrastructure', 'devops', 'site reliability',
                          'web', 'cloud', 'programmer'],
    'machine learning': ['machine learning', 'ml', 'ai', 'deep learning', 'llm', 'applied scientist', 'research engineer',
                         'computer vision', 'nlp', 'perception'],
    'data science': ['data scien', 'data analy', 'analytics', 'data engineer', 'business intelligence'],
    'quant': ['quant', 'trader', 'quantitative', 'strats', 'algorithmic', 'trading intern', 'trading analyst', 'trading engineer', 'trading developer'],
    'hardware': ['hardware', 'electrical', 'embedded', 'firmware', 'fpga', 'asic', 'silicon', 'circuit', 'rf'],
    'robotics': ['robot', 'autonom', 'controls', 'mechatronic', 'perception', 'guidance', 'gnc'],
    'product': ['product manag', 'product design', 'technical program', 'tpm'],
    'finance': ['investment bank', 'finance', 'financial', 'private equity', 'asset management', 'wealth', 'equity research', 'summer analyst',
                'global markets', 'capital markets', 'sales & trading', 'sales and trading', 'm&a', 'mergers', 'leveraged finance', 'restructuring',
                'treasury', 'fp&a', 'credit', 'fixed income', 'investment', 'portfolio', 'banking', 'private credit', 'venture', 'underwriting'],
    'investment banking': ['investment bank', 'm&a', 'mergers', 'capital markets', 'leveraged finance', 'restructuring', 'coverage', 'ibd',
                           'summer analyst', 'corporate finance', 'advisory'],
    'accounting': ['accounting', 'accountant', 'audit', 'assurance', 'tax', 'cpa', 'controller', 'financial reporting', 'sox'],
    'sales and trading': ['sales & trading', 'sales and trading', 'global markets', 'trading', 'trader', 'markets', 'fixed income', 'equities'],
    'actuarial': ['actuar', 'underwriting', 'insurance', 'risk analyst', 'claims'],
    'real estate': ['real estate', 'property', 'reit', 'development', 'acquisitions'],
    'security': ['security', 'cyber', 'offensive', 'appsec'],
    'design': ['design', 'ux', 'ui', 'graphic', 'visual', 'creative', 'illustrat', 'motion'],
    'marketing': ['marketing', 'brand', 'social media', 'content', 'growth', 'communications', 'pr ', 'public relations', 'seo'],
    'sales': ['sales', 'business development', 'account', 'partnerships'],
    'consulting': ['consult', 'strategy', 'advisory'],
    'operations': ['operations', 'supply chain', 'logistics', 'procurement', 'project manag', 'program'],
    'healthcare': ['health', 'clinical', 'nurs', 'medical', 'patient', 'pharm', 'public health', 'hospital'],
    'research': ['research', 'lab', 'scientist', 'analyst'],
    'policy': ['policy', 'government', 'public affairs', 'legislat', 'advocacy', 'nonprofit', 'non-profit'],
    'education': ['teach', 'tutor', 'education', 'curriculum', 'instruct'],
    'writing': ['writ', 'editor', 'journalis', 'copy', 'reporter'],
    'legal': ['legal', 'law', 'paralegal', 'compliance'],
    'hr': ['human resources', 'people ops', 'recruit', 'talent'],
    'mechanical': ['mechanical', 'manufactur', 'aerospace', 'civil', 'structural', 'chemical', 'industrial'],
    'civil': ['civil', 'structural', 'transportation', 'geotech', 'construction', 'water resources', 'infrastructure'],
    'architecture': ['architect', 'interior design', 'urban design', 'landscape', 'urban planning', 'planner'],
    'environmental': ['environment', 'sustainab', 'climate', 'energy', 'ecolog', 'conservation', 'renewable', 'esg'],
    'biology': ['biolog', 'biotech', 'life science', 'molecular', 'genetic', 'microbio', 'immunolog', 'neuroscien', 'cell', 'lab'],
    'chemistry': ['chemist', 'chemical', 'formulation', 'analytical', 'materials scien'],
    'pharma': ['pharm', 'clinical research', 'regulatory', 'drug', 'medical affairs', 'clinical trial'],
    'public health': ['public health', 'epidemiolog', 'health policy', 'global health', 'community health'],
    'psychology': ['psycholog', 'behavioral', 'mental health', 'counsel', 'social work', 'therap'],
    'economics': ['econom', 'policy analy', 'research analyst', 'pricing'],
    'statistics': ['statistic', 'biostatistic', 'actuar', 'data analy', 'quantitative analy'],
    'journalism': ['journalis', 'reporter', 'editorial', 'newsroom', 'editor', 'producer', 'broadcast'],
    'media': ['media', 'film', 'video', 'production', 'entertainment', 'studio', 'podcast', 'broadcast', 'animation', 'music'],
    'communications': ['communications', 'public relations', 'pr ', 'corporate affairs', 'internal comms', 'media relations'],
    'supply chain': ['supply chain', 'logistics', 'procurement', 'sourcing', 'planning', 'inventory', 'distribution'],
    'hospitality': ['hospitality', 'hotel', 'event', 'guest', 'culinary', 'tourism', 'restaurant'],
    'retail': ['retail', 'merchandis', 'buyer', 'store', 'e-commerce', 'ecommerce', 'category'],
    'fashion': ['fashion', 'apparel', 'merchandis', 'textile', 'styling'],
    'sports': ['sport', 'athletic', 'fitness', 'coaching'],
    'government': ['government', 'public sector', 'federal', 'municipal', 'legislat', 'congress', 'civic', 'public service'],
    'nonprofit': ['nonprofit', 'non-profit', 'foundation', 'philanthrop', 'fundrais', 'development', 'ngo', 'community'],
    'cybersecurity': ['security', 'cyber', 'soc ', 'threat', 'grc', 'penetration', 'infosec'],
    'aerospace': ['aerospace', 'aircraft', 'propulsion', 'flight', 'avionics', 'space', 'satellite'],
    'agriculture': ['agricultur', 'agronom', 'food science', 'crop', 'animal science', 'farm'],
}


def role_terms(role):
    """Search terms for any role a user types, known or not. Unknown roles match on word stems, so 'marine biology'
    finds 'Marine Biologist' and 'environmental science' finds 'Environmental Sciences Intern'."""
    r = role.lower().strip()
    if r in ROLE_SYNONYMS:
        return ROLE_SYNONYMS[r], []
    words = [w for w in re.findall(r'[a-z0-9+#&]+', r) if w not in ('and', 'of', 'the', 'for', 'in')]
    stems = [w if len(w) <= 4 else w[:max(4, len(w) - 3)] for w in words]
    return [r], stems


def role_hit(role, title, desc=''):
    syns, stems = role_terms(role)
    if any(re.search(r'\b' + re.escape(x), title) for x in syns):
        return True
    if stems and all(re.search(r'\b' + re.escape(x), title) for x in stems):
        return True
    # part of it in the title and the whole phrase in the posting (a 'Marine Intern' that's about marine biology)
    return bool(stems) and any(re.search(r'\b' + re.escape(x), title) for x in stems) and role.lower() in desc[:2000].lower()


def _grad_ok(text, year, month):
    """Look for 'graduating between X and Y' style windows; return (ok, note) or (None, '')."""
    if not year:
        return None, ''
    try:
        y = int(year)
    except ValueError:
        return None, ''
    m_idx = MONTHS.index(month[:3].lower()) if month and month[:3].lower() in MONTHS else 4
    me = y * 12 + m_idx
    pat = re.compile(r'(?:graduat\w*|degree|completion)[^.\n]{0,60}?(?:(%s)[a-z]*\.?,? )?(20\d\d)[^.\n]{0,25}?'
                     r'(?:and|to|through|-|–|or)\s*(?:(%s)[a-z]*\.?,? )?(20\d\d)' % ('|'.join(MONTHS), '|'.join(MONTHS)), re.I)
    m = pat.search(text)
    if m:
        a = int(m.group(2)) * 12 + (MONTHS.index(m.group(1)[:3].lower()) if m.group(1) else 0)
        b = int(m.group(4)) * 12 + (MONTHS.index(m.group(3)[:3].lower()) if m.group(3) else 11)
        return a <= me <= b, f'grad window {m.group(2)}-{m.group(4)}'
    m = re.search(r'graduat\w*[^.\n]{0,40}?(?:by|before|no later than|prior to)\s+(?:(%s)[a-z]*\.?,? )?(20\d\d)'
                  % '|'.join(MONTHS), text, re.I)
    if m:
        b = int(m.group(2)) * 12 + (MONTHS.index(m.group(1)[:3].lower()) if m.group(1) else 11)
        return me <= b + 3, f'grad by {m.group(2)}'
    return None, ''


ONLY = re.compile(r'([A-Z][\w&.\- ]{1,40}?)\s+(?:students?|candidates?)\s+only', re.I)


def fit(job, prof, vault_terms=None):
    """vault_terms: set of LEXICON terms the user's vault contains (makes the score personal)."""
    s = prof.get('search', {})
    title = job.get('title', '')
    t = title.lower()
    text = f"{title}\n{job.get('description', '')}"
    why, score = [], 32.0
    only = ONLY.search(title)
    if only and (prof.get('school') or '').lower()[:6] not in only.group(1).lower():
        return 0, f'restricted to {only.group(1).strip()} students'
    company = (job.get('company') or '').lower()
    if any(c.lower() == company for c in s.get('companies_skip', [])):
        return 0, 'company on skip list'
    if any(x and re.search(r'\b%s' % re.escape(x.lower()), t) for x in s.get('exclude', [])):
        return 0, 'excluded keyword in title'
    kind = s.get('kind', 'internship')
    if kind == 'internship':
        if not INTERN.search(title):
            return 0, 'not an internship'
        if SENIOR.search(title) and not re.search(r'\bintern', title, re.I):
            return 0, 'senior role'
        score += 10
    elif kind == 'new-grad':
        if SENIOR.search(title) or INTERN.search(title):
            return 0, 'not new-grad level'
        score += 10 if NEWGRAD.search(title) else 0
    elif SENIOR.search(title) and not s.get('allow_senior'):
        score -= 25
    roles = s.get('roles') or []
    hit = []
    for r in roles:
        if role_hit(r, t, job.get('description') or ''):
            hit.append(r)
    if roles and not hit:
        return 0, 'role does not match'
    if hit:
        score += 18
        why.append('role: ' + ', '.join(hit))
    if vault_terms and job.get('description'):
        from . import ats
        want = [t for t, w, n in ats.keywords(job['description']) if t not in ats.SOFT]
        if want:
            have = sum(1 for t in want if t in vault_terms)
            frac = have / len(want)
            score += round(22 * frac)
            if frac >= .5:
                why.append(f'{have}/{len(want)} of its skills')
        else:
            score += 11
    elif vault_terms:
        score += 11  # no description yet: neutral
    if any(x and x.lower() in t for x in s.get('include', [])):
        score += 10
        why.append('include keyword')
    season = (s.get('season') or '').lower()
    yr = re.search(r'20\d\d', season)
    if yr:
        years = set(re.findall(r'20\d\d', title))
        if not years and job.get('source') == 'community':
            years = set(re.findall(r'20\d\d', job.get('description', '')[:80]))
        if years and yr.group() not in years:
            return 0, f'wrong cycle ({", ".join(sorted(years))})'
        if yr.group() in title:
            score += 8
            why.append(yr.group())
    if re.search(r'\bhigh[- ]school\b', title, re.I) and prof.get('school'):
        return 0, 'high school program'
    es = re.search(r'20\d\d', prof.get('earliest_start') or '')
    if es and int(es.group()) > time.gmtime().tm_year and re.search(r'\b(immediate(ly)? start|start(ing)? immediately|asap)\b', title, re.I):
        return 0, 'immediate start, before your earliest start'
    locs = [l.lower() for l in s.get('locations', [])]
    loc = job.get('location') or ''
    if locs and loc:
        if any(l in ('united states', 'us', 'usa') for l in locs):
            parts = [p for p in re.split(r';|\|| / ', loc) if p.strip()]
            us_parts = [p for p in parts if US.search(p) and not CANADA.search(p)]
            if not us_parts and not any(l in loc.lower() for l in locs if l not in ('united states', 'us', 'usa')):
                return 0, 'outside target locations'
        elif not any(l in loc.lower() for l in locs):
            score -= 20
    ok, note = _grad_ok(text, prof.get('grad_year'), prof.get('grad_month'))
    if ok is False:
        return 5, note + ' (you are outside it)'
    if ok:
        score += 10
        why.append(note)
    if prof.get('needs_sponsorship') and NO_SPONSOR.search(text):
        return 3, 'no sponsorship / citizenship required'
    cit = (prof.get('citizenship') or '').lower()
    if cit and not re.search(r'\bu\.?s\.?\b|united states|american', cit) and CITIZEN.search(text):
        return 3, 'US citizenship or clearance required'
    m = re.match(r'(20\d\d)-(\d\d)-(\d\d)', job.get('posted') or '')
    if m:
        import datetime
        age = (datetime.date.today() - datetime.date(*map(int, m.groups()))).days
        if age > 120:
            score -= 25
            why.append('old posting')
        elif age > 60:
            score -= 10
        elif age <= 3:
            score += 6
            why.append('posted in the last 3 days')
    if any(c.lower() == company for c in s.get('companies_priority', [])):
        score += 15
        why.append('priority company')
    return max(1, min(100, round(score))), '; '.join(why)
