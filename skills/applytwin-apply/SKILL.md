---
name: applytwin-apply
description: "Apply to jobs or internships for the user with ApplyTwin, end to end, in their browser. Use for 'twin: apply to my top N', 'apply to job <id>', 'apply to everything new at <company>', or running the job-application loop. Needs a browser the agent can drive (Claude in Chrome, computer use, or Codex browser/computer use)."
---

# ApplyTwin apply loop

You are the hands; ApplyTwin is the memory. ApplyTwin's MCP tools hold the user's vault, answers, job queue and history.
You drive the browser. Quality over speed: every application should be as good as one the user would do
themselves on a careful day.

## Setup (once per session)
1. `applytwin_get_profile`: note `apply.auto_submit`, `daily_limit`, `per_company_cap`, `stop_on`.
2. `applytwin_playbook("general")` and follow it. Keep it in mind for every job.
3. Use the twin's browser: the Playwright tools (`browser_navigate`, ...) ApplyTwin registered, on a profile that keeps the
   user's sign-ins. In an unattended Autopilot run never use Claude in Chrome, computer use or a built-in Chrome tool (they
   wait for approvals nobody gives); if one of those fails, switch to the Playwright tools. Make sure it works: open about:blank in your own tab or window (never the user's existing tabs). If the
   browser tool doesn't work, `applytwin_notify` once with the error and stop. Never log jobs as blocked because of your
   own browser: ApplyTwin puts such jobs back in the queue and tells you to stop after two.

## For each job
1. **Pick**: `applytwin_next_jobs(n)` (or the job the user named) -> `applytwin_claim(job_id)`. Skip if not claimed.
2. **Read**: `applytwin_get_job(job_id)`. Check knockouts against the profile: graduation window, work
   authorization/sponsorship, degree level, location, citizenship/clearance. The result's `knockouts` lists the ones
   ApplyTwin found in the description (e.g. "Graduation window Dec 2027 - Aug 2028; you graduate May 2029"); read the
   posting too, since windows are phrased many ways. If the user clearly doesn't qualify,
   `applytwin_log_application(job_id, "Skipped", "<that exact reason>")` and move on. If `already_applied` is not
   empty, this role was already submitted: log Skipped "duplicate: ..." and never submit it again.
3. **Tailor** (if `apply.tailor_every_resume`):
   - `applytwin_tailor_apply(job_id)` with NO plan. A dedicated writer builds the resume (focused plan, honesty
     check, one-page fit); it started when you claimed the job, so do steps 4-5 first and call this when you reach the
     upload field. It returns `pdf` and `tex`. Use the returned `pdf`.
   - Write your own plan (`applytwin_tailor_prompt` then `applytwin_tailor_apply(job_id, plan)`) only when the user
     asked for a specific change to this resume.
4. **Prepare answers**: Greenhouse: `applytwin_job_questions(job_id)`. Others: read the form's questions, then
   `applytwin_answer_questions([{question, options}], job_id)` (always the job_id, and the options of every dropdown or
   radio). `action: "knockout"` = the form's own options rule the user out (e.g. graduation years that stop before
   theirs): log Skipped with `skip_reason`. `formats` gives a date as MM/YYYY, YYYY-MM, etc. Results with `action: "write"` are open-ended questions
   (why this company, what interested you, anything else): write them yourself following `how`, never ask the user and
   never leave them blank. Anything else returned null is a fact only the user knows: collect those, ask the user ONCE
   for all of them (batch across jobs when you can), then `applytwin_save_answer` each.
5. **Fill**: open `apply_url`, `applytwin_playbook(<job.ats>)`, and fill every field. Upload the tailored PDF.
   Write every open-ended answer (required or optional) from the vault + posting, following the `how` rules from step 4.
6. **Verify**: read back every field value; fix anything empty or wrong (selects especially: pick options by
   clicking, never by keyboard on Workday, and check the shown text). Right before Submit, make sure the site doesn't
   say "already applied" (Ashby, Workday and iCIMS reject duplicates): if it does, log Skipped "duplicate: ...".
7. **Submit or hand off**:
   - `auto_submit` true: submit once, confirm the success page, `applytwin_log_application(job_id, "Applied",
     "<1-line note>", pdf)`.
   - `auto_submit` false: leave the tab on the review screen, log "Needs User" with "ready to submit", and
     tell the user which tabs are ready.
8. **Emailed verification codes** (Greenhouse and others send one after many submits):
   - `profile.apply.email_codes == "agent"`: the user has allowed you to read their email for codes. Use your email tool
     (Gmail connector, or their already-signed-in webmail in the browser), open the newest message from that company/ATS in
     the last 15 minutes, read the code, type it. Never forward, store or show codes anywhere else.
   - otherwise: `applytwin_notify(title="Code needed for <company>", message="Check your email and type it in the open tab", url, job_id)`,
     log "Needs User", leave the tab open, and move on. Tabs close when the run ends, so the note you write must never
     promise an open tab: say what the user does (answer <question> in ApplyTwin, sign in at <site>); pressing Finish
     in ApplyTwin refills the application from where it stopped.
9. **Only-the-user steps** (sign-in, password, account creation, CAPTCHA, arbitration, assessments, essays over ~250 words,
   a required fact the vault doesn't have such as a date of birth or a recommender's name): `applytwin_notify(...)` with
   exactly what is needed and the URL, log "Needs User" with notes naming the exact blocker ("Workday sign-in required at
   <url>", "hCaptcha on submit", "required: date of birth"), keep the tab, continue. Fill everything else first: on a
   no-account form fill the whole form; where an account is needed, leave the tab on the sign-in / create-account page.
   A second item for the same site is grouped with the first (`batched: true`), so report each blocker plainly. Never type a password or solve a
   CAPTCHA, and never fill such a fact with a guess or another answer.
10. **Coming back**: at the end of the run call `applytwin_needs_you` and give the user the grouped list (one sign-in per
   site unblocks all of its jobs). Whenever the user says they handled something, call `applytwin_pending_jobs` and finish
   each one that is now unblocked: `applytwin_get_job` shows `resume_from`, so continue where it stopped (reuse the open tab,
   keep what is filled), then `applytwin_log_application(..., "Applied")`.

## What ApplyTwin sorts out for you
- `applytwin_next_jobs` never hands you homepage-only links, clear title/location knockouts, jobs waiting for a page-error
  retry, or jobs on a site that is waiting for the user's sign-in (`waiting_on_you`).
- Logging Needs User for a closed posting, a homepage link or a duplicate files it as Skipped. A page error or timeout
  (not on the submit step) goes back to the queue once (`requeued: true`). `stop: true` in any result = end the run.

## Between jobs
- Respect pacing in the general playbook (Greenhouse spacing, company caps).
- Every ~5 jobs, give the user a 1-line progress update.
- At the end: a short table of applied / ready for you / needs you / skipped, with links.

## Never
Type passwords. Type emailed codes unless the user turned on `email_codes: agent`. Solve CAPTCHAs. Create accounts. Invent experience, numbers, skills or
availability. Accept legal agreements for the user. Apply to a company on the skip list.
