# ADR 0004: Process identity — one exact process key, one entity id

## Status

Proposed — needs team approval: the Detection Engine (Sokhi) and the Windows agent change.
Date: 2026-10-06.

## Context (current evidence)

Four process identities exist today (system design D4):

| Where | Derivation | Problem |
|---|---|---|
| Linux sensord | `sha256(host\|boot_id\|tgid\|start_ticks)[:32]` | No prefix; truncated |
| Windows Officer, process-entity-v2 | `proc_` + sha256(`"process-entity-v2"`, host, pid, start time in **ms**) | No boot; ms precision can collide for fast PID reuse |
| Windows Officer, process-context-v1 | `proc_` + sha256(host, pid, Sysmon process GUID) | Different id for the same process in another event family |
| Detection Engine | `(host_id, pid, timestamp)` resolved through per-PID live intervals | Explicitly ignores the agent ids, because they are inconsistent |

The command path already has an exact key on both agents: `{pid, start_time_ticks, boot_id}` in
command schema 2. Linux verifies it through pidfd and `/proc/<pid>/stat` field 22; Windows
verifies it through the native creation time. Live verification on Linux (2026-10-06) showed a
target from another boot refused with `boot_mismatch` and the exact target killed.

## Decision

1. **The process key** is `(host_id, boot_id, pid, start_ticks)`.
   - `boot_id` is the boot scope `boot_` + sha256 hex.
     - Linux: digest of the kernel `boot_id` text.
     - Windows: the agent's existing boot scope.
   - `start_ticks` is the OS-native start time as a canonical decimal string.
     - Linux: clock ticks since boot (`/proc/<pid>/stat` field 22).
     - Windows: FILETIME creation time in 100 ns units.
2. **The entity id** is `proc_` + sha256 hex of the UTF-8 string
   `process-key-v3\n<host_id>\n<boot_id>\n<pid>\n<start_ticks>`. It is computed identically by
   agents, Manager and Detection Engine. Contracts publish test vectors for it.
3. **The process reference** in an envelope is:
   - `{pid, start_ticks?, boot_id?, entity_id?, resolution, native?}`;
   - `resolution: exact` only when `start_ticks` came from the kernel for this very process;
   - otherwise `source_scoped`, `unscoped` or `unresolved` (ADR 0003), with `entity_id` omitted.
4. **The Detection Engine** joins on `entity_id` when `resolution = exact`. It keeps its interval
   resolver for records without an exact key: datasets, legacy Officer schemas and degraded
   providers. The resolver is kept, not discarded.
5. **Response** targets are built only from exact keys (ADR 0008). A detection that has no exact
   key can recommend collection, but cannot produce a kill target.

## Alternatives considered

- **Sysmon process GUID as the identity.** It exists only when Sysmon is installed, and has no
  Linux equivalent.
- **Keep the per-agent ids and translate them in Manager.** Manager cannot recompute an id
  without the inputs, and the ms-precision Windows id cannot be made exact afterwards.
- **(host, pid, time) intervals only.** This is Sokhi's current approach. It is robust for
  datasets, but cannot tell PID reuse apart within the clock resolution, and cannot be used for
  response.

## Consequences

- Linux changes `compute_entity_id` (prefix, full digest, boot digest instead of raw UUID).
  Internal WAL records written before the change keep their old ids, and Manager stores them as
  legacy ids.
- Windows adds the boot to its id and switches to 100 ns ticks.
- The Detection Engine's provenance graph keys nodes by `entity_id` when present. This is the
  only behavioural change to Sokhi's design, and it is additive.

## Migration

1. contracts publishes the derivation and test vectors.
2. Both agents emit `entity_id` v3 in endpoint-record 2.0 (ADR 0002). Linux 1.0 and Windows 1.0
   keep their current ids until 2.0.
3. Manager computes v3 itself from the key fields when they are present, so that both versions
   can be joined during migration.
4. The Detection Engine reads `entity_id` when `resolution = exact`.

## What remains provisional

- Thread identity, and containers: does the key need a PID-namespace component for Linux
  container processes? Today `tgid` is the root-namespace PID, which is correct for the host
  sensor.
- Process identity across hibernation on Windows.
