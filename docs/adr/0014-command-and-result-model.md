# ADR 0014: Command and result model

## Status

Proposed — it consolidates what is implemented. Date: 2026-10-06.

## Context (current evidence)

- **The Response Engine contract** (`panopticon-response-engine`) defines:
  - `Command` with `command_id`, `agent_id`, `action`, `expires_at`, `target` and
    `correlation_id`;
  - `CommandResult`, schema 1 and 2;
  - a closed set of 7 actions;
  - a 9-state lifecycle (contracts ADR 0001).
- Manager injects `host_id` and `schema_version` at dispatch.
- **Linux** (ADR 024) implements `KILL_PROCESS` and `COLLECT_PROCESS_INFO`, and answers
  `unsupported_action` for the other five.
  - Results go to `POST /api/v1/agents/{id}/command-results` (schema 2), with
    `result_id = res-<command_id>` and the detail stored in the ledger, so a retry sends the same
    bytes.
  - A `response.action` audit record is written through the telemetry path.
- **Windows** implements all seven:
  - `COLLECT_FILE` returns path, size and sha256 evidence, never the content;
  - `QUARANTINE_FILE` moves the file under an allowed root and applies deny-execute and
    deny-write ACLs;
  - `ISOLATE_HOST` and its release are implemented;
  - results carry native execution evidence.

## Decision

1. **The action set stays closed:** the seven actions, with no shell and no script execution.
   Adding an action is a contracts change with fixtures for both agents.
2. **The command lifecycle is Manager's:** created → (approved) → queued → delivered → accepted →
   result (succeeded, failed, rejected or indeterminate) → closed, or expired or cancelled.
3. **Results are idempotent by `result_id`.** The endpoint stores the result detail before
   sending it.
4. **Two records of every action.** The *result* goes to the command API, and the *audit
   record* goes through telemetry (`kind: response`, category `response.action`, ADR 0002). The
   audit record is what detection and the Console timeline see; the result is what the lifecycle
   sees. They correlate on `command_id`.
5. **Linux closes its action gaps in this order:**
   1. `COLLECT_NETWORK_CONNECTIONS` (read-only; reuses the sock_diag code);
   2. `COLLECT_FILE` (hash-only evidence, as on Windows);
   3. `QUARANTINE_FILE`;
   4. `ISOLATE_HOST` and its release, through the privileged helper (Linux ADR 004).

## Alternatives considered

- **A generic "run script" action.** Rejected: it is unbounded, and it cannot be authorized
  meaningfully.

## Consequences

- Windows `command_result` records and the Linux `response.action` record converge under one
  category in endpoint-record 2.0.

## Migration

The category merge happens in endpoint-record 2.0. The Linux actions follow the order above, each
verified live.

## What remains provisional

- Result content size limits for collection actions.
- Streaming large collections as artifacts (ADR 0015).
