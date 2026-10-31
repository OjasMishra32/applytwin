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
# Windows PowerShell 5.1 turns anything a program prints to stderr (even a warning) into a stopping error while
# ErrorActionPreference is Stop, so external programs run through this, with their own exit code deciding success.
function Run {   # no param() block on purpose: every argument (even '-c' or '-m') goes to the program untouched
  $prev = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
  # Python writes UTF-8 and PowerShell reads it as UTF-8 for the call (else a path like C:\Users\José comes back garbled,
  # so Python is "not found", and checkmarks print as junk); both are put back afterwards, leaving the user's window as it was
  $pyEnc = $env:PYTHONIOENCODING; $env:PYTHONIOENCODING = 'utf-8'
  $conEnc = $null; try { $conEnc = [Console]::OutputEncoding; [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false } catch {}
  try { $exe = $args[0]; $rest = @($args | Select-Object -Skip 1); & $exe @rest 2>&1 | ForEach-Object { "$_" } }
  finally {
    $ErrorActionPreference = $prev; $env:PYTHONIOENCODING = $pyEnc
    if ($conEnc) { try { [Console]::OutputEncoding = $conEnc } catch {} }
  }
}
function Die($m) { Write-Host "  x $m" -ForegroundColor Red; throw "ApplyTwin install stopped: $m" }

Write-Host "Installing ApplyTwin" -ForegroundColor White
# older Windows PowerShell can default to TLS 1.0, which GitHub refuses
try { [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12 } catch {}
# a window keeps the PATH it was opened with: pick up Python / Node.js installed since (winget, python.org)
foreach ($p in (@([Environment]::GetEnvironmentVariable('Path', 'Machine'), [Environment]::GetEnvironmentVariable('Path', 'User')) -join ';') -split ';') {
  if ($p -and (($env:Path -split ';') -notcontains $p)) { $env:Path = "$env:Path;$p" }
}

# A real Python 3.9+ (the Microsoft Store placeholder only opens the Store, so test each candidate), also one installed
# without "Add python.exe to PATH" ticked
$cands = @(@('py', '-3'), @('python'), @('python3'))
foreach ($g in @("$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe", "$env:ProgramFiles\Python3*\python.exe")) {
  foreach ($f in @(Get-ChildItem $g -ErrorAction SilentlyContinue | Sort-Object FullName -Descending)) { $cands += , @($f.FullName) }
}
$Py = $null
foreach ($c in $cands) {
  try {
    $argv = @($c) + @('-c', "import sys; print(sys.executable if sys.version_info >= (3, 9) else '')")
    $exe = Run @argv | Select-Object -Last 1
    if ($LASTEXITCODE -eq 0 -and $exe -and (Test-Path -LiteralPath $exe.Trim())) { $Py = $exe.Trim(); break }
  } catch {}
}
if (-not $Py) { Die "ApplyTwin needs Python 3.9+. Install it with:  winget install Python.Python.3.12   (no winget? get it from https://www.python.org/downloads/ ), then run this again." }
Ok "Python ($Py)"
if (Get-Command npx -ErrorAction SilentlyContinue) { Ok "Node.js $(node -v)" } else { Warn "Node.js not found. Your twin needs it to drive a browser:  winget install OpenJS.NodeJS.LTS   (or https://nodejs.org)" }
$have = $false
if (Get-Command claude -ErrorAction SilentlyContinue) { Ok "Claude Code found"; $have = $true }
if (Get-Command codex -ErrorAction SilentlyContinue) { Ok "Codex found"; $have = $true }
if (-not $have) {
  Warn "Neither Claude Code nor Codex is installed. Install one (any paid plan works, no API key):"
  Write-Host "      npm install -g @anthropic-ai/claude-code     # then run: claude   and type /login"
  Write-Host "      npm install -g @openai/codex                 # then run: codex login"
}
# npm's commands are .ps1 scripts in PowerShell, which this PC's script policy blocks ("running scripts is disabled")
if (@('Restricted', 'AllSigned') -contains [string](Get-ExecutionPolicy)) {
  Warn "PowerShell here blocks npm's commands. Type claude.cmd / codex.cmd / npm.cmd instead (or use Command Prompt)."
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

# unpack next to the install folder (same drive), so moving it into place can't fail halfway across drives
$parent = Split-Path $Dir -Parent
if (-not (Test-Path $parent)) { New-Item -ItemType Directory $parent | Out-Null }
$tmp = Join-Path $parent (".applytwin-install-" + [guid]::NewGuid())
New-Item -ItemType Directory $tmp | Out-Null
try {
  if (-not $Sha -and (Get-Command tar.exe -ErrorAction SilentlyContinue)) {
    # GitHub couldn't be asked for the newest tested version (rate limit): use the copy published on the site, not untested main
    Invoke-WebRequest "https://apply.twinly.tech/applytwin.tar.gz" -OutFile "$tmp\a.tgz" -UseBasicParsing
    New-Item -ItemType Directory "$tmp\x" | Out-Null
    tar.exe -xzf "$tmp\a.tgz" -C "$tmp\x"
  } else {
    Invoke-WebRequest "https://codeload.github.com/$Repo/zip/$Ref" -OutFile "$tmp\a.zip" -UseBasicParsing
    Expand-Archive "$tmp\a.zip" "$tmp\x"
  }
  $top = Get-ChildItem "$tmp\x" -Directory | Select-Object -First 1
  if (-not (Test-Path "$($top.FullName)\bin\applytwin")) { Die "The download looks incomplete. Try again in a minute." }
  # a file antivirus or a running copy still holds can block deleting the last old copy: set it aside instead
  if (Test-Path "$Dir.old") { Remove-Item "$Dir.old" -Recurse -Force -ErrorAction SilentlyContinue }
  if (Test-Path "$Dir.old") { Rename-Item "$Dir.old" ((Split-Path $Dir -Leaf) + ".old-" + [guid]::NewGuid()) }
  if (Test-Path $Dir) {
    try { Rename-Item $Dir "$Dir.old" }
    catch {
      # Windows won't rename a folder the running app is working in: stop the app (it starts again below) and retry
      Get-CimInstance Win32_Process -Filter "Name='pythonw.exe' or Name='python.exe'" -ErrorAction SilentlyContinue | Where-Object {
        $_.CommandLine -and ($_.CommandLine.Contains("$Dir\bin\applytwin") -or $_.CommandLine -match '-m applytwin') -and $_.CommandLine -match 'applytwin"?\s+app(\s|$)'
      } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
      Start-Sleep 2
      Rename-Item $Dir "$Dir.old"
    }
  }
  # antivirus scans the files just unpacked and holds them for a moment ("access denied"): wait it out
  for ($i = 0; ; $i++) { try { Move-Item $top.FullName $Dir; break } catch { if ($i -ge 10) { throw }; Start-Sleep 1 } }
  if (Test-Path "$Dir.old") { Remove-Item "$Dir.old" -Recurse -Force -ErrorAction SilentlyContinue }
  if ($Sha) { Set-Content "$Dir\INSTALLED" $Sha -NoNewline }   # lets the app update itself from here on
} finally {
  if (-not (Test-Path $Dir) -and (Test-Path "$Dir.old")) { Rename-Item "$Dir.old" $Dir }   # never leave you without the app
  Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
}
Ok "ApplyTwin in $Dir"

# an `applytwin` command, on PATH for new terminals
# the short (8.3) path keeps it working for usernames with accents (José), which an ASCII .cmd file can't hold
$PyCmd = $Py
try { $s = (New-Object -ComObject Scripting.FileSystemObject).GetFile($Py).ShortPath; if ($s) { $PyCmd = $s } } catch {}
if ($PyCmd -match '[^\x00-\x7F]') {   # this drive has no short names: let cmd fill in the user folder itself when it runs
  foreach ($v in @('LOCALAPPDATA', 'APPDATA', 'USERPROFILE')) {
    $b = [Environment]::GetEnvironmentVariable($v)
    if ($b -and $Py.StartsWith($b.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase) -and $Py.Substring($b.TrimEnd('\').Length) -notmatch '[^\x00-\x7F]') {
      $PyCmd = "%$v%" + $Py.Substring($b.TrimEnd('\').Length); break
    }
  }
}
Set-Content "$Dir\applytwin.cmd" "@`"$PyCmd`" `"%~dp0bin\applytwin`" %*" -Encoding ASCII
# add to the user PATH without expanding entries like %NVM_SYMLINK% (SetEnvironmentVariable would freeze them)
$envKey = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey('Environment', $true)
$rawPath = [string]$envKey.GetValue('Path', '', [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
if (($rawPath -split ';') -notcontains $Dir) {
  $envKey.SetValue('Path', ($(if ($rawPath) { "$rawPath;$Dir" } else { $Dir })), [Microsoft.Win32.RegistryValueKind]::ExpandString)
  [Environment]::SetEnvironmentVariable('APPLYTWIN_PATH_REFRESH', '1', 'User')   # tells Windows the environment changed
  [Environment]::SetEnvironmentVariable('APPLYTWIN_PATH_REFRESH', $null, 'User')
}
$envKey.Close()
$env:Path = "$env:Path;$Dir"
Run $Py -m pip install --quiet --user pypdf | Out-Null   # optional: lets the ATS check read PDFs; never stops the install

Write-Host "`nConnecting your agents" -ForegroundColor White
Run $Py "$Dir\bin\applytwin" install-agents | Write-Host
Write-Host "`nChecking your setup" -ForegroundColor White
Run $Py "$Dir\bin\applytwin" doctor | Write-Host
$global:LASTEXITCODE = 0   # doctor reports missing steps with a non-zero code; that's advice, not a failed install
Write-Host "`n* Free for every student. If it helps you, star it: https://github.com/OjasMishra32/applytwin" -ForegroundColor Yellow
if ($env:APPLYTWIN_NO_APP) { return }

# Run like a normal app: start quietly at login (so localhost:4747 always works and daily scans happen), a Start menu entry
$Pyw = Join-Path (Split-Path $Py) 'pythonw.exe'; if (-not (Test-Path $Pyw)) { $Pyw = $Py }
$sh = New-Object -ComObject WScript.Shell
$startup = Join-Path ([Environment]::GetFolderPath('Startup')) 'ApplyTwin.lnk'
# (working folder: the home folder, never the app folder, which Windows would then refuse to swap on the next update)
$lnk = $sh.CreateShortcut($startup); $lnk.TargetPath = $Pyw; $lnk.Arguments = "`"$Dir\bin\applytwin`" app --no-open"; $lnk.WorkingDirectory = $env:USERPROFILE; $lnk.WindowStyle = 7; $lnk.Save()
Ok "ApplyTwin starts by itself when you sign in"
# the Start menu entry starts the app if it isn't running (a plain link to the address just showed "can't connect"), then opens it
$programs = [Environment]::GetFolderPath('Programs')
Remove-Item (Join-Path $programs 'ApplyTwin.url') -ErrorAction SilentlyContinue   # the old link-only entry
$m = $sh.CreateShortcut((Join-Path $programs 'ApplyTwin.lnk')); $m.TargetPath = $Pyw; $m.Arguments = "`"$Dir\bin\applytwin`" app"
$m.WorkingDirectory = $env:USERPROFILE; $m.Description = 'Open ApplyTwin (http://localhost:4747)'; $m.Save()
Ok "ApplyTwin is in your Start menu"
Start-Process $Pyw -ArgumentList "`"$Dir\bin\applytwin`" app --no-open" -WorkingDirectory $env:USERPROFILE -WindowStyle Hidden
# open the page once the app answers (the first start can take longer than a few seconds), never onto "can't connect"
$up = $false
for ($i = 0; $i -lt 30 -and -not $up; $i++) {
  Start-Sleep 1
  try { Invoke-WebRequest 'http://127.0.0.1:4747/api/stats' -UseBasicParsing -TimeoutSec 2 | Out-Null; $up = $true } catch {}
}
Start-Process 'http://localhost:4747'
if (-not $up) { Warn "ApplyTwin is still starting. If the page says it can't connect, wait a minute and reload it." }
Write-Host ""
Write-Host "  ================================================================" -ForegroundColor Green
Write-Host "    ApplyTwin just opened in your web browser:  http://localhost:4747" -ForegroundColor Green
Write-Host "    Sign in THERE (continue with Google), add your resume, press Start." -ForegroundColor Green
Write-Host "  ================================================================" -ForegroundColor Green
Write-Host "  No new tab? Type  http://localhost:4747  into your browser's address bar."
Write-Host "  Open it any time: ApplyTwin in the Start menu, that address, or type: applytwin"
Write-Host "  You can close this window. (apply.twinly.tech only shows your results; the app is http://localhost:4747.)"
}
