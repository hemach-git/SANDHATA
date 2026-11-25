# SANDHĀTĀ Career Intelligence

**Search, Analyze, Navigate, Discover, Highlight, Apply, Track, Advance.**

An invite-only user job-search workspace with protected resumes, original posting snapshots, evidence-grounded comparisons, an application tracker, analytics and an administrator console.

## Current release

Version 0.2 is a working localhost pilot. It uses real Keycloak OIDC, PostgreSQL forced row-level security, Streamlit, a durable LangGraph comparison worker, local Ollama, Plotly, and authenticated protected downloads. Automated tests use a separate disposable database. AI comparisons remain experimental pending the full reviewed evaluation dataset. Public production deployment is not complete.

Start with [the implementation and operating handoff](docs/23_Implementation_and_Operating_Handoff.md), then [the document index](docs/00_Document_Index.md). Paired Word files are in `deliverables/word`. Design documents record the intended target; document 23 records the implemented subset and release limits.

## Run locally on Windows

Prerequisites: Python 3.12, Docker Desktop/Engine, Git and Ollama with an installed compatible structured-output model. Use a separate checkout outside BRIHASPATI.

```powershell
Set-Location -LiteralPath 'C:\Users\Chepuri\Documents\ChatGPT\SANDHATA'
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

## Deployment and GitHub

Current operation is local to this home computer, with individual user logins. Use a separate browser profile per person and sign out when switching users. AWS is a future deployment target; the CHAKRA AWS account/profile is excluded. See [the AWS deployment guide](docs/24_AWS_Deployment_Guide.md) and `deploy/aws/foundation.json` for the isolated infrastructure foundation. Read-only STS and CloudFormation template validation passed; no AWS infrastructure has been created. A future separate AWS setup, domain and budget will be supplied when deployment resumes.

`Dockerfile`, `compose.production.yaml` and `deploy/Caddyfile` package the application tier. Production requires actual DNS/host access, a production OIDC provider, PostgreSQL roles, persistent storage and protected secrets. Do not expose the local Keycloak development container. The operating handoff supplies the checklist.

Repository: https://github.com/hemach-git/sandhata. The user runs publication commands from [the GitHub guide](docs/11_GitHub_and_Collaboration_Guide.md). Protected files are ignored and excluded from container builds. SANDHĀTĀ is the display name; `sandhata` is the ASCII identifier. The branding acronym is original and is not a Sanskrit translation.
