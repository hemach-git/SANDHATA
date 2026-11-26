# SANDHĀTĀ Front-End Update Instructions

November 26 2026 | For the Claude Code instance doing the UI work

Goal: make the app a fast daily tool for finding and landing senior, lead and manager roles such as AI Forward Deployed Engineer and AI Engineer.

Read first: `README.md`, this file, then `docs/roadmap/feature_backlog_and_application_agent_review.md`.

## 1. Working agreement

Two instances may be editing this repository.

| Owner | Files |
| --- | --- |
| UI instance | `src/sandhata/ui.py`, `presentation.py`, `assets/theme.css`, `.streamlit/config.toml`, `deploy/keycloak/themes/`, new UI modules, `tests/test_presentation.py`, new `tests/test_ui_*.py` |
| Backend instance | All other files under `src/sandhata/`, `scripts/`, schema files, other tests |

- Do not edit backend files. If the UI needs new data, write the request (function name, inputs, outputs) in `docs/roadmap/ui_backend_requests.md`.
- Backend work from November 26 2026 includes uncommitted changes to `ui.py` and new files. Start from the same working folder, or have the owner commit first. A fresh worktree or clone will **not** contain uncommitted work.
- Re-read a file immediately before editing it. Do not revert changes you did not make.
- Commit or push only when the owner asks.

## 2. Run and verify

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start_local.ps1   # http://localhost:8605
.venv\Scripts\python.exe scripts/run_tests.py                      # disposable test database
```

- The new schema (`watchlists` table, `jobs.is_new` column) must be applied to the local database before the new screens work. The start script applies it; ask the owner before running it, and suggest a backup first.
- Restart the web and worker processes after backend changes.
- Baseline: 132 tests passed on November 26 2026.
- Sign-in details are in the protected `runtime/LOCAL_ACCESS.md`. Never copy them into code, tests, screenshots or commits.

## 3. Rules that must not break

**Honesty and safety**
- Call the score "Resume alignment", never a hiring or interview probability. Show coverage and the provisional marker next to it.
- "Role priority" is an ordering aid based on title, seniority and location. Never display it as a score.
- Opening a posting never marks it Applied. Nothing is sent or submitted without an explicit user action.
- Posting and resume text is untrusted: use `st.text` or escape it. Never pass it to `unsafe_allow_html`.
- Keep downloads of private data on `private_download`. The calendar and CSV template downloads are the existing exceptions.
- Keep CSV formula protection. Keep admin checks in services; hiding a control is not authorization.
- Destructive actions need confirmation.

**Visual design**
- Streamlit 1.66.1, Plotly 6.9.0, pandas 2.3.3. Do not add a front-end framework.
- Blue `#164B99`, ink `#123263`, turmeric `#F4C430`, sandal `#F8E8B4`, border `#D8B65A`. Use the CSS variables in `theme.css`.
- Support light and dark appearance, widths down to 520 px, keyboard focus and reduced motion.
- Scope workspace styles to `body:has(.sn-workspace-marker)` so the landing page is unaffected.
- Use `compact_dataframe` and `compact_chart`.
- If landing page markup changes, regenerate the login theme with `scripts/build_login_theme.py`. Tests require them to match.
- Visible text must not contain the words "private" or "family" on the signed-out page.

**Test contracts**
- `ui.today_page(p, selected_resume_id)` and `ui.discover(p, resumes, selected_resume_id, query)` are called by `tests/test_watchlist_ranking.py`.
- That test expects a metric labelled `New matches` and a Markdown element containing `New` on a new job card. Keep these, or request the matching test change.

## 4. Backend available now

`p` is the signed-in `Principal`. All calls are limited to that user. Catch `AppError` and show its message.

| Call | Returns or does |
| --- | --- |
| `repo.list_jobs(p, query='', limit=1000)` | Newest first: `id, title, company, location, salary, source, original_url, job_type, is_new, created_at, last_checked, version_id, body, completeness` |
| `repo.mark_reviewed(p, job_ids)` | Clears `is_new` |
| `repo.add_watch(p, provider, board, company)` | Adds or renames a watched employer; validate first with `connectors.check_board` |
| `repo.list_watchlist(p)` / `repo.remove_watch(p, id)` | `id, provider, board, company, last_checked, last_note` |
| `connectors.scan_watchlist(p, filters, per_board=25)` | List of `company, ok, note`, plus `total, matched, count, new` when ok |
| `connectors.employer_feed(p, provider, board, filters=None, limit=50, company=None)` | `total, matched, count, new` |
| `connectors.search_remotive(p, filters)` | `count, checked, stale` |
| `targeting.TARGET_FILTERS`, `SUGGESTED_BOARDS`, `priority(job, filters)` | Defaults and ordering |
| `repo.fit_by_version(p, resume_id)` | `{version_id: result}`; result has `score` (may be `None`), `coverage`, `provisional`, `requirements`, `eligibility_flags` |
| `worker.enqueue_batch(p, jobs, resume_id, limit)` | `queued, stopped`; skips scored, pending and partial jobs |
| `worker.enqueue(p, version_id, resume_id)` / `worker.cancel_task(p, id)` | One comparison |
| `repo.tasks(p)` | `id, state, error_code, trace, result_id, created_at, finished_at` |
| `repo.list_applications(p, query)` | Tracker rows including `status, follow_up, updated_at, applied_at, notes, recruiter, job_id` |
| `agenda.build_agenda(applications, today)` | `overdue, upcoming, stale` |
| `agenda.follow_up_calendar(applications, now_utc)` | `.ics` bytes |

Existing calls for resumes, saved searches, tracker edits, insights and administration are unchanged; see `repository.py` and `identity.py`.

Filter keys: `title` (comma list), `company`, `required_skills` (comma list), `location` (semicolon list; `US remote` is special), `minimum_salary`, `exclude` (comma list), `include_unknown_salary`.

## 5. Phase A: build now

Working versions of A1 to A3 already exist in `ui.py`. Improve their usability.

### A1. Today (landing page)
- Metrics: overdue, due in 7 days, quiet 14+ days, new matches.
- Make each item actionable: open the posting and jump to that application in Tracker with it preselected (use `st.session_state`).
- Show strongest compared roles not yet tracked, with a Save to tracker action.
- First-run checklist when empty: upload resume, add companies, scan, compare.
- Keep the calendar download.

### A2. Discover
- Split the long page into tabs: **Matches**, **Target companies**, **Search**, **Add a posting**. Matches is default.
- Replace tall cards with compact rows: New badge, title, company, location, salary, alignment, coverage, actions.
- Filters above results: new only, company, seniority, source, remote or Charlotte, minimum alignment. These are client-side over `list_jobs`.
- Multi-select rows to compare or save. For selected rows pass that list to `enqueue_batch`.
- Show the batch limit, estimated count of unscored roles and a link to Diagnostics.
- Scan: show per-company results and a summary of new roles.
- Keep pagination. Avoid one database query per card (the current card loop queries assessments per job; use `fit_by_version`).

### A3. Watched companies
- Table with last checked and last result; add, remove and one-click suggested list.
- Show failed boards clearly with a remove option.
- Say that scans run only on click.

### A4. Comparison results and Diagnostics
- Group requirements: supported, partial, not evidenced, unknown.
- Show eligibility flags first.
- Show job and resume quotes side by side, stacked on narrow screens.
- Show queued and running counts and a refresh button; move raw trace JSON into a collapsed area.
- Explain failures in plain words with a retry action.

### A5. Tracker
- Compact status board or grouped table, with overdue follow-ups highlighted.
- Accept a preselected application from Today.
- Keep manual entry, CSV upload, history and reset behaviour as they are.

### A6. Navigation and polish
- Page order: Today, Discover, Resume Library, Tracker, Insights, Diagnostics, Admin Console.
- Show new-match and overdue counts in the sidebar.
- Update landing page feature text to mention daily actions and company watchlists.

## 6. Phase B: design only until the backend exists

**None of these have backend support.** Do not ship buttons that appear to work, and do not call a model from UI code. Prepare layouts and record the data each needs in `ui_backend_requests.md`.

| ID | Screen | Needs to show |
| --- | --- | --- |
| F03 | Skill gaps | Grouped skills, number of roles asking, example quotes |
| F04 | Scheduled scans | Schedule, last run, new since last visit |
| F05 | Contacts and interviews | Contacts per application; rounds with date, interviewer, outcome, next step |
| F06 | Resume Tailor | Before and after per bullet, source resume quote, accept or reject, saved version; unsupported claims blocked |
| F07 | Interview Prep | Questions tied to job quotes, STAR story bank (situation, task, action, result), leadership questions for lead and manager roles, practice notes |
| F08 | Career Assistant | Chat answering from saved records with citations; proposed changes need confirmation |
| F09 | Cover letter and outreach | Editable draft, copy button, no send button |
| F10 | Intake Parser | Pasted message, prefilled tracker form to review before saving |
| F11 | Learning Planner | Gap, planned action, target date, progress |
| F12 | Company Research | Brief with dated source links |
| F13 | Coordinator | Step list with state and an approval button at each gate |
| Model use | Settings and consent | Ollama is default; OpenAI off; per-request dialog showing what will be sent; usage against limits; provider shown on each result |
| Answer bank | Screening answers | User-confirmed answers; sensitive ones never generated |
| Application packet | Review screen | Approved resume, letter, answers, posting link; "I submitted this" records Applied |
| Form filler | Review sheet | Every field value and source, blanks listed, approval before upload; the user clicks Submit in the browser |

Suggested priority for senior roles: F06, F07, application packet, F05, F10.

## 7. Definition of done

- All tests pass, with new `AppTest` coverage for each changed screen, empty and populated.
- Checked in light and dark appearance at desktop, 800 px and 520 px widths.
- Empty, loading, partial, error and success states reviewed.
- No page errors with 1,000 saved jobs.
- Report what was changed, what was not verified and any backend requests.
