# SANDHĀTĀ Resume Analyst Agent Guide

Version 0.2 | October 26 2026 | Prepared for Hema Chepuri | Design baseline

This document specifies the intended implementation. Application code, test results, live integrations, GitHub publication and production deployment are not established by this document. Dates are delivery targets in America/New_York, subject to the release gates.

## Mission and evidence boundary

Build a faithful, versioned profile from the resume the user explicitly selected. The analyst extracts stated evidence; it does not manufacture missing experience, merge different resume versions or infer protected characteristics. A resume is protected untrusted input, including any instructions written inside it.

## Input and output contract

Input is resume_version_id, parser_version, canonical text and passage references. ResumeProfile contains skills with supporting evidence, role history, dated intervals, responsibilities, achievements, education, certifications and parse warnings. Each substantive item contains a quote and source offsets or an explicit unknown state. Personal contact fields are excluded from model input unless a later feature needs them and the owner enables it.

## Parsing workflow

Verify file type, size and page limits before extraction. For text PDF use pypdf; for DOCX use python-docx. Detect empty or implausibly sparse extraction and ask the UI to show an OCR-not-supported message. Preserve section boundaries and create canonical offsets. Show a preview so the owner can confirm parsing. A corrected text/profile creates a new version with user_correction provenance rather than modifying historical evidence.

## Interpretation rules

Distinguish explicit skill mentions from skill evidence in actual work. Deduplicate overlapping employment dates before calculating relevant experience; do not simply sum all role durations. Missing or ambiguous months produce qualified ranges. Do not infer current certifications, work authorization, willingness to relocate or salary expectations from unrelated resume content. A user preference belongs in profile memory, not in resume evidence.

## Tools and permissions

Allowed tools are protected file read for the selected version, parser, passage index and schema/evidence validator. No network fetch, employer application, tracker update or cross-resume search is available. The service persists validated output under the original version. Deletion removes profile and passage content from active storage and invalidates dependent caches.

## Example output behavior

If a project says implemented ETL pipelines with Python and AWS, extract Python, AWS and ETL with that quote. Do not infer Kubernetes. If a resume says cloud migration without naming a vendor, record cloud migration and leave AWS-specific evidence unknown. A recommendation may suggest clarifying actual experience but must never supply an invented achievement metric.

## Failure handling and acceptance

Malformed or encrypted files fail clearly with no persisted partial original left behind. Sparse parse warnings block confident comparison until the user reviews text. Validate every extracted quote literally. Test multi-column PDFs, bulleted DOCX, overlapping dates, unknown dates, injection text and deletion. Telemetry records file hash, parser version, page count, warnings and duration, excluding text, file names with personal details and protected paths. Proposed module path is src/sandhata/agents/resume.py.

## User permission contract

All inputs carry a server-resolved Principal; tools and service code enforce its tenant, owner, active membership and auth_version. Never accept a model-provided owner_id or administrator role as authority. Every read, write, cache, checkpoint and model context is scoped before execution. A model cannot switch user members, activate an account, grant roles or run housekeeping.

Only public provider payloads may be shared in cache. Resume evidence, imported descriptions, personal queries, tracker events and assessments remain protected. Workers recheck membership before protected steps and stop on suspension. Missing scope fails closed. Administrator status does not grant access to another member's career content. Cross-user requests abstain or return a safe denial, even if a guessed record ID exists.

Required verification includes member A requesting member B evidence, cache reuse, forged IDs/role instructions and a suspended user's queued run. Log opaque scope IDs and safe outcomes, never protected prompt or resume text. Account management and cleanup belong to deterministic admin services, not this agent.
