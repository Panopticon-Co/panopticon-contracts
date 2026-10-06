# ADR 0011: Collection providers, fallbacks and declared capability

## Status

Accepted for Linux (Linux ADR 005). Proposed as the platform rule. Date: 2026-10-06.

## Context (current evidence)

- **Linux** runs providers per capability family, each tier `primary` or `fallback`. For example,
  process telemetry can come from eBPF or from netlink proc connector plus `/proc`, and file
  telemetry from fanotify.
  - Its `health` record lists, per provider: `name`, `state`, `reason`, `capabilities`, `events`,
    `drops`, `family` and `tier`.
  - Records carry `provenance.provider` and `mechanism`, and `unavailable` lists the fields a
    fallback could not fill.
- **Windows** combines ETW and Sysmon.
  - It reports coverage per capability through `CapabilityState`: available, unavailable,
    unsupported, and so on.
  - Coverage keys include `Q.security_product` and `state.security_center.*`.
- The two models express the same idea with different vocabularies.

## Decision

1. Every endpoint declares capabilities from a shared catalog in contracts. Examples:
   `process.exec`, `process.exit`, `file.write`, `network.connect`, `dns.query`, `auth.logon`,
   `response.kill_process`.
2. Each capability has one state from the closed set
   `active | degraded | unavailable | unsupported | disabled`, plus the provider and tier
   (`primary | fallback`) and a reason code.
3. A fallback provider must:
   - mark its records' `provenance.mechanism`;
   - list unfillable fields in `unavailable`;
   - never claim `exact` identity resolution it cannot guarantee (ADR 0003).
4. A change in capability state is a `health` record. Coverage (ADR 0016) is computed from these
   records and from gaps.

## Alternatives considered

- **Per-agent vocabularies, translated in Manager.** That moves an endpoint concern into Manager,
  and the Console would show different words for the same thing.

## Consequences

- Linux maps its provider states onto the closed set; Windows maps `CapabilityState` onto it.
- The capability catalog becomes the source for the Console coverage view and for the matrix in
  each agent's documentation.

## Migration

The capability catalog and the health body are part of endpoint-record 2.0 (ADR 0002). Until
then, Manager maps both health forms into the coverage projection.

## What remains provisional

- Granularity: whether capabilities are per category or per field group.
