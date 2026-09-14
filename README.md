# panopticon-contracts

Canonical, versioned wire-contract definitions and compatibility fixtures for the
response half of Panopticon&Co's detection-to-response pipeline: the closed
7-action `Command` / `CommandResult` envelope shared by `panopticon-manager` and
the endpoint agents.

## Status

Capstone/research security project, active development. Not a production product.
All four downstream implementers (`panopticon-response-engine`,
`panopticon-manager`, `panopticon-linux-agent`, `panopticon-agent`) have been
checked against this repository's fixtures at least once, on real CI — see
`docs/COMPATIBILITY.md` for the current per-repo matrix and known gaps. There is
exactly one schema version (`"1"`) in use today.

## What this repository is

A single source of truth for:

- the closed 7-action response vocabulary (`KILL_PROCESS`, `COLLECT_PROCESS_INFO`,
  `COLLECT_NETWORK_CONNECTIONS`, `COLLECT_FILE`, `QUARANTINE_FILE`, `ISOLATE_HOST`,
  `RELEASE_HOST_ISOLATION`)
- the typed `Command` wire envelope and its per-action target shapes
- the typed `CommandResult` wire envelope and its outcome/rejection vocabulary
- the response lifecycle state machine and its legal transitions
- deterministic golden fixtures (valid, invalid, boundary, adversarial) that any
  language-specific implementation can be checked against

## What this repository is NOT

It is **not a runtime service, not business logic, and not an authentication
system**. It ships no server, no daemon, no container image, and no network
endpoint, and it introduces no new runtime dependency for anything that consumes
it. Panopticon remains a **one-deployable-backend** architecture:
`panopticon-manager` is the only thing that runs as a service; the Linux and
Windows agents are endpoint processes; this repository is a versioned document +
fixture set that those repos are checked against, by hand or in CI — not a
library any of them load at runtime.

See `docs/adr/0001-panopticon-contracts.md` for the full rationale and
`docs/CONTRACT.md` for the actual contract definition (reconciled against the
real implementations, not an idealized rewrite).

## Architecture role

This repository governs one boundary in the larger Panopticon pipeline — the
hand-off from a detection recommendation to a dispatched, executable command:

```
panopticon-detection-engine (eyedetect)
        |  recommendation vocabulary (TERMINATE_PROCESS, ISOLATE_HOST, BLOCK_FIREWALL_IP, ...)
        v
panopticon-response-engine (domain package, vendored into Manager)
        |  translate_recommendation() -> one of the 7 closed actions, or None
        |  response_engine.contract.Command / CommandResult (Pydantic)
        v
panopticon-manager (FastAPI)
        |  injects host_id + schema_version + created_at, authorizes, dispatches over HTTP
        v
   +----+----+
   v         v
panopticon-linux-agent   panopticon-agent (Windows / "Officer")
   (C++ command.hpp/.cpp)   (C++ response/command.hpp/.cpp)
        |
        v
   CommandResult  ->  Manager  ->  audit / Console
```

`panopticon-contracts` is **not** in this call chain at runtime. It is the
document and fixture set that `response-engine`, `manager`, `linux-agent`, and
`agent` are each independently checked against, so the JSON one repo emits is
provably the JSON another repo's hand-written decoder actually accepts. It does
not define the upstream event schema between the endpoint agents' telemetry
collectors and the detection engine — that boundary is owned by
`panopticon-agent/schema/event.schema.json` and the detection engine's ingestion
adapter, not by this repository.

## Key capabilities

- JSON Schema (draft 2020-12, `additionalProperties: false`, strict) for both wire
  envelopes, with `if`/`then` rules that tie `target`'s shape to `action`.
- A closed, enum-enforced 7-action set — no eighth action, no free-text execution
  field, ever, without a superseding ADR (see `docs/adr/0001-panopticon-contracts.md`).
- Golden fixtures covering valid commands (one per action), a dozen distinct
  invalid/adversarial commands, valid and rejected results, and lifecycle
  transitions.
- `scripts/validate_fixtures.py`, run in CI, which validates every fixture
  against its schema, checks lifecycle sanity, and can additionally scan sibling
  implementer repos for banned execution patterns (`--grep-repos`).
- A documented, source-verified compatibility matrix (`docs/COMPATIBILITY.md`)
  and a security invariant list (`docs/SECURITY.md`) that records both what is
  schema-enforced and what is only enforced by each implementation's own code.

## Repo structure

```
schema/
  command.schema.json          -- Command wire envelope (schema_version 1)
  command_result.schema.json   -- CommandResult wire envelope (schema_version 1)
fixtures/
  README.md                    -- fixture conventions: fixed vs. variable fields
  commands/valid.json          -- one valid Command per closed action
  commands/invalid.json        -- 11 invalid/adversarial Command scenarios
  results/valid.json           -- valid CommandResult examples
  results/rejected.json        -- rejected-outcome CommandResult examples
  lifecycle/transitions.json   -- legal/illegal/expiry lifecycle transitions
docs/
  CONTRACT.md                  -- the canonical contract: actions, envelopes, lifecycle
  VERSIONING.md                -- schema version policy (additive vs. breaking)
  COMPATIBILITY.md             -- per-repo implementation matrix and known gaps
  SECURITY.md                  -- adversarial invariants and how each is enforced
  adr/0001-panopticon-contracts.md -- why this repository exists
scripts/
  validate_fixtures.py         -- schema + lifecycle + (optional) cross-repo scan
requirements.txt               -- jsonschema>=4.21
.github/workflows/ci.yml       -- CI: fixture validation + banned-pattern scan
```

## Dependencies

Python 3.10+ and one third-party package: `jsonschema>=4.21` (`pip install -r
requirements.txt`). Nothing else — no build step, no compiled artifact, no
runtime service.

## Using this repository from a consuming repo

There is no package to install. Either:

1. Read the fixtures directly (e.g. as a git submodule, or a sibling CI checkout)
   and assert your implementation encodes/decodes them identically — this is what
   `panopticon-response-engine`, `panopticon-manager`, and `panopticon-agent`
   currently do (see `docs/COMPATIBILITY.md`), or
2. Diff your implementation's hardcoded action list / target-shape rules /
   lifecycle transitions against `docs/CONTRACT.md` when you touch them — this is
   what `panopticon-linux-agent` currently does, since it has no JSON-file-reading
   test infrastructure yet.

`panopticon-response-engine` remains the actual Python implementation of this
contract (`response_engine.contract`, `response_engine.lifecycle`); this
repository documents and fixtures that implementation's wire behavior so the two
native agents (and Manager) can be checked against it without importing Python.

## Validating locally

These are the exact commands CI runs (`.github/workflows/ci.yml`), reproduced
here so a local run matches CI precisely:

```bash
pip install -r requirements.txt

# Validate every fixture against schema/*.schema.json and the lifecycle
# sanity checks.
python scripts/validate_fixtures.py

# Confirm every JSON file under schema/ and fixtures/ is syntactically valid.
for f in $(find schema fixtures -name '*.json'); do
  python -c "import json,sys; json.load(open(sys.argv[1]))" "$f"
done
```

To additionally run the banned-execution-pattern scan (`docs/SECURITY.md`'s
direct source search for `system(`, `popen(`, `exec*`, `/bin/sh`, `/bin/bash`,
`bash -c`, `sh -c`, `EXECUTE_COMMAND`) against local sibling checkouts of the
five implementer repos:

```bash
python scripts/validate_fixtures.py --grep-repos \
  ../panopticon-response-engine ../panopticon-manager \
  ../panopticon-linux-agent ../panopticon-agent ../panopticon-detection-engine
```

`--grep-repos` takes any number of local paths; CI's `banned-execution-pattern-scan`
job checks out all five repos as siblings and passes exactly those five paths (see
the workflow file for the literal invocation). Files under `.venv`, `venv`,
`vendor`, `node_modules`, `build`, `.git`, `__pycache__`, `vcpkg`,
`vcpkg_installed`, and `.claude` are excluded from the scan, and matches inside a
file whose name or path contains "test"/"tests" are treated as expected
regression coverage (a test asserting a banned pattern is rejected), not a
violation.

## Versioning and compatibility policy

`schema_version` on the wire `Command` envelope is a plain string, currently
always `"1"`, treated as an integer counter (`"1"`, `"2"`, ...), not semver. Full
policy in `docs/VERSIONING.md`; summary:

- **Additive in theory, breaking in practice today**: every current decoder
  rejects unknown top-level keys (both native agents' `parse_command_json`, and
  `response_engine.contract`'s Pydantic models with `extra="forbid"`), so any new
  field is a breaking change until that changes.
- **Breaking changes** (adding/removing/renaming a field, changing a type or
  range, adding/removing an action, changing `outcome`'s vocabulary, changing a
  lifecycle transition) require a new `schema_version`, updated
  `schema/*.schema.json`, new fixtures, an updated `docs/CONTRACT.md`, and
  coordinated updates landed across every consuming repo in the same change —
  not a rolling migration, since there is no version-negotiation mechanism today.
- There is no formal RFC process in this repository beyond the ADR convention
  already used for the repository's own existence (`docs/adr/`); a schema-shape
  change is proposed and reviewed as a normal pull request per
  `CONTRIBUTING.md`, not through a separate governance body.
- There is no per-version fixture directory yet (`fixtures/v1/`, `fixtures/v2/`)
  because there is only one schema version; that split happens at the next
  version bump, not before.

## Integration with other Panopticon repos

- [panopticon-agent](https://github.com/Panopticon-Co/panopticon-agent) — Windows
  endpoint agent ("Officer"); implements `response/command.hpp`/`command.cpp`
  against this contract and loads this repository's fixture files directly in CI.
- [panopticon-linux-agent](https://github.com/Panopticon-Co/panopticon-linux-agent)
  — Linux endpoint agent; implements `command.hpp`/`command.cpp` against this
  contract, checked by direct source audit and hand-reproduced fixture scenarios.
- [panopticon-detection-engine](https://github.com/Panopticon-Co/panopticon-detection-engine)
  ("eyedetect") — emits the looser recommendation vocabulary
  (`TERMINATE_PROCESS`, `ISOLATE_HOST`, `BLOCK_FIREWALL_IP`) that
  `response_engine.recommendation.translate_recommendation` maps onto this
  contract's closed action set. It is upstream of this contract, not an
  implementer of it.
- [panopticon-response-engine](https://github.com/Panopticon-Co/panopticon-response-engine)
  — the canonical Python implementation of `Command`, `CommandResult`, and the
  lifecycle state machine this repository documents and fixtures.
- [panopticon-manager](https://github.com/Panopticon-Co/panopticon-manager) —
  FastAPI service that vendors `response_engine`, injects `host_id` /
  `schema_version` / `created_at` at dispatch time, authorizes, transports, and
  persists the lifecycle across its `response_actions` and `commands` tables.
- [panopticon-console](https://github.com/Panopticon-Co/panopticon-console) —
  surfaces dispatched commands, results, and audit history; does not itself
  implement this contract's wire types.
- [Panopticon-Co](https://github.com/Panopticon-Co) — organization home for all
  of the above.

If a schema or enum in this repository changes, every one of the repos above
that implements or consumes it must be checked for compatibility in the same
change — see `CONTRIBUTING.md`.

## Security invariants

`docs/SECURITY.md` documents, invariant by invariant, what is schema-enforced
versus what can only be verified by reading each implementer's source. Two
invariants worth calling out here because they are load-bearing for the whole
contract:

- **PID-reuse protection**: `KILL_PROCESS` / `COLLECT_PROCESS_INFO` targets are
  `{pid, start_time_ticks}`, never a bare `pid`. `start_time_ticks` is an opaque,
  OS-native process-creation token (Linux `/proc/[pid]/stat` field 22; Windows
  `GetProcessTimes` creation `FILETIME`) that only the *originating host's own
  agent*, re-observing the process fresh, may interpret. `translate_recommendation`
  fails closed (returns `None`, no command staged) if either field is missing —
  it never guesses a target.
- **Closed action-set validation**: exactly seven actions exist
  (`schema/command.schema.json`'s closed `enum`, and
  `scripts/validate_fixtures.py`'s exact-count assertion). There is no
  `EXECUTE_COMMAND`, `RUN_SCRIPT`, `SHELL`, or `FIREWALL_RULE` action or field
  anywhere in `Command` or `target`, enforced by `additionalProperties: false` at
  every object level plus each implementation's own strict decoding.

See `docs/SECURITY.md` for the full sixteen-invariant list, including which are
schema-checkable and which are cross-field or runtime invariants that this
repository records but cannot itself enforce structurally.

## Known limitations

- No cross-field validation in JSON Schema for `created_at < expires_at`
  ordering, non-UTC-offset rejection, or command expiry — these are documented
  as known schema-vs-implementation gaps and are enforced only by each
  implementing agent's own code (`docs/SECURITY.md`'s "Schema limitation" notes).
- `panopticon-linux-agent` is checked by direct source audit and hand-reproduced
  fixture scenarios, not by loading this repository's fixture files directly (it
  has no JSON-file-reading test infrastructure yet) — see `docs/COMPATIBILITY.md`.
- No version-negotiation mechanism exists: an agent and the Manager it talks to
  must run the same `schema_version` at all times, enforced only by operational
  discipline, not by code.
- `docs/SECURITY.md` invariant 15 (no raw command output in `CommandResult.detail`)
  is a code-review invariant, not a JSON-shape-testable one — it must be checked
  manually on every change to result serialization in any implementer repo.

## Contributing, security, and license

- See `CONTRIBUTING.md` for the schema-change process.
- See `SECURITY.md` for how to privately report a vulnerability (do not use
  public GitHub issues for security reports).
- Licensed under the [MIT License](LICENSE).
- Community expectations are described in `CODE_OF_CONDUCT.md`.
