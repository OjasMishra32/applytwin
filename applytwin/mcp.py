"""MCP server (stdio, JSON-RPC 2.0, no dependencies). Gives Claude Code / Codex the tools to run the whole pipeline:
find jobs, read them, tailor a resume, answer questions, pull the per-ATS playbook, claim and log applications.
The agent does the browser part with its own computer-use / browser tools.
"""
import json
import os
import sys
import traceback

from . import api, store

S = lambda **props: {"type": "object", "properties": props}
STR, NUM, BOOL = {"type": "string"}, {"type": "number"}, {"type": "boolean"}

def _browser_soon():
    """An apply session starts with next_jobs: open the twin's window now, so the browser tool connects to it."""
    import threading
    threading.Thread(target=lambda: __import__('applytwin.twin', fromlist=['ensure']).ensure(), daemon=True).start()


TOOLS = [
    ("applytwin_setup_status", "Onboarding checklist: what the user still needs to set up (profile, vault, search prefs, Chrome).", S(), lambda a: api.setup_status()),
    ("applytwin_get_profile", "The user's profile: contact, school, grad date, work authorization, EEO answers, search filters, apply policy (auto_submit, daily_limit, per_company_cap, stop_on).", S(), lambda a: api.get_profile()),
    ("applytwin_update_profile", "Deep-merge a patch into the profile, e.g. {\"search\": {\"roles\": [\"software engineer\"]}}.", S(patch={"type": "object"}), lambda a: api.update_profile(a.get('patch', {}))),
    ("applytwin_get_vault", "The Career Vault: every experience, project, bullet, skill and award the user has (more than fits on one page). Entries have ids; bullet n of entry X is 'X.n'.", S(), lambda a: api.get_vault()),
    ("applytwin_save_vault", "Replace the whole Career Vault (JSON Resume-like: basics, education, experience[{org,title,location,start,end,url,bullets[]}], projects[{name,tagline,tech[],date,url,bullets[]}], research[{title,venue,url,role}], leadership[], skills[{label,items[]}], awards[], order[]). Use after structuring a brain dump. Never invent facts.", S(vault={"type": "object"}), lambda a: api.save_vault(a['vault'])),
    ("applytwin_get_dump", "The raw brain dump text the user pasted (old resumes, LinkedIn export, notes) that still needs structuring into the vault.", S(), lambda a: {"text": api.get_dump()}),
    ("applytwin_scan_jobs", "Scrape every enabled source (SimplifyJobs lists, SmartRecruiters live feed, ~500 Greenhouse/Lever/Ashby/Workday boards) and score fit. Takes 1-3 minutes.", S(sources={"type": "array", "items": STR}), lambda a: api.scan(a.get('sources'))),
    ("applytwin_list_jobs", "Search found jobs. status: new|applied|skipped|all. order: fit|new.", S(query=STR, status=STR, min_fit=NUM, limit=NUM, order=STR), lambda a: api.list_jobs(a.get('query', ''), a.get('status', 'new'), a.get('min_fit'), a.get('limit', 50), None, a.get('order', 'fit'))),
    ("applytwin_queue", "The full apply queue: every open role that fits the user, dream companies first, then by fit (respects caps and skip list). Returns total, dream count and the first n jobs.", S(n=NUM), lambda a: api.queue(int(a.get('n', 50)), for_agent=True)),
    ("applytwin_import_resume", "Import a resume or any career text into the vault (parses sections, entries and bullets; merges with what's there). Pass text, or name + base64 data for a PDF/DOCX/TEX file.", S(text=STR, name=STR, data=STR), lambda a: api.import_resume(a.get('name', ''), a.get('data'), a.get('text'))),
    ("applytwin_next_jobs", "The apply queue: best unapplied matches, respecting the daily limit and per-company caps. Start every apply session here. Already filtered: homepage-only links, clear title/location knockouts, page errors waiting for their retry, and jobs on a site waiting for the user's sign-in (listed in waiting_on_you: don't open those). Ordered so Greenhouse submits are spaced out. stop:true = end the run.", S(n=NUM), lambda a: (_browser_soon(), api.next_jobs(int(a.get('n', 10))))[1]),
    ("applytwin_get_job", "Full job record including the description (fetched on demand), plus knockouts (hard requirements in the posting that rule the user out, e.g. a graduation window: log Skipped with that exact reason) and already_applied (earlier applications to the same role at this company: never submit twice). resume_from = this application stopped earlier: continue where it stopped. site_waiting / link_warning explain site-level issues.", S(job_id=STR), lambda a: api.job_for_agent(a['job_id'])),
    ("applytwin_import_applied", "Record jobs the user ALREADY applied to outside ApplyTwin (found in their confirmation emails, a tracker, or told to you), so they are never applied to again, even if they appear in a later scan. items: [{company, title, url?, date?, status?}]. Only record what you actually saw.",
     {"type": "object", "properties": {"items": {"type": "array", "items": {"type": "object", "properties": {"company": STR, "title": STR, "url": STR, "date": STR, "status": STR}, "required": ["company", "title"]}}, "source": STR}, "required": ["items"]},
     lambda a: api.import_applied(a.get('items') or [], a.get('source') or 'email')),
    ("applytwin_add_job", "Track a job by URL (and optional pasted description) that the scrapers did not find.", S(url=STR, title=STR, company=STR, description=STR), lambda a: api.add_job(a['url'], a.get('title', ''), a.get('company', ''), a.get('description', ''))),
    ("applytwin_job_questions", "Greenhouse only: the application's questions with suggested answers from the bank, before opening the form.", S(job_id=STR), lambda a: api.job_questions(a['job_id'])),
    ("applytwin_ats_report", "ATS report: posting keyword coverage (matched/missing hard skills) + resume lint. Pass job_id or jd_text; omit both to lint the vault.", S(job_id=STR, jd_text=STR), lambda a: api.ats_report(a.get('job_id'), a.get('jd_text'))),
    ("applytwin_tailor_prompt", "The tailoring prompt for a job (vault + posting + rules). Only for writing a custom plan when the user asked for a specific change; normally call applytwin_tailor_apply(job_id) with no plan instead.", S(job_id=STR), lambda a: api.tailor_prompt(a['job_id'])),
    ("applytwin_tailor_apply", "The tailored one-page resume PDF for a job. Call it with NO plan: a dedicated writer (focused AI plan, honesty check, one-page fit) builds it, started when you claimed the job, so it is usually ready by the time you reach the upload field. Pass a plan only for a change the user asked for. Returns pdf path, ATS coverage, positioning.", S(job_id=STR, plan={"type": "object"}, template=STR), lambda a: api.tailor_apply(a['job_id'], a.get('plan'), a.get('template'), 'agent' if a.get('plan') else 'auto')),
    ("applytwin_render_resume", "Render the master (untailored) resume or a quick heuristic tailor (job_id) in a template: classic, harvard, modern, banking, finance, minimal, compact, accent.", S(template=STR, job_id=STR), lambda a: api.render_resume(a.get('template'), a.get('job_id'))),
    ("applytwin_templates", "List resume templates and what each is best for.", S(), lambda a: api.templates()),
    ("applytwin_answer_questions", "Answer application questions from the user's bank. questions: strings or {question, options[]}; ALWAYS pass job_id (company-specific questions like 'Have you worked for / applied to X?' are answered from the vault and history) and the options of every dropdown/radio (the right option is picked; school/major/degree never fall to a different specific option). action:'write' = write it yourself for this job; action:'knockout' = the form's own options rule the user out (log Skipped with skip_reason); formats = the date in MM/YYYY, YYYY-MM etc. Null answers: ask the user, then applytwin_save_answer.", S(questions={"type": "array"}, job_id=STR), lambda a: api.answer_questions(a.get('questions', []), a.get('job_id'))),
    ("applytwin_save_answer", "Save a new or corrected answer so the user is never asked again.", S(question=STR, answer=STR, key=STR), lambda a: api.save_answer(a['question'], a['answer'], a.get('key'))),
    ("applytwin_playbook", "Step-by-step fill guide and gotchas for an ATS: greenhouse, lever, ashby, workday, smartrecruiters, icims, oracle, jobvite, workable, linkedin, general.", S(ats=STR), lambda a: {"playbook": api.playbook(a.get('ats', 'general'))}),
    ("applytwin_claim", "Atomically claim a job before applying so parallel agents never double-apply. Returns claimed:false (with the reason) if taken, already applied, or past the daily limit / company cap.", S(job_id=STR), lambda a: api.claim(a['job_id'], who=os.environ.get('APPLYTWIN_RUN_ID', 'agent'))),
    ("applytwin_log_application", "Record what happened: right after submitting (Applied | Needs User | Skipped | Failed), and later when the user hears back (Interview | Offer | Rejected). For Needs User / Skipped / Failed, notes must say exactly why, starting with the blocker ('sign-in required at <url>', 'emailed code at <url>', 'hCaptcha on submit', 'required question: <text>', 'closed: page does not exist'). ApplyTwin files closed postings, homepage links and duplicates as Skipped itself; a browser-tool failure or a page error goes back to the queue (requeued:true, nothing logged) and stop:true means end the run. Outcomes teach ApplyTwin what works for this user. For a job not in ApplyTwin's list, also pass company and title.", S(job_id=STR, status=STR, notes=STR, resume_path=STR, company=STR, title=STR), lambda a: api.log_application(a['job_id'], a.get('status', 'Applied'), a.get('notes', ''), a.get('resume_path', ''), agent=True, company=a.get('company', ''), title=a.get('title', ''))),
    ("applytwin_vault_backups", "Saved earlier versions of the user's Career Vault (one is kept before every change), newest first, with how many roles/projects each has.", S(), lambda a: api.vault_backups()),
    ("applytwin_restore_vault", "Put a saved version of the Career Vault back: the newest one with content, or the backup file named. Use when the user's resume was lost or wrongly changed.", S(file=STR), lambda a: api.restore_vault(a.get('file'))),
    ("applytwin_remember", "Learn a lasting preference from the user and apply it to every future resume: note (free text like 'keep it formal' or 'never mention my GPA'), pin (entry id or bullet id 'x.n' to always include), avoid (id to never include), or field+template (preferred template for a field).", S(note=STR, pin=STR, avoid=STR, field=STR, template=STR), lambda a: api.remember(a.get('note'), a.get('pin'), a.get('avoid'), a.get('field'), a.get('template'))),
    ("applytwin_forget", "Remove a stored preference (note, pin or avoid).", S(note=STR, pin=STR, avoid=STR), lambda a: api.forget(a.get('note'), a.get('pin'), a.get('avoid'))),
    ("applytwin_insights", "What ApplyTwin has learned about this user: stored preferences, interview rate by field and template, bullets that won interviews. Log outcomes (Interview, Offer, Rejected) with applytwin_log_application to feed it.", S(), lambda a: api.insights()),
    ("applytwin_fill_password", "On a sign-in or create-account page in the twin's browser: ApplyTwin types the user's saved password into every password box on that page (and its confirm box). You never see or type the password. Only works when the user turned on signing in for them; otherwise the result says to notify the user. Returns filled (how many boxes) and the email to use.", S(url=STR), lambda a: api.fill_password(a.get('url', ''))),
    ("applytwin_open_browser", "Make sure the twin's browser window is open (ApplyTwin keeps one Chrome window open between runs, with the user's sign-ins). Call before your first browser action if the browser tool can't connect.", S(), lambda a: {"open": __import__('applytwin.twin', fromlist=['ensure']).ensure()}),
    ("applytwin_notify", "Tell the user something needs them RIGHT NOW (emailed code, sign-in, CAPTCHA, a question only they can answer). Sends a desktop notification and adds it to their in-app inbox; a second item for the same site and blocker is grouped with the first (batched:true, no second alert). Then log Needs User and move on to the next job.", S(title=STR, message=STR, url=STR, job_id=STR, kind=STR), lambda a: api.notify(a.get('title', 'Needs you'), a.get('message', ''), a.get('url', ''), a.get('job_id', ''), a.get('kind', 'needs_you'))),
    ("applytwin_reply", "Answer the user about ONE application (they wrote to you about it in the app). One or two plain sentences: what you did, and what they still need to do. Shown under that application in Needs you.", S(job_id=STR, text=STR), lambda a: api.reply(a['job_id'], a['text'])),
    ("applytwin_needs_you", "Everything waiting on the user, batched: grouped by blocker and site (one sign-in per site unblocks all of its applications; one Answers-page visit covers every question), biggest group first, each with the one action to take. Call at the end of a run and tell the user group by group.", S(), lambda a: api.needs_you()),
    ("applytwin_inbox", "Open items waiting on the user (and whether they were resolved).", S(), lambda a: api.inbox()),
    ("applytwin_pending_jobs", "Jobs you stopped on for the user that are not finished. Check at the end of a run and finish the ones the user has unblocked (e.g. they signed in).", S(), lambda a: api.pending_jobs()),
    ("applytwin_stats", "Counts: matched jobs, applied today / this week, statuses.", S(), lambda a: api.stats()),
]
BY = {t[0]: t for t in TOOLS}


def reply(i, result=None, error=None):
    msg = {"jsonrpc": "2.0", "id": i}
    msg.update({"error": error} if error else {"result": result})
    sys.stdout.write(json.dumps(msg, default=str) + '\n')
    sys.stdout.flush()


STEPS = {'claim': 'Opening the posting', 'get_job': 'Opening the posting', 'tailor_prompt': 'Tailoring your resume',
         'tailor_apply': 'Tailoring your resume', 'render_resume': 'Tailoring your resume', 'ats_report': 'Checking your resume',
         'playbook': 'Filling the application', 'answer_questions': 'Filling the application', 'job_questions': 'Filling the application',
         'save_answer': 'Filling the application', 'notify': 'Asking you something', 'log_application': 'Logging it',
         'next_jobs': 'Picking the next job', 'queue': 'Picking the next job', 'pending_jobs': 'Picking the next job',
         'needs_you': 'Picking the next job'}


def _activity(name, args):
    """What the agent is doing right now, for the Autopilot page (and the stuck-run timer)."""
    try:
        import time
        step = STEPS.get((name or '').replace('applytwin_', ''))
        cur = store.load('activity.json', {}) or {}
        if not step:   # any other tool call still shows the twin is working (so the stuck timer never fires on it)
            store.save('activity.json', {**cur, "at": time.time()})
            return
        job = args.get('job_id') or (cur.get('job_id') if step not in ('Picking the next job',) else '')
        store.save('activity.json', {"step": step, "job_id": job or '', "at": time.time()})
    except Exception:
        pass


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except ValueError:
            continue
        m, i = req.get('method'), req.get('id')
        if i is None:
            continue  # notification
        if m == 'initialize':
            reply(i, {"protocolVersion": req.get('params', {}).get('protocolVersion', '2025-06-18'),
                      "capabilities": {"tools": {}}, "serverInfo": {"name": "applytwin", "version": "0.1.0"},
                      "instructions": "ApplyTwin runs the user's job search. Start with applytwin_setup_status. To apply: applytwin_next_jobs -> "
                                      "applytwin_claim -> applytwin_get_job (log Skipped with the exact reason if it lists knockouts such as a "
                                      "graduation window, or already_applied) -> applytwin_tailor_apply(job_id, no plan) -> applytwin_playbook(ats) -> "
                                      "fill the form in the browser using applytwin_answer_questions -> submit only if profile.apply.auto_submit "
                                      "-> applytwin_log_application. Never type passwords, solve CAPTCHAs, create accounts or invent facts."})
        elif m == 'ping':
            reply(i, {})
        elif m == 'tools/list':
            reply(i, {"tools": [{"name": n, "description": d, "inputSchema": s} for n, d, s, _ in TOOLS]})
        elif m == 'tools/call':
            p = req.get('params', {})
            t = BY.get(p.get('name'))
            if not t:
                reply(i, error={"code": -32602, "message": "unknown tool"})
                continue
            try:
                _activity(p.get('name'), p.get('arguments') or {})
                out = t[3](p.get('arguments') or {})
                reply(i, {"content": [{"type": "text", "text": json.dumps(out, default=str, ensure_ascii=False)[:180000]}]})
            except Exception as e:
                reply(i, {"content": [{"type": "text", "text": f"error: {e}\n{traceback.format_exc()[-800:]}"}], "isError": True})
        else:
            reply(i, error={"code": -32601, "message": f"method not found: {m}"})


if __name__ == '__main__':
    main()
