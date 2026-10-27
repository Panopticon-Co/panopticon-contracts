# Endpoint telemetry catalog (endpoint-record 1.0)

Producer: `panopticon-agent` (Officer, Windows). Consumers: Manager v2 ingest,
the Detection Engine, and the response path. This document, the envelope schema
`schema/endpoint-record/1.0.schema.json`, the family schemas under
`schema/endpoint-record/1.0/families/` and [ENDPOINT_RECORD_1.md](ENDPOINT_RECORD_1.md)
form the contract. If they disagree, the schemas win, and the disagreement is a bug.
Agent-side field-level ML parity notes stay in the agent's
`docs/windows-endpoint/FEATURE_FIELD_PARITY.md`. That page defers to this one on
wire semantics.

## 1. Authoritative representation and version

- Wire format: one JSON object per record, `schema_version: "1.0"`, uploaded as
  protocol-2 NDJSON (see ENDPOINT_RECORD_1.md).
- `kind` ∈ observation | state | health | gap | evidence | command_result.
  `category` names the family.
- `data` is defined per `(kind, category)` by the family schema listed in
  `families/index.json`. A family that isn't indexed is validated at the envelope
  level only. Consumers must treat that family's `data` as producer-defined and
  unversioned.
- Validation: `python scripts/endpoint_records.py [--current-producer] [paths]`.

## 2. Pipeline mapping (what each boundary keeps, derives or drops)

| Boundary | Transformation | Preserved | Derived | Dropped |
|---|---|---|---|---|
| Native source → `RawEvent` | Decoders (TDH/ETW, Sysmon XML, minifilter port, hook pipe) build typed facts | Decoded fields, exact text, native tokens | Nothing | Native bytes; undecodable records become decoder failures counted in collector health |
| `RawEvent` → `source_facts` | `decoded_source_facts_v1` | Every decoded field, invalid UTF-8 as hex, enum indices (`*_value`) | Nothing | Nothing |
| `RawEvent` → normalized (legacy-derived families) | `normalize_*_event` (0.3 vocabulary) | Category/type names, paths, network tuple | `event.id` (`evt_` hash), leaf name, user split, lowercase SHA-256 | Phase/status (kept in source_facts only); invalid hashes refuse normalization |
| → canonical record | `EndpointRecordFactory` | Normalized `data` + `source_facts` + `enrichment` | Envelope identities, `record_id`, epoch/sequence, `subject` (process reference), `received_at`, capture uptime | Legacy `schema_version`; the legacy PID-only entity is replaced by the canonical reference |
| Failure at any stage above | `normalization_failure` evidence | Source facts and error text | — | The would-be observation (never silently) |
| → journal | Encrypted durable append; checkpoint transaction for bookmarked sources | Exact record bytes | Local sequence | Nothing on acceptance; refusals are counted and retried |
| → upload → Manager | Protocol-2 batches; identical-bytes dedup by `record_id` | Bytes, receipts | Manager projections | Rejected records stay journaled with reasons |
| → Detection Engine | Canonical adapter (DE snapshot branch) or the legacy `OfficerIngestionAdapter` over `data` | See §9 | `event_type` | See §9 for measured losses |

## 3. Family catalog

| Family (kind/category) | Data layout | Source kinds today | Schema rev | Fixture | Highest evidence level |
|---|---|---|---|---|---|
| observation/process | legacy_derived | etw, sysmon (EID 1) | 1 | families/process.json | L5 Sysmon EID 1 live on a dev host (agent VALIDATION 2026-10-22); L3 ETW |
| observation/process_stop | canonical_direct | etw, sysmon (EID 5) | 2 | process_stop.json | L3 |
| observation/network | legacy_derived | sysmon (EID 3) | 1 | network.json | L3 |
| observation/file | legacy_derived | sysmon (EID 11/23/…); minifilter **provisional** | 1 | file.json, file_minifilter.json | L3 (Sysmon); L1 only for minifilter (no producer yet) |
| observation/registry | legacy_derived | sysmon (EID 12–14) | 1 | registry.json | L3 |
| observation/image_load | legacy_derived | sysmon (EID 7) | 1 | image_load.json | L3 |
| observation/dns | windows_sysmon_extended_v1 | sysmon (EID 22) | 1 | dns.json | L3 |
| observation/process_access | windows_sysmon_extended_v1 | sysmon (EID 10) | 1 | process_access.json | L3 |
| observation/remote_thread | windows_sysmon_extended_v1 | sysmon (EID 8) | 1 | remote_thread.json | L3 |
| gap/source_loss | producer_body (supervisor body fully specified) | agent | 1 | source_loss.json | L3 |
| evidence/normalization_failure | canonical_direct | agent | 1 | normalization_failure.json | L3 |
| health/endpoint_health | canonical_direct | agent | 1 | endpoint_health.json | L3 |
| observation/windows_event_log, evidence/filesystem_usn_*, gap/filesystem_usn_gap, state/* (~35 categories) | producer-defined | win32, agent | — (envelope only) | — | L3 per collector (agent VALIDATION) |

Evidence levels: L1 contract, L2 unit, L3 component, L4 integration (Manager/DE),
L5 real-Windows, L6 end-to-end. Every family fixture is **synthetic input
through the real producer code**, never a capture (`fixture.real_capture: false`).
No family has L4 or L6 evidence yet.

## 4. Timestamps

| Field | Meaning |
|---|---|
| `provenance.event_time_ns` | Exact source event time, signed ns since the Unix epoch, decimal string. Process start = creation time; process stop = termination time; Sysmon EID 8/10/22 prefer the source `UtcTime`; gap/health/state = capture time. |
| `observed_at` | `event_time_ns` rounded to UTC milliseconds, for display. Never use it for ordering at sub-ms precision. |
| `data.event.timestamp` | Equals `observed_at` for observations (the validator enforces this). |
| `provenance.received_at` | When the agent built the record (wall clock). |
| `provenance.capture_uptime_ms` | Agent host uptime at record creation; with `collector_epoch`/`sequence` it gives a monotonic order inside one epoch. |
| `source_facts.event_time_ns` | The decoded source time, also kept in failure evidence. |

Wall clocks can step. Order within an epoch by `sequence`, not by time.

## 5. Process identity, actor and target

- `subject` is the **actor** (the process that performed the operation) and is
  authoritative. Its `resolution` is the attribution quality:
  - `native_exact` means PID plus exact native creation ticks within one boot.
  - `source_scoped` means the source GUID within its provider/channel namespace.
  - `native_unscoped` means ticks are known but the boot isn't, so the entity is null.
  - `unresolved` means only a PID is known, so the entity is null.
  - Digests are defined in ENDPOINT_RECORD_1.md and checked by the validator.
- `data.process.entity_id` always equals `subject.entity_id`. `data.process.pid`
  equals `subject.observed_pid`.
- Parents: `data.process.parent.identity` is a separate reference. A parent PID
  alone stays unresolved and is never matched by PID or time.
- Targets (process_access, remote_thread): `data.<family>.target` carries its own
  reference with independent resolution. Actor and target are never merged.
- Cross-source joins are only by equal `entity_id`. Two `native_exact` references
  from different sources (for example ETW start and minifilter write) join when PID
  and creation ticks match. Sysmon references are `source_scoped` and **do not**
  join ETW references. No alias proof exists yet.
- PID reuse: the same PID with different creation ticks gives a different entity
  (tested). Activity can arrive before or without a start record. That is
  expected, and consumers must not invent the creation event.
- `start_time_ticks` is FILETIME creation ticks as a decimal string. The response
  path needs it as an exact integer (parse it, never round it) and only from
  `native_exact` references.
- Image path is the source-reported string. The image hash is present only when
  the source reported it. Neither is file identity.

## 6. Operations and outcomes

- File: `data.file.operation` ∈ create, delete, rename, open, write,
  set_information, overwrite. The outcome is `data.source_facts.file.phase` plus
  `status`:
  - `reported` (Sysmon) means the source states the operation happened; status is null.
  - `attempted` (minifilter pre-operation) means the outcome is unknown.
  - `completed` (minifilter post-operation) means status holds the NTSTATUS.
  A completed operation with a failure NTSTATUS is still that operation type and
  did not take effect. `status.interpreted` is always false. Consumers decide
  success (NT_SUCCESS: high bits 00/01). `delete` means deletion was requested or
  reported, not that the file is gone. Rename keeps both paths. A path is not a
  stable file identity; file-ID/volume context is planned with the minifilter.
- `process_access` is a handle open with a raw access mask, not memory
  modification. `remote_thread` is thread creation in another process; its
  module/function are Sysmon's inference. `dns` is a resolver query and its
  answers, not a connection. `network` is a connection report, with no payload
  and no byte counts.
- No observation carries a detection verdict (the schemas reject a `verdict`
  field). Officer reports what it observed.

## 7. Absence, unknown values and deduplication

- `null` means the source did not supply the value. A **missing key** (allowed
  only where the schema marks it optional) means the record predates that field;
  treat it as unknown. `data.unavailable[]` (extended families) names a missing
  field and the reason. Never read null as zero, false or empty.
- Unknown enum values: producers never emit values outside the schema. Consumers
  should treat an unrecognised value as unknown and keep the record, never crash.
- `*_value` integers in `source_facts` are C++ enum indices. The index tables are
  in the family schemas' descriptions. Use the named fields.
- `data.source.record_id` (legacy alias) is a JSON number that some consumers
  round above 2^53. `provenance.native_record_id` (decimal string) is authoritative.
- Deduplication: `record_id` identifies one emitted record; byte-identical resend
  is a duplicate. The same source observation is identified by
  `(provenance.kind, provider, channel, native_record_id)` when present.
  Otherwise use `provenance.native_observation_id` (the legacy `evt_` hash) for
  legacy-derived families.

## 8. Source health and loss

- `gap/source_loss` with `data.changes` is the collector supervisor's report.
  - `events_lost`, `realtime_buffers_lost` and `log_buffers_lost` carry exact
    `previous`/`total`/`delta`.
  - A null delta means the change is unknown (reset, wrap or an unavailable sample).
  - Events, buffers and notifications are different units. Never sum them.
  - `startup_continuity_unknown` means nothing before the first sample is known.
- Other `source_loss` bodies (ETW session ownership, IP Helper, raw handoff,
  state freshness, Event Log/USN/FIM lifecycle) are producer-defined.
- `health/endpoint_health` gives per-capability state: healthy, degraded,
  unavailable, disabled, unsupported or blind. It describes current coverage, not
  past capture.
- `provenance.continuity` is `unverified` for all live sources. No record proves
  that nothing was missed, so absence of events is not absence of activity.

## 9. Measured Detection Engine compatibility

Command: `python scripts/detection_compat.py --engine <checkout>`. This is the
real adapter on these fixtures, run 2026-10-26.

| Family | DE main `b234287` | DE `ml/process-start-classifier` `70c6192` |
|---|---|---|
| process, network, file (Sysmon), registry, image_load | accepted, no loss | accepted, no loss |
| process_stop | `process_stop_stop` (unmapped). Before Officer `9d20777` it was misread as `process_create`. | `process_terminate` |
| dns / process_access / remote_thread | accepted with loss (query name, access mask, start address, target) | accepted, no loss |
| file via minifilter | loses actor ticks and outcome | ticks arrive as a string; outcome not read |

## 10. Consumer requirements not yet satisfied

1. Canonical-only families (process_stop, dns, process_access, remote_thread)
   need the canonical adapter. Do not feed them to the legacy adapter. DE main
   should map `process_stop/stop` to `process_terminate`.
2. Read file outcome from `data.source_facts.file.phase/status`, not `data.file`.
3. Parse decimal-string `start_time_ticks` and native tokens to exact integers.
   Use them for response only from `native_exact` references.
4. Key process entities on `subject.entity_id`. Don't join Sysmon `source_scoped`
   and ETW `native_exact` entities by PID or time.
5. Respect `null`, missing-key and `unavailable` semantics (§7) in feature
   extraction. Missing must not become zero.
6. Manager v2 ingest of the family records (L4) is unverified on Manager main,
   which lacks the v2 routes (agent Wave 6).

## 11. Planned families and status

| Planned | Status | Notes |
|---|---|---|
| Minifilter file activity (`file`, source `minifilter`) | Pipeline, schema and provisional fixture only; driver not implemented | Will add file-ID/volume context through the coordination loop |
| API instrumentation | Planned; no wire category yet | Will map onto `remote_thread`/`process_access` where semantics match; memory-protection/allocation families need a use case and schema first |
| Kernel-Network ETW flows, AMSI | Planned | Flow ≠ DNS; AMSI content may be partial or absent |
| WinRM/RDP inventory | Planned | State family |
| Windows Event Log, USN, FIM, state inventories | Implemented, envelope-only | Need family schemas |

## 12. Evolution rules

- The envelope `schema_version` stays `1.0` for additive changes. A breaking
  change (removing or renaming a field, changing a type, unit or meaning) needs a
  new envelope version plus coordinated Manager/DE changes (see VERSIONING.md).
- Family schemas carry a `revision` in `index.json`. Additive fields bump it. New
  fields are optional in the schema, so older journaled records still validate,
  and required in `--current-producer` mode, so the producer can't regress.
- New families: write a use case, check source observability, define semantics,
  add a schema, an `index.json` entry, fixtures from the real producer, and
  valid/invalid tests. Run `detection_compat.py`. Update this catalog.
- Deprecation: mark it here and in the family schema description for at least one
  revision before removal. Removal is a breaking change.
- Fixtures under `families/` are regenerated by the agent's
  `officer-contract-fixtures`. `record_id`, epoch, `received_at`, uptime and
  sequence differ on each run by design. `fixtures/.../invalid/` are static
  single-rule violations.

## 13. Status update — 2026-10-27 (Wave 6)

Coordinated branches: agent `windows-endpoint-completion`, Manager
`windows-endpoint-v2-ingest`, response-engine `windows-command-result-v2`,
Detection Engine `windows-canonical-endpoint-ingest`, contracts (this branch).

Evidence levels raised:
- **L4 for every family in §3:** the Manager test suite posts every family
  fixture through the real v2 route and reads it back byte-for-byte. Native
  Officer emitters (inventories, source gaps, source facts, response decoder,
  KILL_PROCESS execution evidence) run through ingest, the Detection Engine's
  canonical adapter and the command v2 path: 279 passed, 0 skipped.
- **L6, development host only (not the VM):** the real agent enrolled. 4,770
  live records were persisted and drained by detection, and DET-PROC-008 fired on
  a live canonical process record. The command round trip is blocked on this
  host because the agent's response channel always verifies TLS. VM validation is
  pending.

Detection Engine (§9/§10): `EndpointIngestionAdapter` now maps the families to
the existing vocabulary:
- `process_stop` becomes `process_terminate`, closing the exact instance.
- `process_access`, `remote_thread` and `dns` go through the 0.5 normalizers,
  with decimal tokens converted exactly.

DET-CRED-010/011 and DET-INJ-011 fire on canonical records. Unresolved
references never infer an actor. Requirements 1–4 in §10 are satisfied on that
branch; 5 (missingness in ML features) remains with the DE track.

Command/result v2: published schema and Python model agree on every golden
fixture (parity test in response-engine). `ACQUIRE_FILE` remains a
**Windows-agent extension outside the shared 7-action set**: the Manager cannot
issue it, the Linux agent rejects it, and no Manager download path for captured
bytes exists. Adding it would be a breaking change (VERSIONING.md).
