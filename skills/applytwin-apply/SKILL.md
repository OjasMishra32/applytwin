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
3. Make sure you have a browser tool. Work in your own tab or window, never in the user's existing tabs.

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
   `applytwin_answer_questions([{question, options}])`. Results with `action: "write"` are open-ended questions
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
     log "Needs User", leave the tab open, and move on.
9. **Only-the-user steps** (sign-in, password, account creation, CAPTCHA, arbitration, assessments, essays over ~250 words,
   a required fact the vault doesn't have such as a date of birth or a recommender's name): `applytwin_notify(...)` with
   exactly what is needed and the URL, log "Needs User" with notes naming the exact blocker ("Workday sign-in required at
   <url>", "hCaptcha on submit", "required: date of birth"), keep the tab, continue. Never type a password or solve a
   CAPTCHA, and never fill such a fact with a guess or another answer.
10. **Coming back**: at the end of the run (and whenever the user says they handled something) call `applytwin_pending_jobs`
   and finish each one that is now unblocked, then `applytwin_log_application(..., "Applied")`.

## Between jobs
- Respect pacing in the general playbook (Greenhouse spacing, company caps).
- Every ~5 jobs, give the user a 1-line progress update.
- At the end: a short table of applied / ready for you / needs you / skipped, with links.

## Never
Type passwords. Type emailed codes unless the user turned on `email_codes: agent`. Solve CAPTCHAs. Create accounts. Invent experience, numbers, skills or
availability. Accept legal agreements for the user. Apply to a company on the skip list.
