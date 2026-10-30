# ApplyTwin installer for Windows:  irm apply.twinly.tech/install.ps1 | iex
# Installs (or updates) ApplyTwin in %USERPROFILE%\.applytwin-app, connects it to Claude Code and Codex, checks your
# setup, opens the app. No API keys: it runs on the Claude Code or Codex plan you already have.
# Runs inside the user's own PowerShell window (irm | iex): it never calls exit (that would close the window), and the
# whole script is one script block so the preferences it sets don't leak into the user's session.
& {
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$Repo = 'OjasMishra32/applytwin'
$Dir = if ($env:APPLYTWIN_DIR) { $env:APPLYTWIN_DIR } else { Join-Path $env:USERPROFILE '.applytwin-app' }
function Ok($m) { Write-Host "  v $m" -ForegroundColor Green }
function Warn($m) { Write-Host "  ! $m" -ForegroundColor Yellow }
function Die($m) { Write-Host "  x $m" -ForegroundColor Red; throw "ApplyTwin install stopped: $m" }

Write-Host "Installing ApplyTwin" -ForegroundColor White

# A real Python 3.9+ (the Microsoft Store placeholder only opens the Store, so test each candidate)
$Py = $null
foreach ($c in @(@('py', '-3'), @('python'), @('python3'))) {
  try {
    $exe = & $c[0] $c[1..9] -c "import sys; print(sys.executable if sys.version_info >= (3, 9) else '')" 2>$null
    if ($LASTEXITCODE -eq 0 -and $exe) { $Py = $exe.Trim(); break }
  } catch {}
}
if (-not $Py) { Die "ApplyTwin needs Python 3.9+. Install it with:  winget install Python.Python.3.12   then run this again." }
Ok "Python ($Py)"
if (Get-Command npx -ErrorAction SilentlyContinue) { Ok "Node.js $(node -v)" } else { Warn "Node.js not found. Your twin needs it to drive a browser:  winget install OpenJS.NodeJS.LTS" }
$have = $false
if (Get-Command claude -ErrorAction SilentlyContinue) { Ok "Claude Code found"; $have = $true }
if (Get-Command codex -ErrorAction SilentlyContinue) { Ok "Codex found"; $have = $true }
if (-not $have) {
  Warn "Neither Claude Code nor Codex is installed. Install one (any paid plan works, no API key):"
  Write-Host "      npm install -g @anthropic-ai/claude-code     # then run: claude   and type /login"
  Write-Host "      npm install -g @openai/codex                 # then run: codex login"
}

# The newest commit on main that passed CI, so a broken change never reaches anyone
$Sha = ''
try {
  $h = @{ 'User-Agent' = 'ApplyTwin-installer' }
  foreach ($c in (Invoke-RestMethod "https://api.github.com/repos/$Repo/commits?sha=main&per_page=6" -Headers $h)) {
    $runs = (Invoke-RestMethod "https://api.github.com/repos/$Repo/commits/$($c.sha)/check-runs" -Headers $h).check_runs
    if ($runs -and -not ($runs | Where-Object { $_.status -ne 'completed' -or @('success', 'skipped', 'neutral') -notcontains $_.conclusion })) { $Sha = $c.sha; break }
  }
} catch {}
if ($env:APPLYTWIN_REF) { $Sha = $env:APPLYTWIN_REF }   # CI installs the exact commit under test
$Ref = if ($Sha) { $Sha } else { 'refs/heads/main' }

$tmp = Join-Path ([IO.Path]::GetTempPath()) ("applytwin-" + [guid]::NewGuid())
New-Item -ItemType Directory $tmp | Out-Null
try {
  Invoke-WebRequest "https://codeload.github.com/$Repo/zip/$Ref" -OutFile "$tmp\a.zip" -UseBasicParsing
  Expand-Archive "$tmp\a.zip" "$tmp\x"
  $top = Get-ChildItem "$tmp\x" -Directory | Select-Object -First 1
  if (-not (Test-Path "$($top.FullName)\bin\applytwin")) { Die "The download looks incomplete. Try again in a minute." }
  if (Test-Path "$Dir.old") { Remove-Item "$Dir.old" -Recurse -Force }
  if (Test-Path $Dir) { Rename-Item $Dir "$Dir.old" }
  Move-Item $top.FullName $Dir
  if (Test-Path "$Dir.old") { Remove-Item "$Dir.old" -Recurse -Force }
  if ($Sha) { Set-Content "$Dir\INSTALLED" $Sha -NoNewline }   # lets the app update itself from here on
} finally { Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue }
Ok "ApplyTwin in $Dir"

# an `applytwin` command, on PATH for new terminals
Set-Content "$Dir\applytwin.cmd" "@`"$Py`" `"%~dp0bin\applytwin`" %*" -Encoding ASCII
$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
if (($userPath -split ';') -notcontains $Dir) { [Environment]::SetEnvironmentVariable('Path', "$userPath;$Dir", 'User') }
$env:Path = "$env:Path;$Dir"
& $Py -m pip install --quiet --user pypdf 2>$null   # optional: lets the ATS check read PDFs

Write-Host "`nConnecting your agents" -ForegroundColor White
& $Py "$Dir\bin\applytwin" install-agents
Write-Host "`nChecking your setup" -ForegroundColor White
& $Py "$Dir\bin\applytwin" doctor
$global:LASTEXITCODE = 0   # doctor reports missing steps with a non-zero code; that's advice, not a failed install
Write-Host "`n* Free for every student. If it helps you, star it: https://github.com/OjasMishra32/applytwin" -ForegroundColor Yellow
Write-Host "`nOpening ApplyTwin at http://localhost:4747  (Ctrl+C to stop, 'applytwin app' to open it again)" -ForegroundColor White
if ($env:APPLYTWIN_NO_APP) { return }
if ($env:APPLYTWIN_NO_OPEN) { & $Py "$Dir\bin\applytwin" app --no-open } else { & $Py "$Dir\bin\applytwin" app }
}
