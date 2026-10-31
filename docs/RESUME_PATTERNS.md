# Resume patterns: what strong public resumes look like

`applytwin/resume_patterns.json` holds aggregate norms for each kind of target role. Shipped profiles: big-tech SWE, quant
trading, asset management/markets, robotics/hardware, startups/founding engineer, data and general software. Investment
banking, ML/AI research, defense tech, quant research/dev and product/design profiles were built but not shipped (see
"Measured effect"). Postings of those kinds keep the plain prompt. The tailor uses the file in two places:

1. **The plan prompt.** The posting is matched to a profile (firm and title first, so "Summer Analyst, Investment Banking at
   Evercore" gets the banking profile and "Technology Summer Analyst" at the same bank does not; then posting text such as
   "security clearance" or "YC W26"; then the field). The prompt then gets a short block: what the top third leads with, the
   usual section order, bullet length and count, varied openers, how the skills section is laid out, the field's conventions,
   what to avoid, and two invented example bullets that show shape only.
2. **The quality pass.** `pattern_flags()` reads the built page the way a recruiter would: filler openers, one verb opening
   three or more bullets, run-on or two-sentence bullets, orphan sections, and too few measured results. If there are two or
   more flags (or the fact checker rejected something), the one existing revision call gets them too. The revised plan is kept
   only if it has no more fact-check rejections and fewer flags. The hard rules don't change: numbers, titles, employers,
   degrees and awards are locked, and the page is one page.

## Where the data came from

- **Public GitHub resume repositories** that people published themselves: repositories named `resume` or `cv` with LaTeX
  source. 14,521 repositories were found through the unauthenticated GitHub search API (about 10 requests a minute, under
  the published rate limit). The main `.tex` file was fetched from `raw.githubusercontent.com` (no robots.txt there), which
  gave 3,065 files. After removing untouched templates, multi-file sources and duplicates, **2,496 resumes** were parsed:
  555 intern-level, 1,010 new-grad and 931 experienced (a rough guess from titles and dates). 124 of the student/new-grad
  resumes list a role at a top firm (big tech, top quant firm, bulge-bracket or elite-boutique bank, large asset manager
  or defense prime).
- **resume-atlas** (Hugging Face `ahmedheakl/resume-atlas`, MIT license, 13,389 resumes in 43 categories), used only as a
  general-population baseline (digits per 100 words, filler-word rates). Its text is lowercased with stopwords removed, so
  it was not used for structure.
- Not used: LinkedIn (never scraped), anything behind a login, and datasets whose source is unclear (for example a
  raw-PDF resume dump with no README).

Finance and quant resumes are almost never published as LaTeX repositories. Only 7 investment-banking, 12
asset-management/markets and 13 quant-trading resumes matched, which is too few for statistics. Those profiles say so in
their `basis` field: their norms come from public recruiting conventions, not from the corpus.

## Privacy

Raw files stayed in a scratch folder outside the repo and were deleted after aggregation. Parsing kept no names, contacts,
links or bullet text. It kept only counts, lengths, normalized section names, first-word verbs, skills-heading labels and
yes/no flags. The JSON in the repo holds aggregates over groups of at least 30 resumes, plus invented example bullets.
`tests/smoke.py` fails if the file ever contains an email address, phone number or URL. Rebuild scripts are not shipped
because they would point at specific people's repositories.

## What stood out

Student and new-grad resumes from people at top firms (n=124), compared with the other student resumes (n=1,441):
- **Bullets are longer and denser.** Median 112 characters vs 105, and the 25th percentile is 92 vs 74. They have fewer
  short fragments and fewer two-sentence bullets (7% vs 8%).
- **Education comes first more often** (68% vs 59%). Every one of them has an Experience section, a Projects section is more
  common (84% vs 73%), and a Summary/Objective is rarer (10% vs 15%).
- **Competitions are on the page twice as often** (40% vs 27%: hackathons, olympiads, ICPC, Kaggle). Startup or founder
  experience (17% vs 9%) and open source (24% vs 18%) are also more common.
- **Numbers are less common than advice suggests.** Only about a third of bullets carry any digit, even among top-firm
  hires (36% vs 33%). ApplyTwin keeps its own rule (aim for half or more, never invent one) and checks it against the vault.
- **The usual order is Education > Experience > Projects > Skills.** Skills are 3-4 labeled lines, most often Languages,
  Developer Tools, Frameworks, Databases and Libraries.
- Filler openers ("Responsible for", "Worked on", "Helped", "Utilized") start about 3% of bullets in this corpus. In
  general-population resumes, words like "assisted" (28% of resumes) and "various" (38%) are far more common than in the
  GitHub student corpus (9% and 19%).

## Measured effect

Two checks ran on frozen postings before anything shipped:
- A **blind A/B review** on 12 postings: Google SWE, a YC seed-stage founding engineer, Semgrep, Jane Street trading, DRW
  quant research, Goldman and Evercore IB, Wellington equity research, Pinterest ML, Field AI robotics, Rocket Lab
  avionics and Anduril embedded. Each posting was tailored by the old and new pipelines with the labels removed. A recruiter
  persona for that firm type picked the stronger page, and every pair was judged twice with the order swapped. This ran over
  3 rounds of fresh generations.
- The **absolute eval harness** on 11 postings, scored 1-10.

Blind wins (new-old) by profile, all rounds: big-tech SWE 8-0, quant trading 8-0, startup 15-1 (Semgrep and YC postings),
robotics/hardware 8-6, asset management 5-3. Not shipped: investment banking 5-11 (the absolute grader also gave Evercore
7 vs 8), ML research 3-5, defense 3-4, quant research 0-4. After the quant-research profile was removed, the DRW posting
with only the quality pass won 4-0. Product/design had no posting in the eval set, so it is not shipped yet.

Absolute harness (11 postings, mean overall out of 10): old pipeline 6.27 and 6.64 (mean 6.45). The shipped configuration
scored 6.36 and 6.77 (mean 6.57). Two earlier versions with every profile on scored 6.64 and 6.55. Repeat runs of the same
code move by about 0.4, so this harness shows no regression rather than a clear gain. The blind pairwise review is the more
sensitive test. A fix found along the way also shipped: when the honesty audit reverts a rewrite to the original line and
that line is already on the page, the duplicate is removed.
