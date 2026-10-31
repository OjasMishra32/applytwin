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
- **Oracle HCM / Oracle Recruiting Cloud**: see `applytwin_playbook("oracle")` (email + emailed code; autocompletes
  need real keystrokes).
- **Taleo / Eightfold / SuccessFactors / Avature / Phenom**: first look for a no-account path on the posting ("Apply as
  guest", "Apply without an account", "Quick apply", or an Avature form that only asks for contact details). Only if
  every path needs an account with a password: leave the tab on the sign-in / create-account page, notes "account
  required at <url>" (never create the account or type a password). Other jobs on that site wait for the user's
  sign-in automatically; once they sign in, the tenant keeps them signed in for the rest.
- **JazzHR** (*.applytojob.com): plain form; a visible reCAPTCHA checkbox sits above Submit. Fill everything, then
  Needs User "reCAPTCHA on submit" with the tab open (never click the checkbox yourself).
- **Paylocity work history**: it requires a full address for every past employer. Fill what the vault has; the rest is
  a question only the user can answer ("required: street address for <employer>").
