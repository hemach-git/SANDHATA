# Sandhātā Career Intelligence

**Search, Analyze, Navigate, Discover, Highlight, Apply, Track, Advance.**

Personal career intelligence for supported job discovery, assisted premium-portal imports, evidence-based resume comparison, application tracking and descriptive analytics.

## Current status

This repository begins with the FDE design and delivery baseline. Application code, automated tests, model evaluations and production deployment are not yet implemented. The October 26–27 2026 schedule is a target subject to verification gates.

## Documentation

Start with [the document index](docs/00_Document_Index.md). There are 22 matching Markdown and Word documents, including architecture and sequence diagrams and individual agent guides. Word versions are in `deliverables/word`.

The planned application uses Streamlit, Python, LangGraph, SQLite FTS5, versioned evidence and a configurable model adapter. Remotive and supported employer feeds provide automated ingestion; LinkedIn, Ladders and Indeed use assisted import unless approved programmatic access is established.

## GitHub

Destination: https://github.com/hemach-git/sandhata

The owner runs publication commands from [the GitHub guide](docs/11_GitHub_and_Collaboration_Guide.md). Check origin and the repository root before staging. Private resumes, job-history databases, tokens and environment files must remain outside Git.

## Regenerate the documents

Use the authoring Python environment with `python-docx` and Pillow, then run `python scripts/build_documents.py`. Existing Markdown is the editable source of record; the generator preserves its edits and rebuilds Word files, diagram images and the manifest. The document index is regenerated. The optional `--reset-sources` flag deliberately replaces Markdown with the original embedded baseline and must only be used when that reset is intended. Rendering and visual QA are a separate step.

Sandhātā is the display name; `sandhata` is the ASCII identifier. The English acronym is an original branding expansion, not a Sanskrit translation. Domain and trademark availability have not been verified.
