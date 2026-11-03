"""Render the example resume in every template and save the PDFs plus what was trimmed, to compare across machines."""
import json
import os
import sys
import tempfile
os.environ['APPLYTWIN_HOME'] = tempfile.mkdtemp()
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from applytwin import render
out = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else 'render-out')
os.makedirs(out, exist_ok=True)
r = json.load(open(os.path.join(ROOT, 'examples', 'resume.example.json'), encoding='utf-8'))
report = {}
for style in ['latex'] + list(render.STYLE_CSS):
    try:
        res = render.render(r, style, os.path.join(out, f'{style}.pdf'))
        report[style] = {k: res.get(k) for k in ('pages', 'scale', 'spacing', 'dropped')}
    except Exception as e:
        report[style] = {'error': f'{type(e).__name__}: {e}'}
    print(style, json.dumps(report[style])[:300], flush=True)
json.dump(report, open(os.path.join(out, 'report.json'), 'w'), indent=1)
