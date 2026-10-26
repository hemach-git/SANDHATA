# Sandhātā MCP and Integration Design

Version 0.1 | October 26 2026 | Prepared for Hema Chepuri | Design baseline

This document specifies the intended implementation. Application code, test results, live integrations, GitHub publication and production deployment are not established by this document. Dates are delivery targets in America/New_York, subject to the release gates.

## Integration policy

MCP exposes controlled application capabilities to a compatible local client. It does not grant access to premium job portals or make prohibited extraction permissible. Provider connectors remain ordinary application services with explicit capabilities and freshness policies.

## Source capability matrix

| Source | Initial mode | Data and constraint |
| --- | --- | --- |
| Remotive | Public API, cached | Description and source URL; 24 hour delayed feed; max four scheduled fetches daily |
| Greenhouse | Board-scoped public GET | Known employer token; request content=true |
| Lever | Employer-scoped postings API | Description sections and URLs; no global full-text search |
| Ashby | Public employer-board API | Description and optional compensation where supplied |
| LinkedIn | Browser search link and manual import | Premium account is not assumed developer access |
| Ladders | Browser search link and manual import | Automated access excluded from baseline |
| Indeed | Browser search link and manual import | Approved integration access required for API expansion |

Remotive requires attribution and backlinks. Its private paid API is separate from ordinary website access. For manual imports, record user_import provenance, original URL, pasted text and time. Email ingestion is deferred; an alert snippet is not a complete job description. Preserve the original portal link and an employer application URL separately when both are known.

## Connector contract

ConnectorCapabilities describes search, full_description, salary, scope and minimum_refresh_interval. fetch_jobs(profile, cursor) returns normalized candidates plus raw source payloads, pagination and errors. HTTP calls use timeouts, source-specific backoff, bounded concurrency and sanitized logs. A connector never invents omitted salary or location. The caller can display partial source results and stale cache status.

## MCP tools for v1

| Tool | Input | Output |
| --- | --- | --- |
| search_saved_jobs | query, filters, limit 1 to 20 | Job summaries and evidence references |
| get_job_detail | job_id, optional description_version_id | Stored description, source and completeness |
| get_match_assessment | assessment_id | Validated assessment for exact input versions |
| get_tracker_summary | date range, group_by allowlist | SQL aggregates with definitions |

Transport is local stdio launched by the owner, with a fixed application data path. Write tools, raw resume download, shell execution and arbitrary URL fetch are not exposed. Tool descriptions disclose read-only behavior and bounded result sizes. Error objects distinguish not_found, invalid_input, unavailable and access_denied without returning stack traces or paths.

## MCP security and evolution

Use the official SDK and test against the chosen client. Do not forward arbitrary access tokens to upstream providers. Validate scopes and record allowed tools. Remote MCP is deferred; adding it requires authentication, transport authorization, origin checks as applicable, TLS and token-audience controls from the current MCP specification. Treat tool results and external descriptions as untrusted data. See the MCP security reference linked in document 21.

## Acceptance and expansion

Contract tests prove schema validity, limit enforcement, missing-record handling and read-only operation. A local smoke test lists tools and reads one synthetic job. Source acceptance requires one real call with attribution and a recorded access review. A connector listed in the architecture but not exercised is marked planned. Future premium APIs must have documented access, permitted storage and a tested refresh policy before activation.
