# Workday (<tenant>.wd<N>.myworkdayjobs.com)

- Requires an account per company. ApplyTwin never creates accounts or types passwords: if the user is not signed
  in, stop (Needs User, notes "Workday sign-in required at <url>") and leave the sign-in page open. Once they are
  signed in, continue.
- First application at a tenant: "Autofill with Resume". Later ones: "Use My Last Application"
  (`.../apply/useMyLastApplication`), which carries everything over; then only review each step.
- **Dropdowns: click, never keyboard.** They are buttons with listboxes (`button[aria-haspopup=listbox]`). Typing or
  arrow keys mis-pick (typing "No" lands on "No, but..." or the wrong country/state). Click the button, then click
  the exact `[role=option]` by its text, then READ the button's text back and confirm it shows the option you meant.
  Wrong? Click again and re-pick. "How did you hear" is a nested menu: click a category, then the leaf.
- Degree in progress: some tenants want "Degree in Progress" rather than "Bachelor's" (Bachelor's = conferred).
- Multi-select search inputs (locations, skills, school): type, wait for the list, click the option, Escape; then
  check a chip with that exact text appeared.
- Self-identify page: name + today's date (MM/DD/YYYY segmented: click month, type digits) + disability box.
- Review page lists everything: verify, then Submit (only with auto_submit) and confirm "Application Submitted".
- **Duplicates:** Candidate Home lists every application at this tenant. If this job is already there (submitted),
  or Workday says you have already applied, do not submit: log Skipped "duplicate: already applied on Workday".
- Old drafts show as "Not Submitted" on Candidate Home: the posting may have closed; check before resuming.
