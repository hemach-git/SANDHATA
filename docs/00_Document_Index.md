# Sandhātā FDE Document Index

Version 0.1 | October 26 2026 | Prepared for Hema Chepuri | Design baseline

This document specifies the intended implementation. Application code, test results, live integrations, GitHub publication and production deployment are not established by this document. Dates are delivery targets in America/New_York, subject to the release gates.

## Package purpose

This package establishes the delivery baseline for Sandhātā Career Intelligence, a private agent-assisted job search and application workspace. It contains project governance, implementation contracts, diagrams, tests and AI evaluation plans, retrieval, integrations, interface design, analytics, operations and five individual agent guides. It supports the accelerated October 26 to 27 2026 target without representing planned capabilities as completed software.

## Reading order

Read the charter and scope first, then architecture and sequence flows. Use the build plan as the implementation checklist. Test and evaluation plans define release evidence; deployment and operations define the handoff. Agent guides inherit the architecture contracts and never override source access or privacy requirements.

## Documents

| Document | Markdown source | Word version |
| --- | --- | --- |
| Sandhātā Project Charter | [Markdown](01_Project_Charter.md) | [Word](../deliverables/word/01_Project_Charter.docx) |
| Sandhātā Scope and Statement of Work | [Markdown](02_Scope_and_Statement_of_Work.md) | [Word](../deliverables/word/02_Scope_and_Statement_of_Work.docx) |
| Sandhātā Low Level Design and Architecture | [Markdown](03_Low_Level_Design_and_Architecture.md) | [Word](../deliverables/word/03_Low_Level_Design_and_Architecture.docx) |
| Sandhātā Sequence Flows | [Markdown](04_Sequence_Flows.md) | [Word](../deliverables/word/04_Sequence_Flows.docx) |
| Sandhātā Technology Stack and Decisions | [Markdown](05_Technology_Stack_and_Decisions.md) | [Word](../deliverables/word/05_Technology_Stack_and_Decisions.docx) |
| Sandhātā Design and Accelerated Build Plan | [Markdown](06_Design_and_Accelerated_Build_Plan.md) | [Word](../deliverables/word/06_Design_and_Accelerated_Build_Plan.docx) |
| Sandhātā Test Plan | [Markdown](07_Test_Plan.md) | [Word](../deliverables/word/07_Test_Plan.docx) |
| Sandhātā AI Evaluation Plan | [Markdown](08_AI_Evaluation_Plan.md) | [Word](../deliverables/word/08_AI_Evaluation_Plan.docx) |
| Sandhātā Memory and RAG Design | [Markdown](09_Memory_and_RAG_Design.md) | [Word](../deliverables/word/09_Memory_and_RAG_Design.docx) |
| Sandhātā MCP and Integration Design | [Markdown](10_MCP_and_Integration_Design.md) | [Word](../deliverables/word/10_MCP_and_Integration_Design.docx) |
| Sandhātā GitHub and Collaboration Guide | [Markdown](11_GitHub_and_Collaboration_Guide.md) | [Word](../deliverables/word/11_GitHub_and_Collaboration_Guide.docx) |
| Sandhātā Observability and Operations Guide | [Markdown](12_Observability_and_Operations.md) | [Word](../deliverables/word/12_Observability_and_Operations.docx) |
| Sandhātā UI Design and User Guide | [Markdown](13_UI_Design_and_User_Guide.md) | [Word](../deliverables/word/13_UI_Design_and_User_Guide.docx) |
| Sandhātā Analytics Requirements and Design | [Markdown](14_Analytics_Requirements_and_Design.md) | [Word](../deliverables/word/14_Analytics_Requirements_and_Design.docx) |
| Sandhātā Production Deployment and Release Guide | [Markdown](15_Production_Deployment_and_Release.md) | [Word](../deliverables/word/15_Production_Deployment_and_Release.docx) |
| Sandhātā Coordinator Agent Guide | [Markdown](16_Coordinator_Agent_Guide.md) | [Word](../deliverables/word/16_Coordinator_Agent_Guide.docx) |
| Sandhātā Search and Intake Agent Guide | [Markdown](17_Search_and_Intake_Agent_Guide.md) | [Word](../deliverables/word/17_Search_and_Intake_Agent_Guide.docx) |
| Sandhātā Resume Analyst Agent Guide | [Markdown](18_Resume_Analyst_Agent_Guide.md) | [Word](../deliverables/word/18_Resume_Analyst_Agent_Guide.docx) |
| Sandhātā Fit Analyst Agent Guide | [Markdown](19_Fit_Analyst_Agent_Guide.md) | [Word](../deliverables/word/19_Fit_Analyst_Agent_Guide.docx) |
| Sandhātā Career Assistant Agent Guide | [Markdown](20_Career_Assistant_Agent_Guide.md) | [Word](../deliverables/word/20_Career_Assistant_Agent_Guide.docx) |
| Sandhātā Risks Decisions and Release Evidence | [Markdown](21_Risks_Decisions_and_Release_Evidence.md) | [Word](../deliverables/word/21_Risks_Decisions_and_Release_Evidence.docx) |

## Format and change discipline

Markdown is the editable source of record. The Word versions contain the same prose, tables and diagrams, formatted for review. A generator keeps the paired content aligned. Regenerate Word files after source changes; do not independently edit both formats without reconciling them. Scripts, diagram assets and the package manifest are included for reproducibility. The Word files are in deliverables/word and the paired Markdown files are in docs.

## Implementation status

The current deliverable is the FDE document baseline and repository preparation. Tests, evaluations, MCP tools, UI, production deployment and live integrations described here require implementation and evidence. Concept diagrams and mockups are labeled as designs. The GitHub guide contains owner-run publication commands for the separate repository.
