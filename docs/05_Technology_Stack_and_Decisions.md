# Sandhātā Technology Stack and Decisions

Version 0.1 | October 26 2026 | Prepared for Hema Chepuri | Design baseline

This document specifies the intended implementation. Application code, test results, live integrations, GitHub publication and production deployment are not established by this document. Dates are delivery targets in America/New_York, subject to the release gates.

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
