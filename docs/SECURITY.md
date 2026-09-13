# Security invariants

This document lists the adversarial invariants this contract enforces, how each is
represented in `schema/*.schema.json` and/or a fixture, and the result of a direct
source search across the implementing repositories for the specific danger patterns
called out in the driving directive.

## Invariant list

| # | Invariant | Enforced by | Fixture |
|---|---|---|---|
| 1 | Exactly seven actions exist; no eighth action is ever accepted. | `schema/command.schema.json`'s closed `enum` on `action`; `scripts/validate_fixtures.py`'s `ACTIONS` count assertion. | `fixtures/commands/invalid/unknown_action.json` |
| 2 | No `shell`, `command`, `script`, `args`, `executable`, or `firewall_rule` field exists anywhere in `Command` or `target`. | `additionalProperties: false` at every object level in both schemas; `response_engine.contract.Command`'s `extra="forbid"`; `panopticon-agent`'s explicit `allowed_keys` enumeration (verified by direct source read). **`panopticon-linux-agent` did NOT enforce this** as of the first audit pass -- its hand-rolled substring-scanning parser extracts only recognized fields and never checks for additional top-level keys, so a smuggled field was silently ignored rather than rejected. No handler ever reads or acts on an unrecognized field, so this was not an exploitable execution path, but it violated the documented closed-envelope invariant. Fixed: see `panopticon-linux-agent`'s own commit adding an explicit unknown-key rejection pass to `parse_command_json`, matching `panopticon-agent`'s behavior. | `fixtures/commands/invalid/smuggled_shell_field.json` |
| 3 | `target` shape is fully determined by `action` -- a process action cannot carry a `path`, a file action cannot carry a `pid`, and no-target actions cannot carry anything. | `schema/command.schema.json`'s `if/then` per-action target rules. | `fixtures/commands/invalid/wrong_target_shape.json` |
| 4 | `start_time_ticks` and `pid` must be positive integers, not booleans, not strings, not zero, not negative. | `schema/command.schema.json` (`type: integer`, `minimum: 1`). | `fixtures/commands/invalid/invalid_target_types.json` |
| 5 | `expires_at` must be UTC; a non-UTC-offset timestamp is rejected outright, never converted. | Documented in `docs/CONTRACT.md`; both native agents' `parse_command_json` enforce this in code (JSON Schema's `date-time` format alone cannot express this -- see "Schema limitation" below). | `fixtures/commands/invalid/non_utc_timestamp.json` |
| 6 | An expired command must never be executed. | Lifecycle: `ANY -> EXPIRED`; `response_engine.lifecycle`. | `fixtures/commands/invalid/expired_command.json` |
| 7 | A command already accepted/executed once must be rejected on replay (same `command_id` seen twice by the same agent). | `command_gate`/`CommandGate` (both agents) with a durable replay ledger. | `fixtures/commands/invalid/replay_detected_scenario.json` |
| 8 | A command addressed to a different `agent_id`/`host_id` must be rejected, not silently executed by whichever agent happens to poll it. | `command_gate`'s agent/host binding check (both agents). | `fixtures/commands/invalid/cross_agent_mismatch.json` |
| 9 | A `CommandResult`'s `correlation_id`, if present, must match the stored command's `correlation_id`, or the result is rejected. | `manager/routers/commands.py`'s explicit check. | `fixtures/commands/invalid/correlation_mismatch.json` |
| 10 | `KILL_PROCESS` against a hardcoded protected PID/critical image must be refused even with an otherwise-valid, authorized command. | `is_protected_process` (both agents). | `fixtures/results/rejected/target_protected.json` |
| 11 | `KILL_PROCESS` is always `ANALYST_APPROVAL` tier -- it can never be dispatched via the `AUTO_SAFE` auto-enqueue path regardless of how its target was resolved. | `manager/detection/response.classify_tier` hardcodes this; `translate_recommendation` cannot override tiering. | `fixtures/commands/valid/kill_process.json` (annotated `"tier": "ANALYST_APPROVAL"`) |
| 12 | `ISOLATE_HOST`/`RELEASE_HOST_ISOLATION` have no SSH/RDP break-glass and no general ESTABLISHED/RELATED bypass -- the sole carve-out is the one configured Manager-exception channel. | Documented architecturally in each agent's isolation implementation (`panopticon-linux-agent`'s isolation ADR; `panopticon-agent`'s WFP single-permit-filter design in `RESPONSE.md`). This repository does not re-implement isolation logic (out of scope per `README.md`), so this invariant is recorded here as a cross-repo assertion to protect, not enforced by a schema. | `fixtures/commands/valid/isolate_host.json` |
| 13 | An unknown/unrecognized action must classify as `ANALYST_APPROVAL` (fail closed), never auto-fire. | `manager/detection/response.classify_tier`'s explicit default. | Documented in `docs/CONTRACT.md` section 1; covered by `panopticon-manager`'s own `test_classify_tier_matches_locked_decisions`. |
| 14 | A detection recommendation that cannot supply a PID-reuse-safe target must produce no command at all, never a guessed one. | `translate_recommendation`'s fail-closed `None` return for `TERMINATE_PROCESS` without both `target_pid` and `target_start_time_ticks`. | `fixtures/commands/invalid/missing_required_field.json` (paired with `docs/CONTRACT.md` section 4) |
| 15 | Raw file content, command stdout/stderr, or arbitrary executable output must never appear in a `CommandResult.detail` or a `Command.target`. | `detail` is a bounded (512 char) free-text field populated only by the agent's own fixed diagnostic strings, never by piping external output into it (verified by direct source read of both agents' result-serialization code -- see `docs/CONTRACT.md` section 3). | N/A -- this is a code-review invariant on future changes, not a JSON-shape-testable one; flagged here so a reviewer checks it explicitly on every change to result serialization. |
| 16 | `ISOLATE_HOST` success must never be reported on local bookkeeping alone -- the isolation helper must apply the intended kernel firewall state, correctly drain the *entire* netlink transaction's acknowledgements, and positively verify the resulting kernel state before returning success. | `panopticon-linux-agent/src/isolation_ruleset.cpp`'s `commit_batch` (explicit per-message ack counting, no longer `mnl_cb_run`'s first-ack-stops shortcut) and `verify_table_exists` (a real `NFT_MSG_GETTABLE` query gating the function's success return). This repository does not re-implement isolation logic (out of scope, see invariant 12), so this is recorded as a cross-repo assertion. **CI-VERIFIED**, not merely code-reviewed: `panopticon-linux-agent`'s `tests/e2e/run_isolation_packet_verification_e2e.sh` wires three real, veth-connected, non-loopback network namespaces and proves actual packet-level containment (an unrelated peer host becomes unreachable during isolation, the pinned Manager exception stays reachable, connectivity returns after release, isolate/release are idempotent) -- see run `https://github.com/Panopticon-Co/panopticon-linux-agent/actions/runs/34764245015`. This invariant exists because an earlier version of the helper violated it silently: an idempotent, expected-to-fail `DELTABLE` sharing one atomic nftables batch with the real `NEWTABLE`/`NEWCHAIN`/`NEWRULE` messages poisoned the whole batch's commit, while the ack-draining bug meant this was never detected -- `ISOLATE_HOST` reported success while applying zero real containment. Both root causes are fixed; see that file's doc comments for full detail. | N/A -- this is a netlink/kernel-state invariant, not a JSON-shape-testable one; the packet-verification e2e script above is its regression coverage. |

## Schema limitation: created_at < expires_at ordering is not schema-checkable

Both agents reject a command whose `created_at` is not strictly before its
`expires_at`. This is a cross-field comparison plain JSON Schema (without a
vocabulary extension) cannot express, so `schema/command.schema.json` validates
each timestamp's shape independently and `scripts/validate_fixtures.py` does not
attempt to assert the ordering invariant structurally -- it is exercised instead by
each implementing repo's own tests (e.g. `panopticon-linux-agent` and
`panopticon-agent` both unit-test `created_at >= expires_at` rejection directly).

## Schema limitation: expiry is not a schema-checkable property

`fixtures/commands/invalid/expired_command` (invariant 6) is rejected because its
`expires_at` is in the past *relative to when it is evaluated*, which is a runtime
comparison against a clock, not a structural JSON property `schema/command.schema.json`
can express. `scripts/validate_fixtures.py` therefore does not schema-check this
fixture at all; the expiry rule itself is proven by `response_engine.lifecycle`'s
`ANY -> EXPIRED` transition and each agent's own expiry check using an injectable
clock (see `fixtures/README.md`'s note on timestamp fields).

## Schema limitation: JSON Schema cannot express "reject non-UTC RFC 3339"

JSON Schema's `format: date-time` accepts any valid RFC 3339 timestamp, including
ones with a non-zero UTC offset (e.g. `2026-01-01T00:00:00+05:00`). The actual
agents are *stricter* than JSON Schema here: they reject any offset other than
`Z`/`+00:00`. `scripts/validate_fixtures.py` therefore does not rely on JSON Schema
alone for invariant 5 -- it additionally inspects the `expires_at` value in
`fixtures/commands/invalid/non_utc_timestamp.json` and asserts that a schema-only
check would (incorrectly) accept it, documenting this as a known schema-vs-
implementation gap rather than a silent, unverified assumption.

## Direct source search for banned execution patterns

Performed against `panopticon-response-engine`, `panopticon-manager`,
`panopticon-linux-agent`, `panopticon-agent`, and `panopticon-detection-engine` for:
`system(`, `popen(`, `exec(`, `execl`, `execlp`, `execv`, `execvp`, `/bin/sh`,
`/bin/bash`, `bash -c`, `sh -c`, `EXECUTE_COMMAND`.

Result: **no occurrence of any of these patterns exists in response-path code** in
any of the five repositories at the time of this repository's creation. (Detection
rule YAML content and unrelated build/tooling scripts may reference shell syntax for
unrelated purposes -- e.g. CI scripts calling real shells to run tests -- which is
expected and out of scope; what matters is that no *response action handler* in the
seven-action closed set constructs or executes a shell command or arbitrary
executable path.) This search should be re-run whenever any of the five
repositories' response-path code changes -- `scripts/validate_fixtures.py`'s
`--grep-repos PATH [PATH...]` mode automates it against local checkouts.
