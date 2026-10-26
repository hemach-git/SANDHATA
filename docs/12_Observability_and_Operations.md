# Sandhātā Observability and Operations Guide

Version 0.1 | October 26 2026 | Prepared for Hema Chepuri | Design baseline

This document specifies the intended implementation. Application code, test results, live integrations, GitHub publication and production deployment are not established by this document. Dates are delivery targets in America/New_York, subject to the release gates.

## Operational questions

The owner must be able to tell whether a search completed, which connector failed, which evidence produced a score, and whether a tracker edit persisted. A Diagnostics page reads run records and safe aggregates. Logs support investigation without retaining private career content.

## Event contract

Each event contains UTC timestamp, level, event_name, trace_id, run_id, component, operation, duration_ms, outcome, retry_count, error_code and application version. Connector events include provider and cache_age_seconds. Model events include model/prompt/rubric versions, input/output token counts when known, and validation outcome. Use opaque entity IDs instead of names, resume text, descriptions, emails, cookies or tokens.

## Metrics and proposed alerts

| Signal | Meaning | Initial action threshold |
| --- | --- | --- |
| Source refresh age | Time since successful fetch | Remotive stale beyond 24 hours; warning only |
| Task failures | Failed runs over last 20 completed runs | More than 20 percent; inspect connector/model |
| Invalid evidence | Quote or schema validation failures | Any repeated failure blocks affected comparison |
| Queue age | Oldest pending task age | Over five minutes; inspect worker |
| Storage | Free disk and backup age | Under 1 GB or backup older than 48 hours |
| Tracker write failure | Transaction failed | Immediate visible error; preserve user edit |

Thresholds are initial operating policies and require tuning. A public-feed delay is distinct from application cache age. No external notification channel is connected by default; warnings appear in Diagnostics and logs.

## Trace and cost review

A trace links planner, connector, parse, retrieval, validation and score events. Store policy versions and content hashes, allowing replay with private fixtures without dumping content into telemetry. Hosted-model cost is calculated only when provider/model pricing is configured and current; otherwise display tokens and unknown cost. Local inference reports duration and model identity, not a fictional zero infrastructure cost.

## Runbook

For no search results, inspect filters, source scope and source outcomes; distinguish empty from unavailable. For stalled comparison, check worker lease, model reachability and task attempts. For invalid output, inspect error code and selected version IDs, then reproduce with a redacted fixture. For failed writes, check disk space and database locks before retry. For lost files, stop worker and restore a consistent database/files snapshot together.

## Retention and escalation

Keep sanitized logs for 14 days and checkpoints seven days initially. Retention cleanup is a tested maintenance operation. If private data appears in telemetry, disable logging of affected fields, restrict access, remove exposed copies and document scope before resuming. If a source rejects access, disable its connector and use assisted import. If a model fabricates evidence, suppress the assessment and rerun evaluation before enabling it.

## Future tracing platform

Adopt OpenTelemetry and Langfuse core when richer cross-component debugging is needed and resource requirements fit the host. Review which Langfuse features require a license and configure redaction before export. This is an extension path; the two-day baseline depends on structured logs and durable run records.
