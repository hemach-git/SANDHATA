# SANDHĀTĀ Career Intelligence

**Search, Analyze, Navigate, Discover, Highlight, Apply, Track, Advance.**

An invite-only user job-search workspace with protected resumes, original posting snapshots, evidence-grounded comparisons, an application tracker, analytics and an administrator console.

## Current release

Version 0.2 is a working localhost pilot. It uses real Keycloak OIDC, PostgreSQL forced row-level security, Streamlit, a durable LangGraph comparison worker, local Ollama, Plotly, and authenticated protected downloads. Automated tests use a separate disposable database. AI comparisons remain experimental pending the full reviewed evaluation dataset. Public production deployment is not complete.

Start with [the implementation and operating handoff](docs/23_Implementation_and_Operating_Handoff.md), then [the document index](docs/00_Document_Index.md). Paired Word files are in `deliverables/word`. Design documents record the intended target; document 23 records the implemented subset and release limits.

## Run locally on Windows

Prerequisites: Python 3.12, Docker Desktop/Engine, Git and Ollama with an installed compatible structured-output model. Use a separate checkout outside BRIHASPATI.

```powershell
Set-Location -LiteralPath 'C:\Users\Chepuri\AI-Products\Prototypes\SANDHATA'
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.lock
powershell -ExecutionPolicy Bypass -File scripts/start_local.ps1
```

On this machine the environment and services are already installed. Open http://localhost:8605 and use the protected `runtime/LOCAL_ACCESS.md` guide for pilot credentials. Never commit or share that file. All listener ports are loopback-only. Other devices cannot access this localhost deployment.

## Verify

```powershell
.venv\Scripts\python.exe scripts/run_tests.py
.venv\Scripts\python.exe scripts/live_evals.py
.venv\Scripts\python.exe scripts/backup.py
docker build -t sandhata:0.2.0 .
```

The live evaluation command uses synthetic text with your local model. Backups are encrypted; keep `runtime/backup.key` separately in a secure vault. The backup script performs an isolated restore drill and never overwrites the active database. Identity-provider backup and real restore remain separate operator procedures.

## Supported sources

Remotive public API uses a deployment-wide six-hour cache. Greenhouse, Lever and Ashby adapters take known employer boards. LinkedIn, Indeed and Ladders open searches in the user's own browser and support full-description manual import. Premium subscriptions do not imply API rights. Employer adapter breadth is implemented but not live-certified for every employer.

## Daily job search

**Today** lists overdue and upcoming follow-ups, applications with no update for 14 days and no follow-up date, new matches, and the strongest compared roles for the selected resume. Follow-ups download as a calendar file without notes.

In Discover, **Target companies** keeps a personal list of Greenhouse, Lever and Ashby boards. Scans run when clicked, filter each whole board before the per-company limit, flag new roles, and continue past a failed board. The default filters target Forward Deployed and AI roles in Charlotte, North Carolina or remote in the United States. Locations are separated by semicolons and matched as whole words. Refreshing a posting keeps the location and salary of tracked applications.

**Compare next unscored roles** queues a batch in the displayed order, subject to the daily quota. Role priority is an ordering aid, not a fit score.

Comparisons accept up to 48,000 combined characters with the default `SANDHATA_MODEL_CONTEXT=32768`; a smaller context lowers the limit. After upgrading, apply the schema with `scripts/migrate.py --schema-only` (the start script also applies it) and restart the web and worker processes. Greenhouse postings imported earlier may contain HTML tags; scan or import that board again.

## Deployment and GitHub

Current operation is local to this home computer, with individual user logins. Use a separate browser profile per person and sign out when switching users. AWS is a future deployment target; the CHAKRA AWS account/profile is excluded. See [the AWS deployment guide](docs/24_AWS_Deployment_Guide.md) and `deploy/aws/foundation.json` for the isolated infrastructure foundation. Read-only STS and CloudFormation template validation passed; no AWS infrastructure has been created. A future separate AWS setup, domain and budget will be supplied when deployment resumes.

`Dockerfile`, `compose.production.yaml` and `deploy/Caddyfile` package the application tier. Production requires actual DNS/host access, a production OIDC provider, PostgreSQL roles, persistent storage and protected secrets. Do not expose the local Keycloak development container. The operating handoff supplies the checklist.

Repository: https://github.com/hemach-git/sandhata. The user runs publication commands from [the GitHub guide](docs/11_GitHub_and_Collaboration_Guide.md). Protected files are ignored and excluded from container builds. SANDHĀTĀ is the display name; `sandhata` is the ASCII identifier. The branding acronym is original and is not a Sanskrit translation.

## Tracker uploads

In Tracker, expand **Upload Tracker**, download the CSV template, and supply one application per row (up to 1,000 rows / 5 MB). Only `title` and `company` are required. Optional columns: `status`, `original_url` (HTTPS), `applied_at`, `follow_up`, `notes`, `description`, `location` (free text, up to 400 characters), `work_arrangement` (OnSite, Hybrid, Remote, or blank). Older CSVs can omit both new columns. Status defaults to Saved. Dates use YYYY-MM-DD; application timestamps also accept ISO 8601 with a timezone, with UTC assumed when absent. Quote notes containing commas or newlines.

Preview and validate before importing. A bad row rejects the whole file. Repeated uploaded URLs (or title/company pairs when no URL exists) are skipped within the member workspace, preserving edits. Imported postings appear in Discover and Tracker; missing descriptions are marked partial. Search, filter status, select a tracker, inspect posting details and update status, location, work arrangement, notes, resume or follow-up. Uploads do not restore exported internal IDs, resume associations or complete historical events.

Trackers are stored in PostgreSQL without automatic expiry. Administrators can permanently delete a selected tracker and its history with a reason recorded in the audit log; account erasure also removes trackers. Posting snapshots remain after individual tracker deletion. Persistence depends on the configured database volume and backups. Deploy schema changes using `scripts/migrate.py --schema-only` before using administrator deletion.

## Manual tracker entry

In Tracker, use **New application · enter manually** for a LinkedIn lead, recruiter message or direct application. Title and employer are required. Add the posting URL, location, work arrangement, source, initial status, optional application and follow-up dates, description and notes. Saved is the default for leads that have not been submitted. **Save new application** saves the record and clears the new-entry form. Validation errors retain the draft. **Reset draft** clears only new-entry fields. **Reset unsaved changes** in the update form reloads the selected application’s stored values. Neither reset deletes records or status history. Repeated posting URLs are skipped without overwriting existing tracker data.

Tracker forms and reports include **Salary Description** (free text, up to 400 characters, such as "$95/hour W2" or "$150k base + bonus") and **Job Type** (Contract, Contract to Hire, Full Time, Part Time, Temporary, Freelance, Internship, Seasonal, Other, or Not specified). CSV headers are `salary_description` and `job_type`; both are optional for older files. Existing posting salary text is reused as Salary Description. Existing records default to an unspecified Job Type. Insights > Application report details and the cohort export include both fields.

**Recruiter** is optional free text (400 characters) for the contact, agency or interview coordinator, available in manual entry, updates, tracker tables, posting details, CSV upload/export and cohort reports. Older CSV files can omit `recruiter`. Save update changes the existing application. Unchanged saves do not write or add history; detail-only edits do not create status events. Only a changed status adds a status-history event. Reset unsaved changes rebuilds the form from stored data and shows an inline confirmation. Earlier status history remains preserved.

Signed-in screens use compact paired form fields, adjacent actions, bounded scrolling tables and side-by-side report charts/tables where space allows. Manual tracker entry starts collapsed. Narrow screens stack fields vertically. Workspace density and contrast styles are scoped to the signed-in marker, preserving the landing layout. Native table colours are retained instead of canvas inversion.
