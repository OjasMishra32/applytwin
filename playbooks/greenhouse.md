# Greenhouse (boards.greenhouse.io / job-boards.greenhouse.io)

- Use the embed form: `https://job-boards.greenhouse.io/embed/job_app?for=<board>&token=<job_id>` (the job's
  apply_url). Company-site wrappers often break submit.
- `applytwin_job_questions(job_id)` returns every question + options + suggested answer BEFORE you open the form.
- Text fields (first_name, last_name, email, phone, LinkedIn, website): focus + select all + type. Verify.
- **react-select dropdowns** (role=combobox): scrollIntoView(center), click/focus, type a distinctive prefix,
  wait 1-2s, then click the exact option (or Return only when the option list shows the exact match).
  Read options with: focus, ArrowDown, read `[role=option]` texts, Escape.
- **Phone "Country" combobox** on the new UI can reset other fields when picked: pick it FIRST (after resume
  parse), then fill everything else.
- Education block (school / degree / discipline / dates) is often hidden from the API: school is a typeahead
  (type the name, wait 3s, click the option). Degree: open and click "Bachelor's". Discipline: choose the exact
  major; if missing pick the closest broad option ("Engineering"); never accept a wrong autocomplete.
- EEO selects: gender options may list "Female" before "Male" (exact click); race can be multi-select.
- Verify chosen values via `[class*=single-value]` / `[class*=multi-value]` text before submitting.
- Upload the resume LAST; after upload take a screenshot so keyboard focus returns to the page.
- Submit: click "Submit application"; success = URL contains /confirmation or a thank-you message.
- Email security code page = hard stop unless `email_codes` is `agent` (Needs User, notes "emailed code at <url>",
  form left filled). It appears after several rapid submits from one browser: `applytwin_next_jobs` already spaces
  Greenhouse jobs out; keep 4-5 minutes between Greenhouse submits and do other ATSes in between.
- Graduation date/year selects that stop before the user's year: pass the options to `applytwin_answer_questions`;
  `action: "knockout"` = log Skipped with its `skip_reason`. If "Other" is offered, pick it and type the real date.
- "There was an error processing your application" on submit: wait a minute, submit once more; still failing = log
  Failed with that message (it is retried later), never hammer the button.
