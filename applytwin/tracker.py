"""Read a job-application tracker in the format people actually keep it in.

CSV/TSV, Excel (.xlsx), Google Sheets and Notion exports, LibreOffice (.ods), Word (.docx), PDF (a printed sheet or a
list), HTML, Markdown, JSON or plain text. Each one becomes a list of tables (rows of cells) that api.import_history
reads by their header row. Standard library only (pypdf, or pdftotext, for PDFs).
"""
import base64
import csv
import datetime
import html.parser
import io
import json
import re
import zipfile
import xml.etree.ElementTree as ET

ACCEPT = '.csv,.tsv,.txt,.xlsx,.xlsm,.ods,.pdf,.docx,.html,.htm,.md,.json'   # the file picker in the app
KINDS = 'CSV, Excel, Google Sheets, Numbers, Notion, PDF, Word or a text file'
NUMBERS = ("That's a Numbers file, which ApplyTwin can't open directly. In Numbers choose File > Export To > CSV "
           "(or Excel), then import that file.")


class Unreadable(RuntimeError):
    pass


def tables(name='', data=None, text=None):
    """[(kind, rows)] for a tracker file. data is base64 (the app's upload) or raw bytes (the command line)."""
    if text is not None and not data:
        return [('text', text_rows(text))]
    raw = data if isinstance(data, (bytes, bytearray)) else base64.b64decode(data or '')
    low = (name or '').lower()
    if not raw.strip():
        raise Unreadable('That file is empty.')
    if raw[:4] == b'%PDF' or low.endswith('.pdf'):
        return [('pdf', pdf_rows(raw))]
    if raw[:8] == b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1':   # the old binary Office formats
        raise Unreadable("That's an older Excel (.xls) or Word (.doc) file. Open it and save it as .xlsx or CSV, "
                         "then import that.")
    if raw[:2] == b'PK':
        try:
            z = zipfile.ZipFile(io.BytesIO(raw))
        except zipfile.BadZipFile:
            raise Unreadable("ApplyTwin couldn't open that file (it may be damaged). Export your tracker again as CSV or Excel.")
        with z:
            names = set(z.namelist())
            if 'xl/workbook.xml' in names:
                return [('excel', t) for t in xlsx_sheets(z)]
            if 'content.xml' in names and b'spreadsheet' in (z.read('mimetype') if 'mimetype' in names else b''):
                return [('ods', t) for t in ods_sheets(z)]
            if 'word/document.xml' in names:
                return [('word', t) for t in docx_tables(z)]
            if low.endswith(('.numbers', '.pages', '.key')) or any(n.startswith('Index/') for n in names):
                raise Unreadable(NUMBERS)
            raise Unreadable(f"ApplyTwin can't read that kind of file. Export your tracker as {KINDS} file.")
    if low.endswith(('.numbers', '.pages')):
        raise Unreadable(NUMBERS)
    s = decode(raw)
    if raw[:4096].count(b'\0') > 8 or s[:4096].count('�') > 40:   # an image or some other binary file
        raise Unreadable(f"ApplyTwin can't read that kind of file. Use a {KINDS} file.")
    head = s.lstrip()[:2000].lower()
    if low.endswith(('.html', '.htm')) or '<table' in head or head.startswith(('<!doctype html', '<html')):
        t = html_tables(s)
        if t:
            return [('html', x) for x in t]
    if low.endswith('.json') or head[:1] in '[{':
        try:
            return [('json', json_rows(json.loads(s)))]
        except ValueError:
            pass
    return [('text', text_rows(s))]


def decode(raw):
    if raw[:2] in (b'\xff\xfe', b'\xfe\xff'):   # Excel's "Unicode text" export
        return raw.decode('utf-16', 'replace')
    try:
        return raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        return raw.decode('cp1252', 'replace')   # an older Excel CSV on Windows


# ------------------------------------------------------------------ plain text: CSV, TSV, Markdown, pasted tables

def text_rows(s):
    lines = [ln for ln in s.splitlines() if ln.strip()]
    if not lines:
        return []
    pipes = [ln for ln in lines if ln.strip().startswith('|') and ln.count('|') >= 3]
    if len(pipes) >= 2 and len(pipes) >= len(lines) / 2:   # a Markdown table (Notion, Obsidian, a README)
        return [[c.strip() for c in ln.strip().strip('|').split('|')] for ln in pipes if not re.fullmatch(r'[\s|:-]+', ln)]
    sample = lines[:60]
    best, score = None, 0
    for d in ('\t', ',', ';', '|'):
        counts = [ln.count(d) for ln in sample]
        hit = sum(1 for c in counts if c >= 1)
        if hit >= max(1, len(sample) * .6) and hit * (2 if d == '\t' else 1) > score:
            best, score = d, hit * (2 if d == '\t' else 1)
    if best:
        return [r for r in csv.reader(io.StringIO('\n'.join(lines)), delimiter=best)]
    return aligned_rows(s.splitlines())


def aligned_rows(lines):
    """Columns lined up with spaces (a sheet printed to PDF, or copied from one). Columns are where the rows below the
    header leave a gap of blank space on every line (a centered header doesn't line up with its cells), or where the
    header's cells start; an empty cell doesn't shift the rest of the row left. A line holding only the tail of a
    wrapped cell joins the row above it (never across a blank line: that's a page break)."""
    chunk = lambda ln: [(m.start(), m.group()) for m in re.finditer(r'\S+(?: \S+)*', ln)]
    lines = [ln.replace('\t', '    ').rstrip() for ln in lines
             if not re.fullmatch(r'\s*(?:page\s*)?\d+(?:\s*(?:of|/)\s*\d+)?\s*', ln, re.I)]   # page numbers
    hi = next((i for i, ln in enumerate(lines[:60]) if len(chunk(ln)) >= 2 and header_index([c for _, c in chunk(ln)])), None)
    if hi is None:
        return [[c for _, c in chunk(ln)] for ln in lines if ln.strip()]
    head, body = [c for _, c in chunk(lines[hi])], lines[hi + 1:]
    block = []
    for ln in body:   # the rows on the header's own page
        if not ln.strip():
            break
        block.append(ln)
    starts = _gutters(block)
    if len(starts) > len(head):   # two header cells one space apart ("Date Applied Status"): split it where the rows do
        h2 = _place([(m.start(), m.group()) for m in re.finditer(r'\S+', lines[hi])], starts)
        if all(h2) and header_index(h2):
            head = h2
    if len(starts) != len(head):
        starts = [p for p, _ in chunk(lines[hi])]
    lines_ = []   # (cells, how many pieces of text, after a blank line)
    gap = False
    for ln in body:
        if not ln.strip():
            gap = True
            continue
        if ln.split() == lines[hi].split():   # the header again on the next page
            continue
        cs = chunk(ln)
        lines_.append((_place(cs, starts), len(cs), gap))
        gap = False
    join = lambda a, b: [(x + ' ' + y).strip() for x, y in zip(a, b)]
    out, before = [head], []
    for i, (row, n, gap) in enumerate(lines_):
        if not row[0] and n <= max(1, len(starts) // 2):   # part of a cell that wrapped onto more lines
            nxt = lines_[i + 1] if i + 1 < len(lines_) else None
            if nxt and not nxt[2] and nxt[0][0] and all(not nxt[0][k] for k, c in enumerate(row) if c):
                before.append(row)   # the top of a vertically centered cell: it belongs to the row below
                continue
            if out[1:] and not gap:
                out[-1] = join(out[-1], row)
                continue
        for b in reversed(before):
            row = join(b, row)
        before = []
        out.append(row)
    return out


def _place(chunks, starts):
    """Cells of one line: each piece of text goes in the column it starts in."""
    row = [''] * len(starts)
    for p, c in chunks:
        k = max([i for i, s in enumerate(starts) if s <= p + 2] or [0])
        row[k] = (row[k] + ' ' + c).strip()
    return row


def _gutters(block):
    """Where each column starts: after 2+ character positions that are blank on every line."""
    used = [any(i < len(ln) and ln[i] != ' ' for ln in block) for i in range(max(map(len, block), default=0))]
    starts, last = [], -10
    for i, u in enumerate(used):
        if u:
            if i - last > 2:
                starts.append(i)
            last = i
    return starts


# ------------------------------------------------------------------ PDF

def pdf_rows(raw):
    txt = ''
    try:
        from pypdf import PdfReader
        from . import store
        with store.quiet_pypdf():
            pages = PdfReader(io.BytesIO(raw)).pages
            try:   # keeps a printed sheet's columns lined up
                txt = '\n'.join(p.extract_text(extraction_mode='layout') or '' for p in pages)
            except TypeError:   # an older pypdf
                txt = '\n'.join(p.extract_text() or '' for p in pages)
    except ImportError:
        import shutil
        import subprocess
        import tempfile
        if not shutil.which('pdftotext'):
            raise Unreadable('Reading PDFs needs pypdf: run  python3 -m pip install pypdf  (or export your tracker as CSV or Excel).')
        with tempfile.NamedTemporaryFile(suffix='.pdf') as f:
            f.write(raw)
            f.flush()
            txt = subprocess.run(['pdftotext', '-layout', f.name, '-'], capture_output=True, text=True, encoding='utf-8',
                                 errors='replace').stdout
    except Exception:
        raise Unreadable("ApplyTwin couldn't open that PDF (it may be damaged or password-protected). Export your tracker "
                         "again, or as CSV or Excel.")
    if len(re.sub(r'\s', '', txt)) < 20:
        raise Unreadable("That PDF has no text in it (it's a picture of the page). Export your tracker as CSV or Excel instead.")
    return text_rows(txt)


# ------------------------------------------------------------------ Excel, LibreOffice, Word

X = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
     'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
     'rel': 'http://schemas.openxmlformats.org/package/2006/relationships',
     'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}


def _rels(z, path):
    try:
        return {r.get('Id'): r.get('Target') for r in ET.fromstring(z.read(path)).iter(f"{{{X['rel']}}}Relationship")}
    except (KeyError, ET.ParseError):
        return {}


def _col(ref):
    n = 0
    for ch in re.match(r'[A-Z]*', ref or '').group():
        n = n * 26 + ord(ch) - 64
    return max(n - 1, 0)


def xlsx_sheets(z):
    """Every sheet as rows of text. Dates stay as Excel's day numbers here (import_history reads them); a cell's link
    is added at the end of its row, so a 'Link' cell that points at the posting still gives the URL."""
    m = X['m']
    shared = []
    if 'xl/sharedStrings.xml' in z.namelist():
        for si in ET.fromstring(z.read('xl/sharedStrings.xml')).iter(f'{{{m}}}si'):
            shared.append(''.join(t.text or '' for t in si.iter(f'{{{m}}}t')))
    rels = _rels(z, 'xl/_rels/workbook.xml.rels')
    out = []
    for sh in ET.fromstring(z.read('xl/workbook.xml')).iter(f'{{{m}}}sheet'):
        target = rels.get(sh.get(f"{{{X['r']}}}id"), '')
        path = target.lstrip('/') if target.startswith('/') else 'xl/' + target
        try:
            root = ET.fromstring(z.read(path))
        except (KeyError, ET.ParseError):
            continue
        links = {}
        lrels = _rels(z, re.sub(r'([^/]+)$', r'_rels/\1.rels', path))
        for h in root.iter(f'{{{m}}}hyperlink'):
            url = lrels.get(h.get(f"{{{X['r']}}}id")) or ''
            if url.startswith('http'):
                links.setdefault(int(re.sub(r'\D', '', h.get('ref', '').split(':')[0]) or 0), []).append(url)
        rows = []
        for r in root.iter(f'{{{m}}}row'):
            cells = {}
            for c in r.iter(f'{{{m}}}c'):
                t, v = c.get('t'), c.find(f'{{{m}}}v')
                if t == 'inlineStr':
                    val = ''.join(x.text or '' for x in c.iter(f'{{{m}}}t'))
                elif v is None:
                    continue
                elif t == 's':
                    val = shared[int(v.text)] if (v.text or '').isdigit() and int(v.text) < len(shared) else ''
                elif t == 'b':
                    val = 'TRUE' if v.text == '1' else 'FALSE'
                else:
                    val = v.text or ''
                cells[_col(c.get('r'))] = val
            row = [cells.get(i, '') for i in range(max(cells) + 1)] if cells else []
            row += links.get(int(r.get('r') or 0), [])
            if any(x.strip() for x in row):
                rows.append(row)
        out.append(rows)
    return out


def ods_sheets(z):
    t = 'urn:oasis:names:tc:opendocument:xmlns:table:1.0'
    tx = 'urn:oasis:names:tc:opendocument:xmlns:text:1.0'
    o = 'urn:oasis:names:tc:opendocument:xmlns:office:1.0'
    xl = 'http://www.w3.org/1999/xlink'
    out = []
    for tab in ET.fromstring(z.read('content.xml')).iter(f'{{{t}}}table'):
        rows = []
        for r in tab.iter(f'{{{t}}}table-row'):
            row, links = [], []
            for c in r:
                if not c.tag.endswith('table-cell'):
                    continue
                val = c.get(f'{{{o}}}date-value') or '\n'.join(''.join(p.itertext()) for p in c.iter(f'{{{tx}}}p'))
                links += [a.get(f'{{{xl}}}href') for a in c.iter(f'{{{tx}}}a') if (a.get(f'{{{xl}}}href') or '').startswith('http')]
                row += [val] * min(int(c.get(f'{{{t}}}number-columns-repeated') or 1), 50 if val else 1)
            if any(x.strip() for x in row):
                rows.append(row + links)
        out.append(rows)
    return out


def docx_tables(z):
    w = X['w']
    root = ET.fromstring(z.read('word/document.xml'))
    rels = _rels(z, 'word/_rels/document.xml.rels')
    out = []
    for tbl in root.iter(f'{{{w}}}tbl'):
        rows = []
        for tr in tbl.iter(f'{{{w}}}tr'):
            cells = [' '.join(''.join(t.text or '' for t in p.iter(f'{{{w}}}t')) for p in tc.iter(f'{{{w}}}p')).strip()
                     for tc in tr.iter(f'{{{w}}}tc')]
            links = [rels.get(h.get(f"{{{X['r']}}}id")) for h in tr.iter(f'{{{w}}}hyperlink')]
            rows.append(cells + [u for u in links if u and u.startswith('http')])
        out.append(rows)
    if not out:   # a list typed as paragraphs, not a table
        paras = [''.join(t.text or '' for t in p.iter(f'{{{w}}}t')) for p in root.iter(f'{{{w}}}p')]
        out.append(text_rows('\n'.join(paras)))
    return out


# ------------------------------------------------------------------ HTML and JSON

class _Tables(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables, self.row, self.cell, self.links = [], None, None, []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'table':
            self.tables.append([])
        elif tag == 'tr' and self.tables:
            self.row, self.links = [], []
        elif tag in ('td', 'th') and self.row is not None:
            self.cell = []
        elif tag == 'a' and (a.get('href') or '').startswith('http') and self.row is not None:
            self.links.append(a['href'])
        elif tag == 'br' and self.cell is not None:
            self.cell.append(' ')

    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self.cell is not None and self.row is not None:
            self.row.append(re.sub(r'\s+', ' ', ''.join(self.cell)).strip())
            self.cell = None
        elif tag == 'tr' and self.row is not None and self.tables:
            if any(self.row):
                self.tables[-1].append(self.row + self.links)
            self.row = None

    def handle_data(self, d):
        if self.cell is not None:
            self.cell.append(d)


def html_tables(s):
    p = _Tables()
    p.feed(s)
    return [t for t in p.tables if t]


def json_rows(d):
    if isinstance(d, dict):   # {"applications": [...]} or {"results": [...]} (Notion's API)
        d = next((v for v in d.values() if isinstance(v, list) and v and isinstance(v[0], dict)), [d])
    items = [x for x in d if isinstance(x, dict)] if isinstance(d, list) else []
    keys = []
    for x in items:
        keys += [k for k in x if k not in keys]
    flat = lambda v: ', '.join(map(str, v)) if isinstance(v, list) else '' if v is None else str(v)
    return [keys] + [[flat(x.get(k)) for k in keys] for x in items] if items else []


# ------------------------------------------------------------------ reading the columns

COLS = {   # header names used by Simplify, Huntr, Teal, Notion, Google Sheets and hand-made trackers (exact first)
    'company': ('company', 'company name', 'employer', 'organization', 'organisation', 'firm', 'business'),
    'title': ('title', 'job title', 'position', 'job position', 'position title', 'role', 'role title', 'job', 'job name', 'internship', 'opportunity'),
    'url': ('url', 'link', 'job url', 'job link', 'posting', 'posting url', 'posting link', 'application link', 'apply link', 'job posting'),
    'status': ('status', 'stage', 'list', 'application status', 'outcome', 'result', 'response', 'progress', 'current status'),
    'date': ('date applied', 'applied date', 'applied on', 'application date', 'date of application', 'submitted on', 'date submitted', 'date'),
    'applied': ('applied', 'applied?', 'submitted', 'submitted?', 'did i apply', 'sent', 'done'),
}
# what a longer header has to contain (and must not) to count as that column: "Company Name (Employer)" is a company,
# "Company Website" is not
LOOSE = {
    'company': (r'compan|employer|organi[sz]ation', r'url|link|website|site|email|contact|location|size|industry|type|logo'),
    'title': (r'title|position|role|job', r'url|link|id\b|board|type|description|location|date|status|level|source|company|website'),
    'url': (r'url|link|posting|href', r'company|linkedin profile|recruiter|contact|date'),
    'status': (r'status|stage|outcome', r'date|visa|sponsor'),
    'date': (r'date|applied on|when', r'deadline|due|start|interview|follow|response|posted'),
}


def _norm(h):
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9?]+', ' ', str(h).lower())).strip()


def header_index(cells):
    """{column: index} when these cells are a tracker's header row (they name a company and a role), else None."""
    head = [_norm(h) for h in cells]
    idx = {k: next((i for i, h in enumerate(head) if h in names or h.rstrip('?') in names), None) for k, names in COLS.items()}
    for k, (want, avoid) in LOOSE.items():
        if idx[k] is None:
            idx[k] = next((i for i, h in enumerate(head) if h and re.search(want, h) and not re.search(avoid, h)
                           and i not in idx.values()), None)
    if idx['date'] is not None and idx['date'] == idx['applied']:   # "Date Applied" is a date, not a yes/no column
        idx['applied'] = None
    name = next((i for i, h in enumerate(head) if h in ('name', 'title name')), None)
    if name is not None and name not in idx.values():   # a Notion database: its "Name" is the company or the role
        k = 'company' if idx['company'] is None and idx['title'] is not None else 'title' if idx['title'] is None else None
        if k and idx['company'] != name:
            idx[k] = name
    return idx if idx['company'] is not None and idx['title'] is not None else None


def excel_date(v):
    """Excel stores dates as days since 1899-12-30; a sheet exported raw shows 45567 instead of 2024-10-01."""
    if re.fullmatch(r'\d{5}(?:\.\d+)?', v or '') and 30000 < float(v) < 80000:
        return (datetime.date(1899, 12, 30) + datetime.timedelta(days=int(float(v)))).isoformat()
    return v
