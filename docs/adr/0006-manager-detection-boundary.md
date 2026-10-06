# ADR 0006: Manager / Detection Engine boundary

## Status

Proposed — needs agreement with the Detection Engine owner (Sokhi). Date: 2026-10-06.

## Context (current evidence)

The Detection Engine (`panopticon-detection-engine`) is a Python package with:

- only `pyyaml` and `pydantic` as dependencies;
- a CLI over NDJSON;
- a stated principle: "detects and recommends, never executes".

Its lines are described in system design D3:

| Line | Contents |
|---|---|
| Engine `main` (`eee2dc2`, Sokhi, merged 2026-10-06) | Outputs and rule metadata made truthful; state pruning under load |
| Sokhi's `phase-2/behavioral-rarity-baseline` (unmerged) | Causal incidents; stateful rules (sequence, threshold, value_count); a provenance graph with identity intervals and directed walks; a risk scorer; behavioural beaconing, DNS and rarity detectors over a shared feature extractor; a normalizer accepting Officer schemas 0.1–0.5; an OTRF dataset adapter; a bounded queue with a SQLite spool |
| Windows snapshot `a535f1d` | `endpoint_adapter` (endpoint-record 1.0 → engine events) and a `proc_` identity fix in `provenance/identity.py` |

Manager runs the engine **in-process**: `DetectionWorker` claims queued events, calls the engine
and writes alerts through an `AlertSink`. Manager `main` vendors `eee2dc2`. The Linux branch
vendors `db4981a` and the Windows branch `a535f1d`.

The engine README claims ingestion via `POST /api/v1/ingest`. That route belongs to Manager, not
the engine. The engine keeps its correlation state in memory, bounded (`max_window_events`
10000).

## Decision

1. **The engine stays a library, embedded in Manager, owned by Sokhi.** It is not a network
   service (ADR 0020 sets the criteria to split it out).
2. **Input** is the *canonical detection event* (CDE), defined in contracts (ADR 0012). Manager
   produces the CDE from endpoint-record 2.0, or from a legacy contract during migration. The
   engine keeps its Officer 0.x and OTRF adapters for datasets and the standalone CLI, and these
   produce the same CDE.
3. **Output** is `Detection` and `Incident` objects (ADR 0012). Each carries:
   - its evidence (CDE ids);
   - the rule and its version;
   - MITRE mapping, severity and score;
   - **recommendations** as an action name and a target *reference* (the process key or entity
     id), never as a command.
4. **Manager owns:**
   - the queue and ordering (per host);
   - persistence of detections and incidents;
   - deduplication across restarts;
   - the translation of a recommendation into an authorized command (Response Engine module,
     ADR 0013);
   - the lookup API for entities.
5. **The engine owns:**
   - rules and their language;
   - stateful windows;
   - the provenance graph;
   - incident formation;
   - scoring and baselines;
   - its in-memory state.

   The state is rebuilt on Manager start by replaying the raw-store window the engine asks for
   (`required_history()`), so no engine state is stored in Manager tables.
6. **The interface is small and versioned:**
   - `Engine(config).process(cde) -> list[Detection | Incident]`;
   - `Engine.required_history() -> timedelta`;
   - `Engine.version`.

   Contract tests in Manager pin it.

## Alternatives considered

- **Detection as a separate service fed by HTTP or a queue.** It would add a network hop, a
  serialization contract and a second deployable, with no measured need. Rejected for now.
- **Manager re-implementing rules.** This duplicates Sokhi's work. Rejected.
- **The engine reading the database directly.** This couples the engine to Manager's schema.
  Rejected.

## Consequences

- One engine revision is vendored by every Manager branch: the lines must be reconciled first
  (system design §10 item 2).
- `endpoint_adapter` from the Windows snapshot becomes Manager's CDE producer, or is replaced by
  it. Its identity change is re-applied onto ADR 0004.
- The README route claim is corrected.

## Migration

1. **Reconcile the engine lines into `main`**, a merge led by Sokhi:
   - Sokhi's phase-2 first;
   - then the Windows `endpoint_adapter`, rebased on top;
   - its `identity.py` change is resolved in favour of ADR 0004.
2. Define the CDE (ADR 0012) and add an adapter from the engine's internal event to the CDE.
3. Manager's `DetectionWorker` calls the new interface. The Linux and Windows branches vendor the
   reconciled revision.
4. Replay-on-start replaces any reliance on the engine's own SQLite spool when it runs inside
   Manager. The spool stays for the standalone CLI.

## What remains provisional

- Whether incidents are computed in the engine (current Sokhi design) or partly in Manager
  (cross-host incidents).
- The replay window length.
- Snapshotting the engine state, if replay is too slow.
