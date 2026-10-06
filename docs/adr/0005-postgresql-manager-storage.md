# ADR 0005: PostgreSQL as Manager's shared store

## Status

Proposed — needs team approval: it touches every Manager module. Date: 2026-10-06.

## Context (current evidence)

- Manager uses one SQLite file in WAL mode for everything: agents, enrollment, legacy events,
  Linux endpoint records (`linux_endpoint_records`, `_streams`, `_detection`, `_health`),
  Windows endpoint records, the detection queue, alerts, response actions, commands and results.
- Manager ADR 003 chose "single worker, sync handlers, events-table-as-queue". That fits SQLite's
  single-writer model.
- The Windows branch has a 17-step migration chain. The Linux branch creates its tables ad hoc in
  `linux_endpoint_store.py`, outside the chain.
- The Console does not read the database at all: it reads an NDJSON file (ADR 0007).
- The Detection Engine's reliability layer has its own SQLite spool.
- Observed scale so far: one Linux VM produces tens to hundreds of records a second at idle, with
  bursts of thousands during builds. A five- to ten-endpoint lab stays well inside one
  PostgreSQL instance.

## Decision

1. **PostgreSQL 16 is Manager's only shared store**, with one database and these schemas:

   | Schema | Contents |
   |---|---|
   | `control` | agents, enrollment, credentials, policies |
   | `telemetry` | raw records as JSONB, partitioned by day; stream cursors; gaps |
   | `entity` | host, process, user, inventory and health projections |
   | `detection` | queue, detections, incidents, evidence references |
   | `response` | recommendations, approvals, commands, results, audit |
   | `artifact` | artifact metadata and custody (ADR 0015) |

2. **Schema changes go through one migration tool (Alembic)**, run at startup. There are no ad hoc
   `CREATE TABLE` statements in modules.
3. **The detection queue** is a table claimed with `SELECT ... FOR UPDATE SKIP LOCKED`, leased per
   host so that each host's events are processed in order.
4. **Idempotency** is enforced by unique constraints: `(stream_key, sequence)` and the record
   digest. Retries are no-ops.
5. **SQLite remains only as a unit-test backend** behind the same repository layer, for as long as
   the migration needs it. Integration tests run against PostgreSQL (a service container in CI;
   `postgres:16` in Docker locally).
6. **No Kafka, Redis or OpenSearch.** The queue, cache and search needs at this scale are met by
   PostgreSQL. ADR 0018 and ADR 0019 state when that changes.

## Alternatives considered

| Option | Verdict |
|---|---|
| **Keep SQLite** | Single writer, no concurrent detection workers, file-level locking under ingest bursts, no network access for Console or lab tools. Fine for a single-process demo; it does not grow. |
| **ClickHouse now** | Excellent for telemetry analytics, but the wrong fit for transactional state (commands, approvals, leases). Running it in addition doubles the operational surface before any volume justifies it. ADR 0019 sets the criteria. |
| **OpenSearch** | Strong full-text search, but weak relational guarantees, a heavy JVM footprint for a laptop lab, and nothing it does is needed by the current Console. |
| **Object storage for telemetry** | Right for artifacts (ADR 0015) and, later, cold telemetry archives; not for queryable state. |

## Consequences

- Manager gains a connection pool and async or threaded workers. Manager ADR 003's single-worker
  constraint is lifted (it is superseded for storage; the process model stays one deployable).
- The lab and CI need PostgreSQL, which is cheap in Docker.
- Raw telemetry retention becomes a partition drop.

## Migration

1. Introduce a repository layer over the existing SQL, keeping SQLite.
2. Port the Windows migration chain to Alembic, and fold the Linux tables into it.
3. Add a PostgreSQL implementation and run the full test suite against both backends.
4. Switch the lab to PostgreSQL. Keep SQLite for unit tests only.
5. Telemetry partitioning and the projection tables come with ADR 0002's single raw table.

## What remains provisional

- JSONB with GIN indexes versus extracted columns for hot fields: decided by query measurements.
- Retention periods.
- The TimescaleDB extension: not adopted; it is reconsidered only before ClickHouse.
