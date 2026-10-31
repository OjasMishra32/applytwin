# Lever (jobs.lever.co/<company>/<id>/apply)

- Plain HTML inputs: setting value via JS + input/change events works; radios via .click(); selects via .value.
- Question text: `closest('li.application-question')` -> `.application-label` / `.text`.
- Resume: input[name=resume]. If the page's accessibility tree is huge, move the input to document.body,
  upload, then move it back. Confirm the hidden `resumeStorageId` gets a value.
- Wait ~30-40s after the resume upload before submitting (an invisible hCaptcha warms up). The first SUBMIT
  click can no-op: wait 5s, click once more with a real coordinate click. More than that = stop (Needs User).
- EEO: selects `eeo[gender|veteran|disability]`, radio `eeo[race]`. If disability is filled, Lever also wants
  `eeo[disabilitySignature]` (full name) and `eeo[disabilitySignatureDate]` (MM/DD/YYYY today).
- Custom card questions are named `cards[<uuid>][fieldN]`.
- "There was an error verifying your application" (or a silent no-op twice) = Lever's invisible hCaptcha refused the
  submit. Never retry more than once: log Needs User "hCaptcha on submit (Lever)", leave the filled tab open for the
  user's Submit click, and do Lever jobs later in the run (after other ATSes), not back to back.
- An earlier resume can be pre-attached from autofill: replace it with the tailored PDF and confirm `resumeStorageId`.
- Hide (don't accept) the cookie banner. Success = /thanks "Application submitted".
