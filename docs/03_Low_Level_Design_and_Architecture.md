# SANDHĀTĀ Low Level Design and Architecture

Version 0.2 | October 26 2026 | Prepared for Hema Chepuri | Design baseline

This document specifies the intended implementation. Application code, test results, live integrations, GitHub publication and production deployment are not established by this document. Dates are delivery targets in America/New_York, subject to the release gates.

## Architecture decision

Use one Streamlit application with OpenID Connect sign-in, a membership and authorization service, bounded LangGraph workflows, and PostgreSQL with row-level security and full-text search. Protected file storage holds originals under opaque user-scoped keys. A separate worker polls durable tasks. The first deployment targets one invited user household with ten test accounts and five concurrent sessions; capacity must be measured before launch.

![Application architecture](assets/architecture.png)

The browser calls presentation functions, which validate typed commands and invoke services. Services resolve a trusted Principal and own database transactions. No browser-supplied owner identifier establishes access. Agents receive read-only evidence and return schema-validated proposals. Only deterministic services update tracker state. External content cannot issue commands or select tools. Hosted deployment places authentication and TLS before the application; the application port is not publicly reachable.

## Proposed source layout

```text
SANDHATA/
  app.py                    Streamlit navigation and page composition
  src/sandhata/
    config.py               validated environment and paths
    domain/                 Pydantic commands and results
    db/                     SQLAlchemy models and migrations
    services/               intake, matching, tracker and analytics
    connectors/             remotive, employer feeds and manual imports
    agents/                 coordinator, intake, resume, fit and career
    retrieval/              passage indexing and evidence lookup
    worker.py               persisted task polling and leases
    mcp_server.py           read-only stdio adapter
  tests/                    unit, integration and UI cases
  evals/                    synthetic fixtures and result records
  deploy/                   container and protected-host configuration
```

These paths describe intended application code. The initial document package does not claim they exist.

## Data model

All IDs are UUID strings; timestamps are stored in UTC and grouped using each member's saved timezone. Every protected row carries tenant_id and owner_user_id. Composite foreign keys include tenant and owner to prevent mismatched parent references. Resume originals, database dumps and credentials never enter Git. Public feed cache data is separate from protected searches, imported descriptions and saved records.

| Entity | Key fields and constraints |
| --- | --- |
| SearchProfile | id, label, filters_json, hard_filters_json, version |
| Job | id, normalized title/company, location, workplace type, active state |
| JobSource | job_id, provider, provider_job_id, original_url, employer_url, last_seen; unique provider and provider_job_id |
| DescriptionVersion | id, job_id, raw_html, plain_text, hash, fetched_at, completeness, provenance |
| ResumeVersion | id, label, hash, protected file path, parsed text, parser_version, created_at |
| Passage | id, parent_type/id/version, section, offsets, text; FTS document |
| MatchAssessment | id, resume_version_id, description_version_id, rubric/model/prompt versions, evidence_json, score, coverage |
| Application | id, job_id, resume_version_id, status, applied_at, notes; unique tenant_id, owner_user_id and job_id for the current tracker item |
| StatusEvent | id, application_id, previous/new status, occurred_at, recorded_at, request_id, actor |
| TaskRun | id, kind, state, lease_until, attempts, checkpoint, error_code, trace_id |
| FollowUp | id, application_id, due_at, completed_at, user text |

![Data relationships](assets/data_model.png)

## Service contracts

search_jobs(profile_id, refresh=False) returns jobs, source outcomes and freshness. import_job(source, url, description, request_id) returns a canonical job and description version. upload_resume(bytes, filename, label) returns a resume version and parse report. compare(job_id, description_version_id, resume_version_id, request_id) returns a task ID. update_status(application_id, new_status, occurred_at, request_id) returns a status event. search_saved(query, filters, limit) returns typed evidence. All outputs distinguish success, partial, unavailable and invalid input.

Every service takes a server-resolved Principal containing user_id, tenant_id, current role, membership state and auth_version. Request IDs are unique within tenant/user/operation and make writes idempotent. Repeating a comparison with identical version and policy inputs reuses a valid cached result. A stale source snapshot is never silently substituted for a new description.

## Fit contract and arithmetic

Extract atomic requirements with category, importance, job quote and offsets. Match each to a resume quote with offsets and status supported, partial, not_evidenced or unknown. Validate quotes against stored text. Supported earns 1, partial earns 0.5, not_evidenced earns 0. Unknown has no asserted score and reduces evidence coverage.

Default category weights are required skills 40, responsibilities and experience 30, preferred skills 15, explicit education or certification 10, and domain 5. Categories absent from the job are omitted and remaining weights renormalized. Within each category use equal atomic requirement weights for rubric v1. Overall score is 100 times the weighted fraction supported over assessed weights. Coverage is assessed weight divided by all applicable requirement weight. Below 80 percent coverage or with incomplete description, show a provisional score; below 50 percent suppress the overall percentage and show evidence only. A missing resume statement is not proof that the user lacks a skill. Eligibility constraints are independent pass, fail or unknown flags and do not disappear inside the average.

## Transactions and failures

Import validates then inserts canonical/source/version/index changes in one transaction. Resume file is written to a temporary path, hashed, parsed, then atomically moved with compensating cleanup on database failure. Tracker update and history append share one transaction. Worker claims tasks using a lease; a crash expires the lease and bounded recovery retries the task. PostgreSQL transactions and row locks protect writes. Workers claim tasks using leases and SKIP LOCKED; each task stores immutable tenant/user scope. The worker rechecks active membership and auth_version before every protected step. Suspension cancels queued work and prevents new model calls; already completed outputs are not served after access is revoked.

## Security and operating limits

Uploads allow text PDF and DOCX, maximum 10 MB and 50 pages as initial configurable limits. Reject mismatched magic types, encrypted files and oversized archives. Render escaped text or sanitized HTML without script execution. Fetch only supported HTTPS connector endpoints; validate redirect destinations and block protected/local addresses for user URLs. Set initial request timeout 15 seconds, two retries with jitter, max 50 candidates and 20 model comparisons per run. These are configuration defaults to validate, not measured capacity.

## Architecture tradeoffs

PostgreSQL adds setup and backup work but is the user-release baseline for concurrent access and defense-in-depth isolation. SQLite is no longer a supported production design. A single host remains a capacity and availability constraint. Streamlit accelerates the workflow; a React frontend becomes a separate decision if the visual acceptance gate cannot be met. FastAPI is deferred because v1 needs no independent public API. The MCP adapter calls the same services and does not add a second business implementation.

## Identity authorization and privacy

Streamlit st.login identifies the OIDC subject; authorization is a separate application responsibility. Use validated issuer and subject as the stable identity key, not editable email or a role claim alone. An invitation must be accepted through a verified intended identity before membership is activated. Bootstrap the first administrator from an out-of-band configured issuer/subject. No open registration or first-login administrator promotion is allowed.

Protected pages, callbacks, downloads, retrieval, exports, model calls, background steps and admin services resolve membership server-side. Suspended memberships fail closed. A request-local Principal is not a globally cached object. Sessions have an idle timeout policy of 30 minutes and an absolute application lifetime of eight hours as initial configurable defaults; the application checks these independently of the OIDC cookie lifetime. Role or account changes increment auth_version and invalidate application sessions and task authority.

PostgreSQL enables and forces RLS on protected tables. In each transaction the service uses transaction-local tenant/user settings from Principal. Policies use both USING and WITH CHECK; missing scope denies access. The application role is not a table owner, superuser or BYPASSRLS role. Migrations use a separate role. Connection pooling must reset scope after commit/rollback. RLS protects against accidental unscoped queries; trusted application services must still resist tampering and validate references.

Protected caches include tenant/user/version/policy in their keys. Shared caches contain only public provider payloads and never resume text, personalized search requests, matches or imported protected descriptions. Files are stored as tenant/user/opaque-ID objects, resolved through an authorized download service. Neither a filesystem path nor a signed link is accepted as authority to another member's file. No protected content enters global Streamlit resource caches.


## Account and administration records

| Entity | Required fields and constraints |
| --- | --- |
| Tenant | id, label, state; initially one user household |
| User | id, oidc_issuer, oidc_subject, display_name, timezone; unique issuer and subject |
| Membership | tenant_id, user_id, role member/admin, state, auth_version; unique tenant/user |
| Invitation | tenant_id, intended_identity_hash, role, token_hash, expiry, redeemed_at, inviter |
| AdminAuditEvent | tenant_id, actor_id, action, target opaque ID, reason, before/after safe metadata, timestamp, trace ID |
| MaintenanceJob | tenant_id, kind, scope, preview counts, request_id, state, lease, confirmation and result |
| QuotaPolicy | tenant_id, optional user_id, upload/storage/model-call limits and effective version |

AdminAuditEvent is append-only to application roles. Retain security/admin audit metadata for 90 days initially and sanitized operational logs for 14 days. Database operators remain privileged and require separate operational controls. The last active administrator cannot be suspended, deleted or demoted; a transaction-level tenant lock serializes these changes.

Admin services expose safe account and resource metadata through dedicated queries, not a general all-users database browser. Routine account administration cannot read resumes, personal notes, match evidence or job-search questions. Account erasure is an exceptional, explicitly confirmed lifecycle operation with an audit trail and backup tombstone handling.
