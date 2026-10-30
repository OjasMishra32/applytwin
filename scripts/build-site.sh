#!/usr/bin/env bash
# Builds the public site for apply.twinly.tech into ./site: landing page, installer, and the app tarball.
set -euo pipefail
cd "$(dirname "$0")/.."
keep="$(mktemp -d)"; [ -d site/.vercel ] && cp -R site/.vercel "$keep/"   # the build empties site/; keep the Vercel link
(cd ui && npm run build >/dev/null && npx vite build -c vite.site.config.js >/dev/null)
[ -d "$keep/.vercel" ] && cp -R "$keep/.vercel" site/; rm -rf "$keep"
mv site/site.html site/index.html
cp scripts/install-remote.sh site/install.sh
date +%Y.%m.%d > VERSION
tar -czf site/applytwin.tar.gz -s ',^\.,applytwin,' --exclude './ui/node_modules' --exclude './site' --exclude '*/__pycache__' \
  --exclude '*.pyc' --exclude '.DS_Store' --exclude './.vercel' --exclude './.claude' --exclude './.git' .
cat > site/vercel.json <<'JSON'
{
  "cleanUrls": true,
  "rewrites": [{ "source": "/install", "destination": "/install.sh" }],
  "headers": [
    { "source": "/install(.sh)?", "headers": [{ "key": "Content-Type", "value": "text/plain; charset=utf-8" }, { "key": "Cache-Control", "value": "no-cache" }] },
    { "source": "/applytwin.tar.gz", "headers": [{ "key": "Cache-Control", "value": "no-cache" }] }
  ]
}
JSON
echo "site/ ready: $(du -sh site | cut -f1), tarball $(du -h site/applytwin.tar.gz | cut -f1)"
