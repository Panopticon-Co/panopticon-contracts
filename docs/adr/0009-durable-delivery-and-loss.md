# ADR 0009: Durable delivery and explicit loss

## Status

Proposed as the platform rule. Implemented on Linux; partial on Windows. Date: 2026-10-06.

## Context (current evidence)

- **Linux**
  - Durability: segmented CRC-framed WAL (Linux ADR 008), fsync policy, a bounded size with an
    explicit eviction loss record (`record_type: loss`).
  - Delivery: the uplink sends batches in sequence order. The cursor advances only on an
    acknowledgement that names an acknowledged sequence (Linux ADR 018).
  - Rejections: a rejected record is quarantined locally, and a `manager_rejected` loss record is
    emitted.
  - Gaps: producer-side drops (queue overflow, provider loss, ring-buffer loss) become loss
    records with ranges and reasons, and survive restart.
  - Verified: against the real Manager, including restart without loss and rejection quarantine.
- **Windows**
  - Durability: a durable telemetry spool, plus `gap` kind and continuity metadata in
    endpoint-record 1.0.
  - Delivery: the freshness challenge on ingest.
  - Gaps: its own documentation states that live durable gap accounting is unfinished.
- **Manager** stores Linux stream cursors (`linux_endpoint_streams`) and acknowledges per stream.
  Windows uses its own receipt.

## Decision

1. **Delivery is at least once.** Every endpoint keeps records in a local durable log until
   Manager acknowledges them. Duplicates are expected; Manager makes them no-ops through
   `(stream, sequence)` and digest uniqueness.
2. **A stream is (installation, boot, collector_epoch).** Its sequence starts at 1 and is
   contiguous. A missing range is either a `gap` record or a defect.
3. **Every loss is represented:**
   - producer drop, eviction, provider failure and Manager rejection all become `gap` records;
   - each gap carries the range, a closed reason code, and a count when the range is not exact.
4. **Manager acknowledges per stream**, with per-line rejections. A rejected record is not
   acknowledged as accepted; it is acknowledged as rejected. The endpoint quarantines it and
   emits a gap.
5. **Coverage is computed from gaps** (ADR 0016). The Console shows it, so missing telemetry is
   visible as missing.

## Alternatives considered

- **Exactly-once** delivery: unachievable across an HTTP boundary without two-phase commit, and
  idempotent receipt makes it unnecessary.
- **Best-effort** delivery without loss records: hides blind spots. Unacceptable for an EDR.

## Consequences

- Windows must finish durable gap accounting to conform.
- Manager needs one stream-cursor table for both operating systems (ADR 0002, ADR 0005).

## Migration

- Linux: no change beyond the 2.0 serializer.
- Windows: complete gap accounting, then run the chaos suite (ADR 0017): kill -9, Manager outage,
  full disk.
- Manager: a single stream table in PostgreSQL.

## What remains provisional

- Backpressure signalling from Manager (HTTP 429 with retry hints) is to be measured in the
  ADR 0018 performance runs.
- Endpoint-side retention limits under a long outage.
