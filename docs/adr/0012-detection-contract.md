# ADR 0012: Detection contract — canonical detection event in, Detection/Incident out

## Status

Proposed — to be agreed with the Detection Engine owner (Sokhi). Date: 2026-10-06.

## Context (current evidence)

- The engine's internal event model comes from its normalizer, which accepts Officer schema
  0.1–0.5, with an OTRF adapter on Sokhi's branch. The Windows snapshot adds `endpoint_adapter`
  for endpoint-record 1.0. Linux records reach detection only as `process.exec`, mapped inside
  Manager (`linux_endpoint_detection`).
- Engine outputs today are alert objects that the `AlertSink` serializes. Sokhi's branch adds
  causal incidents with explainable context and an event-counts-once risk score. Detection
  `main` (`eee2dc2`) made output fields and rule metadata "truthful", which is a breaking change
  to the output shape.
- No contract repository defines either the input or the output. Manager tests pin them
  implicitly.

## Decision

1. **Canonical detection event (CDE)**, a JSON Schema in contracts. It contains:
   - `cde_version` and `event_id` (the envelope `record_id`);
   - `host` (id, os, boot) and `time`;
   - `category` (ADR 0003 categories);
   - `actor`: a process reference with `entity_id` when exact, image, command line and user;
   - `parent`: the same shape;
   - `target`: the file, network, registry or process object;
   - `attributes`: category-specific, flattened for rule matching;
   - `provenance` and `confidence`.

   Manager produces CDEs. The engine's dataset adapters produce the same shape.
2. **Detection**, a JSON Schema in contracts. It contains:
   - `detection_id` (deterministic from rule id, rule version and evidence ids, so a replay
     deduplicates);
   - rule (`id`, `version`, `name`), `severity`, `score`, `mitre[]`;
   - `host`, `actor` reference, `evidence[]` (CDE ids);
   - `explanation` (the engine's human-readable context);
   - `recommendations[]`: `{action, target_ref, rationale, confidence}`, where `action` is from
     the closed Response Engine set and `target_ref` is an entity id or process key, never a
     command.
3. **Incident**, a JSON Schema in contracts. It contains `incident_id`, `detections[]`,
   `entities[]`, a time range, `score`, `tactics[]` and a `narrative`. Single-host incidents are
   formed by the engine; cross-host incidents are Manager's, later.
4. Rules stay in the engine's YAML format, owned by Sokhi. Rules declare the categories and
   operating systems they need, so coverage can show which rules are blind on which host.

## Alternatives considered

- **Sigma as the external rule format.** It is worth supporting as an import later, but the
  engine's stateful and sequence rules go beyond Sigma's core.
- **Let the engine consume the envelope directly.** That couples rules to wire details and to OS
  bodies.

## Consequences

- The engine's internal event type maps one-to-one onto the CDE, which can be done by an adapter
  without changing the rules.
- Manager stores Detections and Incidents as rows (ADR 0005), with the JSON kept for evidence.

## Migration

1. Write the CDE from the union of the fields the current rules use (count them from the
   engine's rule YAML).
2. Manager produces CDEs for `process.exec` on both operating systems first.
3. The engine accepts CDEs behind its adapter interface (ADR 0006).

## What remains provisional

- Field naming (ECS-like versus the engine's current names).
- Whether `explanation` is structured.
