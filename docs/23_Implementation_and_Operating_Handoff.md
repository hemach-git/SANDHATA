# SANDHĀTĀ Implementation and Operating Handoff

Version 0.2 | October 26 2026 | Prepared for Hema Chepuri | Local pilot

SANDHĀTĀ now runs as a local application in its own repository outside BRIHASPATI. This document records the implemented behavior and operating steps. The earlier design documents remain the target specification; their planned features are not automatically release claims. Public user access from other devices and production acceptance remain pending.

## Implemented application

| Area | Implemented behavior | Verification and limits |
| --- | --- | --- |
| User identity | Keycloak OIDC sign in, identity-bound expiring invitations, independent member workspaces | Real administrator sign in tested; service isolation tested with three identities |
| Authorization | Transaction-local tenant and owner scope, forced PostgreSQL RLS, composite owner foreign keys, current membership checks | Cross-user job, resume, search, download and administrator denials tested |
| Discovery | Remotive cached public feed and local filters; known Greenhouse, Lever and Ashby employer adapters | Remotive HTTP 200 live check; employer coverage needs live certification per selected board |
| Premium sources | LinkedIn, Indeed and Ladders search links and full-description manual import | No collection of portal credentials or automated scraping |
| Resumes | PDF and DOCX parsing, immutable versions, original file download and deletion | Size, format, archive and ownership checks; scanned PDF OCR is not implemented |
| Comparison | Selected document versions, typed extraction, literal quote validation, deterministic scoring, one repair | Local model smoke checks only; comparisons are experimental |
| Tracker | Saved, Applied, Interviewing, Offer, Hired, Rejected, Withdrawn and Cancelled statuses with dated events and notes | Explicit submissions only, idempotent service writes, protected exports |
| Analytics | Status donut, weekly applications, observed event counts, source and resume cohort tables, latest per-job gaps | Descriptive outcomes; no predictions or causal resume-effect claims |
| Memory and retrieval | Saved profiles, immutable document text, PostgreSQL full-text passages with offsets | Lexical retrieval; no embedding service or conversational answer generator |
| MCP | Local stdio tools search_my_jobs, search_my_evidence and list_my_tracker | Fifteen-minute owner capability; role changes revoke authority; no writes |
| Administration | Users, roles, quotas, suspension, invitations and revocation, safe audit, usage, previewed housekeeping | Administrator UI does not grant access to another member's career content |
| Operations | Durable task leases, cancellation, JSON metadata logs, heartbeat, encrypted backup and isolated restore | No external telemetry platform or notification channel configured |

## Start and access

The project root is C:/Users/Chepuri/Documents/ChatGPT/SANDHATA. The entry URL is http://localhost:18501 (the local identity provider displays the actual sign-in form within the landing layout), the protected download service at localhost:18502, PostgreSQL at 127.0.0.1:15432, and local Keycloak at localhost:18180. These ports are deliberately loopback-only. Existing CHAKRA and BRIHASPATI services are separate.

Use scripts/start_local.ps1 to start the local services. It preserves existing settings. Credentials are only in runtime/LOCAL_ACCESS.md. The three generated local identities are admin, member-a and member-b. Use a separate browser profile for each user member. Sign out and close all SANDHĀTĀ tabs when handing the computer to someone else; downloaded files also remain on the shared computer. Each new sign-in explicitly requests identity-provider login instead of silently reusing the previous person's SSO identity. Only the administrator is initially an application member; an administrator creates an invitation for the exact verified identity email before a member redeems it after sign in. For actual relatives, provision individual identity-provider accounts, then invite them. Never share the administrator login.

In Discover, enter title, company, skill, location and salary filters. Search Remotive or open a premium source in your own browser. Copy the entire original description into the import form and retain its original HTTPS URL. Partial descriptions must be marked partial. In Resume Library, upload a text PDF or DOCX and inspect the parsed preview. Select that version in the sidebar, queue a comparison, and inspect Diagnostics for the result and literal citations.

Save an opportunity to Tracker, then explicitly record Applied and subsequent events with their actual dates. Insights reports applied-date cohorts in the configured account timezone. A Hired event does not invent a missing Offer or Interview event. A score measures resume alignment with extracted requirements, not hiring probability. Missing resume evidence does not prove a missing skill.

## Verification evidence

The reproducible automated command is .venv/Scripts/python.exe scripts/run_tests.py. It creates and removes only a randomly named sandhata_test_ database and never uses the active user database as a test target. The current recorded run has 61 passing cases. Raw results are in deliverables/verification/application_tests.txt.

Three synthetic live model cases used local gpt-oss:20b: direct evidence passed, a missing-skill case passed, and an injection case was safely withheld after validation. See deliverables/verification/live_model_evals.json for actual results, traces and latency. This is a smoke evaluation, not the planned reviewed 48-pair dataset, held-out benchmark or proof of semantic accuracy. Broad usefulness gates remain unpassed. An earlier unsupported literal quote was rejected and prompted the bounded repair fix.

The encrypted application backup was decrypted and restored into a separate sandhata_restore_ database. Table counts and forced RLS were checked before that disposable database was removed. See deliverables/verification/backup_restore.json. The application container built successfully after adding a platform marker for the Windows-only dependency. Local UI verification uses synthetic content labeled SAMPLE; no real job application was submitted.

## Operations and recovery

Run scripts/backup.py with the local operator environment. It locks application writes while exporting a consistent database snapshot and copying referenced originals. The archive is encrypted with AES-GCM and stored under backups. Keep runtime/backup.key separately in a secure vault; without this key the backup is unrecoverable. Do not commit the key or archive. Copy encrypted backups off the machine through your own secure storage process. Identity-provider state and secrets require their own protected backup.

For a real restore, stop all app writers, preserve current deletion_tombstones separately, decrypt into a protected staging directory, restore into a new database and verify counts, file hashes and RLS. Reconcile newer account and resume tombstones before reconnecting users; an old backup must not resurrect erased records. Restore identity-provider state with its own runbook, rotate sessions and test two-member isolation. The supplied script automates an isolated verification drill; it intentionally does not overwrite the live database. Backup retention and off-machine scheduling are operator tasks.

Diagnostics shows protected comparison runs and evidence. Admin Console shows metadata and resource counts, not resumes or protected tracker notes. Check runtime/data/worker_heartbeat and operations.jsonl for worker health. Local model outages leave saved jobs and Tracker usable. Cancellation prevents future inference steps and result publication; an already executing local inference may finish before its result is discarded. Old task and expired invitation cleanup uses the administrator preview and confirmation workflow.

## Production application tier

The production Compose file packages web, protected download API, worker and Caddy TLS proxy. Supply a real SANDHATA_HOSTNAME with DNS pointing to a Linux host. Provision production PostgreSQL and a production OIDC issuer independently; the local Keycloak start-dev service and H2 storage are not a production identity deployment. Create the app and worker roles, apply schema.sql and admin_schema.sql using migration credentials, then seed the first administrator from a verified issuer and subject. Do not reuse synthetic local subjects or bootstrap passwords.

Create runtime/production/app.env containing only the app database URL, tenant UUID, OIDC issuer, app HTTPS URL, API HTTPS base URL ending in /private, local/private model endpoint and model name. Create worker.env with the same non-secret settings and worker database URL. Neither runtime environment may contain PostgreSQL superuser, migration or identity-provider operator credentials. The application container does not load the development .env file.

Mount a production Streamlit secrets.toml at runtime/production/secrets.toml with a new cookie secret, confidential OIDC client secret, HTTPS redirect_uri ending in /oauth2callback, provider discovery URL and openid profile email scopes. Register that exact redirect with the provider. Give runtime/production/data owner UID 10001, restrict its host permissions, and use encrypted persistent storage. Keep only Caddy ports 80 and 443 public; database, model and app services stay protected.

Build with docker build -t sandhata:0.2.0 . and launch with docker compose -f compose.production.yaml up -d after creating the protected settings and production dependencies. Verify HTTPS, OIDC, invitations, two independent members, revoked access, protected downloads, five concurrent sessions and off-host restore on that actual host. Pin deployment image digests after target verification. No host, DNS domain or production issuer has been supplied, so no public endpoint is claimed.

## GitHub collaboration and next gates

All publication commands must run from the separate sandhata repository. Review git status, git diff --check and the staged file list. Confirm .env, .streamlit/secrets.toml, runtime, backups and actual career data are excluded. Commit source, tests, documentation and safe verification records together. Then run git push -u origin main and compare git rev-parse HEAD with git ls-remote origin refs/heads/main. A local commit is not remote publication. The owner requested to run GitHub commands collaboratively; the command guide remains the publication handoff.

Remaining acceptance work is the full human-reviewed evaluation dataset, real-user acceptance, selected employer board live certification, full responsive and accessibility audit, scheduled off-host backups with identity-provider recovery, and target-host production verification. These gaps limit the release to a local pilot with experimental AI; they are not silently marked complete. The open-source extension path remains pgvector for measured retrieval gaps, OpenTelemetry and Langfuse for richer traces, and a React UI if Streamlit no longer fits the product needs.
