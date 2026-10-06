# ADR 0021: Observability of the platform itself

## Status

Proposed (P2). Date: 2026-10-06.

## Context (current evidence)

- Manager logs to stdout.
- The Linux sensor reports its own health as telemetry and writes a log.
- There are no metrics endpoints and no tracing. Performance claims cannot be checked.

## Decision

1. **Manager exposes Prometheus metrics** (`/metrics`, internal network only):
   - ingest rate, latency and rejections by reason;
   - queue depth and age;
   - detection latency;
   - command lifecycle counts and latency;
   - database pool usage.
2. **Endpoints do not expose metrics ports.** Their self-metrics travel as `health` records
   (ADR 0016), and Manager re-exports them as metrics per host.
3. **Lab C runs Prometheus, Grafana and Loki** in an `obs` VM. Lab A and Lab B can run the same
   stack from compose when needed.
4. Every record and command carries correlation ids already (`record_id`, `command_id`,
   `correlation_id`). The harness uses them to follow an event end to end. OpenTelemetry tracing
   is deferred.

## Alternatives considered

- **OpenTelemetry everywhere now.** Useful later; the overhead is not justified yet.

## Consequences

- The `perf` suite (ADR 0017) reads Prometheus for its budgets.

## Migration

Metrics are added to Manager when it moves to PostgreSQL.

## What remains provisional

- Alerting on platform health.
