# ADR 0016: Health and coverage

## Status

Proposed. Date: 2026-10-06.

## Context (current evidence)

- Linux emits `health` records: overall `status`, per-provider state, counters, coverage.
- Windows emits `health` kind records and capability coverage (`CapabilityState` per key).
- Manager stores Linux health in `linux_endpoint_health`. There is no unified host view, and the
  Console shows no health at all.

## Decision

1. **Host health**, a Manager projection, combines:
   - last contact;
   - last record time and lag;
   - agent version and policy version;
   - boot;
   - delivery backlog (if the endpoint reports it);
   - the capability states (ADR 0011);
   - gap totals over a window (ADR 0009).
2. **Coverage** is a per-host matrix of capabilities × state, joined with the rules that need each
   capability (ADR 0012), so the Console can say "rule X cannot fire on host Y because
   `file.write` is unavailable".
3. **Status** is derived, never self-reported alone. A host is:
   - `healthy` when it has contact, its lag is within threshold, all primary capabilities are
     active and it has no new gaps;
   - `degraded` when any of those fail;
   - `silent` past a contact threshold.
4. The endpoint's own `status` is kept as an input, not as the verdict.

## Alternatives considered

- **Trust the endpoint's self-reported status.** A compromised or broken endpoint can lie, or
  simply stop reporting.

## Consequences

- The Console host view and the demo's coverage panel come from this projection.

## Migration

Manager maps both health forms now. endpoint-record 2.0 unifies them later.

## What remains provisional

- The thresholds.
- Whether to alert on health changes (detections of kind `sensor_tamper`).
