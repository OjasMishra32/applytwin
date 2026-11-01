"""Build the data behind apply.twinly.tech/demo by running ApplyTwin's real tailor on a made-up student and three made-up
postings. The page then shows real output (the rewrites, keyword scores and the finished one-page resume), not a mockup.

Run it on a machine where Claude Code or Codex is signed in:  python3 scripts/demo/make_demo.py
It writes scripts/demo/out/ (data.json and one PNG per resume page), which build-site.sh copies into the site.
Everything here is fictional: the student, the schools' details and the companies.
"""
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'out')
os.environ['APPLYTWIN_HOME'] = tempfile.mkdtemp(prefix='atdemo')   # never the real ~/.applytwin
os.environ.setdefault('APPLYTWIN_NO_TWIN', '1')
sys.path.insert(0, os.path.join(HERE, '..', '..'))
from applytwin import ats, store, tailor  # noqa: E402

STUDENT = {
    "basics": {"name": "Maya Chen", "email": "maya.chen@example.edu", "phone": "(555) 010-2048", "location": "Austin, TX",
               "links": [{"label": "github.com/mayachen-demo", "url": "https://github.com/mayachen-demo"}]},
    "education": [{"id": "ut", "school": "State University", "degree": "B.S. Computer Science", "minor": "Mathematics",
                   "start": "Aug 2024", "end": "May 2028", "gpa": "3.8/4.0", "location": "Austin, TX",
                   "coursework": ["Data Structures", "Algorithms", "Databases", "Operating Systems", "Machine Learning", "Statistics"]}],
    "experience": [
        {"id": "lab", "title": "Undergraduate Research Assistant", "org": "Human-Centered Computing Lab, State University",
         "start": "Jan 2025", "end": "Present", "location": "Austin, TX", "tech": ["Python", "pandas", "scikit-learn", "PostgreSQL"],
         "bullets": ["Wrote Python scripts to clean survey data from 2,400 participants for a study on study habits",
                     "Built a dashboard in Streamlit so the lab could look at survey results without asking me to run queries",
                     "Trained a logistic regression model that predicted course dropout with 81% accuracy on held-out students",
                     "Moved the lab's spreadsheets into a PostgreSQL database and wrote the queries the team uses every week"]},
        {"id": "it", "title": "IT Help Desk Assistant", "org": "State University Libraries", "start": "Sep 2024", "end": "Dec 2024",
         "location": "Austin, TX", "tech": ["Windows", "Jira"],
         "bullets": ["Answered about 40 tickets a week from students and staff about laptops, printers and Wi-Fi",
                     "Wrote 12 help articles that cut repeat printer questions",
                     "Helped set up 60 laptops for a new computer lab"]},
    ],
    "projects": [
        {"id": "budget", "name": "BudgetBuddy", "tagline": "Expense tracker web app", "tech": ["React", "Node.js", "Express", "MongoDB"],
         "bullets": ["Built a React and Node.js app where students log expenses and see monthly spending by category",
                     "Added login with JSON Web Tokens and a REST API with 14 endpoints",
                     "About 150 students at my school used it during the spring semester"]},
        {"id": "bus", "name": "Campus Bus Tracker", "tagline": "Hackathon project, 2nd place", "tech": ["Python", "Flask", "Leaflet"],
         "bullets": ["Made a Flask app that shows live campus bus locations on a map from the city's open data feed",
                     "Placed 2nd of 38 teams at the university hackathon"]},
        {"id": "cnn", "name": "Plant Disease Classifier", "tagline": "Class project", "tech": ["PyTorch", "Python"],
         "bullets": ["Trained a convolutional neural network in PyTorch to spot 5 leaf diseases from photos, 92% test accuracy",
                     "Used data augmentation to make up for a small dataset of 3,000 images"]},
    ],
    "leadership": [{"id": "acm", "title": "Workshop Lead", "org": "ACM Student Chapter", "start": "Aug 2025", "end": "Present",
                    "bullets": ["Taught 4 beginner workshops on Git and Python to about 30 students each"]}],
    "skills": [{"label": "Languages", "items": ["Python", "JavaScript", "Java", "SQL", "C"]},
               {"label": "Frameworks", "items": ["React", "Node.js", "Express", "Flask", "PyTorch", "pandas", "scikit-learn"]},
               {"label": "Tools", "items": ["Git", "PostgreSQL", "MongoDB", "Docker", "Linux"]}],
    "awards": [{"name": "2nd place, State University Hackathon", "date": "2025"}],
}

JOBS = [
    {"id": "demo_swe", "company": "Northwind Robotics", "title": "Software Engineering Intern, Summer 2027", "ats": "greenhouse",
     "location": "Austin, TX", "url": "https://example.com/northwind",
     "description": """Northwind Robotics builds software for warehouse robots. As a Software Engineering Intern you will build
features in our web dashboard (React, TypeScript) and backend services (Node.js, REST APIs, PostgreSQL) that operators use to
monitor fleets. You will write tests, review code, and ship to production with your team.
Requirements: pursuing a BS in Computer Science or related; experience with JavaScript/React and Node.js; REST API design;
SQL databases; Git. Nice to have: Docker, authentication (JWT/OAuth), building tools that real users rely on."""},
    {"id": "demo_data", "company": "Lumen Bank", "title": "Data Science Intern", "ats": "workday", "location": "Dallas, TX",
     "url": "https://example.com/lumen",
     "description": """Lumen Bank's analytics team is hiring a Data Science Intern to help predict customer churn and
build dashboards for business partners. You will clean large datasets with Python (pandas), build classification models with
scikit-learn, write SQL against our data warehouse, and present findings to non-technical stakeholders.
Requirements: coursework in statistics and machine learning; Python, pandas, scikit-learn; SQL; data visualization
(Tableau, Streamlit or similar); clear communication. Nice to have: experience with survey or behavioral data, PostgreSQL."""},
    {"id": "demo_ml", "company": "Atlas Health", "title": "Machine Learning Intern, Medical Imaging", "ats": "lever",
     "location": "Remote (US)", "url": "https://example.com/atlas",
     "description": """Atlas Health uses computer vision to help clinicians read medical images faster. Our ML interns train
and evaluate deep learning models (PyTorch, CNNs) on imaging datasets, work on data augmentation for small labeled datasets,
and measure model accuracy carefully. Requirements: Python, PyTorch, convolutional neural networks, machine learning
fundamentals, experience training and evaluating models. Nice to have: image classification projects, Linux, Docker."""},
]


def page_png(pdf, out):
    try:
        import pymupdf as fitz
    except ImportError:
        import fitz
    d = fitz.open(pdf)
    d[0].get_pixmap(dpi=110).save(out)


def main():
    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT)
    store.save('resume.json', STUDENT)
    v = store.resume()
    data = {"student": {"name": STUDENT['basics']['name'], "school": "State University", "degree": "B.S. Computer Science",
                        "year": "Sophomore"}, "jobs": []}
    base = os.path.join(OUT, 'master.png')
    from applytwin import render
    r0 = render.render(tailor.ensure_ids(json.loads(json.dumps(STUDENT))), 'classic', os.path.join(store.HOME, 'master.pdf'))
    page_png(r0['pdf'], base)
    master, master_txt = r0['resume'], render.pdf_text(r0['pdf'])
    for j in JOBS:
        print('tailoring', j['company'], flush=True)
        d = os.path.join(store.HOME, 'out', j['id'])
        r = tailor.tailor(v, j, j['description'], mode='auto', style='classic', out_dir=d)
        rep = json.load(open(os.path.join(d, 'tailor.json'), encoding='utf-8'))['report']   # the full rewrites, from and to
        png = f"{j['id']}.png"
        page_png(r['pdf'], os.path.join(OUT, png))
        # "before" is her usual one-page resume as it reads to a screener, not her whole vault (that can't fit on a page)
        before = ats.report(master, j['description'], r0['pages'], master_txt)
        data['jobs'].append({
            "id": j['id'], "company": j['company'], "title": j['title'], "location": j['location'], "ats": j['ats'],
            "description": j['description'], "page": png,
            "score_before": round(before.get('score', 0)), "score_after": round(r.get('score') or 0),
            "rewrites": [{"from": ats.plain(x['from']), "to": ats.plain(x['to'])} for x in (rep.get('rewrites') or [])
                         if ats.plain(x['from']).strip() != ats.plain(x['to']).strip()][:5],
            "positioning": r.get('positioning') or '', "missing": (r.get('missing') or [])[:5],
        })
    json.dump(data, open(os.path.join(OUT, 'data.json'), 'w'), indent=1)
    print('wrote', OUT)


if __name__ == '__main__':
    main()
