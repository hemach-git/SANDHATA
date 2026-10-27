# SANDHĀTĀ Scope and Statement of Work

Version 0.2 | October 26 2026 | Prepared for Hema Chepuri | Design baseline

This document specifies the intended implementation. Application code, test results, live integrations, GitHub publication and production deployment are not established by this document. Dates are delivery targets in America/New_York, subject to the release gates.

## Delivery agreement

This is a technical scope baseline for an owner-built personal application, not a commercial contract or fee quotation. Delivery consists of source code, executable configuration, paired documentation, verification evidence and an operating handoff. Work begins with the documents, then implementation; documentation alone does not satisfy application acceptance.

## Requirements and acceptance

| ID | Requirement | Acceptance evidence |
| --- | --- | --- |
| R01 | Search profile for titles, companies, skills, location and salary | Save and reload filters; hard and soft preferences differ |
| R02 | Several supported sources and assisted premium imports | Remotive and one employer connector succeed; all four preferred sources can be recorded |
| R03 | Cards and original descriptions | Card opens stored full text; original URL and source visible |
| R04 | Resume library | Upload two text PDFs or DOCX files and select either |
| R05 | Fit and gaps | Selected resume version compared with selected description version |
| R06 | Tracker | Status, dates and notes survive restart; history retained |
| R07 | Analytics | Funnel, status chart, weekly trend and skill gaps reconcile with fixture |
| R08 | Internal search | Keyword search and structured filters find saved jobs and notes |
| R09 | Collaborating agents | Typed handoffs and persisted run trace demonstrate each module |
| R10 | Delivery engineering | Reproducible setup, tests, evals, observability and release runbook |
| R11 | Memory and RAG | Version-scoped evidence retrieval, citations and deletion propagation |
| R12 | MCP | Local read-only tools pass schema and privacy tests |
| R13 | UI quality | Empty, loading, partial, error and success states reviewed |
| R14 | Production operations | Protected deployment, restore and rollback evidenced before hosted claim |

## Included work packages

WP1 defines charter, contracts, data model and visual system. WP2 implements intake, resumes, matching and tracker. WP3 adds retrieval, analytics, local MCP and run diagnostics. WP4 verifies, packages, publishes to the separate repository and prepares or performs protected deployment when a host is available. Agent guides cover coordinator, intake, resume, fit and career assistance.

## Explicit limitations

No commitment to automated collection from paid LinkedIn, Ladders or Indeed sessions. No automatic employer submission, outreach, mailbox integration, browser extension, OCR, public self-service registration, cross-household collaboration or hiring prediction. Advanced analytics in v1 means descriptive cohort and pipeline analysis; predictive models require more data and validation.

## Delivery priorities

P0 is intake, full description fidelity, resume selection, evidence comparison, tracker durability, privacy and basic retrieval. P1 is analytics, read-only MCP, source expansion and release diagnostics. Production readiness and publication are separate gates. If time expires, unfinished P1 work is explicitly listed and the release stays a local pilot rather than being called fully complete.

## Dependencies and change control

Owner supplies representative resumes and jobs securely. Runtime, model endpoint, Git authentication and deployment access must be available. A new connector, hosting platform or UI framework change is estimated against the remaining two-day budget. Record changes in decisions with rationale, acceptance impact, owner and date. Acceptance is evidenced in the release checklist; no implied financial or business outcome warranty.

## Multi user scope and acceptance

| ID | Required capability | Acceptance evidence |
| --- | --- | --- |
| R15 | Invite-only user identities | Two members can sign in independently; an uninvited identity is denied |
| R16 | Protected user workspaces | Member A cannot search, download, compare or mutate member B records |
| R17 | Administrator console | Only active administrators can manage members and system operations |
| R18 | Revocation and permissions | Suspension or demotion blocks the next protected operation, including queued work |
| R19 | Audited housekeeping | Cleanup uses bounded previews, confirmation, leases and immutable audit events |
| R20 | User production gate | Concurrent-session, cache isolation, PostgreSQL RLS and restore tests pass |

R15 through R20 are P0 for a user release. The administrator guide in document 22 owns the detailed permissions and operating procedures. Routine administration excludes member career-content inspection and impersonation. Resume/job sharing between members is deferred; all imported and derived career records are protected by default.
