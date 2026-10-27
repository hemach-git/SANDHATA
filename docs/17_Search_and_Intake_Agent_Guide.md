# SANDHĀTĀ Search and Intake Agent Guide

Version 0.2 | October 26 2026 | Prepared for Hema Chepuri | Design baseline

This document specifies the intended implementation. Application code, test results, live integrations, GitHub publication and production deployment are not established by this document. Dates are delivery targets in America/New_York, subject to the release gates.

## Mission

Translate search preferences into supported connector requests, then produce canonical jobs with original descriptions and provenance. Assist with premium-portal imports without implying unavailable API access. Language-model planning may interpret intent; connector execution, validation and persistence remain deterministic.

## Input and output contract

SearchProfile includes titles, role families, companies, required/preferred skills, locations, workplace types, salary/currency/period, seniority and exclusions. Hard constraints and soft preferences are separate. Output JobCandidate includes provider, provider ID, source URL, employer URL when known, raw payload, description, retrieved_at, completeness and normalized fields with extraction provenance.

## Steps and tools

Validate inputs and normalize aliases without changing the user's intent. Determine supported filters for each connector and apply unsupported filters locally with a warning where needed. Query Remotive only when its cache allows refresh. Known employer-board tokens scope Greenhouse, Lever and Ashby calls. Manual import accepts source, original URL and full pasted text, then previews extracted fields for correction.

Store original content before summarizing. Never compose a full description from search snippets. Source salary and location remain unknown if omitted. Preserve location restrictions for remote roles. Record inferred fields as inferred. Validate URLs, redirects and permitted hosts. Sanitize display HTML and do not execute source scripts.

## Deduplication and freshness

Exact provider IDs are authoritative within a source. Same canonical employer URL or matching employer requisition is strong cross-source evidence. Similar title/company/location alone creates a duplicate suggestion rather than silently merging different openings. Keep all source links. Content hashes create description versions only when canonical text changes. A source failure does not mark every cached job closed; distinguish not_seen, unknown and confirmed_closed.

## Limits and failure handling

Initial connector timeout is 15 seconds with at most two transient retries, respecting provider limits. A 401, forbidden page or login wall becomes unavailable/assisted_import; do not retry indefinitely. A user import with insufficient text is saved as partial only after showing that status. Model extraction failures leave original text usable and normalized fields editable.

## Quality examples

A remote role restricted to US residents is not worldwide. A salary string of $80 per hour is not $80,000 annually. A card missing posted_at says not disclosed rather than displaying retrieval time as posting time. A listing from LinkedIn with an employer application URL retains both sources and the user's discovery attribution.

## Verification and observability

Tests cover missing fields, source outages, duplicate imports, changed descriptions, blocked URLs, rate limits and source attribution. Evaluate query relevance against reviewed search profiles. Log provider, duration, cache age, candidate count and error code; avoid full payloads and cookies. Proposed module path is src/sandhata/agents/intake.py and connectors live in src/sandhata/connectors.

## User permission contract

All inputs carry a server-resolved Principal; tools and service code enforce its tenant, owner, active membership and auth_version. Never accept a model-provided owner_id or administrator role as authority. Every read, write, cache, checkpoint and model context is scoped before execution. A model cannot switch user members, activate an account, grant roles or run housekeeping.

Only public provider payloads may be shared in cache. Resume evidence, imported descriptions, personal queries, tracker events and assessments remain protected. Workers recheck membership before protected steps and stop on suspension. Missing scope fails closed. Administrator status does not grant access to another member's career content. Cross-user requests abstain or return a safe denial, even if a guessed record ID exists.

Required verification includes member A requesting member B evidence, cache reuse, forged IDs/role instructions and a suspended user's queued run. Log opaque scope IDs and safe outcomes, never protected prompt or resume text. Account management and cleanup belong to deterministic admin services, not this agent.
