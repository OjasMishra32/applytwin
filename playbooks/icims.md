# iCIMS (careers-<co>.icims.com)

- The form is inside a **same-origin** iframe (`#icims_content_iframe`). Page-level element searches and accessibility
  snapshots often miss it: reach in with
  `document.querySelector('#icims_content_iframe').contentDocument` (or navigate the tab straight to the iframe's
  `src`, which shows the form on its own and is easiest).
- **Resume upload inside the iframe:** browser upload tools usually only reach top-level file inputs. Either open the
  iframe `src` directly and upload there, or use the DataTransfer hand-off: add a temporary
  `<input type=file id=at-up>` to the TOP document, upload the PDF to it with your upload tool, then in JS:
  `const dt = new DataTransfer(); dt.items.add(document.getElementById('at-up').files[0]);
  const inp = frameDoc.querySelector('input[type=file]'); inp.files = dt.files;
  inp.dispatchEvent(new Event('change', {bubbles: true}));` and confirm the file name shows in the form.
- Most iCIMS portals require sign-in by email and often an hCaptcha: that is a hard stop for ApplyTwin. Fill the
  email only if the user asked, never solve the captcha; hand the tab to the user (Needs User, notes "iCIMS sign-in /
  hCaptcha at <url>"), then continue after they sign in.
- Steps are paginated (Contact, Resume, Questions, EEO, Review). Upload the PDF on the resume step, verify the
  parsed fields, answer questions from the bank, and stop at Review unless auto_submit.
- "You have already applied for this job" = duplicate: log Skipped "duplicate: already applied on iCIMS".
- "This job is no longer accepting applications" = log Skipped "closed: ...".
- Profile step with a resume already on file: replace it with the tailored PDF (Remove, then upload) and confirm the name.
