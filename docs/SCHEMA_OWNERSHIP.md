# Shared schema ownership

`panopticon-contracts/schema` owns cross-component wire schemas:

| Boundary | Canonical file |
| --- | --- |
| Legacy Windows/Linux telemetry 0.2–0.4 | `telemetry-event-0.4.schema.json` |
| Canonical endpoint telemetry | `endpoint-record/1.0.schema.json` and family schemas |
| Legacy commands/results | `command.schema.json`, `command_result.schema.json` |
| Windows boot-bound process commands | `windows-process-command-v2.schema.json` |
| Durable execution evidence | `command-result-v2.schema.json` |

The legacy telemetry schema is initially an exact copy of Officer's
`schema/event.schema.json`, retaining its stable `$id` and wire behavior.
That agent-local file is a compatibility mirror for existing native build tools.
Schema changes should originate here and update mirrors in the same release;
Manager's ingest contract tests compare its mirror with this canonical copy.
No endpoint rebuild or runtime dependency is introduced by publishing this file.

Command cancellation is an orchestration operation, not an eighth endpoint action.
An authorized command may become CANCELLED only before dispatch. Poll and cancel
must serialize atomically. Dispatched/accepted commands cannot be cancelled by
this API because execution may already have begun. Late receipts remain evidence
without changing CANCELLED, EXPIRED or any other terminal state.
