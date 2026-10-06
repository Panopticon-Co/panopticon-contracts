# Canonical endpoint record 1.0

The record envelope preserves Windows endpoint evidence independently of the legacy five-category telemetry schema. Schema: `schema/endpoint-record/1.0.schema.json`. C++-produced examples: `fixtures/endpoint-record/1.0/valid.json`. The generic envelope supports observation, state, health, gap, evidence and command-result records; supporting an envelope kind does not establish that its complete collection/response subsystem exists.

Protocol 2 uses authenticated HTTPS `POST /api/v2/endpoint/records`, NDJSON, at most 1,000 records/8 MiB per batch and 1 MiB per record. Agent identity must match the bearer enrollment; host identity must match the enrollment's host. A mismatch rejects the entire request with 403 and acknowledges nothing. Old protocol 1 remains separate; batches must never mix protocols. Manager commits with FULL/WAL before sending receipts. Duplicate record IDs require byte-identical payloads; a collision rejects/rolls back the batch with 409, preserving existing evidence.

The response echoes batch ID and exact received/accepted/duplicate/rejected counts. Rejections identify a one-based line and, when available, its `record_id` in the compatibility `event_id` field. Missing/partial/invalid receipts acknowledge nothing. The endpoint retains rejected originals and reasons rather than disposing of evidence.

`endpoint` separates enrolled `agent_id`/`host_id`, Windows `device_id`, persistent random `installation_id`, and nullable native `boot_id`. Device ID is currently Windows MachineGuid, which can be duplicated by imaging; it is neither authentication nor a universally unique hardware identity. Installation identity belongs to the protected journal. Enrollment identity is loaded before canonical collection. Collector epochs are independently random; `sequence` orders observations within that epoch. Sequence gaps after failed acceptance remain visible in later records, but durable live gap accounting is unfinished.

All opaque 64-bit tokens use decimal strings: native creation ticks, source record IDs, collector generation, sequence and exact signed nanosecond event time. This prevents JavaScript number rounding. Display timestamps are UTC millisecond strings; precise event time remains separately retained. Provenance explicitly labels current source continuity `unverified`; native loss/bookmark supervision is not yet qualified.

`collector_generation` is optional for compatibility with prior record 1.0
producers; every new Windows factory supplies a nonzero installation-scoped
generation committed before collection. Manager migration 14 binds generations
to random epochs and orders state by generation/sequence rather than client wall
clock. A generation/epoch fork returns whole-request 409 with no acknowledgment.
Other installations remain retained history until a controlled activation
workflow is implemented. Latest readback includes `projection_status` with
`current`, `superseded`, `inactive_installation` or `unverified` ordering. Consumers
must inspect this status. Observation freshness stays explicitly `unverified`:
even the latest ordered record can be an offline backlog. Native-source/live
coverage proof, controlled installation replacement and restart qualification
remain open.

Canonical capture age is now a separate optional proof. Provenance may include
paired `capture_clock` and decimal uint64 `capture_uptime_ms`; new Windows records
use `windows_uptime_ms`. Authenticated `POST /api/v2/endpoint/freshness-challenge`
issues an agent-bound one-use nonce valid for 15 seconds. Upload headers carry
`X-Panopticon-Freshness-Nonce` and `X-Panopticon-Capture-Context` (installation,
boot, generation, epoch and decimal `send_uptime_ms`). Manager migration 15 binds
matching capture facts to a conservative age bound and reports capture freshness
separately from ordering and native observation freshness. Invalid/missing proof
does not reject telemetry; capture stays unverified. Duplicate receipts never
renew capture age. Unknown Manager process epochs or unsupported elapsed clocks
invalidate proof. Receipt `capture_age_records` counts newly accepted records
with capture-age facts, not fresh or healthy sensors. Native source-event age,
sensor continuity, distributed/restart qualification and controlled replacement
remain open.

Process resolution is mandatory when a process reference exists:

- `native_exact`: entity derived from host + native boot + PID + exact native creation token. Never round time.
- `source_scoped`: source GUID + provider/channel namespace + host + boot scope + observed PID. Different families from the same source join through the same GUID.
- `native_unscoped`: exact native token exists but native boot scope is unavailable. Entity is null.
- `unresolved`: insufficient instance facts. Entity is null; preserve observed PID and facts.

Digest input is concatenated UTF-8 fields, each encoded as its decimal **byte** length, colon, then bytes. Native fields: `native-process-instance-v1`, host ID, boot ID, decimal PID, decimal creation ticks. Source fields: `source-process-instance-v1`, host ID, boot ID or `unknown`, namespace, decimal PID, source GUID. Entity is `proc_` plus lowercase SHA-256. Manager verifies digest, boot scope and payload/reference consistency. The subject reference is authoritative; payload process identity must not contradict it.

Do not join native and source-scoped instances using PID, millisecond proximity, or the current process behind a historical PID. A verified alias bridge requires stronger evidence and remains unfinished. A source-scoped identity alone does not authorize native process response. Exact held-handle target re-observation is still required at execution time. Requested parent and actual creator must eventually be separate relationships; the current parent PID is not promoted into a verified parent instance.

The JSON Schema validates structural shape. Consumers must also enforce semantic checks: actual calendar timestamps; uint64/signed-nanosecond bounds; exact/source/unresolved resolution prerequisites; boot consistency; identity digest and process payload agreement; valid/unique bounded health capability states; authentication and host binding. Manager's typed validator enforces these checks. Standalone fixture validation checks identity digests and key uncertainty invariants; it is not a replacement for complete receiver validation.

Explicit parent references follow the same digest/boot proof rules as subjects;
their PID/entity payload must agree. A payload parent entity without a reference
is invalid. Known observation families also require matching envelope/payload
categories. Requested parent and actual creator remain separate future facts.

Manager migration 13 adds durable Detection disposition to retained canonical
records, including upgrade backfill. The engine validates exact/source references
and uses an entity index independent of legacy PID/time heuristics. Unresolved
activity/ancestry never inherits a guessed instance. All canonical-triggered
alerts carry `endpoint_context` (triggering record, kind/category, endpoint,
provenance, subject) and agent-scoped SHA-256 replay identities. New domains expose
their full payload under explicit event vocabulary; domain rules still require
separate implementation/qualification.

Source supervision emits `kind=gap`, `category=source_loss`, null subject, and
agent provenance from `Officer-Source-Supervisor`. Data retains named counters,
their units, exact decimal totals/previous/deltas, null unknown counts/deltas,
consumer/statistics transitions and pending reconciliation. Event loss, buffer
loss and subscription notifications are distinct units and must not be summed.
Startup and counter reset/wrap/query outage do not establish continuous coverage.
These domain payloads use the existing extensible data object; Manager preserves
them and Detection exposes `endpoint_gap_source_loss` without inventing a process.
This partial gap producer does not imply complete loss accounting or bookmarks.

Observations additionally retain `data.source_facts` with representation
`decoded_source_facts_v1`, exact original decoded time/tokens/fields, and separate
`data.enrichment` for cached process context. Invalid UTF-8 fields use a lossless
hex-byte object rather than replacement text. Normalization/serialization refusal
is `kind=evidence`, `category=normalization_failure`, with agent provenance and
original decoded source facts. Capture time remains distinct from source event
time. These artifacts preserve currently decoded facts, not original native bytes
or all failed decoding. Native subject identity may remain exact despite a rejected
hash; unresolved source identity is never guessed from PID. Full domain payloads
remain available to Detection without pretending failed normalization succeeded.

Current limitations: cross-source alias proof, persistent process graph/lifecycle,
complete host inventory and state reconciliation (native `host_inventory` 1.0
snapshots now carry named per-query states and non-atomic/incomplete scope),
complete state models/rules, signed command/result 2, resumable evidence transfer,
schema generator/parity automation, complete durable source/stage gaps and reconciliation, health priority delivery,
bounded live observation age/proof, source/record cryptographic provenance,
Response/Console investigation and fleet qualification remain open. Canonical
record routing through Detection is implemented and fixture-tested; that does
not qualify the full end-to-end Windows endpoint surface.
