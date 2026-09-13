# ADR 0001: Introduce panopticon-contracts

## Status

Accepted.

## Context

Panopticon's response pipeline spans four independently-versioned repositories in
three languages: `panopticon-detection-engine` (Python) emits recommendations,
`panopticon-response-engine` (Python, vendored into `panopticon-manager`) defines
the canonical `Command`/`CommandResult`/lifecycle domain model, `panopticon-manager`
(Python/FastAPI) transports and persists it, and both `panopticon-linux-agent` and
`panopticon-agent` (C++20) independently hand-implement the same wire shapes to
decode and execute it. Each native agent's `command.hpp`/`command.cpp` was written
by reading Manager's behavior and re-deriving the JSON shape by hand -- there was no
single document or fixture set either agent's author could check against, and no
automated signal if the two agents (or an agent and Manager) drifted apart.

Concretely, the audit backing this ADR found:

- `response_engine.contract.Command`'s own field set (`command_id`, `agent_id`,
  `action`, `expires_at`, `target`, `correlation_id`) does not match what actually
  goes over the wire (`host_id` and `schema_version` are injected by
  `panopticon-manager` at dispatch time, and both native agents hardcode
  expectations against the *wire* shape, not the Python model's declared fields).
  This was previously undocumented anywhere outside the router source code.
- `panopticon-linux-agent`'s eight-value local `receipt_code` enum collapses onto
  `CommandResult`'s three-value `outcome` field in a specific, source-code-only
  mapping that no document described before this repository existed.
- The response lifecycle is a single nine-state machine in
  `response_engine.lifecycle`, but Manager persists it across two tables with a
  documented naming compression (`response_actions.REJECTED` overloads both
  "declined pre-dispatch" and the lifecycle's own `CANCELLED` concept). This was
  previously explained only in a code comment inside `lifecycle.py`.

None of these are bugs -- each is a deliberate, reasonable engineering decision. But
each was discoverable only by reading multiple repositories' source code side by
side, which does not scale as more response actions, more agents, or more analysts
are added.

## Decision

Create `Panopticon-Co/panopticon-contracts`: a repository containing the
reconciled contract documentation (`docs/CONTRACT.md`), a versioning policy
(`docs/VERSIONING.md`), a compatibility matrix (`docs/COMPATIBILITY.md`), a security
invariant list (`docs/SECURITY.md`), JSON Schema definitions for the wire `Command`
and `CommandResult` envelopes, and deterministic golden fixtures (valid, invalid,
and adversarial) that any implementation in any language can be checked against.

## Why this does NOT imply microservices

This repository ships no server, no daemon, no container image, and no network
endpoint. It is read the same way a shared `.proto` file, a JSON Schema package, or
an OpenAPI spec would be read: by humans maintaining hand-written decoders, and by
each repo's own test suite loading fixture files as test data. Panopticon remains a
single deployable backend (`panopticon-manager`) plus two independent endpoint
agent processes. Introducing a contracts repository changes *where documentation and
fixtures live*, not *how many things run*.

## Why contracts are separate from Response Engine business logic

`panopticon-response-engine` remains the actual, executable implementation of this
contract in Python -- policy (`policy.py`), tiering, and recommendation translation
(`recommendation.py`) stay there, because they require runtime state (the current
alert, the enrolled-agent table) that a static fixture repository cannot and should
not model. This repository documents and fixtures the *shape* of what
`response_engine` produces and consumes; it does not reimplement or replace any of
its logic. A change to tiering policy is a `response_engine` change; a change to
what fields exist on `Command` is a `panopticon-contracts` + `response_engine`
change together.

## Why OS-specific execution remains in agents

Path-jailing rules, nftables rule shapes, WFP filter GUIDs, and AF_UNIX helper IPC
are meaningful only to one operating system each. Centralizing them here would
either force one agent to depend on OS-specific code paths it can never execute, or
force this repository to become an abstraction layer neither agent actually needs
(both agents already implement the closed action set correctly using entirely
different native APIs). This repository stops at the wire boundary: what bytes go
over HTTP, not what syscalls an agent makes to honor them.

## Why golden fixtures

A shared prose document can still be read differently by two implementers. A golden
fixture is unambiguous: either an implementation's decoder accepts
`fixtures/commands/valid/kill_process.json` and rejects
`fixtures/commands/invalid/wrong_target_shape.json`, or it does not. Fixtures also
make future contract changes safer to review -- a PR that changes
`schema/command.schema.json` should come with fixture changes that make the intent
concrete rather than only a prose diff.

## How versioning works

See `docs/VERSIONING.md`. Summary: `schema_version` is an integer-as-string counter;
because every current decoder (Python `extra="forbid"` models and both native
agents' exact-key-set JSON parsing) rejects unknown fields, in practice any field
change is breaking and must ship as a coordinated, atomic change across every
consuming repository -- there is no distributed version-negotiation infrastructure,
and none is planned unless a future phase genuinely needs independently-upgradable
agents in the field.

## What is intentionally NOT included

- No eighth action, no `EXECUTE_COMMAND`/`RUN_SCRIPT`/`SHELL`/`FIREWALL_RULE` action
  or field, ever, without a superseding ADR.
- No response policy, authorization, or tiering implementation (stays in
  `response_engine`/`manager`).
- No database models, FastAPI routers, or Manager orchestration code.
- No detection algorithms or rule content (stays in `panopticon-detection-engine`).
- No Linux- or Windows-specific execution code (nftables, WFP, shell, AF_UNIX IPC).
- No Kafka, gRPC, service registry, API gateway, or Kubernetes manifests -- this
  repository has no runtime component to orchestrate.
