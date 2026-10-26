# Sandhātā Production Deployment and Release Guide

Version 0.1 | October 26 2026 | Prepared for Hema Chepuri | Design baseline

This document specifies the intended implementation. Application code, test results, live integrations, GitHub publication and production deployment are not established by this document. Dates are delivery targets in America/New_York, subject to the release gates.

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
