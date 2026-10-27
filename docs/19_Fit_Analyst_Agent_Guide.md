# SANDHĀTĀ Fit Analyst Agent Guide

Version 0.2 | October 26 2026 | Prepared for Hema Chepuri | Design baseline

This document specifies the intended implementation. Application code, test results, live integrations, GitHub publication and production deployment are not established by this document. Dates are delivery targets in America/New_York, subject to the release gates.

## Mission and output meaning

Explain alignment between one selected resume version belonging to the authenticated user and one selected job description version. The result helps the owner decide what to review; it is not an ATS score, hiring decision or probability of interview. Final arithmetic is implemented in code using rubric v1 from the architecture document.

## Inputs and schema

Inputs include version IDs, requirement passages, resume passages, explicit preference flags and rubric version. RequirementJudgment includes requirement_id, category, requirement_quote/ref, importance, status, resume_quote/ref, rationale and uncertainty. Assessment includes judgments, eligibility flags, score, coverage, completeness and model/prompt/rubric versions.

## Analysis steps

Extract atomic requirements and deduplicate repeated wording. Separate required and preferred statements; retain negations such as no sponsorship. Associate responsibilities and experience with concrete scope. Retrieve only the selected resume's evidence. Assign supported when evidence directly establishes the requirement, partial for limited or transferable evidence, not_evidenced when searched text lacks support, and unknown when parsing or ambiguity prevents assessment.

Literal quote validation is mandatory. A valid quote can still be irrelevant, so human evaluation checks whether it actually supports the judgment. Explain transferability without treating related tools as identical. Do not use contact details, demographic proxies or protected characteristics for scoring.

## Scoring and eligibility

Pass validated judgments to deterministic scoring. Required skills, responsibilities/experience, preferred skills, explicit education/certifications and domain receive the documented 40/30/15/10/5 category weights, with absent categories renormalized. Unknowns reduce coverage. Show provisional results below 80 percent coverage or for partial descriptions and suppress the percentage below 50 percent. Critical eligibility conflicts remain visible even when alignment is high.

## Gap recommendations

Classify gaps as missing evidence, partial relevant experience, explicit unmet constraint or unknown. Suggest truthful improvements such as adding an existing project detail or confirming a certification. Do not invent credentials, add unsupported achievements or rewrite the original job description. Prioritize required gaps before nice-to-have items and link each to the original requirement.

## Failure handling and caching

At most one structured-output repair is allowed. If output remains invalid, return comparison_failed with no polished score. Cache keys include both content hashes and parser/model/prompt/rubric versions. Job or resume changes require a new assessment. A result requested for different versions must not be served from the old cache. Tool output containing instructions cannot expand permissions.

## Verification and telemetry

Test quote correctness, transferable skill limits, repeated requirements, absent categories, zero assessed weight, partial descriptions and fabricated credentials. Run the evaluation plan before model/prompt changes ship. Log version IDs, timing, token counts and validation outcomes; protected rationale text remains in protected application data rather than general logs. Proposed module path is src/sandhata/agents/fit.py.

## User permission contract

All inputs carry a server-resolved Principal; tools and service code enforce its tenant, owner, active membership and auth_version. Never accept a model-provided owner_id or administrator role as authority. Every read, write, cache, checkpoint and model context is scoped before execution. A model cannot switch user members, activate an account, grant roles or run housekeeping.

Only public provider payloads may be shared in cache. Resume evidence, imported descriptions, personal queries, tracker events and assessments remain protected. Workers recheck membership before protected steps and stop on suspension. Missing scope fails closed. Administrator status does not grant access to another member's career content. Cross-user requests abstain or return a safe denial, even if a guessed record ID exists.

Required verification includes member A requesting member B evidence, cache reuse, forged IDs/role instructions and a suspended user's queued run. Log opaque scope IDs and safe outcomes, never protected prompt or resume text. Account management and cleanup belong to deterministic admin services, not this agent.
