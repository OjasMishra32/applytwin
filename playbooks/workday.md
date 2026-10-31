# Workday (<tenant>.wd<N>.myworkdayjobs.com)

- Requires an account per company (tenant). ApplyTwin never creates accounts or types passwords. First check whether the
  user is already signed in (their email in the header / "Candidate Home"); the tenant remembers the browser. If not:
  open Apply, choose "Autofill with Resume", and stop on the Sign In / Create Account page with the tab open; notes
  "Workday sign-in required at <tenant url>" (or "Workday account required at ..." when it shows Create Account).
  Every other job at that tenant waits for that one sign-in (`applytwin_next_jobs` holds them back), so report it once.
  After the user signs in, `applytwin_get_job` shows `resume_from`: continue from the step it stopped on.
- "The page you are looking for doesn't exist" / "This job posting is no longer available" = closed: log Skipped
  "closed: Workday page does not exist" right away. Don't hunt for another URL unless the job id (JR...) is in
  the tenant's search.
- A maintenance page (community.workday.com/maintenance-page) or a page that stops loading = transient: log Failed
  with that error; ApplyTwin retries it later by itself.
- First application at a tenant: "Autofill with Resume". Later ones: "Use My Last Application"
  (`.../apply/useMyLastApplication`), which carries everything over; then only review each step.
- **Dropdowns: click, never keyboard.** They are buttons with listboxes (`button[aria-haspopup=listbox]`). Typing or
  arrow keys mis-pick (typing "No" lands on "No, but..." or the wrong country/state). Click the button, then click
  the exact `[role=option]` by its text, then READ the button's text back and confirm it shows the option you meant.
  Wrong? Click again and re-pick. "How did you hear" is a nested menu: click a category, then the leaf.
- Degree in progress: some tenants want "Degree in Progress" rather than "Bachelor's" (Bachelor's = conferred).
- My Experience step: an old resume already attached from the user's last application at this tenant is NOT the tailored
  one. Delete it (the trash icon next to the file), upload the tailored PDF, wait for the file name, then check parsed rows.
- Field of study is a searchable multi-select: type the exact major; if it is not offered, pick the closest broad TRUE
  option ("Engineering"), never a sibling major. Graduation year lists that stop before the user's year = graduation
  window: Skipped.
- Multi-select search inputs (locations, skills, school): type, wait for the list, click the option, Escape; then
  check a chip with that exact text appeared.
- Self-identify page: name + today's date (MM/DD/YYYY segmented: click month, type digits) + disability box.
- Review page lists everything: verify, then Submit (only with auto_submit) and confirm "Application Submitted".
- **Duplicates:** Candidate Home lists every application at this tenant. If this job is already there (submitted),
  or Workday says you have already applied, do not submit: log Skipped "duplicate: already applied on Workday".
- Old drafts show as "Not Submitted" on Candidate Home: the posting may have closed; check before resuming.
