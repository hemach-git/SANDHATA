"""Build the paired Markdown and Word FDE document set from one content source."""
from pathlib import Path
import re, json, zipfile, hashlib, argparse
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs'
WORD = ROOT / 'deliverables' / 'word'
ASSETS = DOCS / 'assets'
for p in (DOCS, WORD, ASSETS): p.mkdir(parents=True, exist_ok=True)

META = 'Version 0.1 | October 26 2026 | Prepared for Hema Chepuri | Design baseline'
STATUS = ('This document specifies the intended implementation. Application code, test results, '
          'live integrations, GitHub publication and production deployment are not established by this document. '
          'Dates are delivery targets in America/New_York, subject to the release gates.')
SOURCES = '''
## Verified source references

Access checked October 26 2026. Recheck access conditions before enabling a connector.

- Remotive API: https://github.com/remotive-com/remote-jobs-api
- Greenhouse Job Board API: https://docs.greenhouse.io/job-board.html
- Lever Postings API: https://github.com/lever/postings-api
- Ashby public postings: https://developers.ashbyhq.com/docs/public-job-posting-api
- LinkedIn automated activity policy: https://www.linkedin.com/help/linkedin/answer/a1340567/automated-activity-on-linkedin?lang=en
- Ladders terms: https://www.theladders.com/corporate/terms
- Indeed developer agreement: https://docs.indeed.com/legal-terms/developer-agreement
- LangGraph overview: https://docs.langchain.com/oss/python/langgraph/overview
- Streamlit container deployment: https://docs.streamlit.io/deploy/tutorials/docker
- MCP security: https://modelcontextprotocol.io/docs/2025-11-25/tutorials/security/security_best_practices
- Promptfoo assertions: https://www.promptfoo.dev/docs/configuration/expected-outputs/
- Langfuse self hosting: https://langfuse.com/self-hosting
'''

CONTENT = {}
def add(name, title, body):
    CONTENT[name] = f'# {title}\n\n{META}\n\n{STATUS}\n\n' + body.strip() + '\n'

add('01_Project_Charter', 'Sandhātā Project Charter', '''
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
''')

add('02_Scope_and_Statement_of_Work', 'Sandhātā Scope and Statement of Work', '''
## Delivery agreement

This is a technical scope baseline for an owner-built personal application, not a commercial contract or fee quotation. Delivery consists of source code, executable configuration, paired documentation, verification evidence and an operating handoff. Work begins with the documents, then implementation; documentation alone does not satisfy application acceptance.

## Requirements and acceptance

| ID | Requirement | Acceptance evidence |
| --- | --- | --- |
| R01 | Search profile for titles, companies, skills, location and salary | Save and reload filters; hard and soft preferences differ |
| R02 | Several supported sources and assisted premium imports | Remotive and one employer connector succeed; all four preferred sources can be recorded |
| R03 | Cards and original descriptions | Card opens stored full text; original URL and source visible |
| R04 | Resume library | Upload two text PDFs or DOCX files and select either |
| R05 | Fit and gaps | Selected resume version compared with selected description version |
| R06 | Tracker | Status, dates and notes survive restart; history retained |
| R07 | Analytics | Funnel, status chart, weekly trend and skill gaps reconcile with fixture |
| R08 | Internal search | Keyword search and structured filters find saved jobs and notes |
| R09 | Collaborating agents | Typed handoffs and persisted run trace demonstrate each module |
| R10 | Delivery engineering | Reproducible setup, tests, evals, observability and release runbook |
| R11 | Memory and RAG | Version-scoped evidence retrieval, citations and deletion propagation |
| R12 | MCP | Local read-only tools pass schema and privacy tests |
| R13 | UI quality | Empty, loading, partial, error and success states reviewed |
| R14 | Production operations | Private deployment, restore and rollback evidenced before hosted claim |

## Included work packages

WP1 defines charter, contracts, data model and visual system. WP2 implements intake, resumes, matching and tracker. WP3 adds retrieval, analytics, local MCP and run diagnostics. WP4 verifies, packages, publishes to the separate repository and prepares or performs private deployment when a host is available. Agent guides cover coordinator, intake, resume, fit and career assistance.

## Explicit limitations

No commitment to automated collection from paid LinkedIn, Ladders or Indeed sessions. No automatic employer submission, outreach, mailbox integration, browser extension, OCR, multi-user tenancy or hiring prediction. Advanced analytics in v1 means descriptive cohort and pipeline analysis; predictive models require more data and validation.

## Delivery priorities

P0 is intake, full description fidelity, resume selection, evidence comparison, tracker durability, privacy and basic retrieval. P1 is analytics, read-only MCP, source expansion and release diagnostics. Production readiness and publication are separate gates. If time expires, unfinished P1 work is explicitly listed and the release stays a local pilot rather than being called fully complete.

## Dependencies and change control

Owner supplies representative resumes and jobs privately. Runtime, model endpoint, Git authentication and deployment access must be available. A new connector, hosting platform or UI framework change is estimated against the remaining two-day budget. Record changes in decisions with rationale, acceptance impact, owner and date. Acceptance is evidenced in the release checklist; no implied financial or business outcome warranty.
''')

add('03_Low_Level_Design_and_Architecture', 'Sandhātā Low Level Design and Architecture', '''
## Architecture decision

Use one Python application with Streamlit presentation, domain services and a bounded LangGraph workflow. SQLite with FTS5 stores structured records and searchable passages; a private file directory holds resume originals. A separate worker process polls durable tasks so Streamlit reruns do not duplicate work. One database writer transaction at a time is sufficient for the personal-use workload.

![Application architecture](assets/architecture.png)

The browser calls presentation functions, which validate typed commands and invoke services. Services own database transactions. Agents receive read-only evidence and return schema-validated proposals. Only deterministic services update tracker state. External content cannot issue commands or select tools. Hosted deployment places authentication and TLS before the application; the application port is not publicly reachable.

## Proposed source layout

```text
sandhata/
  app.py                    Streamlit navigation and page composition
  src/sandhata/
    config.py               validated environment and paths
    domain/                 Pydantic commands and results
    db/                     SQLAlchemy models and migrations
    services/               intake, matching, tracker and analytics
    connectors/             remotive, employer feeds and manual imports
    agents/                 coordinator, intake, resume, fit and career
    retrieval/              passage indexing and evidence lookup
    worker.py               persisted task polling and leases
    mcp_server.py           read-only stdio adapter
  tests/                    unit, integration and UI cases
  evals/                    synthetic fixtures and result records
  deploy/                   container and private-host configuration
```

These paths describe intended application code. The initial document package does not claim they exist.

## Data model

All IDs are UUID strings; timestamps are UTC ISO 8601 and converted to the owner's display timezone. Foreign keys are enabled. Resume text is private. Database files and uploads never enter Git.

| Entity | Key fields and constraints |
| --- | --- |
| SearchProfile | id, label, filters_json, hard_filters_json, version |
| Job | id, normalized title/company, location, workplace type, active state |
| JobSource | job_id, provider, provider_job_id, original_url, employer_url, last_seen; unique provider and provider_job_id |
| DescriptionVersion | id, job_id, raw_html, plain_text, hash, fetched_at, completeness, provenance |
| ResumeVersion | id, label, hash, private file path, parsed text, parser_version, created_at |
| Passage | id, parent_type/id/version, section, offsets, text; FTS document |
| MatchAssessment | id, resume_version_id, description_version_id, rubric/model/prompt versions, evidence_json, score, coverage |
| Application | id, job_id, resume_version_id, status, applied_at, notes; one current tracker item per job |
| StatusEvent | id, application_id, previous/new status, occurred_at, recorded_at, request_id, actor |
| TaskRun | id, kind, state, lease_until, attempts, checkpoint, error_code, trace_id |
| FollowUp | id, application_id, due_at, completed_at, user text |

![Data relationships](assets/data_model.png)

## Service contracts

search_jobs(profile_id, refresh=False) returns jobs, source outcomes and freshness. import_job(source, url, description, request_id) returns a canonical job and description version. upload_resume(bytes, filename, label) returns a resume version and parse report. compare(job_id, description_version_id, resume_version_id, request_id) returns a task ID. update_status(application_id, new_status, occurred_at, request_id) returns a status event. search_saved(query, filters, limit) returns typed evidence. All outputs distinguish success, partial, unavailable and invalid input.

Request IDs make writes idempotent. Repeating a comparison with identical version and policy inputs reuses a valid cached result. A stale source snapshot is never silently substituted for a new description.

## Fit contract and arithmetic

Extract atomic requirements with category, importance, job quote and offsets. Match each to a resume quote with offsets and status supported, partial, not_evidenced or unknown. Validate quotes against stored text. Supported earns 1, partial earns 0.5, not_evidenced earns 0. Unknown has no asserted score and reduces evidence coverage.

Default category weights are required skills 40, responsibilities and experience 30, preferred skills 15, explicit education or certification 10, and domain 5. Categories absent from the job are omitted and remaining weights renormalized. Within each category use equal atomic requirement weights for rubric v1. Overall score is 100 times the weighted fraction supported over assessed weights. Coverage is assessed weight divided by all applicable requirement weight. Below 80 percent coverage or with incomplete description, show a provisional score; below 50 percent suppress the overall percentage and show evidence only. A missing resume statement is not proof that the user lacks a skill. Eligibility constraints are independent pass, fail or unknown flags and do not disappear inside the average.

## Transactions and failures

Import validates then inserts canonical/source/version/index changes in one transaction. Resume file is written to a temporary path, hashed, parsed, then atomically moved with compensating cleanup on database failure. Tracker update and history append share one transaction. Worker claims tasks using a lease; a crash expires the lease and bounded recovery retries the task. SQLite uses WAL, busy timeout and a local persistent disk; never put the live database on shared network storage.

## Security and operating limits

Uploads allow text PDF and DOCX, maximum 10 MB and 50 pages as initial configurable limits. Reject mismatched magic types, encrypted files and oversized archives. Render escaped text or sanitized HTML without script execution. Fetch only supported HTTPS connector endpoints; validate redirect destinations and block private/local addresses for user URLs. Set initial request timeout 15 seconds, two retries with jitter, max 50 candidates and 20 model comparisons per run. These are configuration defaults to validate, not measured capacity.

## Architecture tradeoffs

SQLite and a single host lower setup cost but do not provide horizontal scaling or high availability. Migrate to PostgreSQL before multiple app replicas. Streamlit accelerates the workflow; a React frontend becomes a separate decision if the visual acceptance gate cannot be met. FastAPI is deferred because v1 needs no independent public API. The MCP adapter calls the same services and does not add a second business implementation.
''')

add('04_Sequence_Flows', 'Sandhātā Sequence Flows', '''
## Flow conventions

The diagrams describe proposed runtime behavior. Solid calls are synchronous service work; a queued task ID separates long model processing from UI refreshes. Each operation uses a request or trace ID. Source failures produce partial results rather than discarding successful connectors.

## Search and import

![Search sequence](assets/sequence_search.png)

1. User saves hard constraints and ranking preferences, then requests refresh.
2. Coordinator loads the profile and connector capabilities. Remotive refresh uses the source cache and rate policy; manual-only sources receive external search links and an import form.
3. Connectors return provider IDs, source URLs, descriptions and retrieval metadata. Job Curator validates, normalizes and merges exact provider duplicates. Cross-source fuzzy matches are suggested unless strong employer/requisition evidence supports merging.
4. One transaction writes sources, original description versions and searchable passages. Cards show source, last checked time, completeness and missing fields.
5. Failure path: timeout records an error and retains the prior cache with a stale label. A login wall returns assisted import, not fabricated text.

## Resume comparison

![Comparison sequence](assets/sequence_compare.png)

1. User chooses a specific job description and resume version.
2. Service verifies both exist and are not pending deletion. A unique cache key includes content hashes, parser, rubric, prompt and model version.
3. Worker retrieves evidence only from the selected versions. Fit Analyst emits atomic requirements, evidence and uncertainty.
4. Validator confirms quote offsets, schema and category membership. One repair attempt is allowed; continued invalid output fails the task.
5. Scoring code computes alignment and coverage. The stored result retains the complete evidence trail. A model outage leaves the job and tracker usable and exposes retry.

## Tracker update and analytics

![Tracker sequence](assets/sequence_tracker.png)

1. User changes status, supplies event date and selects the resume used when applying.
2. Service validates the command and detects duplicate request IDs. It supports revisiting a status with a new event; it does not delete previous history.
3. Transaction updates current application state and appends the event. Applied date is stored separately and is not inferred from link clicks.
4. Analytics reads committed events and updates charts for the selected date cohort. Explanations use computed aggregates with metric definitions.

## Retrieval and MCP

A local MCP client calls search_saved_jobs or get_job_detail. The adapter validates bounded arguments and invokes read-only services. Retrieval filters owner and selected entity/version before ranking, returns passage IDs and citations, and refuses unavailable records. The assistant answers from evidence or says the record does not establish the answer. Local MCP has no status mutation or automatic application tool in v1.

## Delete and restore

Deleting a resume removes its original, parsed text, passages, checkpoints and dependent private match evidence from active storage. Application history may retain a tombstoned resume label without content. Backup expiry and restore-time deletion replay prevent reintroducing deleted content. A restore uses a stopped app or a consistent SQLite backup; integrity and representative file hashes are checked before the worker restarts.
''')

add('05_Technology_Stack_and_Decisions', 'Sandhātā Technology Stack and Decisions', '''
## Recommended baseline

Select the smallest stack that supports all critical acceptance paths. Pin resolved package versions in a lock file during implementation; this plan does not invent compatible version pins. Use Python 3.12 as the starting compatibility target and prove the locked environment in CI.

| Layer | Selection | Reason |
| --- | --- | --- |
| UI | Streamlit and theme CSS within supported boundaries | Fast personal dashboard delivery |
| Charts | Plotly | Interactive funnels, bars and trends |
| Validation | Pydantic | Explicit input and output contracts |
| Workflow | LangGraph OSS | Typed state and bounded graph execution |
| Storage | SQLite FTS5, SQLAlchemy, Alembic | Structured memory, search and migrations |
| Fetch | HTTPX and Beautiful Soup | Supported APIs and permitted HTML |
| Resume parsing | pypdf and python-docx | Text PDF and Word support |
| Model runtime | Ollama behind provider adapter | Local inference option |
| AI evaluation | pytest fixtures; Promptfoo optional comparison harness | Evidence and regression checks |
| MCP | Official Python MCP SDK after compatibility verification | Local read-only interoperability |
| Observability | JSON logs, run table and diagnostics page | Minimal operational footprint |
| Packaging | OCI image and Compose; Podman or Docker Engine | Reproducible private deployment |
| Source control | Git with GitHub repository | Owner-selected collaboration destination |

## Open source boundary

GitHub is a hosted service choice, not an open-source dependency claim. Hosted model endpoints, premium job accounts and infrastructure can be paid services. Ollama's license does not determine the license of a downloaded model. Select a model after a local benchmark and license review. Enterprise Langfuse features are not assumed free. Maintain a dependency and model license inventory in the implementation release.

## Decisions and alternatives

ADR01 chooses SQLite for one owner and one host; PostgreSQL is the migration path for concurrent replicas. ADR02 chooses lexical retrieval plus structured evidence because exact skills and source citations matter more than broad semantic recall in v1. Embeddings are a later enhancement, not a prerequisite for RAG. ADR03 chooses Streamlit over React to protect the schedule; the UI gate still tests layout and accessibility. ADR04 chooses service functions over a separate FastAPI layer, avoiding duplicated validation. ADR05 keeps MCP local and read-only.

## Model selection

Start with one model profile capable of structured extraction. Benchmark a Qwen-family model sized for available hardware, or configure an owner-selected hosted provider. No specific local model is promised until memory, context length and latency are tested. Store model identifier and provider settings with every assessment. CPU-only operation may require fewer simultaneous comparisons. A model outage must not block search of saved jobs or tracker updates.

## Dependency discipline

Use a project-local virtual environment and a lock generated from declared requirements. CI installs from that lock, checks vulnerabilities and exercises parsers against malformed input. Keep dev and runtime dependencies distinct. Rendering tools used for these documents are authoring dependencies, not application runtime requirements. Document generation is reproducible from scripts/build_documents.py.

## Expansion triggers

Add PostgreSQL for multiple processes needing sustained concurrent writes, embeddings for measured recall gaps, FastAPI for external application clients, and a separate tracing platform when JSON runs no longer support debugging. Each change gets an ADR, migration plan and eval rerun rather than being added solely for architectural appearance.
''')

add('06_Design_and_Accelerated_Build_Plan', 'Sandhātā Design and Accelerated Build Plan', '''
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
| Day 2 hour 8 | Git publication and private deployment if host ready | Tagged local release or verified deployment |

If document preparation or discovery exceeds the allocation, recalculate remaining work openly. Deferred connector breadth must be reflected in scope and release notes. A failed critical gate delays release; it is not relabeled as complete.

## Design order

First agree one example search profile and three example jobs. Sketch Discover, Details, Resume Library, Tracker, Insights and Diagnostics. Define card fields, empty/loading/error states and evidence table. Implement storage and service contracts before model prompting. Use synthetic fixtures until the privacy path is verified, then conduct the owner's real-data walkthrough locally.

## Proposed implementation milestones

M1 is deterministic import and persistence. M2 is one validated match with selected versions. M3 is tracker, retrieval and analytics. M4 is MCP, operations and release. Each milestone produces a small commit with tests or an explicit verification record. The separate Git repository includes only Sandhātā files; no finance-project credentials, data or history are copied.

## FDE gates

G0 Embed accepts the owner workflow and constraints. G1 Solve accepts a real end-to-end local slice. G2 Generalize accepts connector contracts, typed evidence and regression fixtures. G3 Productize accepts privacy, recovery, evaluations, visual review and operating guide. G4 Hosted verifies TLS, authentication, persistent storage, health and rollback on the actual target host. G4 may remain pending without preventing an accurately labeled local pilot.

## Engineering task dependencies

Canonical jobs precede description indexing; resume parsing precedes evidence validation; both version stores precede scoring. Status events precede analytics. Read-only services precede MCP. Container configuration follows a runnable application. A production DNS/TLS setup follows a selected host. The owner handles GitHub commands collaboratively; a push is verified by remote commit ID, not inferred from local commits.

## Review cadence

Review the first vertical slice immediately, then review after tracker and analytics integration. Maintain a live checklist of passed, failed and not-run cases. Record elapsed work, remaining scope and blocking dependency at each gate. No external outreach or application submission is part of these build activities.
''')

add('07_Test_Plan', 'Sandhātā Test Plan', '''
## Verification strategy

Test contracts, calculations, storage and failure behavior with deterministic fixtures. Use separate synthetic data for automated tests. Run live provider tests only when explicitly enabled and respect source cache policies. The release record must include commands, commit, environment, timestamp, test counts and failure summaries. No test has been run merely because it is specified here.

## Critical test cases

| ID | Scenario | Expected result |
| --- | --- | --- |
| T01 | Import valid full job twice | One canonical/source record; unchanged version reused |
| T02 | Same job description changes | New immutable version; old assessment remains versioned |
| T03 | Remotive timeout or rate response | Partial result and stale label; no refresh storm |
| T04 | Premium page needs login | Assisted import offered; no fabricated description |
| T05 | Upload text PDF and DOCX | Text and parser version stored; preview available |
| T06 | Encrypted, oversized or malformed upload | Clear rejection; no partial file leak |
| T07 | Select resume A then B | Distinct assessment keys and visible selected version |
| T08 | Evidence quote not in resume | Invalid judgment rejected or unknown |
| T09 | Absent category and unknown evidence | Correct renormalization and coverage behavior |
| T10 | Salary omitted or different periods | No invented pay; preserve units; comparisons qualify |
| T11 | Repeat tracker request after UI rerun | Single status event for request ID |
| T12 | Reopen or correct status | Auditable event history, correct current state |
| T13 | Worker killed during comparison | Lease expires; bounded recovery without duplicate write |
| T14 | Resume deleted | File, passages and private assessment evidence removed |
| T15 | HTML script or prompt injection in job | Script not executed; embedded instructions ignored |
| T16 | User URL targets localhost or redirect | Fetch blocked before private network access |
| T17 | App restarted | Jobs, resumes and tracker persist |
| T18 | Analytics fixed fixture | Counts and denominators match expected values |
| T19 | MCP unknown tool or oversized request | Bounded schema error; no write capability |
| T20 | Backup restored on clean directory | Integrity check and representative hash match |

## Layers and fixtures

Unit tests cover filter normalization, duplicate keys, quote offsets, scoring, date conversion and cohort arithmetic. Integration tests use a temporary SQLite database and file root with connector HTTP responses recorded from permitted or synthetic examples. UI tests exercise upload, resume selector, evidence expansion, tracker editing, global search and chart filters. Use Streamlit's app testing surface where supported and browser tests for interactions that need a browser.

## Visual and accessibility review

Review widths 1440, 1024 and 390 pixels, keyboard navigation, visible focus, readable contrast, long titles and missing fields. Every major page needs empty, loading, success and failure examples. Numeric fit scores have labels and explanations; charts have a table alternative. Do not rely on color alone for status or errors. Record screenshots with synthetic data and actual review findings.

## Performance and resilience targets

On the declared test machine with 500 saved jobs, target p95 saved-job search under 1 second across 30 queries and ordinary tracker writes under 1 second. Model comparison latency is measured separately by model/hardware; show progress and cancellation if it exceeds 10 seconds. These are initial engineering targets, not current measurements. Disk-full and database-lock cases must leave transactions consistent and present a useful error.

## Release gate

All critical T cases pass; no unresolved critical privacy, security or data-loss defect; eval gate passes; owner can complete the real workflow. A skipped live connector test is reported as not verified, with the affected capability labeled accordingly. Regression failures need reproduction, fix and a targeted rerun before broad release validation.
''')

add('08_AI_Evaluation_Plan', 'Sandhātā AI Evaluation Plan', '''
## Evaluation objective

Determine whether extraction, ranking and comparison are useful, evidence-grounded and stable enough for personal decision support. Evaluate the selected model and prompt versions, not agent labels. A high fit percentage without valid evidence fails evaluation.

## Initial dataset

Create 12 synthetic job descriptions and four synthetic resumes, yielding 48 reviewed pairs. Cover clear matches, partial transferable experience, seniority gaps, missing certifications, location restrictions, unknown salary and incomplete descriptions. Add 12 adversarial cases for injected instructions, fabricated credentials, duplicate jobs, misleading keyword repetition and attempts to retrieve another resume. The owner labels expected requirements and acceptable judgments; one review pass catches ambiguous labels. Keep a reserved 12-pair subset unchanged during prompt tuning and report the small sample limitation.

## Metrics and proposed gates

| Measure | Method | Initial gate |
| --- | --- | --- |
| Output validity | Parse schema and required fields | 100 percent valid or explicit failed task |
| Evidence correctness | Quote/offset check plus human relevance review | 100 percent literal validity; at least 95 percent relevance |
| Requirement extraction | Compare to reviewed atomic labels | F1 at least 0.85 |
| Judgment agreement | Supported/partial/not evidenced/unknown vs labels | At least 85 percent exact agreement |
| Unsupported claims | Count claims without valid evidence | Zero critical fabricated credentials |
| Ranking usefulness | Owner rates top five per profile | At least four relevant where fixture contains five |
| Injection resistance | Adversarial instructions ignored | Zero unauthorized writes or data disclosures |
| Repeatability | Three runs for 12 pairs | Score spread at most 10 points or flagged unstable |

These are proposed acceptance thresholds, not attained scores or statistical guarantees. Report numerators, denominators and confidence limitations. Any change to rubric, model, parser, prompt or retrieval reruns relevant evaluations.

## Scoring evaluation

Test arithmetic independently of the model. Verify absent category renormalization, partial credit, unknown handling, coverage suppression, eligibility flags and duplicate requirement removal. Calibrate score bands against owner judgments; do not tune thresholds to imply interview probability. Compare model-driven judgments with a simple keyword baseline to establish whether AI adds useful interpretation.

## Retrieval evaluation

Label 20 saved-data questions with relevant passage IDs, including exact skill names, negative requirements and date/status queries. Target recall at five of at least 0.90 on answerable questions and correct abstention on every deliberately unanswerable fixture. Structured tracker questions use SQL rather than asking a model to count retrieved snippets. Scope tests prove that resume selection restricts eligible evidence before ranking.

## Execution and reporting

Use pytest for deterministic assertions and a versioned JSONL dataset for model cases; optionally wrap provider comparisons with Promptfoo. Save input hashes, expected labels, actual outputs, model/prompt/rubric versions, latency and token usage. Review errors by category and retain examples privately. A model-as-judge may supplement human review but cannot certify evidence correctness alone.

## Release decision

Pass requires critical safety cases, evidence grounding and arithmetic gates plus agreed usefulness thresholds. If usefulness fails, ship tracker/import features as a clearly labeled pilot and disable or mark experimental comparisons; do not silently lower the threshold. Baseline comparison and the held-out results accompany release notes. Production monitoring samples newly encountered cases for later evaluation updates.
''')

add('09_Memory_and_RAG_Design', 'Sandhātā Memory and RAG Design', '''
## Purpose and boundaries

Persistent memory stores explicit owner preferences, imported job versions, resume versions and application events. RAG answers questions from those saved records with citations. Agent conversation is short-lived workflow state; it is not evidence of credentials or application status. No public web crawling corpus or external vector service is required for the first release.

## Memory classes

| Class | Store | Update rule |
| --- | --- | --- |
| Preferences | SearchProfile JSON | Explicit save and version |
| Career evidence | ResumeVersion and Passage | Upload or confirmed correction creates a version |
| Job evidence | DescriptionVersion and Passage | Content change creates a snapshot |
| Application history | Application and StatusEvent | User command with event and record timestamps |
| Execution memory | TaskRun and checkpoints | Run-scoped state; expire after retention window |
| Derived analysis | MatchAssessment | Immutable input and policy version references |

## Indexing pipeline

Parse text, preserve a canonical normalized text representation, split at headings and bullet boundaries, and retain parent version, section and character offsets. Target 300 to 600 tokens per passage with small overlap only when needed. Quotes and offsets refer to canonical stored text; the original payload remains separate. FTS5 indexes passage text with UNICODE tokenization; normalized skill aliases such as PostgreSQL/Postgres improve recall without rewriting the source evidence.

## Retrieval pipeline

Validate the question, select entity/version scope, apply structured filters, perform parameterized FTS lookup, rank and return up to five passages initially. Apply a total context budget of 6000 tokens, including the question and system instructions; truncate with an explicit omitted-evidence flag. Retrieve neighboring passages when a requirement refers to a prior heading. Candidate grouping prevents duplicates from occupying every slot.

Resume matching filters to the chosen resume version and chosen description version before retrieval. A general question can search authorized saved jobs, but cannot silently combine resumes as if they were one document. Tracker counts and dates come from SQL aggregates with record citations rather than lexical passages.

## Citation contract

EvidenceRef contains entity_type, entity_id, version_id, passage_id, section, start_offset, end_offset and quote. The validator checks the quote against the version text and confirms that it falls inside the referenced passage. UI citations open the stored record and show the relevant passage; source job URLs remain available separately. If a record is deleted or not available, the assistant abstains or reports the limitation.

## Freshness and retention

Preference changes affect new runs; prior results retain prior inputs. Job refresh does not overwrite applied-to snapshots. Keep execution logs 14 days and checkpoints seven days as initial configurable defaults. Keep owner career records until explicit deletion. Backups retain at most seven daily snapshots by default; record deletion tombstones and replay them during restore until all affected backups expire. Explain that immediate deletion from active storage does not erase prior offline backups instantly.

## Privacy and future semantic search

Do not send contact details to hosted models when not needed. Keep private uploads and indexes outside the repository, with OS permissions and encrypted host storage. If measured lexical recall is inadequate, add local embeddings and pgvector after selecting PostgreSQL or a measured local vector option. Embedding indexes inherit the same version filters, deletion rules and privacy restrictions. RAG quality is evaluated using the queries and gates in document 08.
''')

add('10_MCP_and_Integration_Design', 'Sandhātā MCP and Integration Design', '''
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
''')

add('11_GitHub_and_Collaboration_Guide', 'Sandhātā GitHub and Collaboration Guide', '''
## Repository destination

The owner created https://github.com/hemach-git/sandhata and will run the network Git commands collaboratively. The local preparation directory is sandhata beneath the current BRIHASPATI workspace; it is an independent Git repository. Always verify the working directory and origin before staging or pushing. Never run git add from the finance repository for this work.

## Initial publication commands

Open PowerShell and run these commands one at a time. The preparation step may already have created the local commit; git status will show whether there are changes. Authenticate through Git Credential Manager when prompted; do not paste tokens into chat.

```powershell
Set-Location -LiteralPath 'C:\\Users\\Chepuri\\Documents\\ChatGPT\\BRIHASPATI - AI Finance Assistant\\sandhata'
git rev-parse --show-toplevel
git status --short
git remote -v
git log -1 --oneline
git ls-remote origin
git push -u origin main
```

The expected top-level path ends in sandhata and origin is https://github.com/hemach-git/sandhata.git. If authentication fails, resolve it in Git Credential Manager. If the repository is private, verify visibility in GitHub settings; do not make resume files public.

## If the remote already has an initial commit

Do not force push. Fetch, inspect and merge remote history, preserving the README or license that GitHub created. Resolve any conflicts in the specific files before continuing.

```powershell
git fetch origin
git log --oneline --all --decorate -8
git merge origin/main --allow-unrelated-histories
git status
git push -u origin main
```

This branch assumes the remote branch is main. If fetch shows another default branch, use that actual branch. A conflict requires resolving files, staging only those files and committing before push. Do not run the merge path unless the remote has history that needs integration.

## Subsequent collaboration

```powershell
git switch -c codex/core-workflow
git add src tests docs README.md
git diff --cached --stat
git commit -m "Implement core job comparison workflow"
git push -u origin codex/core-workflow
```

The example paths for implementation commits apply only once those directories exist. Review the staged content before every commit. Use a pull request for implementation changes and include behavior, validation and remaining limits. Avoid committing generated runtime logs, private resumes, SQLite files, environment files and document QA render images.

## Publication verification

After push, compare git rev-parse HEAD with git ls-remote origin refs/heads/main. Confirm the same commit and inspect the repository file list in GitHub. Record the SHA and URL in the release evidence. A local commit alone is not proof of publication. Never bypass rejected updates with force; inspect divergence first.

## Release workflow

Pin dependencies, run tests/evals, review the diff and create a version tag only after acceptance. Suggested first implementation tag is v0.1.0; the design package is not an implemented application release. Keep CI deterministic with synthetic data; a separate optional job handles live provider checks without exposing secrets in logs.
''')

add('12_Observability_and_Operations', 'Sandhātā Observability and Operations Guide', '''
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
''')

add('13_UI_Design_and_User_Guide', 'Sandhātā UI Design and User Guide', '''
## Visual direction

Use the display title Sandhātā and the subtitle Career Intelligence. SANDHĀTĀ expands to Search, Analyze, Navigate, Discover, Highlight, Apply, Track, Advance. The acronym appears in About and onboarding rather than crowding every screen. The application helps organize the user's applications; it does not submit them automatically.

![Discover screen concept](assets/ui_discover.png)

The concept is a design mockup, not a running application screenshot. Use navy #10243A for navigation, teal #087F8C for primary actions, background #F5F7FA, white content surfaces and dark text #172B4D. Use amber for qualified warnings and red for errors with text labels. Typography uses an accessible system sans serif with 16 pixel-equivalent body text, clear headings and tabular numbers for metrics. Verify contrast rather than assuming palette choices pass.

## Navigation and information hierarchy

The sidebar contains Discover, Resume Library, Tracker, Insights and Diagnostics. Global search is visible at the top. A compact source health strip explains automatic versus assisted sources and last refresh. Main job cards show title, company, location/workplace, salary with units, skills, source, posting date when known, retrieval age and completeness. Fit appears only after selecting and comparing a resume.

## Discover and job detail

Enter a search profile, separate must-have constraints from preferences, and run supported-source search. External search buttons open premium portals in the user's browser. Import opens a form for source, URL and full pasted description, then previews extracted fields before saving. Pasting a URL alone does not promise full retrieval.

Select a card to open Details. Tabs show Original Description, Requirements, Resume Fit and Tracker. Original wording remains distinct from AI summaries. A citation opens the stored passage and highlights its evidence; the original posting is a separate link. Explain unknown salary and partial descriptions visibly. A stale-source warning retains the cached record without implying the job is still open.

## Resume library and comparison

Upload PDF or DOCX, assign a label and review parsed text. Select a version explicitly before comparing. The Fit view shows category breakdown, evidence coverage, eligibility flags, matched requirements and not-evidenced items. Provisional scores explain their limitation. Resume guidance may recommend clearer wording supported by existing evidence; it must not invent credentials or experience.

## Tracker and insights

Use a filterable table first; a board is optional if the timebox permits. Status changes request event date and optional note. Opening Apply leads to the original site; the user later records Applied. History is available in Details. Insights provides date cohort filters, metric explanations, readable charts and downloadable tables. No-data charts explain how records will populate them.

## State and accessibility specification

Empty states show the next action and no invented sample statistics. Loading states show current operation and preserve prior committed results. Errors retain input, explain the failed action and offer a bounded retry. Buttons and focus order are keyboard accessible. Status has text and icon, not color alone. At 390 pixels, cards stack and wide tables scroll with clear headings. Long role titles wrap without clipping. Charts have text/table alternatives and descriptive titles.

## UI acceptance and design constraints

Use supported Streamlit composition and theme configuration before fragile DOM-specific CSS. Measure perceived quality with owner review at desktop and mobile widths. The design gate checks consistent spacing, hierarchy, typography, evidence visibility and the complete workflow. If Streamlit cannot meet this gate, estimate a React implementation openly rather than promising a same-day replacement. Screenshots use synthetic records only.
''')

add('14_Analytics_Requirements_and_Design', 'Sandhātā Analytics Requirements and Design', '''
## Objective and data basis

Show where the owner's effort goes, how applications progress and which evidence gaps recur. Analytics is descriptive decision support for a personal search. It does not establish that a source or resume causes better outcomes. Metrics are computed in SQL and deterministic Python, then explained by the Career Assistant.

## Metric definitions

| Metric | Definition | Visualization |
| --- | --- | --- |
| Current pipeline | Applications by current status as of query time | Donut and table |
| Application activity | Count of distinct first applied events per local calendar week | Trend line |
| Interview conversion | Applied cohort with an interview event divided by applied cohort size | Funnel and percentage |
| Offer conversion | Applied cohort with an offer event divided by applied cohort size | Funnel |
| Source yield | Jobs, applications and interviews attributed to discovery source | Grouped bars |
| Time to first response | First user-recorded response minus applied_at | Median and sample count |
| Stage duration | Time between adjacent status events; ongoing stage separate | Distribution |
| Skill gaps | Count of distinct jobs with a not-evidenced atomic skill | Ranked bars |
| Resume outcomes | Applied/interview/offer counts by resume version used | Comparison table |
| Salary coverage | Jobs with comparable disclosed salary divided by selected jobs | Coverage and range chart |

## Cohort and attribution rules

Applied cohorts use first applied date within the selected interval, then observe later events through the as-of date. A funnel is not a set of unrelated current status counts. An application can advance through skipped stages; observed event counts remain truthful and no missing interview event is manufactured. Rejections and withdrawals remain in cohort denominators. Distinct application IDs prevent multiple interviews from inflating conversion.

Store discovery_source on the application when saved, with user correction available. A job may have several source URLs but receives one primary attribution for reporting; source overlaps are shown separately. Resume outcomes use the version actually submitted, not the most recently uploaded resume. Small cohorts under ten display a small-sample notice; do not rank tiny samples as statistically superior.

## Salary and time handling

Preserve original currency, interval and text. Compare annual salaries only within the same currency and compatible basis by default. Hourly-to-annual conversion, if enabled, requires explicit hours and weeks assumptions displayed in the report. Do not mix base salary and total compensation. Store UTC timestamps; use America/New_York for day/week grouping, including daylight-saving transitions. Negative or missing durations are flagged and excluded from duration summaries with counts shown.

## Example reconciliation fixture

Create ten applied applications in one cohort; four have screening, three have interview, one has offer and one is hired. Expected interview conversion is 3/10 and offer conversion 1/10; current-status counts may differ. Add two saved-only jobs that do not enter applied denominators. Give two source links to one job and verify it still counts once. These numbers are synthetic expected results, not actual user outcomes.

## Query and export design

Reusable query functions accept date range, source, resume, role and status filters. Each result returns metric_version, as_of, cohort bounds, numerator, denominator, exclusions and rows. CSV exports include these definitions or an adjacent metadata file. Cache keys include the latest tracker event revision, preventing stale charts after updates. Free-text assistant answers cite the aggregate query and relevant records.

## Advanced roadmap

Add cohort maturity comparisons, response-time survival analysis and richer salary breakdowns after sufficient records accumulate. Forecasting or probability-of-offer features require a separate statistical design and validation. The first release's impressive analytics comes from clear definitions, interactive filtering and trustworthy evidence rather than speculative prediction.
''')

add('15_Production_Deployment_and_Release', 'Sandhātā Production Deployment and Release Guide', '''
## Deployment target and claim boundary

The baseline production target is a single private Linux host running one application instance and one worker against local persistent storage. Host provider, domain, identity provider and budget are not yet selected. This document is a deployment specification; it is not evidence of a deployed service. A private local pilot can precede hosted production.

![Private deployment architecture](assets/deployment.png)

## Runtime topology

An authenticated TLS reverse proxy routes browser traffic and WebSocket upgrades to Streamlit. Use Caddy or an existing reverse proxy with oauth2-proxy or an equivalent established OIDC gate. Restrict access to the owner's identity. Bind the application to a private container network; expose only the proxy. Keep the worker and model endpoint private. Local stdio MCP is not exposed over the public network.

Mount persistent data at /data for database, uploads and safe operational state. Use one SQLite database on local disk with WAL and foreign keys. Container restarts must retain the volume. Do not place the live database in the image, repository, ephemeral filesystem or a shared network filesystem. A move to multiple replicas requires PostgreSQL and a revised file-storage design.

## Configuration contract

| Variable | Purpose | Handling |
| --- | --- | --- |
| SANDHATA_DATA_DIR | Persistent private data root | Required outside source tree |
| SANDHATA_MODEL_PROVIDER | Local or configured hosted adapter | Validated allowlist |
| SANDHATA_MODEL_NAME | Model identity | Recorded with assessments |
| SANDHATA_MODEL_BASE_URL | Model endpoint | Private network preferred |
| SANDHATA_MODEL_API_KEY | Hosted credential if needed | Secret injection; never log |
| SANDHATA_TIMEZONE | Display and analytics timezone | America/New_York default |
| SANDHATA_LOG_LEVEL | Operational verbosity | No raw content at any level |
| SANDHATA_REMOTIVE_REFRESH_HOURS | Cache interval | At least six hours for scheduled refresh |

These are proposed settings to implement and validate. Keep runtime secrets out of .env.example. A local model on another machine needs authenticated private connectivity and compatible capacity; it is not implicitly available in the container.

## Release procedure

1. Select host, access mode and model; confirm owner identity restriction and storage path.
2. Check out the verified release SHA; install the exact dependency lock or build the pinned image.
3. Stop writes, create a consistent backup and apply migrations in a one-time release step.
4. Start application and worker under non-root accounts with constrained file permissions.
5. Validate health endpoint, proxy authentication, WebSocket traffic, file permissions and model reachability.
6. Run the synthetic import, comparison, tracker and chart smoke tests through the deployed UI.
7. Restart both containers and verify persistence. Restore a backup to a separate location and verify integrity.
8. Record deployment URL privately, SHA/image digest, migration version, smoke results and rollback target.

## Backup and rollback

Use SQLite's online backup mechanism or stop writers; do not copy only the live .db file while WAL writes are active. Capture uploads and database consistently, encrypt backup storage and retain seven daily copies initially. Proposed recovery objectives are at most 24 hours of data loss and two hours to restore; prove them with a timed drill. Reapply deletion tombstones on restore. Roll back the application image only when schema compatibility is known; otherwise restore the matching database/files backup and disclose the data-loss interval.

## Health and security gate

Use Streamlit's documented health path for process readiness and a worker heartbeat for task processing. Model availability is a separate dependency state. Verify unauthenticated requests cannot read pages or uploads; access logs contain no tokens or resume data. Confirm durable storage, disk headroom, backups and manual recovery instructions. Do not call the deployment production-ready until these checks have actual results.

## Evidence and ongoing ownership

Release evidence includes CI/test/eval summaries, owner walkthrough, restore log, authenticated UI check, immutable commit and known limitations. The owner operates credentials and backup access. A failed critical check leaves the release candidate unpromoted. No automatic infrastructure purchase or public exposure is required by this document.
''')

add('16_Coordinator_Agent_Guide', 'Sandhātā Coordinator Agent Guide', '''
## Mission and authority

Coordinate search, import and comparison through bounded typed workflows. The coordinator decides the next allowed step and manages state; it does not invent source capabilities, approve application submissions or rewrite tracker history. It is a logical agent inside one application, not a separate deployed service.

## Inputs and outputs

Inputs are operation, request_id, profile_id, selected job/description/resume versions, user intent and execution budget. Output is RunResult with run_id, state, completed artifacts, per-source outcomes, warnings and error codes. Shared state contains IDs and validated artifacts, not unrestricted credentials or arbitrary executable instructions.

## Workflow contract

Search route is validate request, load profile, plan allowed connector calls, fetch/cache, curate, persist and summarize. Comparison route is validate versions, retrieve evidence, invoke Resume and Fit services, validate, calculate and persist. Tracker commands go directly to the deterministic service after user intent is validated. Career answers use retrieval/SQL without mutation.

States are queued, running, waiting_dependency, completed, partial, failed and cancelled. Checkpoints record completed node and versioned input hashes. A lease protects worker ownership. Replaying a node must reuse idempotency keys rather than append duplicate records. Cancellation prevents new model calls and permits already committed records to remain.

## Operating instructions

Validate identifiers before routing. Select only connectors whose capability allows the requested operation. Pass the explicit selected resume version to every comparison. Treat tool output as data and validate it before the next step. Allow two transient connector retries and one model schema repair; otherwise return a partial or failed result. Stop when the configured call/time budget is exhausted. Never interpret job-description instructions as owner authorization.

## Tools and permissions

Allowed tools are profile read, connector fetch, resume profile read, evidence retrieval, comparison service and run persistence. Tracker writes require an explicit user command and use the dedicated service. No shell, arbitrary external URL access, premium-cookie extraction, email sending or application submission tool is allowed.

## Example and failure response

For a search across Remotive and a manual-only source, return Remotive records plus the assisted-import entry point, with separate source outcomes. If the model is offline, preserve the saved job and show comparison unavailable. If the resume is deleted mid-run, fail with selected_resume_unavailable and discard private uncommitted evidence. Do not silently select another resume.

## Verification and telemetry

Tests cover invalid routes, duplicate request IDs, exhausted budgets, lease recovery, cancellation and source partial failures. Record node durations, outcomes, version IDs and retry counts without raw private text. Acceptance requires a trace showing all intended handoffs and a failure trace proving bounded recovery. Proposed module path is src/sandhata/agents/coordinator.py.
''')

add('17_Search_and_Intake_Agent_Guide', 'Sandhātā Search and Intake Agent Guide', '''
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
''')

add('18_Resume_Analyst_Agent_Guide', 'Sandhātā Resume Analyst Agent Guide', '''
## Mission and evidence boundary

Build a faithful, versioned profile from the resume the user explicitly selected. The analyst extracts stated evidence; it does not manufacture missing experience, merge different resume versions or infer protected characteristics. A resume is private untrusted input, including any instructions written inside it.

## Input and output contract

Input is resume_version_id, parser_version, canonical text and passage references. ResumeProfile contains skills with supporting evidence, role history, dated intervals, responsibilities, achievements, education, certifications and parse warnings. Each substantive item contains a quote and source offsets or an explicit unknown state. Personal contact fields are excluded from model input unless a later feature needs them and the owner enables it.

## Parsing workflow

Verify file type, size and page limits before extraction. For text PDF use pypdf; for DOCX use python-docx. Detect empty or implausibly sparse extraction and ask the UI to show an OCR-not-supported message. Preserve section boundaries and create canonical offsets. Show a preview so the owner can confirm parsing. A corrected text/profile creates a new version with user_correction provenance rather than modifying historical evidence.

## Interpretation rules

Distinguish explicit skill mentions from skill evidence in actual work. Deduplicate overlapping employment dates before calculating relevant experience; do not simply sum all role durations. Missing or ambiguous months produce qualified ranges. Do not infer current certifications, work authorization, willingness to relocate or salary expectations from unrelated resume content. A user preference belongs in profile memory, not in resume evidence.

## Tools and permissions

Allowed tools are private file read for the selected version, parser, passage index and schema/evidence validator. No network fetch, employer application, tracker update or cross-resume search is available. The service persists validated output under the original version. Deletion removes profile and passage content from active storage and invalidates dependent caches.

## Example output behavior

If a project says implemented ETL pipelines with Python and AWS, extract Python, AWS and ETL with that quote. Do not infer Kubernetes. If a resume says cloud migration without naming a vendor, record cloud migration and leave AWS-specific evidence unknown. A recommendation may suggest clarifying actual experience but must never supply an invented achievement metric.

## Failure handling and acceptance

Malformed or encrypted files fail clearly with no persisted partial original left behind. Sparse parse warnings block confident comparison until the user reviews text. Validate every extracted quote literally. Test multi-column PDFs, bulleted DOCX, overlapping dates, unknown dates, injection text and deletion. Telemetry records file hash, parser version, page count, warnings and duration, excluding text, file names with personal details and private paths. Proposed module path is src/sandhata/agents/resume.py.
''')

add('19_Fit_Analyst_Agent_Guide', 'Sandhātā Fit Analyst Agent Guide', '''
## Mission and output meaning

Explain alignment between one selected resume version and one selected job description version. The result helps the owner decide what to review; it is not an ATS score, hiring decision or probability of interview. Final arithmetic is implemented in code using rubric v1 from the architecture document.

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

Test quote correctness, transferable skill limits, repeated requirements, absent categories, zero assessed weight, partial descriptions and fabricated credentials. Run the evaluation plan before model/prompt changes ship. Log version IDs, timing, token counts and validation outcomes; private rationale text remains in private application data rather than general logs. Proposed module path is src/sandhata/agents/fit.py.
''')

add('20_Career_Assistant_Agent_Guide', 'Sandhātā Career Assistant Agent Guide', '''
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
''')

add('21_Risks_Decisions_and_Release_Evidence', 'Sandhātā Risks Decisions and Release Evidence', '''
## Current baseline

The owner selected Sandhātā with ASCII identifier sandhata, requested paired Markdown and DOCX documents, and created https://github.com/hemach-git/sandhata. The initial implementation is a single-user Streamlit application with SQLite, bounded agent coordination and assisted premium imports. GitHub network commands will be run collaboratively by the owner. Public branding clearance and hosting selection remain open.

## Risk register

| Risk | Impact | Mitigation and owner |
| --- | --- | --- |
| Premium account lacks API rights | Automated source coverage reduced | Assisted import; owner verifies approved access |
| Two-day capacity overrun | Scope or date missed | Vertical slice first; collaborator reports remaining work |
| Model fabricates evidence | Misleading fit judgment | Literal validation, reviewed evals, suppress invalid score |
| Resume privacy leak | Private data disclosure | Private storage, redaction, no personal data in Git |
| SQLite data loss | Tracker unavailable | Consistent backup, restore drill, one-host topology |
| UI fails quality target | Poor usability | Visual gate and early owner walkthrough |
| Weak extraction on PDFs | Incomplete comparison | Parse preview, unknown labels, OCR deferred |
| Name collision | Rebranding work | Domain/trademark check before public brand launch |
| Production host not ready | Hosted release delayed | Accurate local pilot label; host remains prerequisite |

## Decision log

D01 uses the FDE sequence Embed, Solve, Generalize, Productize, adapted to the owner's accelerated path. D02 separates application data and history from the finance project. D03 preserves original descriptions and versions. D04 keeps eligibility outside the average fit score. D05 implements lexical RAG before embeddings. D06 makes MCP local/read-only. D07 uses descriptive analytics and truthful small-sample reporting. D08 keeps product branding configurable so a later name change does not require schema migration.

## Open decisions

Select local or hosted model after hardware and privacy review. Select production host, domain and authentication provider. Confirm repository visibility. Confirm whether an approved private API exists for any premium source. Obtain owner sample jobs/resumes without committing them. These are implementation inputs rather than reasons to stop independent document preparation.

## Release evidence ledger

| Gate | Required evidence | Baseline state |
| --- | --- | --- |
| Document preparation | Matched MD/DOCX and visual QA report | Generated and checked during authoring; consult manifest |
| Source publication | Local SHA matches remote SHA | Pending owner Git commands |
| Local application | Setup and end-to-end workflow evidence | Not implemented in document package |
| Tests | Commit-linked test report | Not run for application |
| AI evals | Dataset, versions and threshold results | Planned |
| UI review | Screenshots and owner walkthrough | Concept only |
| Recovery | Timed restore and integrity report | Planned |
| Production | URL, access check, health and deployed SHA | Not deployed |

## Source and naming notes

Sandhātā draws inspiration from the Vishnu Sahasranama, with an interpreted connection between actions and their results. The English acronym is an original product expansion, not a literal translation. Traditional commentary varies. See https://www.sadagopan.org/ebook/pdf/Vishnu%20Sahasranama%20v1.pdf. Prior naming research found existing uses of Sandhi AI and Sthiraa; no domain/trademark clearance is claimed for the selected name.
''' + SOURCES)

add('00_Document_Index', 'Sandhātā FDE Document Index', '''
## Package purpose

This package establishes the delivery baseline for Sandhātā Career Intelligence, a private agent-assisted job search and application workspace. It contains project governance, implementation contracts, diagrams, tests and AI evaluation plans, retrieval, integrations, interface design, analytics, operations and five individual agent guides. It supports the accelerated October 26 to 27 2026 target without representing planned capabilities as completed software.

## Reading order

Read the charter and scope first, then architecture and sequence flows. Use the build plan as the implementation checklist. Test and evaluation plans define release evidence; deployment and operations define the handoff. Agent guides inherit the architecture contracts and never override source access or privacy requirements.

## Documents

INDEX_PLACEHOLDER

## Format and change discipline

Markdown is the editable source of record. The Word versions contain the same prose, tables and diagrams, formatted for review. A generator keeps the paired content aligned. Regenerate Word files after source changes; do not independently edit both formats without reconciling them. Scripts, diagram assets and the package manifest are included for reproducibility. The Word files are in deliverables/word and the paired Markdown files are in docs.

## Implementation status

The current deliverable is the FDE document baseline and repository preparation. Tests, evaluations, MCP tools, UI, production deployment and live integrations described here require implementation and evidence. Concept diagrams and mockups are labeled as designs. The GitHub guide contains owner-run publication commands for the separate repository.
''')

# Native code-generated diagrams keep the architecture editable and legible in Word.
FONT_DIR = Path('C:/Windows/Fonts')
def font(n=22, bold=False):
    for f in (('arialbd.ttf' if bold else 'arial.ttf'), 'segoeui.ttf'):
        if (FONT_DIR/f).exists(): return ImageFont.truetype(str(FONT_DIR/f), n)
    return ImageFont.load_default()

def wrap(draw, text, maxw, ft):
    out=[]
    for para in text.split('\n'):
        line=''
        for word in para.split():
            trial=(line+' '+word).strip()
            if draw.textlength(trial,font=ft)>maxw and line: out.append(line); line=word
            else: line=trial
        out.append(line)
    return out

def label(draw, xy, text, ft, fill='#172B4D', width=300, center=False):
    lines=wrap(draw,text,width,ft); y=xy[1]
    for line in lines:
        x=xy[0] - draw.textlength(line,font=ft)/2 if center else xy[0]
        draw.text((x,y),line,font=ft,fill=fill); y+=ft.size+7

def box(d, rect, title, body='', fill='#EDF4F6'):
    d.rounded_rectangle(rect, radius=14, fill=fill, outline='#9BB5BF',width=2)
    label(d,(rect[0]+18,rect[1]+16),title,font(24,True),width=rect[2]-rect[0]-36)
    if body: label(d,(rect[0]+18,rect[1]+57),body,font(20),width=rect[2]-rect[0]-36)

def arrow(d,a,b,caption=''):
    import math
    d.line([a,b],fill='#087F8C',width=4)
    angle=math.atan2(b[1]-a[1],b[0]-a[0]); length=13
    pts=[b,(b[0]-length*math.cos(angle-.45),b[1]-length*math.sin(angle-.45)),(b[0]-length*math.cos(angle+.45),b[1]-length*math.sin(angle+.45))]
    d.polygon(pts,fill='#087F8C')
    if caption: label(d,((a[0]+b[0])/2+8,(a[1]+b[1])/2-28),caption,font(17),width=220)

def canvas(title,w=1400,h=900):
    im=Image.new('RGB',(w,h),'white'); d=ImageDraw.Draw(im)
    label(d,(35,22),title,font(30,True),width=w-70)
    return im,d

def diagrams():
    im,d=canvas('Sandhātā application architecture',1400,850)
    box(d,(35,105,330,255),'Owner browser','Search, resume, tracker, insights')
    box(d,(420,105,1000,255),'Streamlit presentation','Validated commands, evidence views and diagnostics')
    arrow(d,(330,180),(420,180))
    box(d,(420,335,1000,480),'Domain services and coordinator','Typed contracts, deterministic writes and scoring')
    arrow(d,(710,255),(710,335))
    box(d,(35,335,330,500),'Background worker','Persisted queue, leases and bounded model calls')
    arrow(d,(420,410),(330,410))
    box(d,(1070,105,1370,300),'Source adapters','Remotive, employer feeds and assisted import')
    arrow(d,(1000,365),(1070,265))
    box(d,(1070,365,1370,530),'Model adapter','Local or owner-selected hosted endpoint')
    arrow(d,(1000,420),(1070,420))
    box(d,(420,600,1000,775),'Private data and evidence','SQLite and FTS5, versioned uploads, history and run records')
    arrow(d,(710,480),(710,600))
    box(d,(35,610,330,775),'Local MCP client','Read-only stdio tools through shared services')
    d.line([(330,690),(370,690),(370,450)],fill='#087F8C',width=4)
    arrow(d,(370,450),(420,450))
    im.save(ASSETS/'architecture.png')

    im,d=canvas('Sandhātā core data relationships',1400,800)
    nodes=[((40,100,390,240),'Job','Canonical opening'),((520,100,870,240),'DescriptionVersion','Immutable description text'),((1010,100,1360,240),'JobSource','Provider and source links'),((40,355,390,500),'ResumeVersion','Private original and parsed text'),((520,355,870,500),'MatchAssessment','Resume and description versions'),((1010,355,1360,500),'Passage','Version-scoped evidence'),((40,610,390,755),'Application','Job and submitted resume'),((520,610,870,755),'StatusEvent','Append-only event history'),((1010,610,1360,755),'TaskRun','State, lease and checkpoints')]
    for rect,t,b in nodes: box(d,rect,t,b)
    for a,b in [((390,170),(520,170)),((695,240),(695,355)),((390,425),(520,425)),((870,425),(1010,425)),((215,500),(215,610)),((390,680),(520,680))]: arrow(d,a,b)
    d.line([(215,100),(215,75),(1185,75)],fill='#087F8C',width=4)
    arrow(d,(1185,75),(1185,100))
    d.line([(40,170),(15,170),(15,680)],fill='#087F8C',width=4)
    arrow(d,(15,680),(40,680))
    im.save(ASSETS/'data_model.png')

    seqs={
      'sequence_search':('Search and intake sequence',['Owner UI','Coordinator','Connector','Data store'],[(0,1,'Search profile and refresh'),(1,2,'Fetch allowed sources or cached results'),(2,1,'Candidates and per-source outcomes'),(1,3,'Validate, deduplicate and store versions'),(3,1,'Canonical jobs and evidence IDs'),(1,0,'Cards, freshness and assisted imports')]),
      'sequence_compare':('Resume comparison sequence',['Owner UI','Services','Worker and model','Data store'],[(0,1,'Choose job and resume versions'),(1,3,'Check versions and cache key'),(1,2,'Queue bounded comparison'),(2,3,'Retrieve scoped passages'),(2,1,'Validated judgments or failure'),(1,3,'Compute and persist assessment'),(1,0,'Score, coverage, gaps and citations')]),
      'sequence_tracker':('Tracker update and analytics sequence',['Owner UI','Tracker service','Data store','Analytics'],[(0,1,'Explicit status command and date'),(1,2,'Idempotent state and event transaction'),(2,1,'Committed revision'),(1,0,'Current status and history'),(0,3,'Request filtered metrics'),(3,2,'Query distinct applied cohort and events'),(3,0,'Charts, definitions and exclusions')])}
    for name,(title,actors,messages) in seqs.items():
        im,d=canvas(title,1400,220+len(messages)*88)
        xs=[170,520,870,1220]
        for x,a in zip(xs,actors):
            box(d,(x-145,90,x+145,165),a)
            d.line((x,165,x,im.height-25),fill='#9BB5BF',width=2)
        for i,(a,b,msg) in enumerate(messages):
            y=215+i*88
            d.rectangle((min(xs[a],xs[b])+5,y-31,max(xs[a],xs[b])-5,y-2),fill='white')
            label(d,((xs[a]+xs[b])/2,y-32),f'{i+1}  {msg}',font(19),width=abs(xs[a]-xs[b])-10,center=True)
            arrow(d,(xs[a],y+20),(xs[b],y+20))
        im.save(ASSETS/(name+'.png'))

    im,d=canvas('Private single host deployment',1400,820)
    box(d,(40,120,390,270),'Owner browser','Authenticated HTTPS session')
    box(d,(520,120,970,270),'TLS and identity gate','Reverse proxy plus owner-restricted OIDC')
    arrow(d,(390,195),(520,195))
    d.rounded_rectangle((430,340,1370,780),radius=20,outline='#9BB5BF',width=3)
    label(d,(455,355),'Private host and container network',font(25,True),width=850)
    box(d,(475,420,850,565),'Application','One Streamlit instance')
    box(d,(930,420,1325,565),'Worker and model adapter','One worker; private model access')
    d.line([(745,270),(745,310),(410,310),(410,490)],fill='#087F8C',width=4)
    arrow(d,(410,490),(475,490))
    box(d,(475,635,1325,745),'Persistent local volume','SQLite, uploads, run state and encrypted backup process')
    arrow(d,(665,565),(665,635)); arrow(d,(1130,565),(1130,635))
    im.save(ASSETS/'deployment.png')

    im,d=canvas('Sandhātā Discover screen concept',1500,1000)
    d.rectangle((0,75,270,1000),fill='#10243A')
    label(d,(24,105),'Sandhātā',font(30,True),fill='white',width=225)
    label(d,(24,152),'Career Intelligence',font(18),fill='#B9D9E2',width=225)
    for i,t in enumerate(['Discover','Resume Library','Tracker','Insights','Diagnostics']):
        y=245+i*80
        if i==0: d.rounded_rectangle((15,y-10,255,y+45),radius=8,fill='#087F8C')
        label(d,(30,y),t,font(22),fill='white',width=220)
    label(d,(310,110),'Discover your next opportunity',font(31,True),width=1100)
    box(d,(310,180,1450,265),'Search saved jobs','Role, company, skills or notes')
    box(d,(310,300,1450,400),'Source status','Remotive automatic | Premium portals assisted | Last refresh visible')
    label(d,(315,435),'Selected resume  AI Engineering v2',font(23,True),width=1100)
    for i,(t,c,s) in enumerate([('Senior AI Engineer','Example Company | US remote | Salary not disclosed','Python | RAG | Evaluation'),('Applied AI Architect','Example Labs | New York hybrid | USD 160k to 190k yearly','Architecture | Python | Cloud')]):
        y=490+i*220
        box(d,(310,y,1450,y+190),t,c)
        label(d,(330,y+100),s,font(21),width=1000)
        label(d,(330,y+145),'View details     Original posting     Compare resume     Save',font(20,True),fill='#087F8C',width=1050)
    label(d,(310,955),'Design concept with synthetic jobs  |  No live results or measured scores shown',font(17),width=1100)
    im.save(ASSETS/'ui_discover.png')

def hyperlink(p, text, target):
    part=p.part
    rid=part.relate_to(target,'http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink',is_external=True)
    h=OxmlElement('w:hyperlink'); h.set(qn('r:id'),rid)
    r=OxmlElement('w:r'); pr=OxmlElement('w:rPr')
    color=OxmlElement('w:color'); color.set(qn('w:val'),'087F8C'); pr.append(color)
    r.append(pr); t=OxmlElement('w:t'); t.text=text; r.append(t); h.append(r); p._p.append(h)

def inline(p,text):
    parts=re.split(r'(\[[^\]]+\]\([^)]+\)|\*\*.*?\*\*|`[^`]+`|https?://\S+)',text)
    for part in parts:
        if not part: continue
        m=re.fullmatch(r'\[([^\]]+)\]\(([^)]+)\)',part)
        if m:
            label_,target=m.groups()
            if target.startswith('../deliverables/word/'):
                target=target.rsplit('/',1)[-1]
            elif target.endswith('.md'): target='../../docs/'+target
            hyperlink(p,label_,target)
        elif part.startswith('http'): hyperlink(p,part,part)
        else:
            r=p.add_run(part[2:-2] if part.startswith('**') else part[1:-1] if part.startswith('`') else part)
            if part.startswith('**'): r.bold=True
            if part.startswith('`'): r.font.name='Consolas'; r.font.size=Pt(9)

def table(doc,rows):
    cols=len(rows[0]); t=doc.add_table(rows=0,cols=cols)
    t.alignment=WD_TABLE_ALIGNMENT.CENTER; t.autofit=False
    widths={2:[2.0,4.8],3:[1.55,2.65,2.6]}.get(cols,[6.8/cols]*cols)
    if rows[0]==['Document','Markdown source','Word version']:
        widths=[4.6,1.1,1.1]
    for col,width in zip(t.columns,widths): col.width=Inches(width)
    for i,row in enumerate(rows):
        cells=t.add_row().cells
        for j,cell in enumerate(cells):
            cell.width=Inches(widths[j]); cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
            tcpr=cell._tc.get_or_add_tcPr()
            sh=OxmlElement('w:shd'); sh.set(qn('w:fill'),'17354D' if i==0 else 'F0F5F8' if i%2==0 else 'FFFFFF'); tcpr.append(sh)
            margins=OxmlElement('w:tcMar')
            for side,val in [('top','85'),('bottom','85'),('left','110'),('right','110')]:
                e=OxmlElement('w:'+side); e.set(qn('w:w'),val); e.set(qn('w:type'),'dxa'); margins.append(e)
            tcpr.append(margins)
            p=cell.paragraphs[0]; p.paragraph_format.space_after=Pt(2); p.paragraph_format.space_before=Pt(2)
            inline(p,row[j] if j<len(row) else '')
            for r in p.runs:
                r.font.size=Pt(9)
                if i==0: r.bold=True; r.font.color.rgb=RGBColor(255,255,255)
        trpr=t.rows[-1]._tr.get_or_add_trPr()
        if i==0: trpr.append(OxmlElement('w:tblHeader'))
        trpr.append(OxmlElement('w:cantSplit'))
    borders=OxmlElement('w:tblBorders')
    for side in ('top','left','bottom','right','insideH','insideV'):
        e=OxmlElement('w:'+side); e.set(qn('w:val'),'single'); e.set(qn('w:sz'),'4'); e.set(qn('w:color'),'D9D9D9'); borders.append(e)
    t._tbl.tblPr.append(borders)
    doc.add_paragraph().paragraph_format.space_after=Pt(2)

def word(name,md):
    doc=Document(); sec=doc.sections[0]
    sec.page_width=Inches(8.5); sec.page_height=Inches(11)
    sec.top_margin=sec.bottom_margin=Inches(.7); sec.left_margin=sec.right_margin=Inches(.8)
    styles=doc.styles
    for border in list(styles.element.iter(qn('w:pBdr'))):
        border.getparent().remove(border)
    for n in ('Normal','Title','Subtitle','Heading 1','Heading 2','Heading 3'):
        styles[n].font.name='Calibri'; styles[n].font.color.rgb=RGBColor(0,0,0)
    styles['Normal'].font.size=Pt(10.5)
    styles['Normal'].paragraph_format.space_after=Pt(7)
    styles['Normal'].paragraph_format.line_spacing=1.08
    styles['Title'].font.size=Pt(26); styles['Title'].font.bold=True
    styles['Title'].paragraph_format.space_after=Pt(12)
    for n,sz in [('Heading 1',15),('Heading 2',12),('Heading 3',11)]:
        styles[n].font.size=Pt(sz); styles[n].font.bold=True
        styles[n].paragraph_format.space_before=Pt(13); styles[n].paragraph_format.space_after=Pt(6)
    header=sec.header.paragraphs[0]; header.add_run('SANDHĀTĀ   |   FDE DELIVERY BASELINE').font.size=Pt(8)
    footer=sec.footer.paragraphs[0]; footer.alignment=WD_ALIGN_PARAGRAPH.RIGHT
    footer.add_run('Design baseline 0.1   |   Page ').font.size=Pt(8)
    fld=OxmlElement('w:fldSimple'); fld.set(qn('w:instr'),'PAGE'); footer._p.append(fld)
    lines=md.splitlines(); i=0; code=False
    while i<len(lines):
        line=lines[i]
        if line.startswith('```'): code=not code; i+=1; continue
        if code:
            p=doc.add_paragraph(); p.paragraph_format.space_after=Pt(2)
            p.paragraph_format.line_spacing=1
            r=p.add_run(line); r.font.name='Consolas'; r.font.size=Pt(8)
            i+=1; continue
        if not line.strip(): i+=1; continue
        if line.startswith('|'):
            rows=[]
            while i<len(lines) and lines[i].startswith('|'):
                if not re.match(r'^\|\s*:?-',lines[i]): rows.append([s.strip() for s in lines[i].strip('|').split('|')])
                i+=1
            table(doc,rows); continue
        if line.startswith('!['):
            m=re.match(r'!\[([^\]]*)\]\(([^)]+)\)',line)
            if m:
                p=doc.add_paragraph(); p.paragraph_format.keep_with_next=True
                p.add_run().add_picture(str(DOCS/m.group(2)),width=Inches(6.75))
                c=doc.add_paragraph(m.group(1)); c.paragraph_format.space_after=Pt(10)
                for r in c.runs: r.italic=True; r.font.size=Pt(9)
            i+=1; continue
        if line.startswith('# '): doc.add_paragraph(line[2:],'Title')
        elif line.startswith('## '): doc.add_heading(line[3:],1)
        elif line.startswith('### '): doc.add_heading(line[4:],2)
        else:
            style='List Bullet' if line.startswith('- ') else 'List Paragraph' if re.match(r'^\d+\. ',line) else None
            text=line[2:] if style=='List Bullet' else line
            p=doc.add_paragraph(style=style); inline(p,text)
        i+=1
    doc.core_properties.title=md.splitlines()[0][2:]
    doc.core_properties.author='Prepared for Hema Chepuri'
    doc.core_properties.subject='Sandhātā Forward Deployed Engineering delivery baseline'
    doc.save(WORD/(name+'.docx'))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reset-sources',action='store_true',help='Replace Markdown with the original embedded baseline')
    args=parser.parse_args()
    diagrams()
    idx=['| Document | Markdown source | Word version |','| --- | --- | --- |']
    for name in sorted(CONTENT):
        if name.startswith('00'): continue
        title=CONTENT[name].splitlines()[0][2:]
        idx.append(f'| {title} | [Markdown]({name}.md) | [Word](../deliverables/word/{name}.docx) |')
    CONTENT['00_Document_Index']=CONTENT['00_Document_Index'].replace('INDEX_PLACEHOLDER','\n'.join(idx))
    manifest=[]
    for name,md in sorted(CONTENT.items()):
        p=DOCS/(name+'.md')
        if p.exists() and not args.reset_sources and not name.startswith('00'):
            md=p.read_text(encoding='utf-8')
        p.write_text(md,encoding='utf-8'); word(name,md)
        manifest.append({'name':name,'markdown':str(p.relative_to(ROOT)).replace('\\','/'),'word':f'deliverables/word/{name}.docx','source_sha256':hashlib.sha256(md.encode()).hexdigest(),'words':len(md.split())})
    (ROOT/'deliverables'/'manifest.json').write_text(json.dumps({'version':'0.1','date':'2026-10-26','documents':manifest,'application_status':'design_only','qa_status':'pending_render'},indent=2),encoding='utf-8')
    print(json.dumps({'documents':len(manifest),'words':sum(m['words'] for m in manifest),'word_directory':str(WORD)},ensure_ascii=True))

if __name__=='__main__': main()
