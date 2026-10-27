# SANDHĀTĀ FDE Document Index

Version 0.2 | October 26 2026 | Prepared for Hema Chepuri | Design baseline

This document specifies the intended implementation. Application code, test results, live integrations, GitHub publication and production deployment are not established by this document. Dates are delivery targets in America/New_York, subject to the release gates.

## Package purpose

This package establishes the delivery baseline for SANDHĀTĀ Career Intelligence, an invite-only user agent-assisted job search and application workspace. It contains project governance, implementation contracts, diagrams, tests and AI evaluation plans, retrieval, integrations, interface design, analytics, operations, five individual agent guides, and a dedicated administrator and user access guide. It supports the accelerated October 26 to 27 2026 target without representing planned capabilities as completed software.

## Reading order

Read the charter and scope first, then architecture and sequence flows. Use the build plan as the implementation checklist. Test and evaluation plans define release evidence; deployment and operations define the handoff. Agent guides inherit the architecture contracts and never override source access or privacy requirements.

## Documents

| Document | Markdown source | Word version |
| --- | --- | --- |
| SANDHĀTĀ Project Charter | [Markdown](01_Project_Charter.md) | [Word](../deliverables/word/01_Project_Charter.docx) |
| SANDHĀTĀ Scope and Statement of Work | [Markdown](02_Scope_and_Statement_of_Work.md) | [Word](../deliverables/word/02_Scope_and_Statement_of_Work.docx) |
| SANDHĀTĀ Low Level Design and Architecture | [Markdown](03_Low_Level_Design_and_Architecture.md) | [Word](../deliverables/word/03_Low_Level_Design_and_Architecture.docx) |
| SANDHĀTĀ Sequence Flows | [Markdown](04_Sequence_Flows.md) | [Word](../deliverables/word/04_Sequence_Flows.docx) |
| SANDHĀTĀ Technology Stack and Decisions | [Markdown](05_Technology_Stack_and_Decisions.md) | [Word](../deliverables/word/05_Technology_Stack_and_Decisions.docx) |
| SANDHĀTĀ Design and Accelerated Build Plan | [Markdown](06_Design_and_Accelerated_Build_Plan.md) | [Word](../deliverables/word/06_Design_and_Accelerated_Build_Plan.docx) |
| SANDHĀTĀ Test Plan | [Markdown](07_Test_Plan.md) | [Word](../deliverables/word/07_Test_Plan.docx) |
| SANDHĀTĀ AI Evaluation Plan | [Markdown](08_AI_Evaluation_Plan.md) | [Word](../deliverables/word/08_AI_Evaluation_Plan.docx) |
| SANDHĀTĀ Memory and RAG Design | [Markdown](09_Memory_and_RAG_Design.md) | [Word](../deliverables/word/09_Memory_and_RAG_Design.docx) |
| SANDHĀTĀ MCP and Integration Design | [Markdown](10_MCP_and_Integration_Design.md) | [Word](../deliverables/word/10_MCP_and_Integration_Design.docx) |
| SANDHĀTĀ GitHub and Collaboration Guide | [Markdown](11_GitHub_and_Collaboration_Guide.md) | [Word](../deliverables/word/11_GitHub_and_Collaboration_Guide.docx) |
| SANDHĀTĀ Observability and Operations Guide | [Markdown](12_Observability_and_Operations.md) | [Word](../deliverables/word/12_Observability_and_Operations.docx) |
| SANDHĀTĀ UI Design and User Guide | [Markdown](13_UI_Design_and_User_Guide.md) | [Word](../deliverables/word/13_UI_Design_and_User_Guide.docx) |
| SANDHĀTĀ Analytics Requirements and Design | [Markdown](14_Analytics_Requirements_and_Design.md) | [Word](../deliverables/word/14_Analytics_Requirements_and_Design.docx) |
| SANDHĀTĀ Production Deployment and Release Guide | [Markdown](15_Production_Deployment_and_Release.md) | [Word](../deliverables/word/15_Production_Deployment_and_Release.docx) |
| SANDHĀTĀ Coordinator Agent Guide | [Markdown](16_Coordinator_Agent_Guide.md) | [Word](../deliverables/word/16_Coordinator_Agent_Guide.docx) |
| SANDHĀTĀ Search and Intake Agent Guide | [Markdown](17_Search_and_Intake_Agent_Guide.md) | [Word](../deliverables/word/17_Search_and_Intake_Agent_Guide.docx) |
| SANDHĀTĀ Resume Analyst Agent Guide | [Markdown](18_Resume_Analyst_Agent_Guide.md) | [Word](../deliverables/word/18_Resume_Analyst_Agent_Guide.docx) |
| SANDHĀTĀ Fit Analyst Agent Guide | [Markdown](19_Fit_Analyst_Agent_Guide.md) | [Word](../deliverables/word/19_Fit_Analyst_Agent_Guide.docx) |
| SANDHĀTĀ Career Assistant Agent Guide | [Markdown](20_Career_Assistant_Agent_Guide.md) | [Word](../deliverables/word/20_Career_Assistant_Agent_Guide.docx) |
| SANDHĀTĀ Risks Decisions and Release Evidence | [Markdown](21_Risks_Decisions_and_Release_Evidence.md) | [Word](../deliverables/word/21_Risks_Decisions_and_Release_Evidence.docx) |
| SANDHĀTĀ Administrator and User Access Guide | [Markdown](22_Administrator_and_User_Access_Guide.md) | [Word](../deliverables/word/22_Administrator_and_User_Access_Guide.docx) |
| SANDHĀTĀ Implementation and Operating Handoff | [Markdown](23_Implementation_and_Operating_Handoff.md) | [Word](../deliverables/word/23_Implementation_and_Operating_Handoff.docx) |
| SANDHĀTĀ AWS Deployment Guide | [Markdown](24_AWS_Deployment_Guide.md) | [Word](../deliverables/word/24_AWS_Deployment_Guide.docx) |

## Format and change discipline

Markdown is the editable source of record. The Word versions contain the same prose, tables and diagrams, formatted for review. A generator keeps the paired content aligned. Regenerate Word files after source changes; do not independently edit both formats without reconciling them. Scripts, diagram assets and the package manifest are included for reproducibility. The Word files are in deliverables/word and the paired Markdown files are in docs.

## Implementation status

The package contains the FDE target specification and a working local pilot. Document 23 records the implemented subset, verification evidence and remaining acceptance gates. AI comparisons are experimental; public deployment is pending. Concept diagrams remain labeled as designs. The GitHub guide contains owner-run publication commands for the separate repository.
