"""LaTeX output. Every tailored resume is also written as a .tex (Jake's Resume layout, the most common
LaTeX resume on Overleaf) so LaTeX users get an editable source. If a TeX engine is installed
(tectonic, lualatex, xelatex or pdflatex) the 'latex' template compiles the PDF with it.
"""
import os
import re
import shutil
import subprocess
import tempfile

PREAMBLE = r"""\documentclass[letterpaper,11pt]{article}
\usepackage[empty]{fullpage}
\usepackage{titlesec}
\usepackage[usenames,dvipsnames]{color}
\usepackage{enumitem}
\usepackage[hidelinks]{hyperref}
\usepackage[english]{babel}
\usepackage{tabularx}
\usepackage[T1]{fontenc}
\input{glyphtounicode}
\pagestyle{empty}
\addtolength{\oddsidemargin}{-0.5in}
\addtolength{\evensidemargin}{-0.5in}
\addtolength{\textwidth}{1in}
\addtolength{\topmargin}{-.5in}
\addtolength{\textheight}{1.0in}
\urlstyle{same}
\raggedbottom
\raggedright
\setlength{\tabcolsep}{0in}
\titleformat{\section}{\vspace{-4pt}\scshape\raggedright\large}{}{0em}{}[\color{black}\titlerule \vspace{-5pt}]
\pdfgentounicode=1
\newcommand{\resumeItem}[1]{\item\small{{#1 \vspace{-2pt}}}}
\newcommand{\resumeSubheading}[4]{\vspace{-2pt}\item
  \begin{tabular*}{0.97\textwidth}[t]{l@{\extracolsep{\fill}}r}
    \textbf{#1} & #2 \\ \textit{\small#3} & \textit{\small #4} \\
  \end{tabular*}\vspace{-7pt}}
\newcommand{\resumeProjectHeading}[2]{\item
  \begin{tabular*}{0.97\textwidth}{l@{\extracolsep{\fill}}r}
    \small#1 & #2 \\
  \end{tabular*}\vspace{-7pt}}
\renewcommand\labelitemii{$\vcenter{\hbox{\tiny$\bullet$}}$}
\newcommand{\resumeSubHeadingListStart}{\begin{itemize}[leftmargin=0.15in, label={}]}
\newcommand{\resumeSubHeadingListEnd}{\end{itemize}}
\newcommand{\resumeItemListStart}{\begin{itemize}}
\newcommand{\resumeItemListEnd}{\end{itemize}\vspace{-5pt}}
"""

SPECIAL = {'&': r'\&', '%': r'\%', '$': r'\$', '#': r'\#', '_': r'\_', '{': r'\{', '}': r'\}', '~': r'\textasciitilde{}',
           '^': r'\textasciicircum{}', '\\': r'\textbackslash{}'}


def esc(s):
    return ''.join(SPECIAL.get(c, c) for c in (s or ''))


def tex(s):
    """light markdown (**bold**, [text](url)) -> LaTeX"""
    out, i = [], 0
    for m in re.finditer(r'\[([^\]]+)\]\(([^)\s]+)\)', s or ''):
        out.append(_bold(esc(s[i:m.start()])))
        out.append(r'\href{%s}{%s}' % (m.group(2).replace('%', r'\%').replace('#', r'\#'), _bold(esc(m.group(1)))))
        i = m.end()
    out.append(_bold(esc((s or '')[i:])))
    return ''.join(out)


def _bold(s):
    return re.sub(r'\*\*(.+?)\*\*', r'\\textbf{\1}', s)


def dates(e):
    a, b = e.get('start', ''), e.get('end', '')
    return esc(f'{a} -- {b}' if a and b else (b or a))


def build_tex(r, k=1.0):
    b = r.get('basics', {})
    contact = [esc(x) for x in (b.get('phone'), b.get('email'), b.get('location')) if x]
    for l in b.get('links', []):
        label = l.get('label') or re.sub(r'^https?://(www\.)?', '', l.get('url', '')).rstrip('/')
        contact.append(r'\href{%s}{\underline{%s}}' % (l.get('url', ''), esc(label)))
    body = [r'\begin{center}', r'\textbf{\Huge \scshape %s} \\ \vspace{1pt}' % esc(b.get('name', ''))]
    if b.get('headline'):
        body.append(r'\small %s \\ \vspace{1pt}' % r' $\cdot$ '.join(tex(h) for h in b['headline']))
    body += [r'\small ' + r' $|$ '.join(contact), r'\end{center}']
    for sec in r.get('order') or []:
        data = r.get(sec)
        if not data:
            continue
        title = (r.get('titles') or {}).get(sec) or {'education': 'Education', 'experience': 'Experience', 'projects': 'Projects',
                                                     'research': 'Research and Publications', 'leadership': 'Leadership',
                                                     'volunteering': 'Volunteer Experience', 'skills': 'Skills',
                                                     'certifications': 'Licenses and Certifications', 'awards': 'Awards'}.get(sec, sec.title())
        body.append(r'\section{%s}' % esc(title))
        if sec == 'education':
            body.append(r'\resumeSubHeadingListStart')
            for e in data:
                deg = ' in '.join(x for x in (e.get('degree'), e.get('major')) if x)
                if e.get('gpa'):
                    deg += f"; GPA: {e['gpa']}"
                body.append(r'\resumeSubheading{%s}{%s}{%s}{%s}' % (esc(e.get('school')), esc(e.get('location')), esc(deg), dates(e)))
                extra = [x for x in (e.get('honors') or []) + ([('Coursework: ' + ', '.join(e['coursework']))] if e.get('coursework') else [])]
                if extra:
                    body += [r'\resumeItemListStart'] + [r'\resumeItem{%s}' % tex(x) for x in extra] + [r'\resumeItemListEnd']
            body.append(r'\resumeSubHeadingListEnd')
        elif sec in ('experience', 'leadership', 'volunteering'):
            body.append(r'\resumeSubHeadingListStart')
            for e in data:
                org = tex(e.get('org', '')) if not e.get('url') else r'\href{%s}{%s}' % (e['url'], tex(e.get('org', '')))
                body.append(r'\resumeSubheading{%s}{%s}{%s}{%s}' % (org, dates(e), tex(e.get('title', '')), esc(e.get('location', ''))))
                if e.get('bullets'):
                    body += [r'\resumeItemListStart'] + [r'\resumeItem{%s}' % tex(x) for x in e['bullets']] + [r'\resumeItemListEnd']
            body.append(r'\resumeSubHeadingListEnd')
        elif sec == 'projects':
            body.append(r'\resumeSubHeadingListStart')
            for p in data:
                nm = r'\textbf{%s}' % tex(p.get('name', ''))
                tag = ' $|$ '.join(x for x in (tex(p.get('tagline', '')), esc(', '.join(p.get('tech', [])))) if x)
                body.append(r'\resumeProjectHeading{%s%s}{%s}' % (nm, (r' $|$ \emph{%s}' % tag) if tag else '', esc(p.get('date', ''))))
                if p.get('bullets'):
                    body += [r'\resumeItemListStart'] + [r'\resumeItem{%s}' % tex(x) for x in p['bullets']] + [r'\resumeItemListEnd']
            body.append(r'\resumeSubHeadingListEnd')
        elif sec == 'skills':
            body.append(r'\begin{itemize}[leftmargin=0.15in, label={}]\small{\item{')
            body.append(r' \\ '.join(r'\textbf{%s}{: %s}' % (esc(s.get('label', '')), esc(', '.join(s.get('items', [])))) for s in data))
            body.append(r'}}\end{itemize}')
        else:  # research, awards, certifications
            body.append(r'\begin{itemize}[leftmargin=0.15in]')
            for x in data:
                if isinstance(x, str):
                    body.append(r'\item\small{%s}' % tex(x))
                else:
                    t = tex(x.get('title', ''))
                    if x.get('url'):
                        t = r'\href{%s}{%s}' % (x['url'], t)
                    body.append(r'\item\small{%s%s%s}' % ((tex(x['role']) + ': ') if x.get('role') else '', t,
                                                           (r'. \textbf{%s}' % tex(x['venue'])) if x.get('venue') else ''))
            body.append(r'\end{itemize}')
    size = r'\fontsize{%.1f}{%.1f}\selectfont' % (10.5 * k, 12.6 * k) if k < 1 else ''
    return PREAMBLE + '\n\\begin{document}\n' + size + '\n' + '\n'.join(body) + '\n\\end{document}\n'


def engine():
    for e in ('tectonic', 'lualatex', 'xelatex', 'pdflatex'):
        p = shutil.which(e)
        if p:
            return e, p
    for d in ('/Library/TeX/texbin', '/opt/homebrew/bin', '/usr/local/bin'):
        for e in ('lualatex', 'pdflatex', 'xelatex', 'tectonic'):
            p = os.path.join(d, e)
            if os.path.exists(p):
                return e, p
    return None, None


def compile_tex(src, out_pdf):
    name, exe = engine()
    if not exe:
        raise RuntimeError('No LaTeX engine found (install tectonic or TeX Live, or pick another template)')
    with tempfile.TemporaryDirectory() as td:
        f = os.path.join(td, 'resume.tex')
        open(f, 'w', encoding='utf-8').write(src)
        cmd = [exe, f] if name == 'tectonic' else [exe, '-interaction=nonstopmode', '-halt-on-error', 'resume.tex']
        for _ in range(1 if name == 'tectonic' else 2):
            subprocess.run(cmd, cwd=td, capture_output=True, timeout=180)
        pdf = os.path.join(td, 'resume.pdf')
        if not os.path.exists(pdf):
            raise RuntimeError('LaTeX failed to compile')
        os.makedirs(os.path.dirname(os.path.abspath(out_pdf)), exist_ok=True)
        shutil.copy(pdf, out_pdf)
    return out_pdf
