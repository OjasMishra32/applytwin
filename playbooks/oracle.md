# Oracle Recruiting Cloud / Oracle HCM (*.oraclecloud.com/hcmUI/CandidateExperience)

- Sign-in is the user's email plus an emailed one-time code (no password). Typing the user's email is fine; the code
  follows `email_codes`: `agent` = read the newest code from that company in the user's email and type it; otherwise
  `applytwin_notify` ("emailed code at <url>"), log Needs User, leave the tab on the code screen and move on. Every
  Oracle job at the same tenant waits on that one code: `applytwin_next_jobs` holds them back until the user is in.
- A returning user is often already signed in (the tenant remembers the browser): check for their name or "Sign Out"
  in the header before asking for anything.
- **Autocomplete fields (school, location, degree, country, phone country) only filter on REAL key events**: JS
  value-setting or a pasted value shows no suggestions and the field stays invalid. Click the field, type the first
  few letters with your browser tool's real typing action (not a script), wait for the list, click the matching
  suggestion, then read the field back.
- Upload the resume first: Oracle parses it into experience and education rows. Then check every parsed row against
  the vault and delete bogus ones (a "school" made of award names, duplicated jobs).
- Dropdowns are listboxes: click, pick by exact text, read the shown value back.
- Questions are spread over several pages; "Next" with an invalid field just scrolls to it. Read the red message.
- E-signature page: typing the user's full name as a signature is an agreement. Fine for the standard "I certify my
  answers are true"; an arbitration agreement = Needs User.
- "You already applied for this job" = duplicate: log Skipped "duplicate: already applied on Oracle".
- "The job is no longer available" / redirect to the job search = log Skipped "closed: <what you saw>".
