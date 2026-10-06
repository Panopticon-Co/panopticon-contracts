# ADR 0002: One canonical endpoint envelope (endpoint-record 2.0)

## Status

Proposed — needs team approval (it changes both agents' wire format). Date: 2026-10-06.

## Context (current evidence)

There are two endpoint record contracts, and each is internally sound:

- **Linux `linux-endpoint/1.0`** (`schema/linux-endpoint/1.0.schema.json`, Linux ADR 017).
  - Shape: a flat record with `schema_version`, `record_type`, `id`, `seq`, `type`, `time`,
    `observed_time`, `host{id, boot_id, hostname}`, `sensor{id, version, policy_version}`,
    `provenance{provider, mechanism, confidence}` and `unavailable`, plus one body object per
    family (`process`, `file`, `network`, `response`, ...).
  - Route: `POST /api/v2/linux-endpoint/records`.
  - Ordering: `seq` is per sensor and contiguous, and loss is a first-class record.
  - Status: verified against a real Manager on Ubuntu 22.04 / 5.15 / x86_64.
- **Windows `endpoint-record/1.0`** (`schema/endpoint-record/1.0`, snapshot branch).
  - Shape: a generic envelope.
    - `kind` ∈ {observation, state, health, gap, evidence, command_result}, plus `category`.
    - `endpoint{agent_id, host_id, device_id, installation_id, boot_id}`.
    - `provenance{collector_epoch, generation, sequence, native ids, continuity, capture_clock}`.
    - `subject` (a `ProcessReference` with `resolution`) and `data`.
  - Route: `POST /api/v2/endpoint/records`, with a freshness challenge.
  - Its own documentation says durable live gap accounting is unfinished.

The cost of having two:

- **Manager.** Two ingest routers, two sets of tables, two receipt formats.
- **Detection Engine.** It reads neither as its primary input: it normalizes Officer schema 0.x,
  and the Windows snapshot adds an `endpoint_adapter` for endpoint-record 1.0.
- **Linux families.** Only Linux `process.exec` reaches detection.
- **Shared code.** Every concept common to both (boot scope, sequence, loss, process reference,
  response audit) is implemented twice.

## Decision

1. **A single envelope, endpoint-record 2.0, for every endpoint.** It is owned by
   `panopticon-contracts` and has the following fields:

   | Field | Content |
   |---|---|
   | `schema_version` | `"2.0"` |
   | `record_id` | Producer-unique id. Delivery idempotency is keyed on `(stream, sequence)` and on the record digest. |
   | `kind` | `observation \| state \| health \| gap \| evidence \| response` |
   | `category` | Dotted, closed per OS family. For example `process.exec`, `file.write`, `network.connect`, `auth.logon`, `registry.set`, `response.action`. |
   | `endpoint` | `{agent_id, host_id, installation_id, boot_id, os: linux\|windows}`. `boot_id` is the boot scope `boot_` + 64 lowercase hex (ADR 0004). |
   | `stream` | `{collector_epoch, sequence}`. A contiguous sequence per (installation, boot, epoch); ADR 0009. |
   | `time` | `{event, observed}`, RFC 3339 UTC. |
   | `provenance` | `{provider, mechanism, confidence, native?}` |
   | `subject` | Optional process reference (ADR 0004). |
   | `data` | The category body, validated by a per-category `$def`. Common bodies (process, file, network, auth, dns, response) are shared; OS-only categories have OS-only bodies. |
   | `unavailable` | Optional list of fields that the provider could not supply. |

2. The schema stays strict (`additionalProperties: false`) at every level. Unknown categories are
   rejected, not passed through.
3. **One ingest route, `POST /api/v2/endpoint/records`, with one receipt shape.** The receipt
   gives an acknowledged sequence per stream, and per-line rejections with closed reason codes.
4. `kind: gap` is how loss is represented, for both operating systems (ADR 0009).

## Alternatives considered

- **Keep two contracts and normalize in Manager.** This is cheapest today. But every common
  concept stays duplicated, and every new consumer (Console, lab harness, a future analytics
  store) would have to understand both. Rejected as an end state; it is the migration path.
- **Adopt the Linux flat record for Windows.** It is simpler to read. But the per-family top-level
  body does not generalize as cleanly as `kind` + `category` + `data`, and Windows already emits
  `state`, `evidence` and continuity metadata that would have to be bolted on.
- **Adopt Windows 1.0 unchanged.** It lacks contiguous per-stream sequence semantics and durable
  gap records, which Linux has proven.
- **A binary format (protobuf/CBOR).** Not needed at the current volume, and NDJSON is
  inspectable in a lab. This can be revisited at the ADR 0018 thresholds.

## Consequences

- Both agents change their serializers. The Linux internal record model and WAL are unaffected:
  the change is in the serializer only.
- Manager has one validator and one raw table.
- Detection consumes the canonical detection event derived from the envelope (ADR 0006), not
  agent-specific shapes.
- The fixtures in contracts become the single acceptance suite for both producers.

## Migration from the current state

1. Write `endpoint-record/2.0` in contracts. Linux and Windows producers contribute real fixtures
   taken from live records; this is not hand-written data.
2. Manager accepts 2.0 on the existing `/api/v2/endpoint/records` route, distinguished by
   `schema_version`. 1.0 (Windows) and `linux-endpoint/1.0` stay accepted, are mapped into the
   same raw table, and are marked `legacy`.
3. Linux sensord gains a 2.0 serializer behind configuration (`uplink_contract=2.0`). The default
   flips after a lab run in which the records are verified.
4. Windows Officer follows the same steps.
5. Remove the legacy routes once neither agent's release manifest uses them.

## What remains provisional

- The exact category list for each OS: it grows with telemetry.
- Whether `evidence` and `state` stay separate kinds.
- A binary encoding.
- The freshness challenge on ingest: it is kept, but whether Linux adopts it is decided with
  ADR 0013.
