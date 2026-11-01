// Landing pages for what people search ("auto apply to internships", "tailor resume to job description"). Plain static
// HTML: crawlers read every word without running JavaScript. Only facts the app actually does; no em dashes.

export const SITE = 'https://apply.twinly.tech'
export const REPO = 'https://github.com/OjasMishra32/applytwin'

export const PAGES = [
  {
    path: '/auto-apply-internships',
    title: 'Auto Apply to Internships with AI, Free | ApplyTwin',
    description: 'ApplyTwin finds internships that fit you, writes a tailored one-page resume for each posting and fills out the application on Greenhouse, Lever, Workday, Ashby and more. Free and open source.',
    h1: 'Auto apply to internships, with a real resume for every one.',
    lede: 'ApplyTwin is a free, open-source app for your computer. It finds internships that fit you, writes a one-page resume for each posting and fills out the application, using the Claude Code or Codex plan you already have.',
    sections: [
      ['Finds the internships worth applying to', 'It scans company career boards and the big internship lists every day, then ranks each posting against your resume, graduation date, work authorization and location. Roles you can\'t get, like PhD-only programs or postings that need sponsorship you don\'t have, are skipped before you ever see them.'],
      ['Writes a resume for each posting', 'Every application gets its own one-page resume, rewritten from your real experience to match that posting\'s words. Numbers, titles, employers and dates never change. It only reorders and rewords what is already true.'],
      ['Fills out the application', 'Your twin opens the application in its own Chrome window and fills every field: contact details, work history, school, links, and screening questions from answers you gave once. It knows the quirks of Greenhouse, Lever, Ashby, Workday, iCIMS, SmartRecruiters and Oracle.'],
      ['You stay in control', 'By default it stops on the review screen so you press Submit. It never solves CAPTCHAs or accepts legal agreements; those come to you in one short list. It signs in and creates job site accounts only if you turn that on, and the AI never sees your password: ApplyTwin types it into the page itself.'],
    ],
    faq: [0, 2, 3, 10],
  },
  {
    path: '/tailor-resume-to-job-description',
    title: 'Tailor Your Resume to Every Job Description, Free | ApplyTwin',
    description: 'Get a one-page resume tailored to each job description: matched keywords, reordered bullets, honest rewrites. ApplyTwin is free, runs on your computer and never invents experience.',
    h1: 'A resume written for each job description. Every word still true.',
    lede: 'Paste a posting, or let ApplyTwin find them. It reads the job description and rebuilds your resume around it: the right projects first, the posting\'s own words, one clean page.',
    sections: [
      ['Matches the words recruiters search for', 'It pulls the skills and requirements out of the job description and puts your matching experience first, in the posting\'s vocabulary, so an applicant tracking system and a recruiter both see the fit.'],
      ['Honest by design', 'A fact check runs on every rewrite. A new number, a bigger scale, a different title or a tool you never listed is rejected and goes back to your own words. Outcomes only appear if your resume already states them.'],
      ['Built from resumes that got offers', 'Its formats come from studying resumes of students who landed internships at top companies, then blind-testing changes with recruiter-style reviews. Only changes that clearly win ship.'],
      ['One page, filled properly', 'Each resume fits exactly one page and ends at the bottom margin, in clean templates that parse correctly in applicant tracking systems. Every one also comes as editable LaTeX.'],
    ],
    faq: [5, 6, 1, 10],
  },
  {
    path: '/open-source-job-application-bot',
    title: 'Open-Source Job Application Bot That Runs on Your Computer | ApplyTwin',
    description: 'ApplyTwin is a free, open-source job application autopilot. Your data stays on your computer, it runs on your own Claude Code or Codex plan, and no API key is needed. Mac, Windows and Linux.',
    h1: 'An open-source job application bot that works for you, not a platform.',
    lede: 'ApplyTwin runs on your own computer. Your resume, answers and applications stay in a folder you own, and the AI work runs on the Claude Code or Codex subscription you already pay for.',
    sections: [
      ['No API key, no new subscription', 'If you can use Claude Code or Codex in a terminal, you can use ApplyTwin. There is nothing extra to buy and no usage meter.'],
      ['Your data stays yours', 'Everything lives in ~/.applytwin on your machine. Signing in backs up your setup so a new laptop picks up where you left off. It never posts, emails or signs up for anything as you.'],
      ['Read every line', 'The code is public on GitHub. You can see exactly what it does with your information, and it updates itself to the newest tested version.'],
      ['Mac, Windows and Linux', 'One command installs it. The installer checks for Python, Node.js and Claude Code or Codex and tells you what is missing.'],
    ],
    faq: [9, 4, 8, 7],
  },
]
