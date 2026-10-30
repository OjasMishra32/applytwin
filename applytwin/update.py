"""Self-update, so nobody has to maintain an install: on start, the app checks GitHub for a newer commit on main and,
if there is one, swaps in the new code before serving. A git checkout (a developer's copy) is never touched.

The installer records the commit it installed in INSTALLED; `applytwin update` does the same thing by hand.
"""
import json
import os
import shutil
import tarfile
import tempfile
import urllib.request

REPO = 'OjasMishra32/applytwin'
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MARK = os.path.join(APP, 'INSTALLED')


def _get(url, timeout=8):
    req = urllib.request.Request(url, headers={'User-Agent': 'ApplyTwin-updater', 'Accept': 'application/vnd.github+json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def is_checkout():
    return os.path.isdir(os.path.join(APP, '.git'))


def installed():
    try:
        return open(MARK, encoding='utf-8').read().strip()
    except OSError:
        return ''


def latest():
    """The newest commit on main whose tests passed in CI, so a broken push never reaches anyone's install."""
    for c in json.loads(_get(f'https://api.github.com/repos/{REPO}/commits?sha=main&per_page=6')):
        runs = json.loads(_get(f"https://api.github.com/repos/{REPO}/commits/{c['sha']}/check-runs")).get('check_runs', [])
        if runs and all(r.get('status') == 'completed' and r.get('conclusion') in ('success', 'skipped', 'neutral') for r in runs):
            return c['sha']
    return ''


def check():
    """{'current', 'latest', 'available', 'managed'}; never raises (offline just means no update)."""
    cur = installed()
    out = {"current": cur[:7], "latest": "", "available": False, "managed": not is_checkout()}
    if is_checkout():
        return out
    try:
        sha = latest()
        out.update(latest=sha[:7], available=bool(sha) and sha != cur)
    except Exception:
        pass
    return out


def apply(sha=None):
    """Download main, replace the app folder in place (your data in ~/.applytwin is separate and untouched)."""
    if is_checkout():
        return {"updated": False, "reason": "This is a git checkout; use git pull."}
    sha = sha or latest()
    if not sha:
        return {"updated": False, "reason": "No tested version available right now."}
    tmp = tempfile.mkdtemp(prefix='applytwin-update-')
    try:
        tgz = os.path.join(tmp, 'a.tgz')
        with open(tgz, 'wb') as f:
            f.write(_get(f'https://codeload.github.com/{REPO}/tar.gz/{sha}', timeout=60))
        with tarfile.open(tgz) as t:
            root = os.path.realpath(os.path.join(tmp, 'x'))
            for m in t.getmembers():   # refuse anything that would land outside the extraction folder
                if not os.path.realpath(os.path.join(root, m.name)).startswith(root + os.sep):
                    raise ValueError('unsafe path in update archive')
            t.extractall(root)
        new = next(os.path.join(root, d) for d in os.listdir(root))
        if not os.path.exists(os.path.join(new, 'bin', 'applytwin')):
            raise ValueError('incomplete download')
        old = APP + '.old'
        shutil.rmtree(old, ignore_errors=True)
        os.rename(APP, old)
        shutil.move(new, APP)
        open(os.path.join(APP, 'INSTALLED'), 'w', encoding='utf-8').write(sha)
        os.chmod(os.path.join(APP, 'bin', 'applytwin'), 0o755)
        shutil.rmtree(old, ignore_errors=True)
        return {"updated": True, "sha": sha[:7]}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
