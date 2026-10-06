# Linux endpoint record 1.0

The wire contract for what `panopticon-sensord` (the Linux endpoint agent) emits, one JSON object per
line. Machine-readable definition: `schema/linux-endpoint/1.0.schema.json`. Fixtures:
`fixtures/linux-endpoint/valid` (real sensord output, trimmed) and `fixtures/linux-endpoint/invalid`.
Check with `python scripts/validate_linux_endpoint.py [--ndjson FILE]`.

This contract is separate from `schema/endpoint-record/1.0.schema.json` (the generic envelope used for
Windows records). The two are not interchangeable; a consumer routes on `schema_version` plus the
presence of `record_type`, and an adapter between them is a consumer concern, not a reason to bend
either schema.

Everything below was checked against records produced by a real sensord on Ubuntu 22.04, kernel
5.15 (508 records, 28 record types, zero validation failures). Types listed under "defined, not yet
emitted" are not in the schema.

## Envelope

Closed object (`additionalProperties: false`). Always present:

| Field | Meaning |
| --- | --- |
| `schema_version` | constant `"1.0"` |
| `record_type` | `event`, `state`, `health` or `loss` |
| `id` | 32 hex, derived from sensor id, boot id and `seq`: stable, so a replayed record keeps its id |
| `seq` | per-sensor monotonically increasing sequence, assigned when the record is written to the durable log; a gap is a detectable loss |
| `type` | `process.exec`, `file.create`, `state.users`, ... |
| `time` | when the thing happened (RFC 3339 UTC, nanoseconds) |
| `observed_time` | when the sensor saw it; `time <= observed_time` for kernel events |
| `host` | `id`, `boot_id`, `hostname` |
| `sensor` | `id`, `version`, `policy_version` |
| `provenance` | `provider`, `mechanism`, `confidence` (`observed`, `reconstructed`, `inferred`, `user_space_reported`) |
| `unavailable` | `[{field, reason}]`: what could not be filled in and why. Absent data is never silently null |

## The nine kinds of information

1. **Raw observations** stay inside the sensor (kernel ring buffers, netlink datagrams). They never
   cross the wire: provenance is carried instead.
2. **Normalized events** (`record_type: event`): `process.*`, `file.*`, `network.*`, `auth.*`,
   `kernel.*`, `mount.changed`. Each carries the actor `process` (full entity, or a `{pid}` stub with
   an `unavailable` entry when the actor exited first), and one body object named after the domain.
3. **Maintained state** (`record_type: state`, `type: state.<object>`): inventories sent in numbered
   parts (`part`, `parts`, `snapshot_id`): `processes`, `host`, `posture`, `users`, `groups`,
   `interfaces`, `mounts`, `modules`, `persistence`. Process items are fully specified. Items of the
   other objects are open objects documented in the telemetry catalog; their fields may grow within
   1.x.
4. **Derived events**: `fim.baseline`, `fim.changed` (a change found by comparing states, with the
   actor attached only when a file event named one), `hash.computed` (a digest arriving after the
   `process.exec` it belongs to; joined on `process.entity_id` + `exec_gen`).
5. **Detections**: defined, not yet emitted by the endpoint. Local policy decisions are produced by
   the policy engine but have no wire record yet.
6. **Evidence**: defined, not yet emitted (forensic acquisition is a later slice).
7. **Commands** and 8. **command results**: unchanged; they use the existing command and
   command-result contracts, which are not part of this schema.
9. **Health and coverage** (`record_type: health`, `loss`): provider states with reasons, a
   `coverage` map of capability to the provider currently supplying it (`null` when nothing does),
   resource use, kernel capabilities, and `loss` records that account for dropped events by stage and
   type. Silence must be explainable from these.

## Process identity

A process is `entity_id` (32 hex, stable for one process lifetime on one boot) with `exec_gen`
(increments on every exec, so a record before and after `execve` are distinguishable) plus `pid` and
`start_ticks`. The pair (`pid`, `start_ticks`) within a `host.boot_id` is the identity the response
path verifies before signalling anything. `confidence.identity` and `confidence.attributes` say
separately whether the identity and the descriptive attributes were observed or reconstructed.

## Delivery, rejection and loss

A record moves through distinct states, and the stream says which one it reached:

`observed` -> `accepted by the sensor` -> `durably committed` (WAL) -> `sent` -> `accepted by the Manager`.

A Manager HTTP 200 does not mean every record in the batch was stored. The acknowledgement
accounts for each record exactly once (`accepted`, `duplicates`, or `rejected` at a named line).
A record rejected permanently is quarantined at the sensor with its reason and sequence number,
the stream continues, and the sequence gap is never renumbered. The sensor then emits a `loss`
record with `stage: manager_rejected`, a count and the sequence numbers, so a rejection can be
told apart from ordinary loss (`kernel`, `queue`, `wal`, `governor`, `transport`).

The `health` body carries machine-readable coverage: providers with `state`, `reason`, `family` and
`tier` (`primary` or `fallback`), `coverage` (capability to serving provider, empty when
uncovered), `wal` (`next_seq`, `durable_seq`, `acknowledged_seq`, `dropped_records`), `totals`
(records, events, loss records, sink errors, uptime, from which rates follow between two health
records), `delivery` (state, acknowledged sequence, retries, refusals, quarantined counts and the
last quarantined sequence numbers) and `kernel` capability flags. `wal`, `totals` and `delivery`
and provider `family` and `tier` are optional so earlier 1.0 sensors remain valid.

## Versioning

Because the envelope is closed, a new field requires a schema release and a coordinated consumer
update, even when the change is additive. Additive changes (new optional fields, new event types,
new `unavailable.reason` values) are minor releases; a removed or retyped field is a new major
version.

## Inventory changes

`posture.changed`, `interface.changed`, `account.changed`, `package.changed`, `device.changed` and
`firewall.changed` are events with a `change` body: the differences between two consecutive
inventories of one host-state object (`object`, `total`, `part`/`parts`, `truncated`, and
`entries` of `{key, kind, before?, after?}` where `kind` is `added`, `removed` or `modified`). The
first inventory of an object is a baseline and produces no change. A change found by comparing
inventories names no acting process (`unavailable` lists `process`). Posture changes are per
setting (`sysctl.kernel/yama/ptrace_scope`), and a setting that could not be read is never reported
as removed. `before` and `after` are JSON values.

## Container context

A `process` object may carry `container`: `{id, runtime, pod_uid?}`. It is derived by the endpoint
from the process cgroup path (Docker, containerd, CRI-O and Podman scopes, and Kubernetes pod
slices), so it is present exactly when the path names a container and absent for host processes.
`runtime` is `kubernetes` when the path names a pod but not the runtime behind it. It is a claim
made by whoever created the cgroup, which is why `cgroup` is always kept next to it.

## UDP flows

`network.udp_flow` is the first datagram of a UDP flow from a process to a destination, once per
destination per 60 seconds per process. It uses the same `network` body as `network.connect`
(`direction` is `outbound`, `state` is empty).
