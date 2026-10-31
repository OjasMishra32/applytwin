# Resume patterns: what strong public resumes look like

`applytwin/resume_patterns.json` holds aggregate norms for each kind of target role. Shipped profiles: big-tech SWE, quant
trading, asset management/markets, robotics/hardware, startups/founding engineer, data and general software (round 1), and
investment banking, ML/AI research and quant research/dev (round 2). The defense-tech and product/design profiles are in
the file with `"shipped": false`: built but not used, because they have not won a blind review (see "Measured effect").
Postings of those kinds keep the plain prompt. `APPLYTWIN_TRY_PROFILES=all` (or a comma list of ids) switches unshipped
profiles on for an eval run. The tailor uses the file in two places:

1. **The plan prompt.** The posting is matched to a profile (firm and title first, so "Summer Analyst, Investment Banking at
   Evercore" gets the banking profile and "Technology Summer Analyst" at the same bank does not; then posting text such as
   "security clearance" or "YC W26"; then the field). The prompt then gets a short block: what the top third leads with, the
   usual section order, bullet length and count, varied openers, how the skills section is laid out, the field's conventions,
   what to avoid, and two invented example bullets that show shape only. A profile can also carry `variants` keyed on the
   title ("Software Engineer (C++)" at a quant firm reads as quant development, "Quantitative Researcher" as research),
   a `force_order` the page is laid out in (ML research: Publications right under Education), `chronological` (banking:
   roles strictly newest first, including roles the page-filler adds), `titles` (banking: "Leadership & Activities",
   "Skills & Interests"), and `checks` for the quality pass.
2. **The quality pass.** `pattern_flags()` reads the built page the way a recruiter would: filler openers, one verb opening
   three or more bullets, run-on or two-sentence bullets, orphan sections, and too few measured results. If there are two or
   more flags (or the fact checker rejected something), the one existing revision call gets them too. The revised plan is kept
   only if it has no more fact-check rejections and fewer flags. The hard rules don't change: numbers, titles, employers,
   degrees and awards are locked, and the page is one page. Profile `checks` add detail flags: a present-tense verb on a
   role that has ended, the same phrase in two bullets of one entry, a role cut to one bullet, and a bullet that restates a
   paper the research section already lists.

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

The round-2 profiles (banking, ML research, quant research/dev, defense) were rewritten from public recruiting guidance,
paraphrased and cross-checked, never copied: university career-center finance guides and sample listings, practitioner
banking guides, quant firms' own interviewing pages and postings (no GPA or finance background required at several, and
competition results named as a signal), Google and Ai2 research-internship postings and academic-CV conventions for
publication status, and defense postings plus clearance-resume guidance (state citizenship when a posting screens on it,
never imply a clearance). Where sources disagree (whether to show a modest GPA, whether banks want an Interests line), the
profile follows the majority convention.

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

### Round 1

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

### Round 2: banking, ML research, quant research/dev, defense

Why round 1's versions lost, from the judges' reasons: the banking profile cut a merger-model case study ("no projects
section") and kept filler lines; the ML profile was applied to an applied recommender-systems posting (Pinterest) and pushed
research-first framing there; the quant profile traded research content for a grading job and stripped the awards; the
defense profile traded hands-on lab evidence for class projects. Round 2 narrowed ML research to research postings (an
applied "Machine Learning Intern" keeps the plain prompt), split quant into research and developer variants, and rebuilt
each profile from recruiting guidance (see above).

The eval used 16 frozen postings, 4 per field, written from the public shape of these programs:
- banking: Evercore, Goldman Sachs, PJT Partners restructuring, and Moelis (given an equity-research student's background);
- quant: DRW and Two Sigma quant research, Citadel quant research (a physics student), Hudson River Trading C++ engineering
  (a backend engineer);
- ML research: Google DeepMind student researcher, NVIDIA research, Ai2 NLP research, Microsoft Research AI for Science
  (the physics student);
- defense: Anduril embedded EE, Lockheed Martin Space software, Northrop Grumman GN&C/flight software, Shield AI mechanical.

Both arms ran the same code, with the profile off (plain prompt plus the quality pass) or on. In every round each posting was
tailored twice by each arm. Each of the two old/new pairs was judged twice, with the order swapped, by a recruiter persona
for that firm. That is 16 judgments per field per round. Every page was also scored by the absolute grader. Three rounds
were planned. Win counts are judgments, so each pair counts twice. The sign test ignores that correlation, so treat p as
optimistic.

| field | blind wins new-old (n) | sign test | absolute, old to new | decision |
|---|---|---|---|---|
| ML research | 36-12 (48) | p < 0.001 | 6.67 to 7.06 | shipped |
| investment banking | 32-15 (47) | p = 0.02 | 6.88 to 6.90 | shipped |
| quant research/dev (first version) | 26-22 (48) | p = 0.67 | 6.29 to 6.29 | revised |
| quant research/dev (revised, 5 rounds) | 46-32 (78) | p = 0.14 | 6.30 to 6.42 | shipped, weakest evidence |
| defense, profile plus citizenship line | 42-6 (48) | p < 0.001 | 6.42 to 6.98 | see ablation |
| defense, profile without the line | 10-22 (32) | p = 0.05 | 6.53 to 6.44 | not shipped |
| defense, citizenship line alone (plain prompt) | 25-7 (32) | p = 0.002 | 6.44 to 6.91 | line shipped |

Notes on the table:
- **Banking.** Run straight against `main` on the Goldman posting, the branch also won 8-4 (n=12).
- **Quant.** The first version folded competition results into the education block, which judges called crammed and which
  left a one-line Awards section. It also dropped a Jane Street internship and added "out of sample" where the vault said
  nothing of the kind.
  - The revised version keeps a full Awards section, keeps every trading-firm or top-tech internship, and forbids
    validation claims the vault doesn't make.
  - Its first three rounds alone were 26-21. Two more rounds were added because that margin was thin.
  - By posting: DRW 14-5, HRT 12-8, Citadel 12-7, Two Sigma 8-12.
- **Defense.** Nearly all of the profile's win came from the citizenship line. Without it, the profile's prompt block lost.
  So the defense profile stays off. What shipped is the line itself, for any posting that screens on citizenship (security
  clearance, U.S. citizen or U.S. person, ITAR, export-controlled), when the user's profile says U.S. citizen (or permanent
  resident, for U.S.-person roles). The page never states or implies a clearance. On the Rocket Lab avionics posting
  (ITAR) the line went 6-2.

**General fixes** shipped alongside, for every field:
- The GPA never splits across lines. When the degree line is too long, the GPA opens the honors line.
- Every bullet ends the same way, and two lines that differ only by a final period become one.
- A weak bullet is never swapped for the original of a bullet already shown in reworded form. That swap caused
  near-duplicate bullets.
- "Did ..." and "Made the ..." count as filler openers.

**Regression check** (`main` against this branch) on the round-1 postings, 2 rounds, 6 postings: 23-24 (n=47). Absolute
scores were 7.23 and 7.17.
- Google, Jane Street, Rocket Lab and the YC startup were even: 4-4, 4-4, 5-3 and 3-5.
- Pinterest went 7-1.
- Wellington went 0-7, and three extra rounds there went 5-7.
- The Wellington verdict tracks one near-random choice: whether the page-filler adds an ongoing research-assistant role or
  a club entry, which depends on a few characters of free space.
  - When the plan itself includes that role, finance's strict newest-first order puts it above the internship, and judges
    mark that down. `main` behaves the same way.
  - A first version of this branch also re-sorted roles the filler added for every finance posting, which put the role
    first more often. Now only banking does that.
  - This is an open item: an ongoing minor role outranking the main internship.
