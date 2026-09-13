# panopticon-contracts

Canonical, versioned wire/domain contract definitions and compatibility fixtures for
Panopticon&Co's detection-to-response pipeline:

```
panopticon-detection-engine (eyedetect)
        |  recommendation vocabulary (TERMINATE_PROCESS, ISOLATE_HOST, BLOCK_FIREWALL_IP, ...)
        v
panopticon-manager
        |  response_engine.translate_recommendation -> one of 7 closed actions
        |  response_engine.contract.Command / CommandResult (Pydantic)
        v
panopticon-response-engine (domain package, vendored into Manager)
        |  Manager injects host_id + schema_version, dispatches over HTTP
        v
   +----+----+
   v         v
panopticon-linux-agent   panopticon-agent (Windows / "Officer")
   (C++ command.hpp/.cpp)   (C++ response/command.hpp/.cpp)
```

## What this repository is

A single source of truth for:

- the closed 7-action response vocabulary
- the typed `Command` wire envelope and its per-action target shapes
- the typed `CommandResult` wire envelope and its outcome/rejection vocabulary
- the response lifecycle state machine and its legal transitions
- deterministic golden fixtures (valid, invalid, boundary, adversarial) that every
  language-specific implementation can be checked against

## What this repository is NOT

It is not a microservice, a daemon, a deployment target, or a network service. It
introduces no new runtime dependency and no new process. Panopticon remains a
**one-deployable-backend** architecture: `panopticon-manager` is the only thing that
runs as a service; the Linux and Windows agents are endpoint processes; this
repository is a versioned document + fixture set that those repos are checked
against, by hand or in CI, not a library any of them must load at runtime.

See `docs/adr/0001-panopticon-contracts.md` for the full rationale, and
`docs/CONTRACT.md` for the actual contract definition (reconciled against the
real implementations, not an idealized rewrite).

## Layout

- `docs/CONTRACT.md` -- the canonical contract: actions, Command, CommandResult, lifecycle.
- `docs/VERSIONING.md` -- schema version policy.
- `docs/COMPATIBILITY.md` -- per-repo implementation matrix and known gaps.
- `docs/SECURITY.md` -- adversarial invariants this contract enforces and how each
  fixture proves it.
- `docs/adr/0001-panopticon-contracts.md` -- why this repository exists.
- `schema/command.schema.json`, `schema/command_result.schema.json` -- JSON Schema
  (draft 2020-12) reconciled against `response_engine/contract.py`'s Pydantic
  validators.
- `fixtures/` -- deterministic golden JSON: valid commands (one per action),
  invalid/adversarial commands, results (including the full rejection-reason
  vocabulary), and lifecycle transition examples.
- `scripts/validate_fixtures.py` -- validates every fixture against its schema and
  checks the security invariants in `docs/SECURITY.md` (exactly 7 actions, no
  shell/exec-shaped fields, etc.). Run in CI.

## Using this repository from a consuming repo

There is no package to install. Either:

1. Read the fixtures directly (e.g. as a git submodule, or copied test data) and
   assert your implementation encodes/decodes them identically, or
2. Diff your implementation's hardcoded action list / target-shape rules /
   lifecycle transitions against `docs/CONTRACT.md` when you touch them.

`panopticon-response-engine` remains the actual Python implementation of this
contract (`response_engine.contract`, `response_engine.lifecycle`); this repository
documents and fixtures that implementation's wire behavior so the two native agents
(and Manager) can be checked against it without importing Python.
