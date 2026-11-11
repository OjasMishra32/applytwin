#!/usr/bin/env bash
# ApplyTwin installer:  curl -fsSL apply.twinly.tech/install | bash
# Installs (or updates) ApplyTwin in ~/.applytwin-app, connects it to Claude Code and Codex, checks your setup, opens the app.
# No API keys: ApplyTwin runs on the Claude Code or Codex plan you already have. Your data lives in ~/.applytwin.
set -euo pipefail

BASE="${APPLYTWIN_URL:-https://apply.twinly.tech}"
REPO="OjasMishra32/applytwin"   # the ApplyTwin repo
# Nothing to install by hand (like the Windows installer): a computer without a usable Python 3.9+ or Node.js gets
# ApplyTwin's own copies in ~/.applytwin-app-runtime. No admin, no Homebrew, no Xcode tools.
RT="${APPLYTWIN_RUNTIME:-$HOME/.applytwin-app-runtime}"
_os="$(uname)"; _arch="$(uname -m)"
case "$_arch" in arm64|aarch64) _pa=aarch64; _na=arm64 ;; *) _pa=x86_64; _na=x64 ;; esac
case "$_os" in
  Darwin) _pyt="$_pa-apple-darwin"; _nt="darwin-$_na" ;;
  *)      _pyt="$_pa-unknown-linux-gnu"; _nt="linux-$_na" ;;
esac
_PY_URL="https://github.com/astral-sh/python-build-standalone/releases/download/20261026/cpython-3.12.16%2B20261026-$_pyt-install_only.tar.gz"
_NODE_V=v26.13.0
_NODE_URL="https://nodejs.org/dist/$_NODE_V/node-$_NODE_V-$_nt.tar.gz"
_fetch() {   # url dest-dir: unpack beside the target, then rename, so a cut-off download never looks installed
  mkdir -p "$RT"; local t; t="$(mktemp -d "$RT/.dl-XXXXXX")"
  curl -fsSL --retry 3 "$1" -o "$t/a.tar.gz" && mkdir "$t/x" && tar -xzf "$t/a.tar.gz" -C "$t/x" \
    && rm -rf "$2" && mv "$(find "$t/x" -mindepth 1 -maxdepth 1 -type d | head -1)" "$2"
  local r=$?; rm -rf "$t"; return $r
}
_good_py() {   # a real Python 3.9+ with ssl; on a Mac without the Xcode tools /usr/bin/python3 is only a stub that opens an install dialog
  [ -x "$1" ] || return 1
  if [ "$_os" = Darwin ] && [ "$1" = /usr/bin/python3 ] && ! xcode-select -p >/dev/null 2>&1; then return 1; fi
  "$1" -c 'import sys, ssl; sys.exit(sys.version_info < (3, 9))' >/dev/null 2>&1
}
PY=""
for c in "$(command -v python3 2>/dev/null || true)" "$RT/python/bin/python3"; do
  [ -n "$c" ] && _good_py "$c" && { PY="$c"; break; }
done
if [ -z "$PY" ]; then
  printf '\033[36m>\033[0m Getting Python ready (a one-time download, about 40 MB)...\n'
  _fetch "$_PY_URL" "$RT/python" && _good_py "$RT/python/bin/python3" && PY="$RT/python/bin/python3" \
    || { printf '\033[31m✗\033[0m Could not download Python. Check your internet connection and run this again.\n'; exit 1; }
fi
case "$PY" in "$RT"/*) export PATH="$RT/python/bin:$PATH" ;; esac
if ! command -v npx >/dev/null 2>&1; then
  if [ -x "$RT/node/bin/npx" ] || { printf '\033[36m>\033[0m Getting Node.js ready (a one-time download, about 50 MB)...\n'; _fetch "$_NODE_URL" "$RT/node"; }; then
    export PATH="$PATH:$RT/node/bin"   # the computer's own Node.js wins if it gets one later
  fi
fi

# newest commit on main that passed CI (falls back to main if GitHub's API is unreachable)
SHA="$("$PY" - "$REPO" <<'PY' 2>/dev/null || true
import json, sys, urllib.request
repo = sys.argv[1]
get = lambda u: json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "ApplyTwin-installer"}), timeout=10))
for c in get(f"https://api.github.com/repos/{repo}/commits?sha=main&per_page=6"):
    runs = get(f"https://api.github.com/repos/{repo}/commits/{c['sha']}/check-runs").get("check_runs", [])
    if runs and all(r.get("status") == "completed" and r.get("conclusion") in ("success", "skipped", "neutral") for r in runs):
        print(c["sha"]); break
PY
)"
SHA="${APPLYTWIN_REF:-$SHA}"   # CI installs the exact commit under test
# the newest commit that passed every test; if GitHub can't be asked (rate limit), the copy published on the site, never untested main
SRC="${APPLYTWIN_SRC:-$([ -n "$SHA" ] && echo "https://codeload.github.com/$REPO/tar.gz/$SHA" || echo "$BASE/applytwin.tar.gz")}"
DIR="${APPLYTWIN_DIR:-$HOME/.applytwin-app}"
b() { printf '\033[1m%s\033[0m\n' "$*"; }
ok() { printf '\033[32m✓\033[0m %s\n' "$*"; }
warn() { printf '\033[33m!\033[0m %s\n' "$*"; }
die() { printf '\033[31m✗\033[0m %s\n' "$*"; exit 1; }

b "Installing ApplyTwin"
ok "$("$PY" -V)"
command -v npx >/dev/null && ok "Node.js $(node -v 2>/dev/null)" || warn "Node.js couldn't be set up. Your twin needs it to drive a browser: https://nodejs.org"
have=0
command -v claude >/dev/null && { ok "Claude Code found"; have=1; }
command -v codex >/dev/null && { ok "Codex found"; have=1; }
[ "$have" = 1 ] || warn "Neither Claude Code nor Codex is installed yet. In the app, press Install and sign in (any paid Claude or ChatGPT plan works, no API key)."

# unpack next to the install folder (same disk) so the final move is an instant rename, never a copy that can fail halfway
mkdir -p "$(dirname "$DIR")"
tmp="$(mktemp -d "$(dirname "$DIR")/.applytwin-install-XXXXXX")"
trap 'rm -rf "$tmp"; [ ! -d "$DIR" ] && [ -d "$DIR.old" ] && mv "$DIR.old" "$DIR"' EXIT   # never leave you without the app
curl -fsSL "$SRC" -o "$tmp/applytwin.tar.gz" 2>/dev/null || curl -fsSL "$BASE/applytwin.tar.gz" -o "$tmp/applytwin.tar.gz" \
  || die "Could not download ApplyTwin (tried GitHub and $BASE)"
mkdir -p "$tmp/x" && tar -xzf "$tmp/applytwin.tar.gz" -C "$tmp/x"
top="$(find "$tmp/x" -mindepth 1 -maxdepth 1 -type d | head -1)"
[ -f "$top/bin/applytwin" ] || die "The download looks incomplete. Try again in a minute."
rm -rf "$DIR.old"; [ -d "$DIR" ] && mv "$DIR" "$DIR.old"
if mv "$top" "$DIR"; then rm -rf "$DIR.old"; else [ -d "$DIR.old" ] && mv "$DIR.old" "$DIR"; die "Could not put ApplyTwin in place. Your existing install is untouched."; fi
[ -n "$SHA" ] && echo "$SHA" > "$DIR/INSTALLED"   # lets the app update itself from here on
chmod +x "$DIR/bin/applytwin"
ok "ApplyTwin $(cat "$DIR/VERSION" 2>/dev/null || echo '') in $DIR"
"$PY" -m pip install --quiet --user pypdf >/dev/null 2>&1 || true   # optional: lets the ATS check read PDFs

mkdir -p "$HOME/.local/bin"
case "$PY" in
  "$RT"/*) # ApplyTwin's own Python: a small launcher, since the script's own `python3` line would find the Mac's stub
     rm -f "$HOME/.local/bin/applytwin"
     printf '#!/bin/sh\nexport PATH="$PATH:%s"\nexec "%s" "%s" "$@"\n' "$RT/node/bin" "$PY" "$DIR/bin/applytwin" > "$HOME/.local/bin/applytwin"
     chmod +x "$HOME/.local/bin/applytwin" ;;
  *) ln -sf "$DIR/bin/applytwin" "$HOME/.local/bin/applytwin" ;;
esac
case ":$PATH:" in
  *":$HOME/.local/bin:"*) ;;
  *) # make the `applytwin` command work in every new terminal
     rcs="$HOME/.bashrc $HOME/.profile"; [ "$(uname)" = Darwin ] && rcs="$HOME/.zprofile $rcs" && touch "$HOME/.zprofile"
     [ -f "$HOME/.zshrc" ] && rcs="$HOME/.zshrc $rcs"   # zsh on Linux reads .zshrc, not .profile
     for rc in $rcs; do
       [ -f "$rc" ] || continue
       grep -qs 'applytwin: .local/bin' "$rc" || printf '\nexport PATH="$HOME/.local/bin:$PATH"   # applytwin: .local/bin\n' >> "$rc"
     done
     ok "Added the applytwin command to your PATH (new terminals)" ;;
esac

echo; b "Connecting your agents"
"$PY" "$DIR/bin/applytwin" install-agents || warn "Could not connect an agent yet. Run 'applytwin install-agents' after installing Claude Code or Codex."
echo; b "Checking your setup"
"$PY" "$DIR/bin/applytwin" doctor || true
echo
printf '\033[33m★\033[0m Free for every student. If it helps you, star it: https://github.com/OjasMishra32/applytwin\n\n'
[ -n "${APPLYTWIN_NO_APP:-}" ] && exit 0

# Run like a normal app: start quietly at login (so localhost:4747 always works and daily scans happen) and add an icon.
mkdir -p "$HOME/.applytwin"
case "$(uname)" in
  Darwin)
    PL="$HOME/Library/LaunchAgents/tech.twinly.applytwin.plist"
    mkdir -p "$(dirname "$PL")"
    cat > "$PL" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>tech.twinly.applytwin</string>
  <key>ProgramArguments</key><array><string>$PY</string><string>$DIR/bin/applytwin</string><string>app</string><string>--no-open</string></array>
  <key>EnvironmentVariables</key><dict><key>PATH</key><string>$HOME/.local/bin:$PATH</string></dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><dict><key>SuccessfulExit</key><false/></dict>
  <key>StandardOutPath</key><string>$HOME/.applytwin/server.log</string><key>StandardErrorPath</key><string>$HOME/.applytwin/server.log</string>
</dict></plist>
PLIST
    launchctl bootout "gui/$(id -u)" "$PL" 2>/dev/null || true
    # launchd often refuses a bootstrap right after a bootout ("Bootstrap failed: 5"); give it a few tries
    for _ in 1 2 3 4 5; do launchctl bootstrap "gui/$(id -u)" "$PL" 2>/dev/null && break; sleep 1; done
    launchctl kickstart -k "gui/$(id -u)/tech.twinly.applytwin" >/dev/null 2>&1 && ok "ApplyTwin starts by itself when you log in"
    # the Mac app (apply.twinly.tech/download) runs this itself and shows ApplyTwin in its own window: no shortcut, no browser tab
    [ -n "${APPLYTWIN_NATIVE:-}" ] && exit 0
    if [ ! -d /Applications/ApplyTwin.app ]; then
      mkdir -p "$HOME/Applications"
      osacompile -o "$HOME/Applications/ApplyTwin.app" -e 'open location "http://localhost:4747"' >/dev/null 2>&1 && ok "ApplyTwin is in your Applications (find it with Spotlight)"
    fi
    sleep 2; [ -d /Applications/ApplyTwin.app ] && open -a /Applications/ApplyTwin.app || open "http://localhost:4747" ;;
  *)
    if command -v systemctl >/dev/null && systemctl --user show-environment >/dev/null 2>&1; then
      mkdir -p "$HOME/.config/systemd/user"
      cat > "$HOME/.config/systemd/user/applytwin.service" <<UNIT
[Unit]
Description=ApplyTwin
[Service]
Environment=PATH=$HOME/.local/bin:$PATH
ExecStart=$PY $DIR/bin/applytwin app --no-open
Restart=always
[Install]
WantedBy=default.target
UNIT
      systemctl --user daemon-reload && systemctl --user enable --now applytwin >/dev/null 2>&1 && ok "ApplyTwin starts by itself when you log in"
    else
      nohup "$PY" "$DIR/bin/applytwin" app --no-open >"$HOME/.applytwin/server.log" 2>&1 &
    fi
    mkdir -p "$HOME/.local/share/applications"
    printf '[Desktop Entry]\nType=Application\nName=ApplyTwin\nExec=xdg-open http://localhost:4747\nTerminal=false\nCategories=Office;\n' \
      > "$HOME/.local/share/applications/applytwin.desktop"
    sleep 2; (xdg-open "http://localhost:4747" >/dev/null 2>&1 &) ;;
esac
echo
b "ApplyTwin is running at http://localhost:4747"
echo "  Open it any time: the ApplyTwin app icon, that address, or type: applytwin"
echo "  This is the app: sign in with Google there, add your resume, press Start. (apply.twinly.tech only shows your results.)"
