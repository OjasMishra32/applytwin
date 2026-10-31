# Resume patterns: what strong public resumes look like

`applytwin/resume_patterns.json` holds aggregate norms for each kind of target role. Shipped profiles: big-tech SWE, quant
trading, asset management/markets, robotics/hardware, startups/founding engineer, data and general software (round 1), and
investment banking, ML/AI research and quant research/dev (round 2), and hardware engineering for embedded/firmware and
chip design/verification titles (round 3), and electrical/board hardware for electrical, avionics and power-electronics
titles (round 4). Since round 5, each profile's `basis` and `n` say how many elite resumes (people who actually landed
top-firm intern or new-grad roles) back it, and jobs in India or continental Europe add a regional overlay on top of their
profile (see "Round 5: elite corpus"). The defense-tech and product/design profiles are in
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
   role that has ended, the same phrase in two bullets of one entry, a role cut to one bullet, a bullet that restates a
   paper the research section already lists, and (hardware) a role or project whose bullets name none of its listed tools.

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
  - Fixed in round 4 (see "Round 4"): an ongoing campus role is now placed by its start date in finance's newest-first
    order, so it no longer sits above the internship.

### Round 3: hardware

Eleven frozen hardware postings, written from the public shape of these programs: NVIDIA ASIC design verification, AMD
design verification, Qualcomm ASIC/digital design, Apple electrical hardware, Intel post-silicon validation, Tesla vehicle
firmware, Anduril electrical, a humanoid-robotics startup's embedded/electrical role, Rivian electrical test and validation,
SpaceX avionics hardware, and Rocket Lab avionics (round 1). Four synthetic vaults (no real people): a computer-engineering
student with board, FPGA and test internships, a digital-design/verification student, an EE embedded/power student, and the
aerospace student from round 1. Same harness as round 2: two generations per arm per round, each old/new pair judged twice
with the order swapped by a recruiter persona for that firm, plus the absolute grader. "Old" is `main`.

What weakened hardware pages on `main`, from the absolute grader's defects and the judges' reasons:
- **Routing.** "Hardware Engineering Intern" at Apple and "Firmware Engineer" at Tesla matched the big-tech SWE profile by
  firm; "Design Verification Engineering Intern" fell to the *design* field (portfolio-first rules); an ASIC role got the
  mechanical-leaning robotics profile ("SolidWorks motor mount" examples).
- **Filler from the page-filler.** It padded short pages with a grocery-store job, a Discord bot and "Completed ISO 26262
  awareness training" (trainings with a standard number in them escaped the filler rule).
- **Wrong lead for the posting.** Verification-first pages for an RTL design role, ISO-training lines under the most
  relevant employer, web-dashboard bullets kept on ASIC pages, the posting's tools (Verdi, PyVISA) only in skills.
- **Qualifiers dropped or upgraded.** "at equal clock", "academic library", "Designing" (in progress) to "Designed",
  cold-flow to hot-fire.

| variant (titles) | rounds | blind wins new-old | absolute, old to new | decision |
|---|---|---|---|---|
| chip design / verification (ASIC, FPGA, RTL, DV, VLSI, silicon, analog) | 4 | 41-7 | 7.71 to 8.10 (n=24) | shipped |
| embedded / firmware (rounds 1-2 ran an earlier wording) | 4 | 23-7 | 7.50 to 7.59 (n=16) | shipped |
| final configuration only (rounds 3-4, both variants) | 2 | 30-8, sign test p < 0.001 | chip 7.75 to 8.17 | |
| electrical / board (Apple, SpaceX, Rocket Lab, Anduril) | 2 | 12-19 | | rebuilt and shipped in round 4 |
| test / validation (Intel, Rivian) | 1 | 0-8 | | still not shipped after round 4 |

- By posting, all rounds: Qualcomm 16-0, AMD 13-3, NVIDIA 12-4, humanoid robotics 13-2, Tesla 10-5.
- The electrical/board variant lost on Apple (1-7), SpaceX (1-6) and Rocket Lab (3-5) and won on Anduril (7-1). Judges
  flipped on where a design-team lead role belongs from one round to the next. Those titles keep their earlier routing
  (Apple hardware stays on the big-tech profile, avionics on robotics/hardware, defense firms on the plain prompt with the
  citizenship line). Validation and test titles keep robotics/hardware or their field's profile. Routing Intel's
  post-silicon title to the hardware field also lost (2-6), so "silicon" is not a hardware field word.
- `hardware_eng` sits after `defense` in the detection order, so defense-firm postings behave as before.

**General fixes** shipped alongside:
- A rewrite can't name a hardware tool (HDL, simulator, EDA, lab instrument, bus, MCU family) that its own role or project
  doesn't list, even when the posting asks for it. Spellings of one part family match ("STM32" for "STM32G4").
- The page-filler never adds an entry whose lines are all filler, or a service job when the page already shows two roles.
  "Completed ... training" lines, awareness/security/ethics trainings and "Filed paperwork" count as filler.
- When the plan splits one vault skills line in two, the new line keeps its own heading instead of printing two lines under
  the same heading.
- "Design verification", VLSI, RTL, PCB, analog, mixed-signal, semiconductor and avionics titles are the hardware field.

**Regression check** (`main` against this branch) on big-tech SWE, quant trading, startup, asset management, banking, ML
research and applied ML, 2 rounds: 27-29 (n=56), absolute 7.59 and 7.59. None of these pages triggered a changed code path
(no tool-guard rejection, no filler entry skipped, no training line), so per-posting splits (banking 6-2, big-tech 2-6) are
generation noise.

### Round 4: electrical/board hardware, test/validation, and finance ordering

Why round 3's electrical/board and test/validation variants lost, from the judges' reasons:
- **Design-team roles were demoted.** Both variants inherited the embedded/chip rule that a design-team role stays under
  Leadership. On board-level postings, judges wanted a titled role that delivered boards ("Electrical Lead", "Avionics
  Subteam Lead") in Experience, and marked pages down for leaving it at the bottom (Apple went 0-4 on this alone in one
  round).
- **Lab evidence was traded away.** The SpaceX pages dropped a lab role with LabVIEW DAQ code and a CubeSat project (both
  named in the posting) for GN&C analysis lines. Rocket Lab pages came out thinner (HIL runs and the 2,000-case Monte Carlo
  were dropped). Some pages bolted "hardware" onto simulation bullets, and UVM/accelerator lines stayed on Apple's
  board-level page.
- **Validation lost to pages that were already good.** The baseline (software or robotics/hardware profile) already
  led with test automation. The variant added a PCB/club block and a TA entry in place of test bullets. Judges also rewarded
  baseline rewrites that added outcomes the vault doesn't state ("driving a bug report to the design team").
- **An outreach section ending in "Coordinated volunteers."** closed several avionics pages in both arms. When a plan writes
  no "leadership" key (it often moves the one strong club role into experience), the vault's whole leadership section was
  printed as-is, filler lines included.

Eval: the six round-3 postings plus four new ones written after the variant and never read for its design (Lucid power
electronics, Blue Origin avionics, GM electrical validation, Marvell post-silicon validation). The same harness as rounds
2-3, with `main` as old. Win counts are judgments, and each pair is judged twice, so the sign test is optimistic.

| change | rounds | blind wins new-old | absolute, old to new | decision |
|---|---|---|---|---|
| electrical/board profile, first version | 3 | 42-29 (p = 0.15) | 7.15 to 7.28 | revised |
| electrical/board profile, revised | 3 | 53-19 (p < 0.001) | 7.15 to 7.18 | shipped |
| test/validation variant, both versions | 6 | 40-54 (revised alone 22-26) | 7.03 to 7.14 | not shipped |
| finance: ongoing campus role by start date | 3 | 34-14 (p = 0.006) | 7.23 to 7.46 | shipped |
| same, order-only (same page, only the order differs) | | 56-0 (28 pages) | | |

- **Electrical/board, revised, by posting:** Apple 12-0, Rocket Lab 11-1, Blue Origin 10-2 (new posting), Lucid 8-4 (new),
  Anduril 8-4, SpaceX 4-8. On SpaceX, some generations dropped the NASA internship or the CubeSat project. Pairs where the
  new page hit no leadership-section change went 47-19, so the profile carries the result.
- **What the electrical/board profile says:**
  - A titled design-team role that delivered hardware goes under Experience with 2-3 measured bullets, in reverse
    chronological order.
  - Keep lab and test evidence (DAQ, test stands, HIL, thermal tests, bring-up), and keep projects that match a named
    preferred qualification.
  - Digital/UVM lines are the first to go on a board-level page.
  - Never bolt on the word "hardware"; mirror the posting's words only on work the vault shows.
  - Skills lead with hardware design and lab lines.
- **Routing:** electrical, avionics, power-electronics, PCB and "hardware engineering" titles get it, ahead of defense and
  big-tech firm routing (the citizenship line still applies). Embedded, firmware, chip, validation, test, mechanical and
  software titles keep their earlier profiles.
- **Validation, by posting:** GM 6-18, Rivian 9-15, Intel 13-11, Marvell 12-10. The revision put validation identity first,
  put design-team roles in experience, and allowed a new result (bug filed, fix, errata) only when the vault states it.
  It still didn't beat pages that were already test-first, so validation and test titles keep robotics/hardware or their
  field's profile.
- **Finance ordering:** a still-ongoing part-time campus role (research or teaching assistant, tutor, peer advisor) is
  placed by its start date. It never sits above an internship that ended after it began. Internships, analyst roles and
  real jobs keep strict newest-first order, and so does Leadership.
  - By posting: Wellington 7-5, Moelis (banking, same student) 10-2, T. Rowe Price 10-2, BlackRock 7-5.
  - The order-only test re-rendered 28 finished pages that carried the role, in `main`'s order and the new order. Judges
    preferred the new order every time.
  - Goldman (6-6) and Google (8-4) ran in the same rounds and never hit the changed code path.

**General fixes** shipped alongside:
- A section the plan left out entirely loses its filler lines, and any club entry with only filler lines. During the eval
  this version also dropped the entries the plan's "cut" list named. That went 13-7 on hardware pairs it touched but lost
  one startup pair (a strong hackathon-infrastructure role was cut), so the shipped version doesn't apply "cut" there.
- A skills heading the plan invented is kept when the vault label would read as another heading printed twice ("GN&C"
  beside "GN&C & Modeling"; 1 page in 1,271 across all eval outputs).

**Regression check** (`main` against the final branch, except that during the run, a section the plan left out also honored
"cut") on big-tech SWE, quant trading, startup, banking (Evercore, Goldman), ML research, applied ML, chip design/verification
(NVIDIA, Qualcomm), embedded (Tesla, Figure) and Wellington, 2 rounds: 50-45 (n=95), absolute 7.73 old vs 7.67 new.
- Only 2 of 48 new pages hit a changed code path: one Wellington page reordered, and one startup page whose cut leadership
  section lost both judgments (that behavior was then removed).
- Every other split is generation noise on identical code: quant trading 0-8, Goldman 2-6, Wellington 2-6, Evercore 7-1,
  Qualcomm 8-0, Figure 8-0, NVIDIA 1-6.

### Round 5: elite corpus

**The rule.** Norms now come only from resumes of people who actually landed top-firm intern or new-grad roles (the
"elite set"); every other resume is a contrast, never a norm. A resume is elite when an Experience or Research entry names
an intern, new-grad or PhD-student role at FAANG/NVIDIA/Apple, a top AI lab, a top quant firm, a bulge-bracket or
elite-boutique bank, a top asset manager, SpaceX/Anduril/a defense prime/Palantir, or Stripe/Databricks/Ramp/Scale
AI/Figma. Programs, insight weeks, virtual experiences, clubs, and a firm named only in an objective, a tool or a project
title don't count. A manual spot check put precision at 80-85%.

**Sources, at the aggregate level.** Public GitHub resume sources only (authenticated code and repository search, under
the published rate limits; files fetched from `raw.githubusercontent.com`): LaTeX, Typst, JSON Resume, YAML and HTML.
About 52,000 files gave 11,719 resumes after removing template copies and duplicates; 6,002 are students or new grads and
471 of them are elite. Hugging Face resume datasets were reviewed and skipped (unclear provenance). Nothing behind a login,
no LinkedIn, no paid sources. Raw files and the repository lists were deleted after aggregation. The repo keeps only counts,
shares and percentiles, with no names, contacts, links, repository names or bullet text.

Elite n by segment: SWE 233 (big-tech 106), ML research 65, applied ML 59, India 101, hardware 42, Europe 42, startup
firms 29. Quant (20), data (22), banking and asset management (4) and the UK (17) are too small, so nothing numeric was
proposed for them.

What separates elite student pages from the contrast (n=471 vs 4,167):
- Bullets are a little longer (median 112 vs 107 characters).
- More roles with fewer bullets each (median 4 roles vs 3).
- Measured results are more common but not the majority: the per-resume median is 27% vs 19%.
- Open source (27% vs 15%) and founder roles (16% vs 10%) are more common.
- Summaries (19% vs 28%) and certifications (8% vs 16%) are rarer.
- Half the elite pages (48%) open three or more bullets with the same verb.

Every shipped profile's `basis` and `n` in `resume_patterns.json` now state its elite count. Where the segment is big
enough (SWE, big-tech SWE, ML research, hardware), an `elite` block holds its percentiles. Software and big-tech bullet
lengths moved to the elite 88-164 characters. Quant, banking, asset management, data, startup and robotics keep their
earlier numbers, and their `basis` says the elite set is too small to replace them.

**Eval.** The harness is the one from rounds 2-4: each arm tailors each posting twice per round, and a recruiter persona
for that firm judges each old/new pair twice with the order swapped. The absolute grader also scores every page. "Old" is
`main`. Each change was tested alone on its own postings: 4 SWE, 2 startup, 3 ML research, 5 chip/embedded and 4
international. The international postings were new: Google Bengaluru and Microsoft IDC for an Indian-campus vault, Google
Zurich and Amazon Berlin for a German vault (both vaults synthetic). Win counts are judgments, and each pair counts twice,
so the sign test is optimistic. Pairs where a page fell back to the built-in writer or failed to render (machine
overload) are excluded, and one overloaded international round was discarded.

| change | rounds | blind wins new-old | sign test | absolute, old to new | decision |
|---|---|---|---|---|---|
| regional overlays (India, continental Europe) | 5 | 53-26 | p = 0.003 | 7.55 to 7.58 | shipped |
| quality pass: repeated opener at 4+ (or >25%), measured-results flag only below 15% | 3 | 42-43 | p = 1 | 7.76 to 7.75 | not shipped |
| SWE shape: 3-4 bullets on the lead role, 2-3 elsewhere, 3-4 skills lines, no summary/certifications | 3 | 24-24 | p = 1 | 6.79 to 7.04 | not shipped |
| startup: elite bullet length (100-173), 2-3 per role | 1 | 1-7 | p = 0.07 | 7.00 to 7.50 | not shipped |
| ML research: Awards section forced when the vault has awards | 2 | 8-15 | p = 0.21 | 7.67 to 7.17 | not shipped |
| ML research: Experience before Publications (against `main`'s order) | 2 | 3-20 | p < 0.001 | 7.58 to 7.33 (vs `main`) | not shipped |
| hardware_eng: elite bullet length (87-147), Education first with coursework | 1 | 5-15 | p = 0.04 | 7.90 to 8.20 | not shipped |

- **Regional overlays, by posting:** Google Bengaluru 14-6, Microsoft IDC 12-7, Google Zurich 14-6, Amazon Berlin 13-7.
  India alone 26-13, continental Europe alone 27-13.
  - A job in India or continental Europe (EU/EEA and Switzerland) keeps its profile and gets a short regional block in
    the prompt. Routing lives in `regions.resume_region()`; the overlay text lives in `resume_patterns.json` under
    "regions".
  - **India (elite n=101):** keep the CGPA on its /10 scale, and keep an Achievements section with exam and contest ranks.
    Real roles go before projects, and certifications are cut first. The vault's awards are shown as their own section
    when it has two or more.
  - **Europe (elite n=42):** spoken languages take one Skills line, there is no Summary, and working-student and HiWi
    roles count as real experience.
  - The UK, Canada and East Asia get no overlay (too few elite resumes).
- **ML research.** The order with Publications right under Education is the plurality on elite pages, not the majority
  (35%). It still beat Experience-first in both directions (3-20), so it stays.
  - A first version of the Awards rule rarely fired, because the planner's two picks deduplicated to one, which then
    folded into Education. It went 16-8, but that result can't be credited to an Awards section.
  - The fixed rule always showed one, and judges called the resulting two-line section a stub (8-15).
- **The quality-pass change** did change the code path: in the round that logged it, the revision call ran on 8 of 11
  `main` pages and 7 of 14 new ones. It moved nothing in either direction.
- **Weak-n changes lost outright.** Startup (n=29) and hardware (n=42) needed a clear margin, and both lost. The hardware
  judges preferred `main`'s pages for putting the most on-target project first and keeping Skills on the posting's tools.

**Regression check** (`main` against the final branch) on big-tech SWE, quant trading, quant research, startup, banking,
asset management, ML research, chip design/verification, embedded and electrical/board, 2 rounds:
- **Result:** 41-37 (n=78), absolute 7.96 vs 7.99.
- **Extra round:** three ML research postings went 6-6.
- **By posting:** startup 7-1, banking 6-2, quant research 6-2, Google 4-4, Jane Street 4-4, Apple 4-4, DeepMind 4-4,
  Tesla 3-4, Wellington 3-5, NVIDIA 0-7. The NVIDIA judges called the pages "near-identical"; they split on a filler line
  the page-filler added and on bullet order. In the quality-pass rounds, the same posting went 7-5 with no hardware change.
- **Rewording the `basis` lines.** A first version rewrote every `basis` line from scratch ("elite set: 65 student resumes
  of people who landed top-lab ... roles"), and the `basis` is printed in the prompt. Its regression went 32-53, including
  1-18 on ML research postings. Keeping each earlier sentence and adding the elite count brought it back to even.
