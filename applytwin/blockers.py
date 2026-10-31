"""Why an application stopped, read from the agent's notes, and what that means for the rest of the run.

Real Autopilot outcomes showed most "Needs you" items were not things the user had to do: a posting that no longer exists,
a queue link that only opens the company homepage, or the agent's own browser not starting. Those are sorted out here so
they never sit in the user's list, and the ones that really need the user (a sign-in, an emailed code, a question) are
grouped so the user handles each site once.
"""
import re
from urllib.parse import urlparse

# (category, pattern) in priority order: the first match wins. Patterns are written against real agent notes.
CATEGORIES = [
    ('ready', r'\bready to submit\b|\bfully filled\b.*\b(tab|open)\b(?!.*\b(code|captcha|sign[- ]?in)\b)'),
    ('duplicate', r'\bduplicate\b|(you|user|candidate) (have|has) already applied|already (applied|submitted) (to|for|on)\b|'
                  r'application (already exists|was already submitted)'),
    ('browser', r'browser (access|host|service|connection|connector|tools?|automation)\b[^.;]{0,40}\b(unavailable|blocked|failed|denied|'
                r'not approved|was denied|is unavailable|down)|computer use (was )?(not approved|denied)|chrome control (denied|not approved)|'
                r'(profile|browser)[^.;]{0,80}already in use|unable to access the browser|could not access (the )?(chrome|browser)|'
                r'browser access is unavailable|playwright (reports|error)[^.;]{0,60}(in use|failed|closed)|tooling blocked|'
                r'(twin|automation) browser keeps closing|tab (was )?closed externally'),
    ('closed', r"page (you are looking for )?(does not|doesn't|does n't) exist|posting (does not|doesn't) exist|\b404\b|page not found|"
               r'no longer (accepting|available|listed|open|posted)|(job|posting|role|requisition) (is |has been )?(closed|expired|removed|filled)|'
               r'returns? 0 jobs|returns zero jobs|position (has been )?filled|not accepting applications|job not found'),
    ('broken_link', r'(company|corporate) homepage|homepage,? not (the|a) (job|posting|role)|links? only to .{0,40}homepage|'
                    r'redirects to (a )?different (role|job|posting)|not the listed|no (job|role) (page|posting|link)|broken link'),
    ('captcha', r'captcha|hcaptcha|recaptcha|turnstile|i.?m not a robot|bot (check|detection)|flagged as (possible )?spam|'
                r'error verifying your application'),
    ('email_code', r'(security|verification|one[- ]time|emailed|email(ed)?|sms|\bgh) code|awaiting [^.;]{0,30}\bcode\b|\botp\b|magic link|verify (your )?email|code (gate|screen|page)'),
    ('account', r'create (an )?account|account (creation|required|needed)|sign[- ]?up (page|step|required)|register (for )?an account|'
                r'new account|account with (a )?password'),
    ('signin', r'sign[- ]?in|log ?in|logged out|session expired|\bsso\b|password'),
    ('agreement', r'arbitration|binding (agreement|authorization)|legal agreement|release (and|&) |non-?disclosure'),
    ('assessment', r'assessment|hirevue|coding (challenge|test)|quiz|video (answer|response|recording|interview)|record(ed)? (a )?video|'
                   r'technical screening|screening (quiz|test)'),
    ('eligibility', r'ineligible|not eligible|eligibility|graduation window|grad window|ph\.?d|master.?s only|requires? (current )?'
                    r'(enrollment|u\.?s\.? (work|citizen))|citizenship|clearance|not (us|u\.s\.) work authori|sponsorship'),
    ('upload', r'upload (failed|did not|didn.t|error)|resume (did not|didn.t|wouldn.t|not) (attach|upload)|file input|could not (attach|upload)|'
               r'transcript (required|not supplied)|portfolio required|writing sample'),
    ('dropdown', r'dropdown|drop-down|combobox|typeahead|autocomplete|picker|listbox|select (did not|didn.t|wouldn.t) (register|stick)|'
                 r'failed to register'),
    ('transient', r'time[ds]? ?out|timed out|stopped responding|not responding|\b5\d\d\b|network error|failed to load|page froze|'
                  r'blank page|crash|no progress for|stuck'),
    ('question', r'question|essay|required (field|answer|q\b)|needs answers?|missing\b|not (established|documented|in (the )?(profile|vault))|'
                 r'only (you|the user) (can|know)|asks? (for )?(your|his|her)'),
]
_RX = [(c, re.compile(p, re.I)) for c, p in CATEGORIES]

LABELS = {'ready': 'Ready for your Submit click', 'duplicate': 'Already applied', 'browser': "The twin's browser didn't start",
          'closed': 'Posting closed', 'broken_link': 'Link is not a job posting', 'captcha': 'CAPTCHA', 'email_code': 'Emailed code',
          'account': 'Account needed', 'signin': 'Sign-in needed', 'agreement': 'Legal agreement', 'assessment': 'Assessment',
          'eligibility': 'Eligibility', 'upload': 'File needed / upload', 'dropdown': 'Dropdown would not take a value',
          'transient': 'Page error or timeout', 'question': 'Question only you can answer', 'other': 'Other'}

# what the user does, once, for a whole group
ACTIONS = {'signin': 'Sign in once at {host} in the twin\'s browser; then press Finish and all {n} continue where they stopped.',
           'account': 'Create your account at {host} once (ApplyTwin never creates accounts); then press Finish and all {n} continue.',
           'email_code': 'Type the emailed code in each open tab ({n}), or set email_codes to "agent" so your twin reads them.',
           'captcha': 'Solve the CAPTCHA and click Submit in each open tab ({n}).',
           'question': 'Answer these once on the Answers page; your twin reuses them everywhere ({n}).',
           'ready': 'Review and click Submit ({n}).',
           'agreement': 'Read and accept the agreement yourself, then submit ({n}).',
           'assessment': 'Take the assessment yourself ({n}).'}


def classify(notes):
    n = notes or ''
    for c, rx in _RX:
        if rx.search(n):
            return c
    return 'other'


def host(url):
    try:
        h = (urlparse(url or '').hostname or '').lower()
    except ValueError:
        return ''
    return h[4:] if h.startswith('www.') else h


GENERIC_PATHS = {'', 'careers', 'career', 'jobs', 'job', 'join', 'join-us', 'joinus', 'work-with-us', 'about', 'company', 'en', 'en-us',
                 'en_us', 'us', 'home', 'index.html', 'index.htm', 'opportunities', 'open-positions', 'openings', 'positions', 'team',
                 'students', 'university', 'early-careers', 'earlycareers', 'internships', 'search', 'search-jobs', 'job-search'}
ATS_HOSTS = re.compile(r'greenhouse\.io|lever\.co|ashbyhq\.com|myworkdayjobs\.com|smartrecruiters\.com|icims\.com|oraclecloud\.com|'
                       r'workable\.com|jobvite\.com|rippling\.com|taleo\.net|successfactors|avature\.net|eightfold\.ai|bamboohr\.com|'
                       r'paylocity\.com|pinpointhq\.com|linkedin\.com|wellfound\.com|ycombinator\.com|dover\.com|recruitee\.com|'
                       r'breezy\.hr|jazzhr|applytojob\.com|teamtailor\.com|personio|gem\.com', re.I)


def homepage_link(url):
    """True when a 'job link' only opens a company homepage or a generic careers page, with nothing that names a posting.
    One tracker sent 160 of these: each cost an agent a page load and a note before it could move on."""
    u = (url or '').strip()
    if not u:
        return False
    try:
        p = urlparse(u if '://' in u else 'https://' + u)
    except ValueError:
        return False
    if not p.hostname or '.' not in p.hostname or ATS_HOSTS.search(p.hostname):
        return False   # an ATS board root still lists jobs, and its posting ids are often in the query or fragment
    if re.search(r'\d{4,}|[0-9a-f]{8}-[0-9a-f]{4}|(job|req|posting|gh_jid|jid|id|lever-source|position)=', f'{p.query} {p.fragment}', re.I):
        return False
    segs = [s for s in p.path.lower().split('/') if s]
    return all(s in GENERIC_PATHS for s in segs)


def grad_options_knockout(options, year, month=''):
    """The form's graduation dropdown ends before (or starts after) the user's graduation: that is the posting's graduation
    window, stated as a list. Returns a ready-to-log Skipped reason, or ''. 'Other' in the list means the form allows it."""
    year = str(year or '').strip()
    opts = [o for o in (options or []) if o and o.strip()]
    if not re.fullmatch(r'20\d\d', year) or not opts:
        return ''
    if any(re.search(r'\bother\b|not listed|none of', o, re.I) for o in opts):
        return ''
    years = sorted({int(y) for o in opts for y in re.findall(r'\b(20\d\d)\b', o)})
    if not years or any(year in o for o in opts):
        return ''
    if len([o for o in opts if re.search(r'\b20\d\d\b', o)]) < len(opts) // 2:
        return ''   # mostly not a year list (e.g. degree names with one year in a hint): don't judge it
    me = f"{month} {year}".strip()
    return (f"graduation window: the form's graduation options run {years[0]}-{years[-1]}; user graduates {me}"
            if int(year) > years[-1] or int(year) < years[0] else '')
