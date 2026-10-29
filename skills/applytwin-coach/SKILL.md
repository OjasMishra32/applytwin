---
name: applytwin-coach
description: "Review and strengthen the user's resume / Career Vault with ApplyTwin like an expert recruiter. Use for 'review my resume', 'make my resume better', 'why am I getting rejected', 'what should I improve', or before a big application cycle."
---

# Resume coaching with ApplyTwin

1. `applytwin_get_vault` and `applytwin_ats_report()` (no job = lint only). Read the guide in the tailor prompt
   (`applytwin_tailor_prompt` on any job shows it) or rely on these rules:
   - one page; strongest evidence in the top third; standard headings; consistent dates
   - 60%+ of bullets quantified; every bullet starts with a strong past-tense verb; 80-200 chars
   - tech named inside bullets, not just in Skills; links to real work (GitHub, live demo, paper)
2. Give a ranked list of the 5 highest-impact fixes, most important first. Be specific: quote the bullet and
   show the rewrite. Example: "Worked on the payments backend" -> "Cut checkout p99 latency 38% (410 to
   255 ms) by moving fraud scoring to an async Kafka consumer" (only with facts the user confirms).
3. Ask for missing facts in one batch (numbers, users, scale, outcomes, links). Never invent them.
4. Apply the fixes to the vault (`applytwin_save_vault`), re-run `applytwin_ats_report`, and render with
   `applytwin_render_resume` in their template. Show before -> after score.
5. If they're getting rejected a lot, check the knockouts too: graduation window, sponsorship answers,
   applying to roles above their level, or applying late (postings older than ~2 weeks get far fewer
   interviews). Suggest `order="new"` scans and the `applytwin watch` notifier.
