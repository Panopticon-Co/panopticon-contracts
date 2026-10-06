# ADR 0020: When the Detection Engine becomes distributed

## Status

Proposed (P2: criteria only). Date: 2026-10-06.

## Context (current evidence)

- The engine is in-process, single-threaded per worker, and keeps its state in memory, bounded
  by `max_window_events` with pruning under load (Sokhi, `c56bbdb`).
- Its provenance graph and incidents are per host.

## Decision

1. **The first scale step is sharding by host:** several Manager detection workers each own a
   set of hosts through the claim/lease queue. Engine state stays per host in each worker, and
   is rebuilt by replay when ownership moves.
2. **A separate detection service** is considered only when one of these holds:
   - a per-host engine cannot keep up with one host's rate;
   - cross-host correlation needs a global state that does not fit one worker;
   - the engine needs a different runtime (GPU or ML inference).
3. Cross-host incidents are Manager's job: a join over Detections in PostgreSQL. They are not
   shared engine state.

## Alternatives considered

- **Stream processing frameworks (Flink and similar).** Massive overhead for the current scale,
  and they would require rewriting Sokhi's engine.

## Consequences

- The engine API must allow state to be built per host, and dropped per host.

## Migration

None now.

## What remains provisional

- Everything here, until measured.
