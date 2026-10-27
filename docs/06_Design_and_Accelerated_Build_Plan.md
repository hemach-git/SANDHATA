# SANDHĀTĀ Design and Accelerated Build Plan

Version 0.2 | October 26 2026 | Prepared for Hema Chepuri | Design baseline

This document specifies the intended implementation. Application code, test results, live integrations, GitHub publication and production deployment are not established by this document. Dates are delivery targets in America/New_York, subject to the release gates.

## Timebox and delivery strategy

The target is a complete local workflow in one to two focused working days starting October 26 2026. Documentation and verification consume the same capacity. Sixteen focused engineering hours are a planning estimate, not an assurance; live source access, hosting credentials and model behavior are external dependencies. Build a thin vertical slice before expanding connectors.

## Hour by hour plan

| Window | Work and dependency | Exit artifact |
| --- | --- | --- |
| Day 1 hours 1 to 2 | Baseline docs, schema, theme and reproducible setup | Charter and running shell |
| Day 1 hours 3 to 4 | Manual import and Remotive cache | Persisted original job and source |
| Day 1 hours 5 to 6 | Resume parser, selected versions and evidence contract | Two usable resume versions |
| Day 1 hours 7 to 8 | Comparison graph, validation and tracker slice | First end-to-end owner walkthrough |
| Day 2 hours 1 to 2 | Tracker history, FTS retrieval and worker recovery | Durable searchable workspace |
| Day 2 hours 3 to 4 | Analytics and one employer connector | Reconciled reports and source coverage |
| Day 2 hour 5 | Read-only MCP and diagnostics | Contract-tested local tools |
| Day 2 hours 6 to 7 | UI review, tests, evals and restore drill | Release evidence bundle |
| Day 2 hour 8 | Git publication and protected deployment if host ready | Tagged local release or verified deployment |

If document preparation or discovery exceeds the allocation, recalculate remaining work openly. Deferred connector breadth must be reflected in scope and release notes. A failed critical gate delays release; it is not relabeled as complete.

## Design order

First agree one example search profile and three example jobs. Sketch Discover, Details, Resume Library, Tracker, Insights and Diagnostics. Define card fields, empty/loading/error states and evidence table. Implement storage and service contracts before model prompting. Use synthetic fixtures until the privacy path is verified, then conduct the owner's real-data walkthrough locally.

## Proposed implementation milestones

M1 is deterministic import and persistence. M2 is one validated match with selected versions. M3 is tracker, retrieval and analytics. M4 is MCP, operations and release. Each milestone produces a small commit with tests or an explicit verification record. The separate Git repository includes only SANDHĀTĀ files; no finance-project credentials, data or history are copied.

## FDE gates

G0 Embed accepts the owner workflow and constraints. G1 Solve accepts a real end-to-end local slice. G2 Generalize accepts connector contracts, typed evidence and regression fixtures. G3 Productize accepts privacy, recovery, evaluations, visual review and operating guide. G4 Hosted verifies TLS, authentication, persistent storage, health and rollback on the actual target host. G4 may remain pending without preventing an accurately labeled local pilot.

## Engineering task dependencies

Canonical jobs precede description indexing; resume parsing precedes evidence validation; both version stores precede scoring. Status events precede analytics. Read-only services precede MCP. Container configuration follows a runnable application. A production DNS/TLS setup follows a selected host. The owner handles GitHub commands collaboratively; a push is verified by remote commit ID, not inferred from local commits.

## Review cadence

Review the first vertical slice immediately, then review after tracker and analytics integration. Maintain a live checklist of passed, failed and not-run cases. Record elapsed work, remaining scope and blocking dependency at each gate. No external outreach or application submission is part of these build activities.

## Revised user critical path

The original hourly table is an initial timebox, not a commitment that the expanded scope fits unchanged. Replace the first shell milestone with OIDC plus invite-only membership, PostgreSQL migrations and owner-scoped storage. The first vertical slice uses two independent member accounts. Implement the administrator account console and audit writes before shared deployment.

Day 1 priorities are identity setup, PostgreSQL/RLS, separate member storage, manual import and the first comparison. Day 2 priorities are revocation, admin housekeeping and diagnostics, tracker/analytics isolation, and user release verification. Source breadth, board-style tracker polish and optional semantic search yield time to these P0 requirements. Production remains pending if identity configuration, concurrency, isolation or recovery gates fail. A realistic reforecast must follow the first authenticated two-account slice.

G1 now requires two members to complete independent workflows. G2 includes owner-scoped connectors, caches, tasks and MCP identity. G3 includes admin authorization, last-admin protection and destructive-job confirmations. G4 requires authenticated user access, PostgreSQL recovery and deployment checks with at least five concurrent test sessions.
