# Other ATSes (all no-login)

- **Jobvite** (jobs.jobvite.com/<co>/job/<id>/apply): hidden file inputs (`.jv-add-attachment-item`): give them
  a visible style + aria-label, upload first, wait ~6s for parse (it DOUBLES anything already typed), then
  select-all + retype each field and verify. Radios: click the label by exact text. Success path /applyConfirmation.
- **Workable** (apply.workable.com/<co>/j/<id>/apply): decline cookies; upload first (autofills); YES/NO are radios.
  Success URL has ?success.
- **Rippling** (ats.rippling.com/.../apply): upload resume (parse fills contact); custom selects: click control,
  screenshot, click option by position; checkboxes need position clicks; date pickers are segmented
  (click MM, type digits, click DD...). Confirmation URL has step=confirmation.
- **Paylocity** (recruiting.paylocity.com/Recruiting/Jobs/Apply/<id>): close the cookie banner with X; upload
  parses work history (each entry needs city/state/zip and "reason for leaving"); react-widgets dropdowns:
  focus by id and press Down N times, verify text.
- **Pinpoint** (*.pinpointhq.com): Rails form, JS setting works; consent checkbox via its label; conditional
  questions may appear after the first submit ("can't be blank"): answer and resubmit once.
- **Gem** forms: long textareas grow while typing and can swallow the next field; fill, then verify each.
- **Oracle HCM / Oracle Recruiting Cloud** (*.oraclecloud.com/hcmUI/CandidateExperience): sign-in is email + an
  emailed one-time code (follow `email_codes`; never a password). **Autocomplete fields (school, location, degree,
  country) only filter on REAL key events**: JS value-setting or a pasted value shows no suggestions and the field
  stays invalid. Click the field, type the first few letters with real keystrokes (your browser tool's type/key
  action, not a script), wait for the list, click the matching suggestion, then read the field back. Dropdowns:
  click and pick by text, verify. Upload the resume first; it pre-fills experience you then check.
- **Taleo / Eightfold / SuccessFactors / Avature**: account with a password required -> hand to the user (Needs User,
  notes "<ATS> account sign-in required at <url>").
