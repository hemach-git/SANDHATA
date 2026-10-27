# SANDHĀTĀ Memory and RAG Design

Version 0.2 | October 26 2026 | Prepared for Hema Chepuri | Design baseline

This document specifies the intended implementation. Application code, test results, live integrations, GitHub publication and production deployment are not established by this document. Dates are delivery targets in America/New_York, subject to the release gates.

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

Parse text, preserve a canonical normalized text representation, split at headings and bullet boundaries, and retain parent version, section and character offsets. Target 300 to 600 tokens per passage with small overlap only when needed. Quotes and offsets refer to canonical stored text; the original payload remains separate. PostgreSQL indexes authorized passage tsvectors with GIN and ranks using ts_rank. Explicit skill aliases handle punctuation-heavy skills such as C++ and C# and variants such as PostgreSQL/Postgres without rewriting source evidence. Owner scope and RLS apply before ranking.

## Retrieval pipeline

Validate the question, select entity/version scope, apply structured filters, perform parameterized FTS lookup, rank and return up to five passages initially. Apply a total context budget of 6000 tokens, including the question and system instructions; truncate with an explicit omitted-evidence flag. Retrieve neighboring passages when a requirement refers to a prior heading. Candidate grouping prevents duplicates from occupying every slot.

Resume matching filters to the chosen resume version and chosen description version before retrieval. A general question can search authorized saved jobs, but cannot silently combine resumes as if they were one document. Tracker counts and dates come from SQL aggregates with record citations rather than lexical passages.

## Citation contract

EvidenceRef contains entity_type, entity_id, version_id, passage_id, section, start_offset, end_offset and quote. The validator checks the quote against the version text and confirms that it falls inside the referenced passage. UI citations open the stored record and show the relevant passage; source job URLs remain available separately. If a record is deleted or not available, the assistant abstains or reports the limitation.

## Freshness and retention

Preference changes affect new runs; prior results retain prior inputs. Job refresh does not overwrite applied-to snapshots. Keep execution logs 14 days and checkpoints seven days as initial configurable defaults. Keep owner career records until explicit deletion. Backups retain at most seven daily snapshots by default; record deletion tombstones and replay them during restore until all affected backups expire. Explain that immediate deletion from active storage does not erase prior offline backups instantly.

## Privacy and future semantic search

Do not send contact details to hosted models when not needed. Keep protected uploads and indexes outside the repository, with OS permissions and encrypted host storage. If measured lexical recall is inadequate, add local embeddings and pgvector after selecting PostgreSQL or a measured local vector option. Embedding indexes inherit the same version filters, deletion rules and privacy restrictions. RAG quality is evaluated using the queries and gates in document 08.

## Multi user memory isolation

Every preference, imported job, description, passage, resume, match, tracker event, follow-up, task and conversation checkpoint belongs to tenant_id and owner_user_id. Only public provider payloads may be cached across users. Public source facts do not make personalized saved searches or notes public.

PostgreSQL full-text queries apply the authenticated owner scope in SQL/RLS before ranking or limiting. No shared FTS index result set may be filtered only after retrieval, because ranking, snippets and counts can disclose other members' data. Conversations and checkpoints use tenant/user/run keys. Embeddings, if added, require the same pre-retrieval isolation and deletion rules.

Administration queries expose account, storage and operational metadata only. Per-member career analytics remain protected; household metrics aggregate system usage rather than resumes, skill gaps or application outcomes. Erasure removes active files/indexes/checkpoints and protected derived content; backup tombstones survive until affected backups expire. Never cascade deletion from a shared public feed cache into unrelated member records.
