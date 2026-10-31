# Applying with ApplyTwin: the general loop (any ATS)

ApplyTwin learned these from 1,500+ real submissions. Follow them exactly; most failed applications come from a
value that *looks* filled but never registered with the page's framework.

## Before the form
1. `applytwin_next_jobs` -> pick one -> `applytwin_claim(job_id)`; if claimed:false, skip it (another agent has it).
2. `applytwin_get_job` and read the posting. Skip and `applytwin_log_application(status="Skipped", notes=<exact reason>)` if
   a hard requirement rules the user out (graduation window, citizenship/clearance when they lack it, degree level).
   `get_job` returns `knockouts` it found in the description; also read the posting yourself. **Graduation windows**
   ("graduating Dec 2027 - Aug 2028", "Class of 2028", "graduate by May 2028") are compared with the user's
   `grad_month`/`grad_year`; outside it = Skipped with notes like "graduation window Dec 2027 - Aug 2028; user
   graduates May 2029". `already_applied` not empty = never submit again (log Skipped "duplicate: ...").
3. Tailor: `applytwin_tailor_prompt` -> write the plan -> `applytwin_tailor_apply(job_id, plan)`. Use the returned PDF.
   If any rewrites were rejected by the fact guard, that's fine; the original bullet was used.
4. `applytwin_playbook(<ats>)` for this ATS's specifics.

## Filling
- **Upload the resume first** on ATSes that parse it (Workday, SmartRecruiters, Jobvite, Paylocity, Workable,
  Rippling): parsing fills fields a few seconds later and can wipe or duplicate what you typed. Wait for the
  parse, then fix fields. On Greenhouse upload LAST (it steals keyboard focus).
- **Real input beats JS.** Many React forms ignore values set by script. Click the field (or focus it), select
  all, type, press Tab. Then read the value back with JS before moving on.
- **Keystrokes only reach the foreground tab.** Click inside the page (or take a screenshot) before typing.
- **Dropdowns:** open, read the options, click the exact option, then read the selected text back. Typing "No" can
  match "Yes, ... now ..."; typing "Male" can match "Female"; arrow keys skip past the right one. Never press Enter
  on an unmatched typeahead: on some forms Enter submits.
- **Autocomplete fields that ignore script** (Oracle HCM, some Workday/Greenhouse typeaheads) only filter on real key
  events: type with your browser tool's keyboard action, wait for suggestions, click one.
- **Forms inside iframes** (iCIMS, some company sites): same-origin frames are reachable via
  `iframe.contentDocument`, or open the iframe's `src` in the tab. A file input inside a frame usually can't take an
  upload directly: upload into a temporary top-level `<input type=file>`, then copy it over with a `DataTransfer`
  (`dt.items.add(file); frameInput.files = dt.files;` + a bubbling `change` event) and confirm the file name shows.
- **"How did you hear about us?"**: pick the closest TRUTHFUL option for where the posting was found (company
  website / careers page, else job board / online, else Other). Never "Referral", "Career fair" or a recruiter
  unless the user said so. `applytwin_answer_questions` with the options picks one for you.
- **AI interview / AI screening consent** (HireVue, "AI-assisted interview"): Yes, unless the user's profile says no.
- **Every question:** `applytwin_answer_questions([{question, options}])`. Answers under the confidence threshold
  come back null: ask the user, then `applytwin_save_answer` so you never ask again.
- **Truthful only.** Never invent experience, skills, GPA, dates or availability. If a question asks for
  something the vault doesn't have (date of birth, a recommender's or referrer's name, an emergency contact, an
  SSN), never guess and never reuse a different answer: leave it blank if optional; if required, `applytwin_notify`
  and log Needs User with the exact question.
- **Optional essays** ("Why us?", "Anything else?"): write 2-4 specific sentences from the vault and the
  posting, plain language, no em dashes, no clichés. Long required essays (>150 words): ask the user first
  unless they said to draft them.

## When the user is needed
- **Emailed codes:** if `profile.apply.email_codes` is `agent`, read the newest code from that company in the user's email
  (Gmail tool, or their signed-in webmail tab) and type it. Otherwise `applytwin_notify` and move on.
- **Sign-ins, passwords, account creation, CAPTCHAs, arbitration agreements, assessments:** `applytwin_notify` with what is
  needed and the URL, log "Needs User", keep the tab open, continue with the next job. Never type a password yourself,
  never solve or click through a CAPTCHA (including "I'm not a robot" boxes and hCaptcha), never type a one-time code
  unless `email_codes` is `agent`. The notes must name the exact blocker and where, e.g. "Workday sign-in required at
  <url>", "hCaptcha on the submit step", "emailed code requested by Greenhouse", "required question: date of birth".
- At the end of every run: `applytwin_pending_jobs`, finish whatever the user unblocked.

## Submitting
- **No duplicates.** Right before Submit, make sure this is not a second application: `applytwin_get_job` showed
  no `already_applied`, and the site doesn't say "already applied". Ashby, Workday, iCIMS and others reject or flag
  duplicates (and some count them against the company's cap). Duplicate = log Skipped "duplicate: <what you saw>".
- Submit only if `profile.apply.auto_submit` is true. Otherwise fill everything, stop on the review/submit
  screen, and tell the user which tab is ready.
- Click Submit ONCE. If nothing happens with no error, do not hammer it (bot detection): wait, check for a
  validation message, fix it, then retry once.
- Confirm success (confirmation URL or "Thank you"/"Application submitted" text), then immediately
  `applytwin_log_application(job_id, "Applied", notes, resume_path)`.

## Pacing
- Respect `daily_limit` and `per_company_cap` (applytwin_next_jobs already does). Many companies cap applications
  (often 2-3 per 30-60 days); a "maximum number of applications" message means stop for that company.
- Greenhouse starts demanding email codes after ~6-8 rapid submits: space Greenhouse submits 4-5 minutes
  apart and interleave other ATSes.
