"""Resume templates -> HTML -> PDF (headless Chrome). Every template is single-column real text so it
parses in every ATS; they differ in typography, header layout, rules and density.

Bullets accept light markdown: **bold** and [text](url).
"""
import glob
import html
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import time


def degree_line(e):
    """'Bachelor of Science' + 'Finance' -> 'Bachelor of Science in Finance'; a degree that already names its field
    ('B.S. in Management') takes the major after a comma, and a major the degree already states isn't said twice."""
    deg, major = (e.get('degree') or '').strip(), (e.get('major') or '').strip()
    if not deg or not major:
        return deg or major
    if major.lower() in deg.lower():
        return deg
    return f'{deg}, {major}' if re.search(r'\b(in|of)\s+\w', deg.split(' of ', 1)[-1] if deg.lower().startswith(('bachelor of', 'master of', 'doctor of')) else deg) else f'{deg} in {major}'

TEMPLATES = {
    'classic': {"label": "Jake's Classic", "desc": "The r/cscareerquestions favorite. Serif, small-caps headings, full rules, dense.",
                "best": "SWE, quant, research"},
    'harvard': {"label": "Harvard Traditional", "desc": "Career-office standard. Times, bold caps headings, black only.",
                "best": "Finance, consulting, any conservative firm"},
    'modern': {"label": "Awesome Modern", "desc": "Light/bold name, accent-colored headings, airy sans.",
               "best": "Startups, product, design-adjacent"},
    'banking': {"label": "Banking", "desc": "Centered headings between rules, calm blue accent.",
                "best": "Business, fintech, generalist"},
    'finance': {"label": "Finance One-Pager", "desc": "Garamond, education first, very dense. Wall Street style.",
                "best": "IB, asset management, trading"},
    'minimal': {"label": "Sans Minimal", "desc": "Left-aligned name, quiet gray headings, lots of whitespace.",
                "best": "Big tech, new grad, design"},
    'compact': {"label": "Compact Engineering", "desc": "No rules, tight spacing. Fits the most content on one page.",
                "best": "Lots of experience, hardware, robotics"},
    'latex': {"label": "LaTeX (Jake's)", "desc": "Real LaTeX typesetting, the Overleaf classic. Needs a TeX engine installed.",
              "best": "SWE, research, anyone who loves LaTeX"},
    'accent': {"label": "Accent Bar", "desc": "Teal name and a slim accent bar on each heading.",
               "best": "Data, AI, standing out while staying ATS-safe"},
}

BASE_CSS = """
@page { size: Letter; margin: 0; }
* { box-sizing: border-box; }
:root { --s: 1; }
html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
/* ATS-safe text: no ligatures (parsers read the "fi"/"ffi" glyphs as one odd character), lining figures (old-style numerals
   bounce in dates and GPAs), no automatic hyphenation (a hyphenated "Kuber-netes" no longer matches a keyword search) */
body { margin: 0; color: #111; font-variant-ligatures: none; font-feature-settings: "liga" 0, "clig" 0, "dlig" 0, "lnum" 1;
       font-variant-numeric: lining-nums; font-kerning: normal; }
.page { width: 8.5in; min-height: 11in; padding: var(--mt) var(--mx); font-family: var(--font); font-size: calc(var(--fs) * var(--k));
        line-height: var(--lh); hyphens: manual; overflow-wrap: break-word; }
a { color: inherit; text-decoration: none; }
h1 { margin: 0; font-size: calc(var(--name) * var(--k)); line-height: 1.1; }
.contact { margin-top: .2em; }
.contact > span, .headline > span { white-space: nowrap; }
.sep { color: var(--muted); padding: 0 .1em; font-weight: 400; }
.headline { margin-top: .15em; font-weight: 600; }
section { margin-top: calc(var(--gap) * var(--k) * var(--s)); }
h2 { margin: 0 0 calc(.3em * var(--k)); font-size: calc(var(--hs) * var(--k)); line-height: 1.15; break-after: avoid; }
.entry { margin-top: calc(var(--egap) * var(--k) * var(--s)); break-inside: avoid; }
.entry:first-of-type { margin-top: 0; }
.row { display: flex; justify-content: space-between; align-items: baseline; gap: 1.2em; }
.row > :first-child { min-width: 0; }
.row > :last-child { white-space: nowrap; text-align: right; flex-shrink: 0; }
.org { font-weight: 700; }
.role { font-style: italic; }
.meta { color: var(--muted); }
.entry > div:not(.row), li, .skills p { text-wrap: pretty; }
ul { margin: calc(.1em * var(--k)) 0 0; padding-left: 1.15em; }
li { margin: calc(.05em * var(--k)) 0 0; padding-left: .1em; }
li::marker { content: "\\2022  "; font-size: .85em; }
.skills p { margin: .08em 0; padding-left: 1.2em; text-indent: -1.2em; }
.tag { color: var(--muted); }
.i { white-space: nowrap; }
"""

# Font stacks avoid Helvetica Neue: Chrome writes its bold and italic word spaces as line breaks in the PDF text layer,
# so a parser reads "Software\nEngineering" (every fallback below extracts cleanly)
STYLE_CSS = {
    # Jake's Resume: Computer Modern when installed, else a sturdy book serif; uppercase tracked headings over a full rule
    'classic': """:root{--font:"Latin Modern Roman","CMU Serif","Computer Modern Serif","Palatino Linotype",Palatino,"Book Antiqua",Cambria,serif;--fs:10.2pt;
      --name:21pt;--hs:10.6pt;--lh:1.22;--mt:.45in;--mx:.5in;--gap:9pt;--egap:5pt;--muted:#333}
      header{text-align:center} h1{text-transform:uppercase;font-weight:700;letter-spacing:.06em}
      h2{text-transform:uppercase;font-weight:400;border-bottom:.6pt solid #000;padding-bottom:1.5pt;letter-spacing:.09em}""",
    # Harvard OCS: Times, centered name, bold caps headings on a rule, black only
    'harvard': """:root{--font:"Times New Roman",Times,"Liberation Serif",serif;--fs:10.8pt;--name:17pt;--hs:10.8pt;--lh:1.2;--mt:.5in;
      --mx:.6in;--gap:9.5pt;--egap:5.5pt;--muted:#000} header{text-align:center} h1{font-weight:700;letter-spacing:.02em}
      h2{text-transform:uppercase;font-weight:700;border-bottom:.8pt solid #000;padding-bottom:1pt;letter-spacing:.03em}""",
    # Awesome-CV: light first name + bold last name, red three-letter accent on headings, a rule out to the margin
    'modern': """:root{--font:"Source Sans 3","Source Sans Pro",Roboto,Helvetica,Arial,sans-serif;--fs:9.9pt;--name:30pt;
      --hs:13pt;--lh:1.26;--mt:.5in;--mx:.6in;--gap:10pt;--egap:5.5pt;--muted:#666;--accent:#DC3522}
      header{text-align:center} h1{font-weight:300;letter-spacing:.01em} h1 b{font-weight:700}
      .contact{color:#555;font-size:.93em} h2{font-weight:700;display:flex;align-items:center;gap:.45em}
      h2 .a{color:var(--accent)} h2::after{content:"";flex:1;border-bottom:.6pt solid #999}
      .meta,.row>:last-child{color:#666;font-style:italic} .org{color:#222}""",
    'banking': """:root{--font:Helvetica,Arial,"Liberation Sans",sans-serif;--fs:9.8pt;--name:25pt;--hs:11.5pt;--lh:1.27;--mt:.5in;
      --mx:.6in;--gap:10pt;--egap:6pt;--muted:#555;--accent:#2F65A7} header{text-align:center}
      h1{font-weight:400;color:#222;letter-spacing:.01em} h2{color:var(--accent);font-weight:700;text-align:center;display:flex;align-items:center;gap:.6em}
      h2::before,h2::after{content:"";flex:1;border-bottom:.8pt solid var(--accent)} .org{color:#222}""",
    # Wall Street one-pager: Garamond (Times where it isn't installed), education first, dense, black only
    'finance': """:root{--font:"EB Garamond",Garamond,"Adobe Garamond Pro",Baskerville,"Baskerville Old Face","Times New Roman",serif;--fs:11pt;--name:18pt;--hs:11pt;
      --lh:1.15;--mt:.45in;--mx:.55in;--gap:7pt;--egap:4pt;--muted:#000} header{text-align:center}
      h1{font-weight:700;letter-spacing:.05em;text-transform:uppercase}
      h2{text-transform:uppercase;font-weight:700;border-bottom:.8pt solid #000;letter-spacing:.04em}""",
    'minimal': """:root{--font:Inter,"SF Pro Text",Helvetica,Arial,sans-serif;--fs:9.6pt;--name:22pt;--hs:8.6pt;
      --lh:1.32;--mt:.55in;--mx:.65in;--gap:11pt;--egap:6pt;--muted:#666} h1{font-weight:650;letter-spacing:-.01em}
      .contact{color:#555} h2{text-transform:uppercase;letter-spacing:.12em;color:#666;font-weight:600;
      border-bottom:1px solid #ddd;padding-bottom:3pt} .org{font-weight:600}""",
    'compact': """:root{--font:Charter,"Bitstream Charter","Source Serif 4","Source Serif Pro",Cambria,"Times New Roman",serif;--fs:9.8pt;--name:20pt;
      --hs:11pt;--lh:1.18;--mt:.4in;--mx:.45in;--gap:6.5pt;--egap:3pt;--muted:#333} header{text-align:center}
      h1{font-weight:700} h2{font-weight:700;margin-bottom:2pt}""",
    'accent': """:root{--font:Lato,Carlito,"Avenir Next",Helvetica,Arial,sans-serif;--fs:9.8pt;--name:26pt;--hs:11pt;--lh:1.26;--mt:.5in;
      --mx:.6in;--gap:10pt;--egap:6pt;--muted:#555;--accent:#0E7C86} h1{color:var(--accent);font-weight:700;letter-spacing:-.005em}
      h2{border-left:3pt solid var(--accent);padding-left:6pt;font-weight:700;text-transform:uppercase;letter-spacing:.06em}
      .row>:last-child{color:#444}""",
}

for _s in ('modern', 'banking', 'minimal', 'harvard'):   # Helvetica's, Arial's and Times' bullets are tiny
    STYLE_CSS[_s] += ' li::marker{font-size:1.15em}'

SECTION_TITLES = {'education': 'Education', 'experience': 'Experience', 'projects': 'Projects', 'research': 'Research and Publications',
                  'leadership': 'Leadership and Activities', 'volunteering': 'Volunteer Experience', 'skills': 'Skills',
                  'certifications': 'Licenses and Certifications', 'awards': 'Awards and Honors'}


_LIGS = {'\ufb00': 'ff', '\ufb01': 'fi', '\ufb02': 'fl', '\ufb03': 'ffi', '\ufb04': 'ffl', '\ufb05': 'st', '\ufb06': 'st'}
_INVISIBLE = re.compile('[\u00ad\u200b-\u200f\u2060\ufeff]')   # soft hyphen, zero-width spaces/joiners, BOM
_ASCII_QUOTES = str.maketrans({'\u2018': "'", '\u2019': "'", '\u201c': '"', '\u201d': '"'})


def clean(x, strict=False):
    """Text that survives every ATS parser: text pasted from a PDF or Word brings ligature glyphs ('ﬁ' reads as one odd
    character, so 'certiﬁed' never matches 'certified'), invisible soft hyphens and zero-width spaces (they split or glue
    words in the text layer) and no-break spaces. strict (emails, phones, URLs) also makes curly quotes plain.
    Walks dicts and lists, so a whole resume can be cleaned at once."""
    if isinstance(x, dict):
        return {k: clean(v, strict or k in ('email', 'phone', 'url')) for k, v in x.items()}
    if isinstance(x, list):
        return [clean(v, strict) for v in x]
    if not isinstance(x, str):
        return x
    x = _INVISIBLE.sub('', ''.join(_LIGS.get(c, c) for c in x)).replace('\u00a0', ' ').replace('\u202f', ' ')
    return x.translate(_ASCII_QUOTES).strip() if strict else x


def md(s):
    s = html.escape(s or '', quote=False)
    s = re.sub(r'\[([^\]]+)\]\(([^)\s]+)\)', r'<a href="\2">\1</a>', s)
    s = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', s)
    return s.replace('--', '\u2013') if False else s


def dates(e):
    a, b = (e.get('start') or '').strip(), (e.get('end') or '').strip()
    return f'{a} \u2013 {b}' if a and b else (b or a)


def _items(xs):
    """'Linear Algebra, GitHub Actions': lines wrap between items, never inside one (a nowrap span, not no-break spaces,
    which some parsers keep as a different character and then miss the phrase in a keyword search)."""
    return ', '.join(f'<span class="i">{html.escape(x)}</span>' if ' ' in x else html.escape(x) for x in xs if x)


def _link(url, inner):
    return f'<a href="{html.escape(url)}">{inner}</a>' if url else inner


def _heading(title, style):
    if style == 'modern':
        return f'<h2><span><span class="a">{html.escape(title[:3])}</span>{html.escape(title[3:])}</span></h2>'
    return f'<h2>{html.escape(title)}</h2>'


def build_html(r, style='classic', k=1.0, titles=None):
    style = style if style in STYLE_CSS else 'classic'  # 'latex' previews with the closest HTML look
    return _doc(STYLE_CSS[style], _page(r, style, titles), k, title=(r.get('basics') or {}).get('name') or 'Resume')


def _doc(css, pages, k=1.0, s=1.0, title='Resume', extra=''):
    return (f'<!doctype html><html><head><meta charset="utf-8"><title>{html.escape(title)}</title>'
            f'<style>{BASE_CSS + css}</style><style>:root{{--k:{k};--s:{s}}}</style>{extra}</head><body>'
            + pages + '</body></html>')


def _page(r, style, titles=None):
    """One resume page's markup (<div class="page">...</div>) for this style."""
    r = clean(r)
    titles = {**SECTION_TITLES, **(r.get('titles') or {}), **(titles or {})}
    b = r.get('basics', {})
    name = html.escape(b.get('name', ''))
    if style == 'modern' and ' ' in name:
        first, last = name.rsplit(' ', 1)
        name = f'{first} <b>{last}</b>'
    contact = [b.get('phone'), b.get('email'), b.get('location')]
    items = [f'<span>{html.escape(c)}</span>' for c in contact if c]
    for l in b.get('links', []):
        label = l.get('label') or re.sub(r'^https?://(www\.)?', '', l.get('url', '')).rstrip('/')
        items.append(f'<span><a href="{html.escape(l.get("url", ""))}">{html.escape(label)}</a></span>')
    # real separator characters with real spaces around them (not CSS ::before content): parsers see "a | b", and
    # the line can wrap between items instead of overflowing the margin
    dot = '|' if style == 'finance' else '\u00b7'   # Baskerville's middle dot sits off-center
    head = [f'<header><h1>{name}</h1>']
    if b.get('headline'):
        head.append('<div class="headline">' + f' <span class="sep">{dot}</span> '.join(f'<span>{md(h)}</span>' for h in b['headline']) + '</div>')
    head.append('<div class="contact">' + ' <span class="sep">|</span> '.join(items) + '</div></header>')
    out = []
    for sec in r.get('order') or list(SECTION_TITLES):
        data = r.get(sec)
        if not data:
            continue
        body = []
        if sec == 'education':
            for e in data:
                deg = degree_line(e)
                extra = '; '.join(x for x in (e.get('minor') and 'Minor in ' + e['minor'], e.get('gpa') and 'GPA: ' + e['gpa']) if x)
                body.append(f'<div class="entry"><div class="row"><span class="org">{html.escape(e.get("school", ""))}</span>'
                            f'<span>{html.escape(e.get("location", ""))}</span></div><div class="row"><span class="role">{html.escape(deg)}'
                            f'{("; " + html.escape(extra)) if extra else ""}</span><span class="meta">{html.escape(dates(e))}</span></div>')
                lines = []
                if e.get('coursework'):
                    lines.append('<b>Relevant coursework:</b> ' + _items(e['coursework']))
                if e.get('honors'):
                    lines.append(md(f' {dot} '.join(e['honors'])))
                body += [f'<div>{l}</div>' for l in lines]
                body.append('</div>')
        elif sec in ('experience', 'leadership', 'volunteering'):
            for e in data:
                org = md(e.get('org', ''))
                if e.get('url'):
                    org = f'<a href="{html.escape(e["url"])}">{org}</a>'
                body.append(f'<div class="entry"><div class="row"><span class="org">{org}</span><span>{html.escape(dates(e))}</span></div>')
                if e.get('title') or e.get('location'):
                    body.append(f'<div class="row"><span class="role">{md(e.get("title", ""))}</span>'
                                f'<span class="meta">{html.escape(e.get("location", ""))}</span></div>')
                if e.get('bullets'):
                    body.append('<ul>' + ''.join(f'<li>{md(x)}</li>' for x in e['bullets']) + '</ul>')
                body.append('</div>')
        elif sec == 'projects':
            for p in data:
                nm = md(p.get('name', ''))
                if p.get('url'):
                    nm = f'<a href="{html.escape(p["url"])}">{nm}</a>'
                tag = ' | '.join(x for x in (md(p.get('tagline', '')), html.escape(', '.join(p.get('tech', [])))) if x)
                body.append(f'<div class="entry"><div class="row"><span><span class="org">{nm}</span>'
                            f'{(" <span class=tag>| " + tag + "</span>") if tag else ""}</span><span>{html.escape(p.get("date", ""))}</span></div>')
                if p.get('bullets'):
                    body.append('<ul>' + ''.join(f'<li>{md(x)}</li>' for x in p['bullets']) + '</ul>')
                body.append('</div>')
        elif sec == 'research':
            body.append('<ul>' + ''.join(
                f'<li>{md(p.get("role", "")) + ": " if p.get("role") else ""}'
                f'{_link(p.get("url"), md(p.get("title", "")))}'
                f'{". <b>" + md(p["venue"]) + "</b>" if p.get("venue") else ""}</li>' for p in data) + '</ul>')
        elif sec == 'skills':
            body.append('<div class="skills">' + ''.join(
                f'<p><b>{html.escape(s.get("label", ""))}:</b> {_items(s.get("items", []))}</p>' for s in data) + '</div>')
        elif sec in ('awards', 'certifications'):
            body.append('<ul>' + ''.join(f'<li>{md(a if isinstance(a, str) else a.get("title", ""))}</li>' for a in data) + '</ul>')
        out.append(f'<section>{_heading(titles.get(sec, sec.title()), style)}{"".join(body)}</section>')
    return '<div class="page">' + ''.join(head) + ''.join(out) + '</div>'


def _win_browsers():
    """Windows installs that aren't at the C:\\Program Files paths: Windows on another drive, a per-user Chrome or Brave,
    found through %ProgramFiles% and the App Paths registry entries the installers write."""
    if os.name != 'nt':
        return []
    out = []
    for var in ('ProgramFiles', 'ProgramFiles(x86)', 'LOCALAPPDATA'):
        base = os.environ.get(var)
        if base:
            out += [os.path.join(base, *p) for p in (('Google', 'Chrome', 'Application', 'chrome.exe'),
                                                     ('Microsoft', 'Edge', 'Application', 'msedge.exe'),
                                                     ('BraveSoftware', 'Brave-Browser', 'Application', 'brave.exe'))]
    try:
        import winreg
        for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            for exe in ('chrome.exe', 'msedge.exe', 'brave.exe'):
                try:
                    with winreg.OpenKey(root, r'SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths' + '\\' + exe) as k:
                        out.append(str(winreg.QueryValue(k, None)).strip('"'))
                except OSError:
                    pass
    except ImportError:
        pass
    return out


def chrome():
    env = os.environ.get('APPLYTWIN_CHROME')
    cands = [env] if env else []
    cands += ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
              '/Applications/Chromium.app/Contents/MacOS/Chromium',
              '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
              '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser',
              r'C:\Program Files\Google\Chrome\Application\chrome.exe',
              r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
              os.path.expandvars(r'%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe'),
              r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
              r'C:\Program Files\Microsoft\Edge\Application\msedge.exe']   # Edge ships with every Windows install
    cands += _win_browsers()
    cands += [shutil.which(x) for x in ('google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser', 'chrome', 'msedge')]
    for c in cands:
        if c and os.path.exists(c):
            return c
    raise RuntimeError('No Chrome/Chromium/Edge found. Install Chrome or set APPLYTWIN_CHROME=/path/to/chrome')


def _print(cmd, out_pdf, limit=60):
    """Run Chrome until the PDF is written. Headless Chrome now and then writes the file and never exits (or hangs before
    writing): stop it once the PDF has stopped growing, or at the limit, so a stuck browser never fails a resume."""
    p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0, last = time.time(), -1
    try:
        while time.time() - t0 < limit:
            if p.poll() is not None:
                return os.path.exists(out_pdf)
            size = os.path.getsize(out_pdf) if os.path.exists(out_pdf) else -1
            if size > 0 and size == last and _pdf_complete(out_pdf):
                return True   # written and finished: Chrome is just slow to exit
            last = size
            time.sleep(0.25)
        return False
    finally:
        if p.poll() is None:
            from .store import kill_tree
            kill_tree(p)   # on Windows Chrome's helper processes survive a plain kill and keep the profile folder open
            try:
                p.wait(5)
            except Exception:
                pass


def _pdf_complete(pdf):
    try:
        with open(pdf, 'rb') as f:
            f.seek(max(0, os.path.getsize(pdf) - 1024))
            return b'%%EOF' in f.read()
    except OSError:
        return False


def html_to_pdf(doc, out_pdf):
    os.makedirs(os.path.dirname(os.path.abspath(out_pdf)), exist_ok=True)
    td = tempfile.mkdtemp()
    try:
        src = os.path.join(td, 'resume.html')
        with open(src, 'w', encoding='utf-8') as f:
            f.write(doc)
        # --use-mock-keychain / --password-store=basic: a fresh Chrome profile otherwise asks the macOS keychain (or the
        # Linux keyring) for its password store on every launch, which pops "A keychain cannot be found" over and over
        for attempt in range(2):
            if os.path.exists(out_pdf):
                os.unlink(out_pdf)
            cmd = [chrome(), '--headless=new', '--disable-gpu', '--no-sandbox', '--no-pdf-header-footer', '--use-mock-keychain',
                   '--password-store=basic', '--no-first-run', '--no-default-browser-check', '--disable-extensions', '--disable-sync',
                   '--print-to-pdf-no-header', f'--user-data-dir={td}/profile{attempt}', f'--print-to-pdf={out_pdf}',
                   pathlib.Path(src).as_uri()]   # file:///C:/... on Windows too
            if _print(cmd, out_pdf):
                break
    finally:
        shutil.rmtree(td, ignore_errors=True)   # a just-stopped Chrome can still hold its profile files on Windows
    if not os.path.exists(out_pdf):
        raise RuntimeError('Chrome did not produce a PDF')
    return out_pdf


def page_count(pdf):
    try:   # reads compressed PDFs too (LaTeX output hides its page objects from a plain text search)
        from pypdf import PdfReader
        from .store import quiet_pypdf
        with quiet_pypdf():   # a half-written PDF falls back to the count below, without pypdf's log noise
            return len(PdfReader(pdf).pages) or 1
    except Exception:
        data = open(pdf, 'rb').read()
        return len(re.findall(rb'/Type\s*/Page(?![s\w])', data)) or 1


def pdf_text(pdf):
    try:
        from pypdf import PdfReader
        from .store import quiet_pypdf
        with quiet_pypdf():
            return '\n'.join(p.extract_text() or '' for p in PdfReader(pdf).pages)
    except Exception:
        return None


def dump_dom(doc, limit=60):
    """Load a page in headless Chrome and return its DOM after scripts ran (None if Chrome failed or hung)."""
    td = tempfile.mkdtemp()
    try:
        src = os.path.join(td, 'measure.html')
        with open(src, 'w', encoding='utf-8') as f:
            f.write(doc)
        cmd = [chrome(), '--headless=new', '--disable-gpu', '--no-sandbox', '--use-mock-keychain', '--password-store=basic',
               '--no-first-run', '--no-default-browser-check', '--disable-extensions', '--disable-sync', '--window-size=1000,1400',
               f'--user-data-dir={td}/profile', '--dump-dom', pathlib.Path(src).as_uri()]
        from .store import NOWIN
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, **NOWIN)
        try:
            out, _ = p.communicate(timeout=limit)
        except subprocess.TimeoutExpired:
            from .store import kill_tree
            kill_tree(p)
            try:
                out, _ = p.communicate(timeout=5)
            except Exception:
                return None
        return (out or b'').decode('utf-8', 'replace')
    except Exception:
        return None
    finally:
        shutil.rmtree(td, ignore_errors=True)


PAGE_PX = 1056   # 11in at 96 CSS px per inch

# Runs inside Chrome over every candidate page (the resume after 0, 1, 2... trims). Policy, in order: the fewest cut lines
# whose page fits with the type shrunk at most to the tier's floor; then the largest type (up to kmax) that still fits; then
# the space left is shared out between sections and entries (up to smax times the normal gaps), so the page ends full
# instead of short.
_FIT_JS = """(function(){
var M=[].slice.call(document.querySelectorAll('.m')),R=document.documentElement.style,C=%s,L=C.limit,cur=-1,pick=null,out;
function show(i){if(cur>=0)M[cur].style.display='none';M[i].style.display='block';cur=i;}
function h(k,s){R.setProperty('--k',k);R.setProperty('--s',s);return M[cur].firstElementChild.getBoundingClientRect().height;}
for(var t=0;t<C.tiers.length&&!pick;t++){var T=C.tiers[t];
  for(var i=T[0];i<=Math.min(T[1],M.length-1);i++){show(i);if(h(T[2],1)<=L){pick=[i,T[2]];break;}}}
if(!pick){var kl=C.tiers[C.tiers.length-1][2];show(M.length-1);out={i:M.length-1,k:kl,s:1,fit:false,h:h(kl,1)};}
else{show(pick[0]);var a=pick[1],b=C.kmax;
  if(h(b,1)<=L)a=b;else for(var n=0;n<10;n++){var m=(a+b)/2;if(h(m,1)<=L)a=m;else b=m;}
  var k=Math.floor(a*1000)/1000,h1=h(k,1),s=1;
  if(C.smax>1){var g=h(k,2)-h1;if(g>0){s=Math.floor(Math.min(C.smax,1+(L-h1)/g)*100)/100;while(s>1&&h(k,s)>L)s=Math.max(1,s-.02);}}
  out={i:pick[0],k:k,s:s,fit:true,h:h(k,s)};}
document.getElementById('fit').textContent=JSON.stringify(out);})();"""


def _fit_measured(r, style, out_pdf, worth=None, kmax=1.04, smax=1.5):
    """One-page fit from measurements instead of trial prints: lay out every trim step in one Chrome load, pick the best
    (see _FIT_JS), then print once. Returns None when Chrome couldn't measure, so the caller falls back to trial prints."""
    import copy
    import json
    states, cur, dropped = [(r, [])], copy.deepcopy(r), []
    for _ in range(80):
        v = _drop_one(cur, worth)
        if not v:
            break
        dropped.append(v)
        states.append((copy.deepcopy(cur), list(dropped)))
    n = len(states)
    cfg = {"limit": PAGE_PX - 2, "kmax": kmax, "smax": smax, "tiers": [[0, 12, .95], [13, 24, .92], [25, max(25, n - 1), .9]]}
    pages = ''.join(f'<div class="m" style="display:none">{_page(s, style)}</div>' for s, _ in states)
    doc = _doc(STYLE_CSS[style], pages + '<pre id="fit"></pre><script>' + (_FIT_JS % json.dumps(cfg)) + '</script>',
               extra='<style>.m .page{min-height:0}#fit{display:none}</style>')
    dom = dump_dom(doc)
    m = re.search(r'<pre id="fit"[^>]*>(\{.*?\})</pre>', dom or '')
    if not m:
        return None
    try:
        fit = json.loads(html.unescape(m.group(1)))
        i, k, s = int(fit['i']), float(fit['k']), float(fit['s'])
    except (ValueError, KeyError, TypeError):
        return None
    res, cut = states[i]
    if os.environ.get('APPLYTWIN_FIT_DEBUG'):
        print('fit', style, fit, file=sys.stderr)
    for attempt in range(4):   # screen layout and print layout agree to the pixel in practice; shrink a hair if they don't
        html_to_pdf(_doc(STYLE_CSS[style], _page(res, style), k, s, title=(res.get('basics') or {}).get('name') or 'Resume'), out_pdf)
        pages_out = page_count(out_pdf)
        if pages_out == 1 or not fit.get('fit'):
            break
        k, s = round(k - .01, 3), 1.0
    return {"pdf": out_pdf, "pages": pages_out, "scale": k, "spacing": s, "dropped": cut, "resume": res}


def render(r, style, out_pdf, one_page=True, worth=None):
    """Render, shrinking type a little and then trimming the lowest-priority lines until it fits one page. worth(text) scores
    a bullet for this job (higher = keep); without it, bullets are trimmed from the end of each list."""
    import copy
    r = copy.deepcopy(r)
    dropped = []
    if style == 'latex':
        from . import latex
        try:
            return _fit(r, out_pdf, one_page, dropped, lambda rr, k: latex.compile_tex(latex.build_tex(rr, k), out_pdf), (1.0, .96, .92), worth)
        except RuntimeError:
            style = 'classic'
    style = style if style in STYLE_CSS else 'classic'
    if one_page and os.environ.get('APPLYTWIN_FIT') != 'legacy':
        # a short resume may set its type a little larger, up to ~11.2pt body text (finance is already at 11pt)
        fs = float((re.search(r'--fs:([\d.]+)pt', STYLE_CSS[style]) or [0, 10])[1])
        res = _fit_measured(r, style, out_pdf, worth, kmax=round(max(1.0, min(1.08, 11.2 / fs)), 3))
        if res:
            return res
    # keep the type readable: shrink only a little, then cut the weakest lines; go smaller only if cutting runs out
    for k in (1.0, .97, .95):
        html_to_pdf(build_html(r, style, k), out_pdf)
        n = page_count(out_pdf)
        if n == 1 or not one_page:
            return {"pdf": out_pdf, "pages": n, "scale": k, "dropped": dropped, "resume": r}
    for k, budget in ((.95, 12), (.92, 12), (.9, 30)):
        for _ in range(budget):
            victim = _drop_one(r, worth)
            if not victim:
                break
            dropped.append(victim)
            html_to_pdf(build_html(r, style, k), out_pdf)
            if page_count(out_pdf) == 1:
                return {"pdf": out_pdf, "pages": 1, "scale": k, "dropped": dropped, "resume": r}
    return {"pdf": out_pdf, "pages": page_count(out_pdf), "scale": .9, "dropped": dropped, "resume": r}


def fits(r, style, k, out_pdf):
    """Would this resume fit on one page at type scale k? (k above 1 asks whether there's room to spare.)"""
    html_to_pdf(build_html(r, style, k), out_pdf)
    return page_count(out_pdf) == 1


def _fit(r, out_pdf, one_page, dropped, make, steps, worth=None):
    for k in steps:
        make(r, k)
        n = page_count(out_pdf)
        if n == 1 or not one_page:
            return {"pdf": out_pdf, "pages": n, "scale": k, "dropped": dropped, "resume": r}
    for _ in range(30):
        v = _drop_one(r, worth)
        if not v:
            break
        dropped.append(v)
        make(r, steps[-1])
        if page_count(out_pdf) == 1:
            return {"pdf": out_pdf, "pages": 1, "scale": steps[-1], "dropped": dropped, "resume": r}
    return {"pdf": out_pdf, "pages": page_count(out_pdf), "scale": steps[-1], "dropped": dropped, "resume": r}


def _drop_one(r, worth=None):
    """Cut the least valuable line first. Entries arrive most-relevant first (the tailor orders them), so we
    trim from the end of each section, in this order: extra bullets on later entries, then the least relevant
    whole roles/projects/skill lines, and only as a last resort papers or the top entries."""
    def bullet(sec, keep, start=0):
        items = r.get(sec) or []
        if worth:   # the least relevant bullet for this job, across every entry that can spare one
            cands = [(worth(b), idx, bi) for idx in range(start, len(items)) if len(items[idx].get('bullets', [])) > keep
                     for bi, b in enumerate(items[idx]['bullets'])]
            if cands:
                _, idx, bi = min(cands)
                return f"{sec}: {ats_plain(items[idx]['bullets'].pop(bi))[:60]}"
            return None
        for idx in range(len(items) - 1, start - 1, -1):
            if len(items[idx].get('bullets', [])) > keep:
                return f"{sec}: {ats_plain(items[idx]['bullets'].pop())[:60]}"

    def entry(sec, floor):
        items = r.get(sec) or []
        if len(items) > floor:
            x = items.pop()
            return f"{sec}: {ats_plain(x if isinstance(x, str) else x.get('name') or x.get('org') or x.get('title') or x.get('label', ''))[:60]}"

    plan = [lambda: entry('volunteering', 1), lambda: bullet('volunteering', 1), lambda: bullet('projects', 2), lambda: bullet('leadership', 1), lambda: bullet('experience', 2, 2),
            lambda: entry('leadership', 1), lambda: entry('experience', 5), lambda: bullet('projects', 1, 2),
            lambda: entry('projects', 4), lambda: entry('skills', 4), lambda: bullet('experience', 1, 3),
            lambda: entry('experience', 4), lambda: entry('awards', 1), lambda: entry('research', 3),
            lambda: entry('projects', 3), lambda: bullet('projects', 1),
            lambda: bullet('experience', 2), lambda: entry('skills', 3),
            lambda: entry('experience', 3), lambda: entry('projects', 2), lambda: bullet('experience', 1),
            # the one leadership entry the plan chose (a design-team lead, a club role) goes only near the end
            lambda: entry('leadership', 0), lambda: entry('research', 2)]   # publications: cut last
    for step in plan:
        v = step()
        if v:
            return v
    return None


def ats_plain(s):
    from .ats import plain
    return plain(s)
