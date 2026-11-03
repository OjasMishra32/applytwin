#!/bin/bash
# First-run setup for the ApplyTwin Mac app. Nothing to install by hand: it gets its own Python (and Node.js if this Mac
# has none) into ~/.applytwin-app-runtime, then runs the same installer as the one-line install, which puts ApplyTwin in
# ~/.applytwin-app and starts it at login. Lines starting with STEP: are shown in the app's setup screen.
set -euo pipefail
RT="$HOME/.applytwin-app-runtime"
ARCH="$(uname -m)"; [ "$ARCH" = arm64 ] && PA=aarch64 || PA=x86_64
[ "$ARCH" = arm64 ] && NA=arm64 || NA=x64
PY_URL="https://github.com/astral-sh/python-build-standalone/releases/download/20261026/cpython-3.12.16%2B20261026-$PA-apple-darwin-install_only.tar.gz"
NODE_V=v26.13.0
NODE_URL="https://nodejs.org/dist/$NODE_V/node-$NODE_V-darwin-$NA.tar.gz"
BASE="${APPLYTWIN_URL:-https://apply.twinly.tech}"
step() { echo "STEP:$*"; }
mkdir -p "$RT" "$HOME/.applytwin"

# unpack into a temp folder next to the target, then rename: a half-finished download never looks installed
fetch() {   # url dest-dir
  local tmp; tmp="$(mktemp -d "$RT/.dl-XXXXXX")"
  curl -fsSL --retry 3 "$1" -o "$tmp/a.tar.gz"
  mkdir "$tmp/x" && tar -xzf "$tmp/a.tar.gz" -C "$tmp/x"
  rm -rf "$2" && mv "$(find "$tmp/x" -mindepth 1 -maxdepth 1 -type d | head -1)" "$2"
  rm -rf "$tmp"
}

step "Getting Python ready"
if ! "$RT/python/bin/python3" -c 'import ssl, sqlite3' >/dev/null 2>&1; then
  fetch "$PY_URL" "$RT/python"
fi

# Node.js runs the browser your twin fills forms in. Use the Mac's own if it has one.
NODE_DIRS="/opt/homebrew/bin:/usr/local/bin"
for d in "$HOME"/.nvm/versions/node/*/bin "$HOME/.volta/bin"; do [ -d "$d" ] && NODE_DIRS="$NODE_DIRS:$d"; done
if ! PATH="$NODE_DIRS:/usr/bin:/bin" command -v npx >/dev/null 2>&1; then
  step "Getting the browser tools ready"
  [ -x "$RT/node/bin/npx" ] || fetch "$NODE_URL" "$RT/node"
fi

# ApplyTwin's own Python comes first; the Mac's Node.js (if any) before the one we downloaded
export PATH="$RT/python/bin:$HOME/.local/bin:$NODE_DIRS:/usr/bin:/bin:/usr/sbin:/sbin:$RT/node/bin"
step "Installing ApplyTwin"
curl -fsSL --retry 3 "$BASE/install" -o "$RT/install.sh"
APPLYTWIN_NATIVE=1 bash "$RT/install.sh" 2>&1 | sed -u 's/\x1b\[[0-9;]*m//g' | while IFS= read -r line; do
  echo "$line"
  case "$line" in
    *"Connecting your agents"*) step "Connecting Claude Code and Codex" ;;
    *"Checking your setup"*) step "Checking everything works" ;;
    *"starts by itself"*) step "Starting ApplyTwin" ;;
  esac
done
[ "${PIPESTATUS[0]}" = 0 ] || exit 1
step "Done"
