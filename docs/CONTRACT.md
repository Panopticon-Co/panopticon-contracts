# The Panopticon Response Contract

This document reconciles the *actual* implementations across
`panopticon-response-engine` (Python, canonical domain model), `panopticon-manager`
(Python, HTTP transport + persistence), `panopticon-linux-agent` (C++), and
`panopticon-agent` (C++, Windows "Officer") as of this repository's creation. Where an
implementation disagreed with its own documentation, the discrepancy is recorded
below rather than silently "corrected" in only one place.

Source files inspected to write this document:

- `panopticon-response-engine/response_engine/contract.py` (canonical `Command`/`CommandResult` Pydantic models)
- `panopticon-response-engine/response_engine/lifecycle.py` (canonical lifecycle state machine)
- `panopticon-response-engine/response_engine/recommendation.py` (detection recommendation -> action translation)
- `panopticon-manager/manager/routers/commands.py` (HTTP transport, wire envelope construction)
- `panopticon-linux-agent/include/panopticon/linux_agent/command.hpp` + `src/command.cpp`
- `panopticon-agent/include/panopticon/officer/response/command.hpp` + `src/response/command.cpp`

## 1. The closed action set

Exactly seven actions exist. No implementation may add an eighth, and none currently
does:

| Action                        | Tier             | Target shape                      |
|--------------------------------|------------------|------------------------------------|
| `KILL_PROCESS`                 | ANALYST_APPROVAL | `{pid, start_time_ticks}`          |
| `COLLECT_PROCESS_INFO`         | AUTO_SAFE        | `{pid, start_time_ticks}`          |
| `COLLECT_NETWORK_CONNECTIONS`  | AUTO_SAFE        | `{}` (no target)                   |
| `COLLECT_FILE`                 | ANALYST_APPROVAL | `{path}`                           |
| `QUARANTINE_FILE`              | ANALYST_APPROVAL | `{path}`                           |
| `ISOLATE_HOST`                 | ANALYST_APPROVAL | `{}` (no target)                   |
| `RELEASE_HOST_ISOLATION`       | ANALYST_APPROVAL | `{}` (no target)                   |

Tiering is `panopticon-manager/manager/detection/response.classify_tier`'s job, not
this contract's -- an *unknown* action must classify as `ANALYST_APPROVAL` (fail
closed), never `AUTO_SAFE`. This repository's fixtures assert the action set is
closed; the tier table above documents the currently-locked assignment for
reference, and is intentionally duplicated in `docs/SECURITY.md` as a security
invariant, not just a UX detail.

There is no `EXECUTE_COMMAND`, `RUN_SCRIPT`, `SHELL`, `FIREWALL_RULE`, or `BLOCK_IP`
action, and none may be added without a superseding ADR. `BLOCK_FIREWALL_IP` is a
**detection-engine recommendation string**, not a response action -- it downgrades to
`ISOLATE_HOST` (see section 4).

## 2. The `Command` wire envelope

The wire JSON an agent receives from `GET /api/v1/agents/{agent_id}/commands` is
**not** identical to `response_engine.contract.Command`'s own field set. Manager
constructs the wire object by taking `Command.model_dump()` (which has
`command_id`, `agent_id`, `action`, `expires_at`, `target`, `correlation_id`) and
injecting **three** additional fields that only Manager knows at dispatch time
(`manager/routers/commands.py`'s `authorize_and_enqueue`):

```json
{
  "command_id": "cmd-0001",
  "agent_id": "agent-linux-01",
  "host_id": "host-linux-01",
  "schema_version": "1",
  "created_at": "2026-01-01T00:00:00Z",
  "action": "KILL_PROCESS",
  "expires_at": "2026-01-01T00:10:00Z",
  "target": {"pid": 4242, "start_time_ticks": 987654321},
  "correlation_id": "corr-0001"
}
```

**This is the actual, reconciled wire contract** -- both native agents
(`panopticon-linux-agent/src/command.cpp`'s `parse_command_json` and
`panopticon-agent/src/response/command.cpp`'s `parse_command_json`) hardcode
exactly this 9-field shape and **require** `created_at`, additionally validating
`created_at < expires_at` before accepting a command. This corrects an error in
this document's first published revision, which omitted `created_at` entirely
after only reading `response_engine/contract.py` and not the two native agents'
actual parsers -- exactly the kind of drift this repository exists to catch. A
future change to `response_engine.contract.Command` to add `host_id`/
`schema_version`/`created_at` directly (so the Python model matches what actually
goes over the wire) is a reasonable follow-up but is out of scope for this
repository, which documents current behavior rather than prescribing a rewrite.

**Verified implementation-vs-implementation discrepancy (unknown-field rejection)**:
`panopticon-agent`'s parser explicitly enumerates all 9 allowed top-level keys and
rejects any JSON object containing a key outside that set (`allowed_keys` in
`command.cpp`) -- matching `response_engine.contract.Command`'s `extra="forbid"`.
`panopticon-linux-agent`'s parser, by contrast, is a hand-rolled substring scanner
(not a real JSON object decode) that extracts only the fields it recognizes and
**never checks whether additional, unrecognized top-level keys are present** -- a
smuggled field such as `"shell": "..."` would currently be silently ignored rather
than rejected. No response handler in `panopticon-linux-agent` ever reads or acts
on an unrecognized field, so this is not currently an exploitable execution path,
but it is a real deviation from the intended closed-envelope invariant (see
`docs/SECURITY.md` invariant 2) and from the other two implementations' stricter
behavior. **Decision**: the implementation is being fixed to match the documented,
safer contract (reject unknown top-level keys), not the other way around --
tracked in `panopticon-linux-agent`'s own commit history and cross-referenced from
`docs/SECURITY.md`.

Field rules (from `Command.enforce_closed_target_schema`, reproduced here so a
non-Python reader does not have to read Pydantic to find them):

- `command_id`, `agent_id`: 1-128 characters.
- `correlation_id`: 1-128 characters. Server-generated (UUID4) if the alert pipeline
  didn't set one; always present on the wire.
- `schema_version`: currently always the literal string `"1"`. See `VERSIONING.md`.
- `created_at`, `expires_at`: RFC 3339 UTC only (`Z` suffix or `+00:00`). Both
  agents reject a timestamp carrying any other offset outright rather than
  converting it, and both additionally reject a command where
  `created_at >= expires_at` (a command that claims to have expired before or at
  the moment it was created).
- `target` for `KILL_PROCESS` / `COLLECT_PROCESS_INFO`: **exactly** the two keys
  `pid` and `start_time_ticks`, both positive integers (not booleans). No other keys
  permitted, none omitted.
  - `start_time_ticks` is an **opaque, OS-native pass-through token** (Linux:
    `/proc/[pid]/stat` field 22; Windows: `GetProcessTimes` creation `FILETIME`). No
    consumer other than the *same host's own agent*, re-observing the process fresh,
    may interpret its magnitude. See
    `panopticon-response-engine/docs/adr/002-terminate-process-start-time-threading.md`.
- `target` for `COLLECT_FILE` / `QUARANTINE_FILE`: **exactly** the one key `path`,
  a non-empty string of at most 4096 characters. Path resolution/jailing
  (`resolve_within_allowed_root` in both agents) is agent-side, OS-specific, and
  intentionally out of this contract's scope -- this contract only bounds the wire
  string's length and requires it be non-empty.
- `target` for every other action: must be empty (`{}`). A non-empty target on
  `ISOLATE_HOST`/`RELEASE_HOST_ISOLATION`/`COLLECT_NETWORK_CONNECTIONS` is a contract
  violation, not tolerated as extra data.
- No implementation may accept a `shell`, `command`, `script`, `args`, `executable`,
  or `firewall_rule` field on `Command` or its `target`. See `docs/SECURITY.md`.

## 3. The `CommandResult` wire envelope

```json
{
  "result_id": "res-0001",
  "command_id": "cmd-0001",
  "outcome": "succeeded",
  "detail": "command accepted for a closed action handler",
  "correlation_id": "corr-0001"
}
```

`outcome` is one of exactly three wire values: `succeeded`, `failed`, `rejected`.
This is intentionally coarser than either native agent's *local* diagnostic
vocabulary. `panopticon-linux-agent`'s internal `receipt_code` enum has eight values
(`succeeded`, `invalid_command`, `expired`, `replay_detected`, `target_mismatch`,
`target_protected`, `unsupported_action`, `execution_failed`) and collapses them onto
the three wire values before submitting a result (`src/command.cpp`,
`serialize_command_result`):

| Local `receipt_code`   | Wire `outcome` |
|-------------------------|----------------|
| `succeeded`              | `succeeded`    |
| `execution_failed`       | `failed`       |
| `invalid_command`        | `rejected`     |
| `expired`                | `rejected`     |
| `replay_detected`        | `rejected`     |
| `target_mismatch`        | `rejected`     |
| `target_protected`       | `rejected`     |
| `unsupported_action`     | `rejected`     |

The finer-grained reason is preserved only in the free-text `detail` field (bounded
to 512 characters, `extra="forbid"` on the model itself). **No implementation may
put raw command output, stdout/stderr, or arbitrary executable output into
`detail`** -- it is a bounded, agent-authored diagnostic string, not a data
exfiltration channel. `panopticon-agent` (Windows) follows the same three-value
collapse for parity; see `docs/COMPATIBILITY.md` for the exact mapping used there.

Manager's `/command-results` handler also enforces (`manager/routers/commands.py`):
a result's `correlation_id`, if present, must match the *stored* command's
`correlation_id` or the result is rejected outright (a forged/confused-deputy
result cannot silently attach itself to the wrong command via a mismatched
correlation id).

## 4. Detection recommendation -> response action translation

`panopticon-detection-engine` (eyedetect) never speaks this contract directly. It
emits a looser recommendation vocabulary as part of an `Alert`'s
`active_response` dict (`ActiveResponseAction.to_dict()`): `TERMINATE_PROCESS`,
`ISOLATE_HOST`, `BLOCK_FIREWALL_IP`. `response_engine.recommendation.
translate_recommendation` is the **single place** this is mapped onto the closed
7-action set:

- `TERMINATE_PROCESS` -> `KILL_PROCESS`, target `{pid, start_time_ticks}` -- **only**
  if both `target_pid` (positive int) and `target_start_time_ticks` (positive int)
  are present and correctly typed. Otherwise: `None` (no command staged). This
  function must never guess a `pid` without a `start_time_ticks` alongside it --
  doing so would defeat the entire PID-reuse defense the rest of the contract is
  built around.
- `ISOLATE_HOST` -> `ISOLATE_HOST`, target `{}` (direct mapping).
- `BLOCK_FIREWALL_IP` -> `ISOLATE_HOST`, target `{}`, with a `"downgraded"` reason
  string -- eyedetect's IP-scoped block recommendation is deliberately widened to a
  full host isolation, because there is no per-IP firewall action in the closed set
  (see ADR referenced in `response_engine`'s own `docs/adr/001-repository-boundary.md`).
- Anything else -> `None`.

`translate_recommendation` returning `None` means **Manager must not enqueue a
command** for that alert's active-response recommendation. `manager/detection/
response.on_alert_created` respects this: a `None` translation produces a
`REJECTED` `response_actions` row with no `command_id`, never a guessed target.

## 5. Lifecycle

```
PENDING -> AUTHORIZED -> DISPATCHED -> ACCEPTED -> SUCCEEDED | FAILED | REJECTED
PENDING -> CANCELLED
ANY (non-terminal) -> EXPIRED
```

Canonical implementation: `response_engine.lifecycle.ResponseActionState` +
`is_legal_transition`. Terminal states (`SUCCEEDED`, `FAILED`, `REJECTED`,
`CANCELLED`, `EXPIRED`) have no outbound transitions.

**Reconciled discrepancy**: Manager does not persist this as one state machine over
one row. It splits it across two tables:

- `response_actions.lifecycle_state` takes only `PENDING`, `AUTHORIZED` (meaning
  "translated into a `commands` row"), `REJECTED`, or `EXPIRED`.
- `commands.lifecycle_state` takes only `AUTHORIZED`, `DISPATCHED`, or a terminal
  state (`SUCCEEDED`/`FAILED`/`REJECTED`/`EXPIRED`).
- Manager has no distinct `CANCELLED` value in its schema. An analyst declining a
  still-`PENDING` `response_actions` row is recorded as `REJECTED` -- reusing the
  terminal-outcome string for what this contract calls `CANCELLED`. This is a
  documented naming compression, not a bug: the two concepts (a pre-dispatch
  decline vs. an agent's post-dispatch rejection) are distinguishable by which
  table and stage produced the row, even though both are spelled `REJECTED` in
  SQL. Wire-visible behavior to an agent is unaffected, since agents never see
  `response_actions` rows.
- `ACCEPTED` is optional. `POST /api/v1/agents/{agent_id}/commands/{command_id}/accept`
  moves `DISPATCHED -> ACCEPTED`, but a result submitted straight from `DISPATCHED`
  is still accepted by Manager. Both native agents call `accept` as a best-effort
  step (its outcome is never checked and never blocks execution).

Fixtures in `fixtures/lifecycle/` exercise both the idealized single-state-machine
view and note where Manager's two-table split changes what a given fixture actually
asserts against a live Manager instance vs. against `response_engine.lifecycle`
directly.

**Reconciled implementation bug (CI-verified fix)**: `response_engine.lifecycle`'s
`_LEGAL_TRANSITIONS` table previously only allowed `DISPATCHED -> ACCEPTED`, which
contradicted this document's own already-recorded description of Manager's real,
intentional behavior (a result submitted straight from `DISPATCHED` has always been
accepted, since `accept` is optional). This meant the canonical lifecycle model was
*stricter* than the system it was supposed to describe. Fixed in
`panopticon-response-engine` by adding `DISPATCHED -> SUCCEEDED | FAILED | REJECTED`
to the legal-transition set, with regression coverage in `tests/test_lifecycle.py`,
and propagated into `panopticon-manager` via a `vendor/response_engine` submodule
bump (all 122 vendored tests still pass unchanged). `ACCEPTED` remains a distinct,
non-terminal state -- this fix does not collapse it into `SUCCEEDED`, it only stops
treating it as a mandatory hop.

## 6. Non-goals of this document

This contract does not define: how an agent decides *when* to poll, transport
authentication mechanics (bearer enrollment, mTLS, etc.), evidence-upload formats
for `COLLECT_PROCESS_INFO`/`COLLECT_NETWORK_CONNECTIONS`/`COLLECT_FILE` (those reuse
existing telemetry/evidence paths per-repo, not a shared wire contract), or
OS-specific execution details (nftables rule shape, WFP filter GUIDs, nsenter/AF_UNIX
helper IPC). Those remain implementation details owned by
`panopticon-response-engine`, `panopticon-linux-agent`, and `panopticon-agent`
respectively.
