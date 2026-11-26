# SANDHĀTĀ Feature Backlog and Application Agent Review

November 26 2026 | Proposal, not yet approved or implemented

Based on reading the README, main source files and key design documents. The application and tests were not run for this review.

## 1. Where the application is today

| Area | Current capability |
| --- | --- |
| Discovery | Remotive search, Greenhouse, Lever and Ashby employer boards, LinkedIn, Indeed and Ladders search links, manual import |
| Resumes | PDF and DOCX upload, immutable versions, download, delete |
| Fit comparison | Local Ollama through LangGraph: extract, validate quotes, repair once, score in code |
| Tracker | Manual and CSV entry, status history, recruiter, salary, follow-up dates |
| Insights | Pipeline, weekly trend, funnel, source and resume outcomes, gaps |
| Platform | Keycloak sign-in, row-level security, admin console, read-only MCP, encrypted backup |

Only the Fit Analyst calls a model. The agent guides describe further agents, including a Coordinator and Career Assistant under `src/sandhata/agents/`, which does not exist yet.

## 2. Feature backlog

Effort is a rough estimate: S small, M medium, L large.

| ID | Feature | Value | Effort |
| --- | --- | --- | --- |
| F01 | Today dashboard: due follow-ups, stale applications, calendar export | Surfaces stored follow-up dates | S |
| F02 | Batch compare and rank jobs by fit | Replaces one-at-a-time comparison | S-M |
| F03 | Skill gaps grouped by skill | Gaps are currently counted by exact quote | M |
| F04 | Scheduled saved searches with new since last visit | Searches run only on click | M |
| F05 | Contacts and interview rounds | Recruiter is a single text field | M |
| F06 | Resume Tailor agent | Rewrites backed by resume evidence | M |
| F07 | Interview Prep agent: questions, STAR story bank, mock practice | Preparation | M |
| F08 | Career Assistant chat (design document 20) | Weekly guidance from saved data | M-L |
| F09 | Outreach and cover letter drafter | User reviews and sends | S-M |
| F10 | Intake Parser: recruiter message to tracker prefill | Less typing | S |
| F11 | Learning Planner (depends on F03) | Turns recurring gaps into a plan | M |
| F12 | Company Research brief with sources | Better preparation | L |
| F13 | Coordinator agent with approval gates | Chains search, ranking, tailoring, prep | L |

Foundations: finish the reviewed evaluation set; handle documents above the 24,000 combined character limit; add OCR and semantic search (pgvector).

## 3. Review of the application agent proposal

Proposal: decouple discovery from execution and require human approval before final submission, in four stages.

**Verdict:** the architecture is sound. The main changes needed are to enforce the approval gate in code, prefer scripted form filling over a free-roaming browser agent, and decide where the browser runs.

### 3.1 Job discovery

| Point | Assessment |
| --- | --- |
| Greenhouse and Lever public APIs | Already implemented, along with Ashby. Remaining work is scheduling, saved boards and new-posting detection (F04) |
| RSS feeds | Reasonable addition. Check each feed's terms and whether it carries the full description |
| Adzuna | Useful for discovery. Its search API returns only a description snippet, so mark these jobs partial and collect the full text before scoring or tailoring |
| SerpApi | Defer. It is a paid intermediary that scrapes Google results. Google sued it in December 2025; claims have been dismissed, most recently in November 2026, with leave to amend |
| Not scraping LinkedIn | Agree; matches current project scope |

### 3.2 Fit scoring and tailoring

- Fit scoring exists and validates literal quotes.
- Quote validation does **not** prove that rewritten text is truthful. Require each tailored bullet to cite its source resume passage, reject new employers, dates, titles, numbers, tools or credentials that are absent from the source, and show a before and after diff for approval.
- Never let a model generate answers about work authorization, sponsorship, salary expectation, demographic or EEO questions, disability or veteran status, criminal history, or legal attestations. Take these from a user-confirmed answer bank or leave them blank.
- Version every generated resume and cover letter and link it to the application.

### 3.3 Form filling

- The Greenhouse and Lever apply endpoints require an employer API key, so a candidate tool needs the browser route.
- Write deterministic Playwright adapters per applicant tracking system, starting with Greenhouse only. Use a model to interpret unrecognized questions, not to drive every click.
- Evaluate Browser-Use or Stagehand only if scripted adapters fall short. Browser-Use is Python-first and can run with Ollama; Stagehand is mainly TypeScript. Local model reliability for browser control is untested here.
- Treat page and posting text as untrusted. Hidden instructions must not change what is filled or where data goes. Allowlist the destination domains.
- Check each site's terms on automated form filling before enabling its adapter.

### 3.4 Human checkpoint

A prompt telling the agent to pause is not a safeguard. Enforce it:

1. The filler has no submit function. The user clicks Submit in the browser.
2. Block form submission requests and the Enter key while automation is in control, then release control to the user. Test this against fixture forms.
3. Some sites send or parse a resume as soon as it is attached. Ask for approval **before upload** as well as before submit.
4. Show a review sheet listing every filled value, its source, and every field left blank.
5. Leave CAPTCHAs and logins to the user. Do not use solving services.
6. Record Applied only after the user confirms submission, as the tracker does today.

### 3.5 Gaps in the proposal

| Gap | Needed |
| --- | --- |
| Where the browser runs | A visible tab requires a helper process on the user's own computer. A container or future AWS worker cannot leave a tab open there |
| Waiting for a person | Task leases last 10 minutes and tasks allow only the compare kind. Add task kinds, a waiting_approval state with expiry, and persisted graph checkpoints (LangGraph interrupt) |
| Duplicates | One active attempt per job; warn if already applied |
| Partial failure | Stop on unknown fields or layout changes and hand over to the user. No blind retries after submission may have occurred |
| Audit | Keep the approved documents, field values, URL and timestamps, protected like other career data |
| Shared computer | Separate browser profile per member; clear sessions at sign-out |
| Quota | Count browser runs and comparisons separately |
| Scope control | Design document 02 excludes employer submission and browser extensions. Record a scope decision before building |

## 4. Model policy: Ollama first, OpenAI only if needed

Owner decision, November 26 2026.

| Rule | Detail |
| --- | --- |
| Default | Ollama handles every task. OpenAI is off unless configured and enabled |
| When OpenAI may be offered | Local output fails validation after one repair; documents exceed the local context budget; local quality fails the evaluation threshold for a task such as tailoring |
| Consent | Ask the user each time, showing what will be sent. No silent fallback |
| Minimization | Remove contact details; never send answer bank or sensitive screening data |
| Same checks | OpenAI output passes the same evidence and fabrication validation |
| Cost | Per-user daily limit and monthly spending cap |
| Records | Store provider and model per result and include them in the cache key |
| Secrets | API key only in protected runtime settings |

Code impact: `matching.py` calls Ollama directly and records one global model name. Add a small provider interface, and pass the provider and model actually used into `score_evidence` and `assessment_key`.

## 5. Recommended sequence

| Phase | Scope | Exit check |
| --- | --- | --- |
| 1 | F01, F02 | Daily value without new model risk |
| 2 | Model provider interface, F06, F09, answer bank | Zero unsupported claims on a reviewed sample |
| 3 | Application packet: documents, answers and link, applied by hand | User can apply from one review screen |
| 4 | Greenhouse filler on the local computer, no submit capability | Fixture tests prove nothing submits |
| 5 | Lever and Ashby adapters, F04, F07, F13 | Each adapter certified separately |

Phase 3 delivers most of the time saving with little automation risk. Measure it before investing in browser automation.

## Sources

Checked November 26 2026. Some are secondary; verify vendor terms before building.

- Greenhouse Job Board API: https://docs.greenhouse.io/job-board.html
- Lever API guide (third party): https://100hires.com/lever-api.html
- Adzuna search documentation: https://developer.adzuna.com/docs/search
- Adzuna terms: https://developer.adzuna.com/docs/terms_of_service
- Google v. SerpApi, November 2026 report: https://www.mediapost.com/publications/article/419346/judge-sides-against-google-in-scraping-battle-with.html
- Browser-Use and Stagehand comparison (third party): https://www.agenticwire.news/article/browser-use-vs-stagehand
