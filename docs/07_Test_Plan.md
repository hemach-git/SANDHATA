# SANDHĀTĀ Test Plan

Version 0.2 | October 26 2026 | Prepared for Hema Chepuri | Design baseline

This document specifies the intended implementation. Application code, test results, live integrations, GitHub publication and production deployment are not established by this document. Dates are delivery targets in America/New_York, subject to the release gates.

## Verification strategy

Test contracts, calculations, storage and failure behavior with deterministic fixtures. Use separate synthetic data for automated tests. Run live provider tests only when explicitly enabled and respect source cache policies. The release record must include commands, commit, environment, timestamp, test counts and failure summaries. No test has been run merely because it is specified here.

## Critical test cases

| ID | Scenario | Expected result |
| --- | --- | --- |
| T01 | Import valid full job twice | One canonical/source record; unchanged version reused |
| T02 | Same job description changes | New immutable version; old assessment remains versioned |
| T03 | Remotive timeout or rate response | Partial result and stale label; no refresh storm |
| T04 | Premium page needs login | Assisted import offered; no fabricated description |
| T05 | Upload text PDF and DOCX | Text and parser version stored; preview available |
| T06 | Encrypted, oversized or malformed upload | Clear rejection; no partial file leak |
| T07 | Select resume A then B | Distinct assessment keys and visible selected version |
| T08 | Evidence quote not in resume | Invalid judgment rejected or unknown |
| T09 | Absent category and unknown evidence | Correct renormalization and coverage behavior |
| T10 | Salary omitted or different periods | No invented pay; preserve units; comparisons qualify |
| T11 | Repeat tracker request after UI rerun | Single status event for request ID |
| T12 | Reopen or correct status | Auditable event history, correct current state |
| T13 | Worker killed during comparison | Lease expires; bounded recovery without duplicate write |
| T14 | Resume deleted | File, passages and protected assessment evidence removed |
| T15 | HTML script or prompt injection in job | Script not executed; embedded instructions ignored |
| T16 | User URL targets localhost or redirect | Fetch blocked before protected network access |
| T17 | App restarted | Jobs, resumes and tracker persist |
| T18 | Analytics fixed fixture | Counts and denominators match expected values |
| T19 | MCP unknown tool or oversized request | Bounded schema error; no write capability |
| T20 | Backup restored on clean directory | Integrity check and representative hash match |

## Layers and fixtures

Unit tests cover filter normalization, duplicate keys, quote offsets, scoring, date conversion and cohort arithmetic. Integration tests use a temporary PostgreSQL database and file root with connector HTTP responses recorded from permitted or synthetic examples. UI tests exercise upload, resume selector, evidence expansion, tracker editing, global search and chart filters. Use Streamlit's app testing surface where supported and browser tests for interactions that need a browser.

## Visual and accessibility review

Review widths 1440, 1024 and 390 pixels, keyboard navigation, visible focus, readable contrast, long titles and missing fields. Every major page needs empty, loading, success and failure examples. Numeric fit scores have labels and explanations; charts have a table alternative. Do not rely on color alone for status or errors. Record screenshots with synthetic data and actual review findings.

## Performance and resilience targets

On the declared test machine with 500 saved jobs, target p95 saved-job search under 1 second across 30 queries and ordinary tracker writes under 1 second. Model comparison latency is measured separately by model/hardware; show progress and cancellation if it exceeds 10 seconds. These are initial engineering targets, not current measurements. Disk-full and database-lock cases must leave transactions consistent and present a useful error.

## Release gate

All critical T cases pass; no unresolved critical privacy, security or data-loss defect; eval gate passes; owner can complete the real workflow. A skipped live connector test is reported as not verified, with the affected capability labeled accordingly. Regression failures need reproduction, fix and a targeted rerun before broad release validation.

## User isolation and administrator cases

| ID | Scenario | Required result |
| --- | --- | --- |
| T21 | Uninvited OIDC identity | Sign-in establishes no application membership |
| T22 | Replayed, expired or wrong-identity invitation | Redemption denied without activating membership |
| T23 | Member A guesses member B record IDs | All service, page, download and export paths deny access |
| T24 | Two users issue identical queries | Protected caches and assessments remain separate |
| T25 | Missing RLS scope or cross-owner foreign key | Query/write denied; no data leaked through error details |
| T26 | Member invokes admin callback directly | Denied server-side; hiding navigation alone is insufficient |
| T27 | Suspend or demote an active account | Next protected operation and queued step denied |
| T28 | Concurrent removal of final administrators | Serialized change preserves at least one active admin |
| T29 | Retry maintenance command | One bounded idempotent job and audit record |
| T30 | Cleanup preview and cancellation | Counts scoped correctly; cancellation prevents further batches |
| T31 | Five simultaneous sessions | No identity, file, cache, worker or connection-pool scope leakage |
| T32 | Logout/login as another member in same browser | No prior member state or download becomes visible |

Use two synthetic member accounts, an administrator and an uninvited identity. Run integration tests against a real disposable PostgreSQL instance with the production application role and forced RLS. Include error/rollback connection-pool reuse, manipulated owner fields and CSV/MCP/private-file paths. Repeat key checks after backup restore and schema migration. No user-accessible release passes while T21 through T32 are failed or unrun.
