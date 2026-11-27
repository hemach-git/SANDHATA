# SANDHĀTĀ Risks Decisions and Release Evidence

Version 0.2 | October 26 2026 | Prepared for Hema Chepuri | Design baseline

This document specifies the intended implementation. Application code, test results, live integrations, GitHub publication and production deployment are not established by this document. Dates are delivery targets in America/New_York, subject to the release gates.

## Current baseline

The owner selected SANDHĀTĀ with ASCII identifier sandhata, requested paired Markdown and DOCX documents, and created https://github.com/hemach-git/sandhata. The proposed implementation is an invite-only user Streamlit application with OIDC, explicit authorization, PostgreSQL RLS, bounded agent coordination and assisted premium imports. A local pilot is implemented; document 23 records its tested subset and remaining gates. GitHub network commands will be run collaboratively by the owner. Public branding clearance and hosting selection remain open.

## Risk register

| Risk | Impact | Mitigation and owner |
| --- | --- | --- |
| Premium account lacks API rights | Automated source coverage reduced | Assisted import; owner verifies approved access |
| Two-day capacity overrun | Scope or date missed | Vertical slice first; collaborator reports remaining work |
| Model fabricates evidence | Misleading fit judgment | Literal validation, reviewed evals, suppress invalid score |
| Resume privacy leak | Protected data disclosure | Protected storage, redaction, no personal data in Git |
| Database data loss | Tracker unavailable | Consistent backup, restore drill, one-host topology |
| UI fails quality target | Poor usability | Visual gate and early owner walkthrough |
| Weak extraction on PDFs | Incomplete comparison | Parse preview, unknown labels, OCR deferred |
| Name collision | Rebranding work | Domain/trademark check before public brand launch |
| Production host not ready | Hosted release delayed | Accurate local pilot label; host remains prerequisite |

## Decision log

D01 uses the FDE sequence Embed, Solve, Generalize, Productize, adapted to the owner's accelerated path. D02 separates application data and history from the finance project. D03 preserves original descriptions and versions. D04 keeps eligibility outside the average fit score. D05 implements owner-scoped PostgreSQL lexical RAG before embeddings. D06 makes MCP local/read-only. D07 uses descriptive analytics and truthful small-sample reporting. D08 keeps product branding configurable so a later name change does not require schema migration.

## Open decisions

Select local or hosted model after hardware and privacy review. Select production host, domain and authentication provider. Confirm repository visibility. Confirm whether an approved protected API exists for any premium source. Obtain owner sample jobs/resumes without committing them. These are implementation inputs rather than reasons to stop independent document preparation.

## Release evidence ledger

| Gate | Required evidence | Baseline state |
| --- | --- | --- |
| Document preparation | Matched MD/DOCX and visual QA report | Generated and checked during authoring; consult manifest |
| Source publication | Local SHA matches remote SHA | Pending owner Git commands |
| Local application | Setup and end-to-end workflow evidence | Local synthetic import, resume and comparison walkthrough verified |
| Tests | Commit-linked test report | 62 automated cases passed; see verification/application_tests.txt |
| AI evals | Dataset, versions and threshold results | Three local synthetic smoke cases; full reviewed benchmark pending |
| UI review | Screenshots and owner walkthrough | Local synthetic browser walkthrough; full accessibility audit pending |
| Recovery | Timed restore and integrity report | Encrypted backup and isolated database restore verified |
| Production | URL, access check, health and deployed SHA | Not deployed |

## Source and naming notes

SANDHĀTĀ draws inspiration from the Vishnu Sahasranama, with an interpreted connection between actions and their results. The English acronym is an original product expansion, not a literal translation. Traditional commentary varies. See https://www.sadagopan.org/ebook/pdf/Vishnu%20Sahasranama%20v1.pdf. Prior naming research found existing uses of Sandhi AI and Sthiraa; no domain/trademark clearance is claimed for the selected name.

## Verified source references

Access checked October 26 2026. Recheck access conditions before enabling a connector.

- Remotive API: https://github.com/remotive-com/remote-jobs-api
- Greenhouse Job Board API: https://docs.greenhouse.io/job-board.html
- Lever Postings API: https://github.com/lever/postings-api
- Ashby public postings: https://developers.ashbyhq.com/docs/public-job-posting-api
- LinkedIn automated activity policy: https://www.linkedin.com/help/linkedin/answer/a1340567/automated-activity-on-linkedin?lang=en
- Ladders terms: https://www.theladders.com/corporate/terms
- Indeed developer agreement: https://docs.indeed.com/legal-terms/developer-agreement
- LangGraph overview: https://docs.langchain.com/oss/python/langgraph/overview
- Streamlit container deployment: https://docs.streamlit.io/deploy/tutorials/docker
- MCP security: https://modelcontextprotocol.io/docs/2025-11-25/tutorials/security/security_best_practices
- Promptfoo assertions: https://www.promptfoo.dev/docs/configuration/expected-outputs/
- Langfuse self hosting: https://langfuse.com/self-hosting

## User scope change and release risks

ADR06 supersedes personal-only SQLite storage with PostgreSQL RLS. ADR07 requires invite-only OIDC plus service authorization. ADR08 defines member/admin roles and protected career data. ADR09 reserves administrative mutations for deterministic, audited services. ADR10 makes account isolation, revocation and concurrent-session tests release blockers.

New risks are leaked shared caches, reused connection scope, exposed object URLs, stale sessions, overprivileged admin tools and backups that reactivate suspended accounts. Mitigate them with owner-keyed caches, transaction-local scope, authorized downloads, auth_version checks, metadata-only admin queries and restore-time revocation replay. Infrastructure operators still have privileged access to storage; application role boundaries cannot remove that trust.

The two-day estimate must be reforecast after the authenticated two-account slice. Public registration, shared resumes, cross-user collaboration, remote MCP and automatic portal-account sharing are excluded. Updated user implementation, admin UI, isolation tests and deployment remain planned until evidence is recorded.

Additional checked references: Streamlit OIDC https://docs.streamlit.io/develop/concepts/connections/authentication ; PostgreSQL RLS https://www.postgresql.org/docs/18/ddl-rowsecurity.html ; Keycloak administration https://www.keycloak.org/docs/latest/server_admin/ . OIDC supplies identity, not application authorization. PostgreSQL owners/superusers/BYPASSRLS roles can bypass ordinary row policies, so the runtime role must not have those privileges.

ADR11, November 26 2026, owner decision: administrators have full access to member resumes, cover letters and other uploaded documents. Every view, download, status change and deletion requires a reason and is audited. This narrows the protection in ADR08 for uploaded documents only. Row-level security stays owner-only; access runs through administrator functions. Agents, MCP, jobs, tracker records and comparisons remain owner-scoped. Members are told in the document library. Residual risk: the reason is not independently reviewed and members cannot yet see their own access history.
