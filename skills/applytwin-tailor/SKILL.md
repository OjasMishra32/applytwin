---
name: applytwin-tailor
description: "Build the best possible tailored one-page resume for a specific job with ApplyTwin, from the user's Career Vault. Use for 'twin: tailor my resume for <job/url>', 'make my resume fit this posting', or when the user pastes a job description and wants a resume for it."
---

# Tailor a resume with ApplyTwin

1. Get the job: a ApplyTwin `job_id`, or `applytwin_add_job(url, title, company, description)` for a pasted posting
   (paste the description text when you can: it makes tailoring far better).
2. `applytwin_ats_report(job_id)` to see the vault's raw coverage and which hard skills are missing.
3. `applytwin_tailor_prompt(job_id)` and write the plan like a top technical recruiter would:
   - **Top third wins.** The first role and its first bullet must hit the posting's #1 requirement.
   - **Choose, don't cram.** 3-5 roles/projects that prove the requirements; 2-4 bullets each; cut the rest.
     Relevance over recency, but keep the current role.
   - **Mirror vocabulary truthfully.** Posting says "CI/CD" and the bullet says "GitHub Actions" -> "CI/CD
     (GitHub Actions)". Posting says "distributed systems" and the bullet describes a sharded service -> say it.
     Never add a tool, number, scale or claim that the same vault entry does not contain (the fact guard
     rejects it anyway).
   - **Skills**: reorder lines and items so the posting's terms lead; drop irrelevant items if space is tight.
   - Template: `applytwin_templates`; finance/consulting -> `finance` or `harvard`, else the user's default.
4. `applytwin_tailor_apply(job_id, plan, template)`. Check: 1 page, coverage (aim 70%+ of hard skills the vault
   can support), and `rejected` (fix or drop those rewrites). Revise once if needed.
5. Report: the PDF path, coverage before -> after, the 3 most important choices you made, and the missing
   hard skills as an honest "to learn or to add if you've done it" list. Ask if they have done any of those
   (if yes, add to the vault with `applytwin_get_vault` + `applytwin_save_vault`, then re-tailor).
