#!/usr/bin/env bash
# ApplyTwin installer:  curl -fsSL apply.twinly.tech/install | bash
# Installs (or updates) ApplyTwin in ~/.applytwin-app, connects it to Claude Code and Codex, checks your setup, opens the app.
# No API keys: ApplyTwin runs on the Claude Code or Codex plan you already have. Your data lives in ~/.applytwin.
set -euo pipefail

BASE="${APPLYTWIN_URL:-https://apply.twinly.tech}"
REPO="OjasMishra32/applytwin"   # the ApplyTwin repo
# newest commit on main that passed CI (falls back to main if GitHub's API is unreachable)
SHA="$(python3 - "$REPO" <<'PY' 2>/dev/null || true
import json, sys, urllib.request
repo = sys.argv[1]
get = lambda u: json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "ApplyTwin-installer"}), timeout=10))
for c in get(f"https://api.github.com/repos/{repo}/commits?sha=main&per_page=6"):
    runs = get(f"https://api.github.com/repos/{repo}/commits/{c['sha']}/check-runs").get("check_runs", [])
    if runs and all(r.get("status") == "completed" and r.get("conclusion") in ("success", "skipped", "neutral") for r in runs):
        print(c["sha"]); break
PY
)"
SRC="${APPLYTWIN_SRC:-https://codeload.github.com/$REPO/tar.gz/${SHA:-refs/heads/main}}"
DIR="${APPLYTWIN_DIR:-$HOME/.applytwin-app}"
b() { printf '\033[1m%s\033[0m\n' "$*"; }
ok() { printf '\033[32m✓\033[0m %s\n' "$*"; }
warn() { printf '\033[33m!\033[0m %s\n' "$*"; }
die() { printf '\033[31m✗\033[0m %s\n' "$*"; exit 1; }

b "Installing ApplyTwin"
command -v python3 >/dev/null || die "ApplyTwin needs Python 3.9+. Get it at https://www.python.org/downloads/ and run this again."
python3 -c 'import sys; sys.exit(sys.version_info < (3, 9))' || die "ApplyTwin needs Python 3.9 or newer (you have $(python3 -V))."
ok "$(python3 -V)"
command -v npx >/dev/null && ok "Node.js $(node -v 2>/dev/null)" || warn "Node.js not found. Your twin needs it to drive a browser: https://nodejs.org"
have=0
command -v claude >/dev/null && { ok "Claude Code found"; have=1; }
command -v codex >/dev/null && { ok "Codex found"; have=1; }
[ "$have" = 1 ] || warn "Neither Claude Code nor Codex is installed. Install one (any paid plan works, no API key):
    npm install -g @anthropic-ai/claude-code     # then run: claude   and type /login
    npm install -g @openai/codex                 # then run: codex login"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
curl -fsSL "$SRC" -o "$tmp/applytwin.tar.gz" 2>/dev/null || curl -fsSL "$BASE/applytwin.tar.gz" -o "$tmp/applytwin.tar.gz" \
  || die "Could not download ApplyTwin (tried GitHub and $BASE)"
mkdir -p "$tmp/x" && tar -xzf "$tmp/applytwin.tar.gz" -C "$tmp/x"
top="$(find "$tmp/x" -mindepth 1 -maxdepth 1 -type d | head -1)"
[ -f "$top/bin/applytwin" ] || die "The download looks incomplete. Try again in a minute."
rm -rf "$DIR.old"; [ -d "$DIR" ] && mv "$DIR" "$DIR.old"
mv "$top" "$DIR" && rm -rf "$DIR.old"
[ -n "$SHA" ] && echo "$SHA" > "$DIR/INSTALLED"   # lets the app update itself from here on
chmod +x "$DIR/bin/applytwin"
ok "ApplyTwin $(cat "$DIR/VERSION" 2>/dev/null || echo '') in $DIR"
python3 -m pip install --quiet --user pypdf >/dev/null 2>&1 || true   # optional: lets the ATS check read PDFs

mkdir -p "$HOME/.local/bin" && ln -sf "$DIR/bin/applytwin" "$HOME/.local/bin/applytwin"
case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) warn "Add ~/.local/bin to your PATH to run 'applytwin' from anywhere." ;; esac

echo; b "Connecting your agents"
python3 "$DIR/bin/applytwin" install-agents || warn "Could not connect an agent yet. Run 'applytwin install-agents' after installing Claude Code or Codex."
echo; b "Checking your setup"
python3 "$DIR/bin/applytwin" doctor || true
echo
b "Opening ApplyTwin at http://localhost:4747  (Ctrl+C to stop, 'applytwin app' to open it again)"
exec python3 "$DIR/bin/applytwin" app ${APPLYTWIN_NO_OPEN:+--no-open} </dev/null
