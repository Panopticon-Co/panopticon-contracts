# ADR 0007: Console reads Manager's API, not files

## Status

Proposed. Date: 2026-10-06.

## Context (current evidence)

- `panopticon-console` (`main` `296e1ad`) is a small Python server.
- It reads the Detection Engine's alert NDJSON file from a configured path, and proxies one
  read-only Manager route (`/api/v1/response-actions`).
- It cannot show host health, coverage, raw records, incidents, command results or approvals.
- When the engine runs inside Manager (the live configuration), the NDJSON file is not the system
  of record. Manager's tables are.
- Manager has the data but no read API designed for an analyst UI.

## Decision

1. **The Console is a client of a Manager read API, and nothing else.** It reads no files and no
   database.
2. **Manager exposes `/api/v1/console/...`** (read model) for:
   - hosts (health, coverage, last seen, agent version, boot);
   - records (filtered, paged);
   - detections and incidents (with evidence);
   - process trees (by `entity_id`);
   - recommendations, approvals and commands with results;
   - artifacts (metadata, download through Manager).
3. **Mutations go through explicit endpoints** (approve, reject or cancel a command; acknowledge
   a detection), and every one is authenticated and audited. Analyst identity is a Manager
   concept (ADR 0013).
4. **The read model** is PostgreSQL views or projection tables (ADR 0005). Paging is
   cursor-based.
5. The API is described by OpenAPI, generated from Manager. Console tests run against a recorded
   fixture of it.

## Alternatives considered

- **Keep the NDJSON file.** It cannot show anything Manager knows that the engine does not, and
  breaks when the engine runs in-process.
- **The Console reads PostgreSQL directly.** That couples the UI to the storage schema and
  bypasses authorization. Rejected.
- **GraphQL.** Not needed for the current screens.

## Consequences

- Manager gains a read-API module and analyst authentication. A local account with a session is
  enough for the lab; SSO is later.
- The Console becomes thin. Its current alert view is re-pointed at `/api/v1/console/detections`.

## Migration

1. Manager adds the read endpoints over the current tables (SQLite is acceptable for this step).
2. The Console switches its alert source behind a setting. The NDJSON reader is removed once the
   lab demo uses the API.
3. Approval actions are added when ADR 0013's analyst identity exists.

## What remains provisional

- The UI technology (the README previously claimed Next.js/React; the code is a Python server).
- Live updates (polling or server-sent events).
- Multi-tenant scoping.
