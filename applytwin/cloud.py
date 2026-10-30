"""Sign in with Google (Supabase Auth) and sync to the cloud.

ApplyTwin shares the Twinly Supabase project (same accounts) but keeps its own space: tables applytwin_accounts /
applytwin_applications and the private storage bucket "applytwin" (objects under <user_id>/). Everything stays
local-first; signing in just backs it up and makes it follow you across machines.

Override with APPLYTWIN_SUPABASE_URL / APPLYTWIN_SUPABASE_ANON_KEY to point a fork at its own project.
"""
import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from . import store

URL = os.environ.get('APPLYTWIN_SUPABASE_URL', 'https://advktwnedlgnhswpxokg.supabase.co')
# The public anon key (safe to ship; row-level security protects every row).
ANON = os.environ.get('APPLYTWIN_SUPABASE_ANON_KEY',
                      'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFkdmt0d25lZGxnbmhzd3B4b2tnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODE1NzkzMTUsImV4cCI6MjA5NzE1NTMxNX0.kPKEMNuqvvzGWKHRSnCtq4vkiYQTicX0wDSiwyYj7LE')
BUCKET = 'applytwin'
_lock = threading.Lock()
_sync_lock = threading.Lock()   # one application upload at a time (token() takes _lock itself)


def _req(method, path, token=None, body=None, headers=None, raw=None, timeout=30):
    h = {'apikey': ANON, 'Authorization': f'Bearer {token or ANON}'}
    data = None
    if raw is not None:
        data = raw
    elif body is not None:
        data = json.dumps(body).encode()
        h['Content-Type'] = 'application/json'
    h.update(headers or {})
    req = urllib.request.Request(URL + path, data=data, method=method, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        out = r.read()
    return json.loads(out) if out and out[:1] in (b'{', b'[') else out


def login_url(redirect):
    return f"{URL}/auth/v1/authorize?" + urllib.parse.urlencode({'provider': 'google', 'redirect_to': redirect})


def _session():
    return store.load('auth.json', None)


def _save(sess):
    store.save('auth.json', sess)
    try:
        os.chmod(store.path('auth.json'), 0o600)
    except OSError:
        pass


def set_session(access_token, refresh_token, expires_in=3600):
    user = _req('GET', '/auth/v1/user', access_token)  # verifies the token with Supabase
    meta = user.get('user_metadata') or {}
    sess = {"access_token": access_token, "refresh_token": refresh_token, "expires_at": time.time() + int(expires_in or 3600) - 60,
            "user": {"id": user['id'], "email": user.get('email'), "name": meta.get('full_name') or meta.get('name'),
                     "avatar": meta.get('avatar_url') or meta.get('picture')}}
    _save(sess)
    first = pull()
    threading.Thread(target=lambda: (_safe(push), _safe(push_applications)), daemon=True).start()
    return {"signed_in": True, "user": sess['user'], "restored": first}


def token():
    with _lock:
        s = _session()
        if not s:
            return None
        if time.time() > s.get('expires_at', 0):
            try:
                r = _req('POST', '/auth/v1/token?grant_type=refresh_token', body={"refresh_token": s['refresh_token']})
            except urllib.error.HTTPError as e:
                if e.code in (400, 401, 403):   # the login was revoked or expired for good: ask to sign in again
                    p = store.path('auth.json')
                    if os.path.exists(p):
                        os.remove(p)
                    return None
                raise
            s.update(access_token=r['access_token'], refresh_token=r['refresh_token'], expires_at=time.time() + r.get('expires_in', 3600) - 60)
            _save(s)
        return s['access_token']


def status():
    s = _session()
    return {"signed_in": bool(s), "user": (s or {}).get('user'), "last_sync": (s or {}).get('last_sync')}


def logout():
    s = _session()
    if s:
        try:
            _req('POST', '/auth/v1/logout?scope=local', s['access_token'])   # only this computer, not every device
        except Exception:
            pass
    p = store.path('auth.json')
    if os.path.exists(p):
        os.remove(p)
    return {"signed_in": False}


def push():
    """Upload profile, vault, answers and learnings (one row per user)."""
    t = token()
    if not t:
        return {"skipped": "not signed in"}
    s = _session()
    row = {"user_id": s['user']['id'], "profile": store.profile(), "vault": store.resume(), "answers": store.answers(),
           "learnings": store.load('learnings.json', {}), "updated_at": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    _req('POST', '/rest/v1/applytwin_accounts?on_conflict=user_id', t, [row],
         {'Prefer': 'resolution=merge-duplicates,return=minimal'})
    s['last_sync'] = time.time()
    _save(s)
    return {"ok": True}


def pull():
    """On sign-in: if this machine has no vault yet, restore everything from the cloud."""
    t = token()
    s = _session()
    rows = _req('GET', f"/rest/v1/applytwin_accounts?user_id=eq.{s['user']['id']}&select=*", t)
    if not rows:
        return False
    r = rows[0]
    local = store.resume()
    if not (local.get('experience') or local.get('projects')) and (r.get('vault') or {}).get('experience') is not None:
        store.save('resume.json', r['vault'])
        if r.get('profile'):
            store.save('profile.json', r['profile'])
        if r.get('answers'):
            store.save('answers.json', r['answers'])
        if r.get('learnings'):
            store.save('learnings.json', r['learnings'])
        return True
    return False


def upload(local_path, key):
    """Store a resume PDF / .tex under <user_id>/<key> in the private bucket. Returns the object path."""
    t = token()
    if not t or not os.path.exists(local_path):
        return None
    s = _session()
    obj = f"{s['user']['id']}/{key}".replace('//', '/')
    ctype = 'application/pdf' if local_path.endswith('.pdf') else 'application/x-tex' if local_path.endswith('.tex') else 'text/plain'
    _req('POST', f'/storage/v1/object/{BUCKET}/{urllib.parse.quote(obj)}', t, raw=open(local_path, 'rb').read(),
         headers={'Content-Type': ctype, 'x-upsert': 'true'}, timeout=60)
    return obj


def _iso(t):
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(t or time.time()))


def push_applications():
    """Upload every application not yet in your account (with the resume it sent), then your imported history once.
    Tracks a local watermark so nothing is uploaded twice."""
    with _sync_lock:
        t = token()
        s = _session()
        if not t or not s:
            return {"skipped": "not signed in"}
        wm = s.get('synced_app_id', 0)
        rows = store.rows('select a.*, j.ats, j.apply_url from applications a left join jobs j on j.id = a.job_id where a.id > ? order by a.id', (wm,))
        out = []
        for r in rows:
            obj = None
            if r['resume_path'] and os.path.exists(r['resume_path']):
                try:
                    obj = upload(r['resume_path'], f"resumes/{r['job_id']}/{os.path.basename(r['resume_path'])}")
                except Exception:
                    obj = None
            out.append({"job_key": r['job_id'], "company": r['company'], "title": r['title'], "url": r['apply_url'] or r['url'],
                        "ats": r['ats'], "status": r['status'], "notes": r['notes'], "resume_path": obj, "created_at": _iso(r['at'])})
        if not s.get('synced_history'):   # roles you applied to before ApplyTwin (imported from your tracker)
            logged = {r['job_id'] for r in store.rows('select job_id from applications')}
            for j in store.rows("select id, company, title, url, apply_url, ats, found_at from jobs where status='applied'"):
                if j['id'] not in logged:
                    out.append({"job_key": j['id'], "company": j['company'], "title": j['title'], "url": j['apply_url'] or j['url'],
                                "ats": j['ats'], "status": "Applied", "notes": "From your history", "resume_path": None, "created_at": _iso(j['found_at'])})
        for i in range(0, len(out), 200):
            _req('POST', '/rest/v1/applytwin_applications', t, out[i:i + 200], {'Prefer': 'return=minimal'}, timeout=60)
        s = _session()
        s['synced_app_id'] = max([wm] + [r['id'] for r in rows])
        s['synced_history'] = True
        s['last_sync'] = time.time()
        _save(s)
        return {"uploaded": len(out)}


def sync_soon():
    """Fire-and-forget push after local changes."""
    if _session():
        threading.Thread(target=lambda: (_safe(push), _safe(push_applications)), daemon=True).start()


def _safe(fn, *a):
    try:
        return fn(*a)
    except Exception:
        return None
