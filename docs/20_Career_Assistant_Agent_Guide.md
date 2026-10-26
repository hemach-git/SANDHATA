# Sandhātā Career Assistant Agent Guide

Version 0.1 | October 26 2026 | Prepared for Hema Chepuri | Design baseline

This document specifies the intended implementation. Application code, test results, live integrations, GitHub publication and production deployment are not established by this document. Dates are delivery targets in America/New_York, subject to the release gates.

## Mission and authority

Help the owner navigate saved jobs, understand computed analytics and plan follow-ups. The assistant answers from saved evidence and deterministic metrics. It may propose a tracker change, but changes occur only through an explicit user action handled by the tracker service. It does not contact recruiters, send email or submit applications.

## Inputs and outputs

Inputs are the owner's question, date/filter context and authorized entity scope. Output Answer contains answer text, EvidenceRefs, metric query metadata, limitations and optional proposed action. Structured questions about counts, dates or status route to SQL; job/resume content questions route to scoped retrieval. Unknown or deleted evidence produces a clear abstention.

## Tools

Allowed reads are search_saved_jobs, get_job_detail, get_match_assessment and get_tracker_summary. Read-only tools can also be exposed via local MCP. An internal update_status service is available to the UI after explicit command validation; it is not exposed as an unrestricted model tool in v1. The assistant cannot access raw uploads outside selected retrieval scope or perform arbitrary web browsing.

## Guidance rules

For which jobs fit me best, ask the data layer for assessments tied to the currently selected resume and show coverage/eligibility beside scores. For how many interviews this month, use distinct applications and the metric's date definition, not snippet counting. For what should I do next, show user-entered follow-ups and evidence-based suggestions with dates, not fabricated employer deadlines.

## Tracker semantics

Current states include Saved, Preparing, Applied, Screening, Interviewing, Offer, Hired, Rejected, Withdrawn and Cancelled. Posting availability is separate. Users can revisit states and correct dates; event history records what happened and when it was recorded. Applied status requires the user to record submission; opening the source link is insufficient. The resume used for application remains pinned even after a new upload.

## Example answers and uncertainty

If asked which resume works better with only two applications per version, show counts and a small-sample limitation; do not declare a winner. If a job disappeared from a failed source refresh, say availability unknown. If asked to add a credential not in the resume, explain that the saved evidence does not support it and offer to record an owner-confirmed correction.

## Verification and observability

Evaluate answer citations, correct SQL routing, date cohorts, abstention and absence of unauthorized mutations. Test timezone edges and repeated user updates. Log intent class, chosen service, record IDs, query duration and outcome without private question text by default. Acceptance includes correct answers over the synthetic analytics fixture and a trace showing that an unapproved suggestion never mutated tracker state. Proposed module path is src/sandhata/agents/career.py.
