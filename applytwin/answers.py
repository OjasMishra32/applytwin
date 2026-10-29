"""Application-question answer bank.

Every application asks the same ~40 questions in different words. The bank stores one truthful answer per
question type; match() maps any wording to the right answer with a confidence. Below the threshold the agent
must ask the user (and save the answer so it never asks twice).
"""
import re

STOP = set('a an the of to for in on and or is are you your do does did be been have has with at by as this that '
           'will would can could please any if from our we us it its which what when where who how'.split())


def _yn(b):
    return 'Yes' if b else 'No'


YEARS = ['Freshman', 'Sophomore', 'Junior', 'Senior']


def standing(p):
    # (now, during a summer internship): a sophomore today is a rising junior next summer
    now = (p.get('class_standing') or '').strip().title()
    if now in YEARS:
        i = YEARS.index(now)
        return now, ('Rising ' + YEARS[i + 1]) if i < 3 else 'Senior'
    return now, ''


def default_bank(p):
    s = p.get('eeo', {})
    grad = f"{p.get('grad_month', '')} {p.get('grad_year', '')}".strip()
    rows = [
        ('work_auth', 'Are you legally authorized to work in the United States?',
         r'(legally )?(authori[sz]ed|eligible|permitted) to work|work authori[sz]ation|right to work', _yn(p.get('work_authorized_us', True))),
        ('sponsorship', 'Will you now or in the future require visa sponsorship?',
         r'sponsor|h-?1b|visa status|immigration (support|assistance)', _yn(p.get('needs_sponsorship', False))),
        ('citizenship', 'What is your citizenship status?', r'citizen(ship)?\b(?! of)|u\.?s\.? person|green card|permanent resident',
         p.get('citizenship') or ''),
        ('relocate', 'Are you willing to relocate?', r'relocat', _yn(p.get('willing_to_relocate', True))),
        ('onsite', 'Are you able to work on-site / hybrid at this location?', r'on-?site|in[- ]office|in person|hybrid|commut',
         'Yes'),
        ('start', 'When can you start?', r'start date|available to start|earliest (start|date)|when can you (start|begin)',
         p.get('earliest_start', '')),
        ('grad', 'What is your expected graduation date?', r'graduat(ion|e) (date|month|year)|expected graduation|when (do|will) you graduate',
         grad),
        ('standing', 'What is your current class standing / year in school?',
         r'class (standing|level|year)|(current|academic) (year|standing)|year in (school|college|university)|what year are you',
         standing(p)[0]),
        ('standing_summer', 'What will your class standing be during the internship?',
         r'rising|standing (during|at the time)|year (during|at the time of) the internship|(entering|going into) your',
         standing(p)[1]),
        ('grad_year', 'Graduation year', r'graduation year|class of|year of graduation', p.get('grad_year', '')),
        ('school', 'School / university', r'(school|university|college|institution)( name)?$|which (school|university)',
         p.get('school', '')),
        ('degree', 'Degree', r'^degree|degree (type|level|pursuing)|highest (level of )?education|degree are you', p.get('degree', '')),
        ('major', 'Major / field of study', r'major|field of study|discipline|area of study|concentration', p.get('major', '')),
        ('gpa', 'GPA', r'\bgpa\b|grade point', p.get('gpa', '')),
        ('enrolled', 'Are you currently enrolled in a degree program?', r'currently (enrolled|pursuing|a student)|enrolled in',
         'Yes'),
        ('age', 'Are you at least 18 years old?', r'18 (years|or older)|at least 18|over the age', 'Yes'),
        ('background', 'Will you consent to a background check?', r'background (check|screen)|drug (test|screen)', 'Yes'),
        ('prior_employee', 'Have you previously worked for this company?',
         r'(previously|ever|currently) (been )?(employed|worked) (by|for|at)|former employee|worked (for|at) .* before', 'No'),
        ('referral', 'Were you referred by an employee?', r'referr?(ed|al)|who referred', 'No'),
        ('hear', 'How did you hear about us?', r'how did you (hear|find|learn)|source of (application|referral)|where did you (hear|find)',
         'Company careers website'),
        ('noncompete', 'Are you subject to a non-compete or non-solicit agreement?', r'non-?compete|non-?solicit|restrictive covenant', 'No'),
        ('government', 'Are you a current or former government employee?', r'government (official|employee)|public official', 'No'),
        ('relatives', 'Do you have relatives working here?', r'relative|family member|related to (anyone|an employee)', 'No'),
        ('salary', 'What are your salary expectations?', r'salary|compensation (expectation|requirement)|pay (expectation|range)|desired (pay|rate)',
         'Open and flexible, in line with the posted range'),
        ('linkedin', 'LinkedIn profile', r'linkedin', p.get('linkedin', '')),
        ('github', 'GitHub', r'github', p.get('github', '')),
        ('website', 'Website / portfolio', r'website|portfolio|personal (site|url)', p.get('website', '')),
        ('phone', 'Phone', r'^(phone|mobile|cell)', p.get('phone', '')),
        ('email', 'Email', r'^e-?mail', p.get('email', '')),
        ('location', 'Current location', r'(current )?(location|city)( of residence)?$|where are you (located|based)', p.get('location', '')),
        ('gender', 'Gender', r'\bgender\b|\bsex\b', s.get('gender', '')),
        ('race', 'Race / ethnicity', r'\brace\b|ethnic', s.get('race', '')),
        ('hispanic', 'Are you Hispanic or Latino?', r'hispanic|latin[oax]', s.get('hispanic', '')),
        ('veteran', 'Veteran status', r'veteran|military (service|status)', s.get('veteran', '')),
        ('disability', 'Disability status', r'disab', s.get('disability', '')),
        ('pronouns', 'Pronouns', r'pronoun', s.get('pronouns', '')),
        ('sms', 'Do you consent to SMS / text messages?', r'\bsms\b|text messag', 'Yes'),
        ('ai_review', 'May AI tools help review your application?', r'automated tools|\bai\b.*(review|process)', 'Yes'),
        ('privacy', 'Do you acknowledge the privacy policy / certify your answers?', r'privacy (policy|notice)|certify|acknowledge|attest|i agree',
         'Yes'),
    ]
    return [{"key": k, "question": q, "pattern": pat, "answer": a, "source": "profile"} for k, q, pat, a in rows]


def _tokens(s):
    return {w for w in re.findall(r'[a-z0-9]+', (s or '').lower()) if w not in STOP and len(w) > 1}


def match(question, bank, options=None):
    """Best answer for one question. options = the dropdown/radio choices, if any (we pick the closest)."""
    q = (question or '').strip()
    best, conf = None, 0.0
    for row in bank:
        pat = row.get('pattern')
        if pat:
            try:
                if re.search(pat, q, re.I):
                    best, conf = row, 0.92
                    break
            except re.error:
                pass
    if not best:
        qt = _tokens(q)
        for row in bank:
            rt = _tokens(row.get('question'))
            if not qt or not rt:
                continue
            j = len(qt & rt) / len(qt | rt)
            if j > conf:
                best, conf = row, j
        conf = min(0.85, conf * 1.3)
    if not best or conf < 0.45 or best.get('answer') in (None, ''):
        return {"question": q, "answer": None, "confidence": round(conf, 2), "key": best.get('key') if best else None,
                "action": "ask the user, then applytwin_save_answer"}
    ans = best['answer']
    if options:
        ans = pick_option(ans, options)
    return {"question": q, "answer": ans, "confidence": round(conf, 2), "key": best.get('key')}


def pick_option(answer, options):
    """Map a free answer onto the closest of the form's options (Yes -> 'Yes, I am authorized...')."""
    a = (answer or '').lower().strip()
    opts = [o for o in options if o and o.lower() not in ('select', 'select one', '--', 'please select')]
    for o in opts:
        if o.lower() == a:
            return o
    if a in ('yes', 'no'):
        for o in opts:
            if re.match(r'^%s\b' % a, o.lower()):
                return o
    at = _tokens(a)
    scored = sorted(opts, key=lambda o: -len(at & _tokens(o)) / (len(_tokens(o)) or 1))
    return scored[0] if scored and at & _tokens(scored[0]) else answer


def upsert(bank, question, answer, key=None):
    key = key or re.sub(r'[^a-z0-9]+', '_', question.lower())[:40]
    for row in bank:
        if row.get('key') == key or row.get('question', '').lower() == question.lower():
            row['answer'] = answer
            row['source'] = 'user'
            return bank
    bank.append({"key": key, "question": question, "pattern": None, "answer": answer, "source": "user"})
    return bank
