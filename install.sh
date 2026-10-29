#!/usr/bin/env bash
# One-step setup: checks Python and Chrome, registers ApplyTwin with Claude Code and Codex, opens the app.
set -e
cd "$(dirname "$0")"
command -v python3 >/dev/null || { echo "ApplyTwin needs Python 3.9+ (https://www.python.org/downloads/)"; exit 1; }
python3 -c 'import sys; sys.exit(sys.version_info < (3, 9))' || { echo "ApplyTwin needs Python 3.9 or newer"; exit 1; }
chmod +x bin/applytwin
python3 -m pip install --quiet --user pypdf 2>/dev/null || true   # optional: lets the ATS check read PDFs
python3 bin/applytwin install-agents
echo
echo "Opening ApplyTwin at http://localhost:4747 (Ctrl+C to stop)"
exec python3 bin/applytwin app
