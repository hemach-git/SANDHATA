# Sandhātā Project Charter

Version 0.1 | October 26 2026 | Prepared for Hema Chepuri | Design baseline

This document specifies the intended implementation. Application code, test results, live integrations, GitHub publication and production deployment are not established by this document. Dates are delivery targets in America/New_York, subject to the release gates.

## Purpose and decision

Build a private career intelligence workspace that reduces repeated job research, makes resume alignment explainable, and records application progress. The owner is the initial user and acceptance reviewer. Premium job portals remain part of the user's search workflow; supported feeds and assisted imports bring their results into one workspace.

Sandhātā is the display name; sandhata is the technical identifier. SANDHĀTĀ expands to Search, Analyze, Navigate, Discover, Highlight, Apply, Track, Advance. This English brand expansion is separate from the Sanskrit inspiration. Domain and trademark availability have not been established.

## FDE delivery framework

Embed means observe the owner's search and application workflow and capture real examples. Solve means deliver one complete job to resume to tracker path. Generalize means separate connector contracts, evidence schemas and metrics so more sources can be added. Productize means verify privacy, recovery, deployment, operating guides and release evidence. These phases overlap within the two-day target; an unpassed gate remains open.

## Outcomes and measurement

| Outcome | Initial target | Evidence |
| --- | --- | --- |
| Useful workflow | Import, compare and save one real job end to end | Owner walkthrough |
| Evidence integrity | Every displayed requirement judgment has a citation or unknown label | Reviewed evaluation set |
| Durable tracking | Status and notes survive restart | Persistence test |
| Original wording | Stored description retains source wording | Text comparison |
| Time saved | Measure baseline and application-assisted task time | Five timed owner trials |

Time savings and interview outcomes are hypotheses until measured. Fit is an alignment measure, not a probability of employment.

## Roles and decisions

The owner supplies example jobs, resumes, access choices and final acceptance. The implementation collaborator prepares code, documentation, test evidence and release candidates. The deployment operator may be the owner. No paid plan or public hosting purchase is presumed. GitHub destination is https://github.com/hemach-git/sandhata; initial visibility must be checked before publication.

## Schedule and success boundary

Target October 26: agreed baseline and functional local vertical slice. Target October 27: integrated personal-use release and private production candidate. Documentation preparation consumes this same time budget. Scope is reduced before evidence gates are waived; final release may move if access or critical defects remain unresolved.

## Constraints and assumptions

One owner, one application instance and modest data volume. Text PDF and DOCX resumes are supported initially. Remotive automatic ingestion is available through its documented public API; LinkedIn, Ladders and Indeed use assisted import unless appropriate programmatic access is established. An available model and its data-handling mode are prerequisites for AI comparison.

## Exit criteria

All P0 acceptance cases pass; no open critical privacy or data-loss defect; matching evaluations satisfy the release rubric; backup restore is demonstrated; deployment evidence is captured if a hosted release is claimed. The owner can export data and explain what each score means. Code, docs and versioned evidence identify the same release commit.
