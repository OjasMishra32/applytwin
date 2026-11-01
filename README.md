# ApplyTwin

ApplyTwin is a free app for your computer that finds internships, writes a one-page resume for each posting and fills out the application for you.

It runs on the Claude Code or Codex plan you already pay for. There are no API keys and no new subscription.

## Install

Mac or Linux, paste this into Terminal:

```bash
curl -fsSL apply.twinly.tech/install | bash
```

Windows, paste this into PowerShell:

```powershell
irm apply.twinly.tech/install.ps1 | iex
```

Before you run it you need Python 3.9 or newer, Node.js, and Claude Code or Codex. The installer checks for each one and tells you what is missing.

### What happens after you paste it

1. **It installs.** ApplyTwin goes into `~/.applytwin-app` (`%USERPROFILE%\.applytwin-app` on Windows), connects itself to Claude Code and Codex, and runs a setup check.
2. **The app opens in your browser at http://localhost:4747.** That page is ApplyTwin, running on your own computer.
3. **Sign in with Google there.** Your setup, answers and applications are saved to your account, so a new laptop picks up where you left off.
4. **Add your resume.** Drop in the one you have (PDF, Word, LaTeX or text) and answer the usual application questions once.
5. **Press Start** on the Autopilot page. It applies in its own browser window and pings you when it needs you.

> **The app is http://localhost:4747.** The website apply.twinly.tech is where you get the install line. Your account page at [apply.twinly.tech/app](https://apply.twinly.tech/app) shows the applications your app has synced, from any device. You sign in, add your resume and press Start on localhost:4747.

From then on ApplyTwin runs like a normal app. It starts by itself when you log in, so http://localhost:4747 always works. You can also open it from the ApplyTwin icon (Applications or Spotlight on Mac, the Start menu on Windows, your app menu on Linux) or by typing `applytwin` in a new terminal. Jobs refresh on their own and the app updates itself. To update by hand, run the install line again or `applytwin update`.

## How it works

**It finds jobs.** ApplyTwin reads the career sites of more than 600 companies (Greenhouse, Lever, Ashby, Workday and SmartRecruiters boards), plus the community internship trackers, The Muse, Hacker News "Who is hiring" and remote job boards. Each posting gets a fit score based on your roles, level, location, graduation date, sponsorship needs and how much of the posting your experience covers. Your dream companies go to the front of the queue.

**It tailors a resume for each posting.** You keep everything you have done in one place, the Career Vault. For each job, ApplyTwin picks your most relevant roles and bullets, orders them for that reader and fits them on one page. A fact check rejects any rewrite that adds a number, tool or claim the original entry doesn't have. Your numbers, titles, employers, degrees and awards stay exactly as you wrote them. There are 8 templates, all single column with real text, so applicant tracking systems can read them.

**It fills the application.** Your own Claude Code or Codex opens the form in a browser, follows ApplyTwin's playbook for that application system, answers from your saved answers and uploads the tailored PDF. Then it stops on the review screen so you press Submit. If you turn on "Submit applications on its own" in Settings, it submits for you.

**It remembers what you applied to.** The same role at the same company is never applied to twice. You can import a CSV of past applications from Simplify, Huntr, Teal, Notion or a Google Sheet.

**It asks you only when it has to.** New questions it hasn't seen before come to you once, and it saves your answer for next time.

## What it will never do

- Show your password to the AI
- Solve a CAPTCHA
- Accept a legal agreement
- Change a number, title, employer, degree or award on your resume

When it hits one of these, it stops and sends you a notification.

Signing in and creating job site accounts (Workday and the like) is off unless you turn it on in Settings, with an email
and a password just for job sites. ApplyTwin then types that password into the page itself, so the AI filling the form
never sees it, and it stays on your computer. Verification codes are read from your email only if you turn that on too.

## FAQ

**Do I need an API key?**
No. ApplyTwin runs on the Claude Code or Codex subscription you already have. If you can use either one in a terminal, you can use ApplyTwin.

**Is apply.twinly.tech the app?**
No. The app runs on your computer at http://localhost:4747. apply.twinly.tech is the website, and apply.twinly.tech/app shows your synced applications.

**Where does my data live?**
On your computer, in a folder called `~/.applytwin`. Signing in backs up your setup so a new laptop picks up where you left off.

**Will it submit applications without me?**
Only if you turn that on. Otherwise it fills every form and stops on the review screen, so you press Submit.

**Does it work on Windows?**
Yes. Mac, Windows and Linux. On Windows, paste the PowerShell command.

**Is it only for software jobs?**
No. It knows what a strong resume looks like in your field, from nursing and finance to design, research and engineering.

**Why do I sign in with Google?**
So your setup, answers and applications are saved to your account. ApplyTwin never posts, emails or signs up for anything as you.

**Does it track me?**
It counts installs with a random ID, your OS, the ApplyTwin version and which agent you use, once a day. Never your name, email, resume, jobs or applications. Turn it off in Settings (Count my install) or set `APPLYTWIN_NO_TELEMETRY=1`.

**What does it cost?**
Nothing. ApplyTwin is free.

## Troubleshooting

Start with the setup check. It lists anything that is missing and how to fix it:

```bash
applytwin doctor
```

**http://localhost:4747 doesn't open, or says it can't connect.**
The first start can take a minute, so wait and reload. If it still won't load, start it yourself with `applytwin app` (on Mac or Linux, open a new terminal first so the command is found). If port 4747 is taken, ApplyTwin uses the next free port and prints the address. You can also pick one: `applytwin app --port 5050`. On Mac and Windows the app's log is `server.log` in the `.applytwin` folder in your home folder.

**Claude Code or Codex isn't signed in.**
Open the Autopilot page in the app and press **Install and sign in**. It installs the agent if needed and opens Claude's or ChatGPT's own sign-in page. From a terminal instead:

```bash
npm install -g @anthropic-ai/claude-code   # then run: claude   and type /login
npm install -g @openai/codex               # then run: codex login
```

Any paid plan works. After signing in, run `applytwin install-agents` so ApplyTwin is connected to it.

**Windows says "running scripts is disabled on this system".**
That is PowerShell's script policy blocking npm's commands. Type `claude.cmd`, `codex.cmd` or `npm.cmd` instead of `claude`, `codex` or `npm`, or run them from Command Prompt. If you'd rather change the policy for your own user account, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

**Python is missing, or too old.**
ApplyTwin needs Python 3.9 or newer. On Mac or Linux, get it from https://www.python.org/downloads/. On Windows:

```powershell
winget install Python.Python.3.12
```

Then close the window, open a new one and paste the install line again.

**Node.js is missing.**
Your twin needs Node.js to drive a browser. Get the LTS version from https://nodejs.org (on Windows, `winget install OpenJS.NodeJS.LTS`).

**`applytwin: command not found`.**
Open a new terminal window. The installer adds the command to your PATH, and windows that were already open don't see it yet.

## Use it from Claude Code or Codex

ApplyTwin also works from a chat with your agent. Try:

- `set me up with applytwin`
- `twin: scan and show my top 20`
- `twin: tailor my resume for <job id or URL> and explain the choices`
- `twin: apply to my top 10`
- `twin: review my resume like a recruiter`

The agent needs a browser it can drive: Claude in Chrome or computer use for Claude Code, or the browser tools in Codex.

The command line works without any agent: `applytwin scan`, `applytwin jobs`, `applytwin tailor JOB_ID`, `applytwin ats JOB_ID`, `applytwin templates`, `applytwin watch --every 120`. Run `applytwin help` for the full list.

## Contributing

Bug reports and ideas are welcome in [Issues](https://github.com/OjasMishra32/applytwin/issues). If an application form trips it up, tell us the company and the application system (Workday, Greenhouse and so on).

To run it from a clone:

```bash
git clone https://github.com/OjasMishra32/applytwin.git
cd applytwin
./install.sh               # connects Claude Code and Codex, then opens http://localhost:4747
python3 tests/smoke.py     # tests
```

The Python side uses only the standard library. `applytwin/` holds the store, job sources, matching, tailoring, rendering, the local server and the MCP server. The app's interface is React in `ui/` and builds into `web/` with `cd ui && npm install && npm run build`; `npm run dev` serves it on port 5173 against a running app. Agent skills are in `skills/`, playbooks for each application system in `playbooks/`, and agent instructions in [AGENTS.md](AGENTS.md). Resume writing rules are in [docs/RESUME_GUIDE.md](docs/RESUME_GUIDE.md).

## License

Copyright (c) 2026 Ojasva Mishra. ApplyTwin is free to use under the [PolyForm Strict License 1.0.0](LICENSE). You may install and run it for any noncommercial purpose. You may not copy, modify, redistribute or sell it, or build other works from it. For any other use, ask first. Bundled third-party code (`applytwin/_vendor/pypdf`) stays under its own BSD license.

## If it helps you

ApplyTwin is free and has no ads. If it saved you some time, please [star the repo](https://github.com/OjasMishra32/applytwin). It's how other students find it.
