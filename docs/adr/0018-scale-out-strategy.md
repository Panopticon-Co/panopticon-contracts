# ADR 0018: Scale-out strategy

## Status

Proposed (P2: direction, not current work). Date: 2026-10-06.

## Context (current evidence)

- One Manager process, one SQLite file, and at most two endpoints have ever been connected at
  once.
- No performance measurement of Manager exists.
- Endpoint WAL and uplink measurements exist only for one Linux VM.

## Decision

Scale in this order, each step taken only when a measured threshold is crossed:

1. **Vertical scaling.** Manager runs multiple workers against PostgreSQL (ADR 0005). Ingest
   handlers are stateless. Detection runs in one worker per host shard, through the claim/lease
   queue.
2. **Read replicas** for the Console read API, when read load interferes with ingest.
3. **Separate ingest and processing deployments of the same Manager code**, when ingest latency
   (p99 above 500 ms at sustained load) or CPU saturation is measured. They still share
   PostgreSQL.
4. **A log or queue (Kafka or Redpanda) between ingest and processing**, only when PostgreSQL
   write throughput is the measured bottleneck after partitioning: roughly above 20–50k records/s
   sustained. ClickHouse comes in at the same time (ADR 0019).

## Alternatives considered

- **Microservices from the start.** Rejected: the cost is operational complexity, with no
  measured need.

## Consequences

- Every stage above has a performance test in `panopticon-lab/perf` that shows the threshold.

## Migration

None until the measurements exist.

## What remains provisional

- All the numbers. They are placeholders until the ADR 0017 `perf` suite produces data.
