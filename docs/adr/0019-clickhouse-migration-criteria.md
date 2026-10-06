# ADR 0019: When telemetry moves to ClickHouse

## Status

Proposed (P2: criteria only). Date: 2026-10-06.

## Context (current evidence)

Raw telemetry will live in PostgreSQL partitions (ADR 0005). Analytics-style queries over long
ranges (hunting, baselines) are where a column store wins.

## Decision

Telemetry, and only telemetry, moves to ClickHouse when **any** of these is measured:

- raw records retained exceed about 500 GB, or 2 billion rows, on PostgreSQL;
- hunting queries over 7 days exceed 10 s p95 after indexing;
- ingest write load on PostgreSQL degrades transactional latency (commands, approvals) beyond
  budget.

When that happens:

- PostgreSQL keeps all transactional and projection state;
- ClickHouse receives raw records through the same ingest pipeline (dual write, or a CDC
  stream);
- the Detection Engine still receives CDEs from Manager, not from ClickHouse.

## Alternatives considered

| Option | Why not |
|---|---|
| OpenSearch | Heavier, and weaker for aggregation |
| TimescaleDB | A smaller step that keeps one engine; considered first when the criteria approach |

## Consequences

- The ingest code writes raw records through one interface, so a second sink can be added.

## Migration

None now.

## What remains provisional

- The thresholds.
