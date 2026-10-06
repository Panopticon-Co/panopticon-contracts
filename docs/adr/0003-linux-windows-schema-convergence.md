# ADR 0003: Linux/Windows schema convergence — common semantics, per-OS bodies

## Status

Proposed — follows ADR 0002. Date: 2026-10-06.

## Context (current evidence)

Both agents model the same concepts differently:

| Concept | Linux today | Windows today |
|---|---|---|
| Boot scope | `host.boot_id` = raw kernel UUID; command scope = `boot_` + sha256(UUID) (since `c84a6dc`) | `endpoint.boot_id` = `boot_` + 64 hex |
| Ordering | `seq`, contiguous per sensor | `provenance.sequence`, with `generation` and `collector_epoch` |
| Record class | `record_type` ∈ {event, state, health, loss} | `kind` ∈ {observation, state, health, gap, evidence, command_result} |
| Loss | `record_type: loss` with ranges and reasons, durable across restart | `gap` kind defined; live durable accounting unfinished |
| Process reference | `process.entity_id` (32 hex), `pid`, `start_ticks` | `subject` ProcessReference with `resolution` |
| Confidence | `provenance.confidence` and `process.confidence{identity, attributes}`, each ∈ {observed, reconstructed, inferred, user_space_reported} | `subject.resolution` ∈ {native_exact, source_scoped, native_unscoped, unresolved}, and `continuity` |
| Response audit | `response.action` record | `command_result` kind |

The Detection Engine's normalizer accepts Officer schemas 0.1–0.5 and maps them onto internal
event types. The rule set is mostly Windows-shaped (Sysmon-derived field names).

## Decision

1. The **semantics** listed in the system design §7 are common and defined once in contracts:
   - identity: host, agent, installation, boot scope, stream, sequence, record id;
   - time;
   - provenance and confidence;
   - process reference;
   - loss and gap;
   - health and coverage;
   - command, result, response audit;
   - evidence reference.
2. **Bodies** are common where the meaning is common:
   - `process.exec` / `process.exit`: image, command line, parent reference, user, integrity or
     credentials;
   - `file.*`, `network.*`, `dns.query`, `auth.*`, `response.action`.

   Each common body has a required core and an `os` extension object that is closed per OS. For
   example, Linux `process.exec` carries namespaces, capabilities and cgroup there; Windows
   carries integrity level, signer and token elevation.
3. **OS-only categories** have their own bodies: Linux `kernel.module`, `bpf.load`, `ns.change`,
   `lsm.decision`, `netfilter.change`; Windows `registry.*`, `service.*`, `wmi.*`,
   `script.block`.
4. **Two separate axes, each with one vocabulary for both operating systems:**
   - **Identity resolution** of a process reference: `exact | source_scoped | unscoped |
     unresolved`. This is the Windows vocabulary without the `native_` prefix. Linux maps
     `identity: observed` with kernel start ticks to `exact`.
   - **Attribute confidence** of the body: `observed | reconstructed | inferred |
     user_space_reported`. This is the Linux vocabulary; Windows adopts it.
5. **Time:** both agents emit RFC 3339 UTC. Native high-resolution ticks travel in `provenance.native`
   or in the process reference; they are never used as the event time.

## Alternatives considered

- **A full common schema with no OS extensions.** This would force lowest-common-denominator
  bodies and lose the very fields that make an EDR useful.
- **Free-form `data`.** It gives up schema strictness, which has already caught real bugs on both
  sides (for example, the Manager rejection tests for `response.action`).

## Consequences

- Detection rules are written against common bodies wherever possible. OS-specific rules read the
  `os` extension explicitly, so a rule says which OS it needs.
- The Detection Engine's Officer 0.x normalizer remains for datasets (OTRF) and for older Windows
  builds, but it is no longer the live path.

## Migration

This is done per category, starting with `process.exec` (the only category in the vertical slice
on both OSes), then network, file and auth. Each step:

1. contracts adds the common body and fixtures from both agents;
2. Manager maps it into the canonical detection event;
3. the rules that use it are ported and tested on both OSes' fixtures.

## What remains provisional

- The exact boundary between core and `os` extension for each category: decided per category,
  with fixtures from both agents.
