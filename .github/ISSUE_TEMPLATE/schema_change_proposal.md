---
name: Schema change proposal
about: Propose a change to the Command/CommandResult contract itself (a field, action, or invariant)
title: "[Schema Change] "
labels: schema-change
assignees: ''
---

## What is changing

Describe the exact change: a new/removed/renamed field, a new/removed action, a
changed target shape, a changed `outcome` value, a changed lifecycle transition,
or a changed invariant.

## Why

What problem does this solve? Why can't it be achieved within the existing
closed 7-action set / existing field set?

## Additive or breaking?

Per `docs/VERSIONING.md`, classify this change:

- [ ] Additive (does not require a `schema_version` bump)
- [ ] Breaking (requires a `schema_version` bump)

Note: because every current decoder rejects unknown top-level keys
(`extra="forbid"` in `response_engine.contract`, and both native agents'
exact-key-set JSON parsing), a new field is a breaking change in practice today
even if it looks additive on paper. Explain your classification.

## Required updates (check off as completed, or leave for the PR)

- [ ] `schema/command.schema.json` and/or `schema/command_result.schema.json`
- [ ] New/updated fixtures under `fixtures/`
- [ ] `docs/CONTRACT.md`
- [ ] `docs/VERSIONING.md` (if breaking, record the new `schema_version`)
- [ ] `docs/SECURITY.md` (if this touches a security invariant)
- [ ] `docs/COMPATIBILITY.md` (per-repo status, once downstream repos are updated)

## Downstream repositories affected

For each, note whether it needs a code change, and whether that change has
happened yet or is tracked elsewhere:

- [ ] `panopticon-response-engine`
- [ ] `panopticon-manager`
- [ ] `panopticon-linux-agent`
- [ ] `panopticon-agent`
- [ ] `panopticon-console`

## Non-goals

Confirm this does not introduce an eighth action, an `EXECUTE_COMMAND`/
`RUN_SCRIPT`/`SHELL`/`FIREWALL_RULE`-shaped field, or a way for `detail`/`target`
to carry raw command output — any of those require a superseding ADR, not a
routine schema change.
