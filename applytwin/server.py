"""Local web app: http://localhost:4747 . Standard library only, binds to 127.0.0.1."""
import json
import threading
import sys
import mimetypes
import os
import re
import traceback
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import api, cloud, store

WEB = os.path.join(store.APP, 'web')


def _q(qs, k, d=None):
    return (qs.get(k) or [d])[0]


GET = {
    r'/api/state': lambda m, qs, b: {"profile": api.get_profile(), "vault": api.get_vault(), "stats": api.stats(),
                                     "setup": api.setup_status(), "templates": api.templates(), "app_dir": store.APP, "home": store.HOME},
    r'/api/stats': lambda m, qs, b: api.stats(),
    r'/api/setup': lambda m, qs, b: api.setup_status(),
    r'/api/jobs': lambda m, qs, b: api.list_jobs(_q(qs, 'q', ''), _q(qs, 'status', 'new'),
                                                 float(_q(qs, 'min')) if _q(qs, 'min') else None, int(_q(qs, 'limit', 150)),
                                                 _q(qs, 'ats'), _q(qs, 'order', 'fit')),
    r'/api/jobs/([\w-]+)': lambda m, qs, b: api.get_job(m.group(1)),
    r'/api/jobs/([\w-]+)/questions': lambda m, qs, b: api.job_questions(m.group(1)),
    r'/api/jobs/([\w-]+)/ats': lambda m, qs, b: api.ats_report(job_id=m.group(1)),
    r'/api/templates': lambda m, qs, b: api.templates(),
    r'/api/answers': lambda m, qs, b: api.get_answers(),
    r'/api/applications': lambda m, qs, b: api.applications(history=_q(qs, 'history') == '1'),
    r'/api/scan': lambda m, qs, b: api.scan_status(),
    r'/api/dump': lambda m, qs, b: {"text": api.get_dump()},
    r'/api/ats': lambda m, qs, b: api.ats_report(),
    r'/api/next': lambda m, qs, b: api.next_jobs(int(_q(qs, 'n', 10))),
    r'/api/queue': lambda m, qs, b: api.queue(int(_q(qs, 'n', 50))),
    r'/api/run': lambda m, qs, b: api.run_status(),
    r'/api/doctor': lambda m, qs, b: api.doctor(),
    r'/api/questions': lambda m, qs, b: api.profile_questions(),
    r'/api/update': lambda m, qs, b: api.update_status(),
    r'/api/agents': lambda m, qs, b: api.agent_status(),
    r'/api/auth': lambda m, qs, b: cloud.status(),
    r'/api/inbox': lambda m, qs, b: api.inbox_poll(),
    r'/api/auth/login': lambda m, qs, b: {"url": cloud.login_url(_q(qs, 'redirect', 'http://localhost:4747/'))},
}
POST = {
    r'/api/profile': lambda m, qs, b: api.update_profile(b),
    r'/api/vault': lambda m, qs, b: api.save_vault(b),
    r'/api/answers': lambda m, qs, b: (store.save('answers.json', b), {"ok": True})[1],
    r'/api/answer': lambda m, qs, b: api.save_answer(b['question'], b['answer'], b.get('key')),
    r'/api/answer/test': lambda m, qs, b: api.answer_questions(b.get('questions', [])),
    r'/api/dump': lambda m, qs, b: api.save_dump(b.get('text', '')),
    r'/api/scan': lambda m, qs, b: api.scan(b.get('sources'), background=True),
    r'/api/jobs': lambda m, qs, b: api.add_job(b['url'], b.get('title', ''), b.get('company', ''), b.get('description', '')),
    r'/api/jobs/([\w-]+)/status': lambda m, qs, b: api.set_job_status(m.group(1), b['status']),
    r'/api/jobs/([\w-]+)/tailor': lambda m, qs, b: api.tailor_apply(m.group(1), b.get('plan'), b.get('template'), b.get('mode', 'auto')),
    r'/api/jobs/([\w-]+)/prompt': lambda m, qs, b: api.tailor_prompt(m.group(1)),
    r'/api/jobs/([\w-]+)/log': lambda m, qs, b: api.log_application(m.group(1), b.get('status', 'Applied'), b.get('notes', '')),
    r'/api/render': lambda m, qs, b: api.render_resume(b.get('template'), b.get('job_id')),
    r'/api/ats': lambda m, qs, b: api.ats_report(b.get('job_id'), b.get('jd'), b.get('resume')),
    r'/api/import': lambda m, qs, b: api.import_resume(b.get('name', ''), b.get('data'), b.get('text')),
    r'/api/run': lambda m, qs, b: api.start_run(b.get('agent', 'claude'), int(b.get('n', 25))),
    r'/api/run/stop': lambda m, qs, b: api.stop_run(),
    r'/api/finish': lambda m, qs, b: api.finish_jobs(b.get('job_ids') or [], bool(b.get('submit'))),
    r'/api/open-twin': lambda m, qs, b: api.open_in_twin_browser(b['url']),
    r'/api/history': lambda m, qs, b: api.import_history(text=b.get('text', '')),
    r'/api/history/email': lambda m, qs, b: api.start_run(b.get('agent') or api.store.profile()['apply'].get('agent') or 'claude', 1,
                                                          prompt=api.email_history_prompt()),
    r'/api/auth': lambda m, qs, b: cloud.set_session(b['access_token'], b['refresh_token'], b.get('expires_in', 3600)),
    r'/api/auth/logout': lambda m, qs, b: cloud.logout(),
    r'/api/sync': lambda m, qs, b: cloud.push(),
    r'/api/inbox/(\d+)/resolve': lambda m, qs, b: api.resolve(m.group(1)),
}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype='application/json'):
        data = body if isinstance(body, bytes) else (json.dumps(body, default=str) if ctype == 'application/json' else body).encode()
        self.send_response(code)
        self.send_header('Content-Type', ctype + ('; charset=utf-8' if ctype.startswith(('text', 'application/json')) else ''))
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(data)

    def _route(self, table, body=None):
        u = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(u.query)
        for pat, fn in table.items():
            m = re.fullmatch(pat, u.path)
            if m:
                try:
                    return self._send(200, fn(m, qs, body))
                except Exception as e:
                    traceback.print_exc()
                    return self._send(500, {"error": str(e)})
        return None

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(u.query)
        if u.path.startswith('/api/'):
            if self._route(GET) is None:
                self._send(404, {"error": "not found"})
            return
        if u.path == '/preview':
            try:
                return self._send(200, api.preview_html(_q(qs, 'template', 'classic'), _q(qs, 'job')), 'text/html')
            except Exception as e:
                return self._send(500, f'<pre>{e}</pre>', 'text/html')
        if u.path == '/file':
            p = os.path.realpath(_q(qs, 'path', ''))
            if not p.startswith(os.path.realpath(store.HOME)) or not os.path.isfile(p):
                return self._send(403, {"error": "forbidden"})
            return self._send(200, open(p, 'rb').read(), mimetypes.guess_type(p)[0] or 'application/octet-stream')
        rel = 'index.html' if u.path in ('/', '') else u.path.lstrip('/')
        f = os.path.realpath(os.path.join(WEB, rel))
        if not f.startswith(os.path.realpath(WEB)) or not os.path.isfile(f):
            f = os.path.join(WEB, 'index.html')
        self._send(200, open(f, 'rb').read(), mimetypes.guess_type(f)[0] or 'text/plain')

    def do_POST(self):
        n = int(self.headers.get('Content-Length') or 0)
        try:
            body = json.loads(self.rfile.read(n) or b'{}')
        except ValueError:
            return self._send(400, {"error": "bad json"})
        if self._route(POST, body) is None:
            self._send(404, {"error": "not found"})


def _self_update():
    """Installed copies update themselves on start (git checkouts never do); turn off with apply.auto_update = false."""
    from . import update
    if update.is_checkout() or store.profile().get('apply', {}).get('auto_update') is False:
        return
    st = update.check()
    if st['available']:
        print(f"Updating ApplyTwin ({st['current'] or 'new'} -> {st['latest']})...")
        try:
            if update.apply().get('updated'):   # restart on the new code
                if os.name == 'nt':
                    import subprocess
                    subprocess.Popen([sys.executable] + sys.argv)
                    sys.exit(0)
                os.execv(sys.executable, [sys.executable] + sys.argv)
        except Exception as e:
            print(f'Update skipped: {e}')


def serve(port=4747, open_browser=True):
    import urllib.request
    _self_update()
    srv = None
    for p in range(port, port + 20):
        try:
            srv = ThreadingHTTPServer(('127.0.0.1', p), H)
            break
        except OSError:
            try:   # ApplyTwin is already running there: just open it
                with urllib.request.urlopen(f'http://127.0.0.1:{p}/api/stats', timeout=2) as r:
                    if r.status == 200 and p == port:
                        print(f'ApplyTwin is already running at http://localhost:{p}')
                        if open_browser:
                            import webbrowser
                            webbrowser.open(f'http://localhost:{p}')
                        return
            except Exception:
                pass
    if srv is None:
        raise SystemExit(f'Ports {port}-{port + 19} are all busy. Free one, or run: applytwin app --port 5050')
    port = srv.server_address[1]
    url = f'http://localhost:{port}'
    # on start: re-apply the current matching rules to saved jobs (so fixes like the skip list reach existing queues),
    # then refresh jobs if the last scan is old
    from . import install
    threading.Thread(target=lambda: (install.refresh_skills(), api.rescore(), api.scan_if_stale()), daemon=True).start()
    print(f'ApplyTwin is running at {url}  (data in {store.HOME})')
    if open_browser:
        import webbrowser
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
