# Platform architecture decisions

These ADRs record decisions that cross repository boundaries. Each repository keeps its own ADRs
for decisions inside it. Where a platform ADR and a repository ADR disagree, the platform ADR
wins, and the repository ADR is listed below as superseded.

The current architecture is described in
[`../architecture/SYSTEM_DESIGN.md`](../architecture/SYSTEM_DESIGN.md). Every ADR from 0002 on
starts from implementation evidence: code, test runs and live lab results as of 2026-10-06.

## Index

| # | Title | Priority | Status | Needs team approval |
|---|---|---|---|---|
| [0001](0001-panopticon-contracts.md) | Introduce panopticon-contracts | — | Accepted | — |
| [0002](0002-canonical-endpoint-envelope.md) | One canonical endpoint envelope (endpoint-record 2.0) | P0 | Proposed | **Yes**: both agents' wire format |
| [0003](0003-linux-windows-schema-convergence.md) | Common semantics, per-OS bodies | P0 | Proposed | With 0002 |
| [0004](0004-process-identity.md) | One exact process key and entity id | P0 | Proposed | **Yes**: Detection Engine and Windows agent |
| [0005](0005-postgresql-manager-storage.md) | PostgreSQL as Manager's shared store | P0 | Proposed | **Yes**: all of Manager |
| [0006](0006-manager-detection-boundary.md) | Manager / Detection Engine boundary | P0 | Proposed | **Yes**: Detection Engine owner |
| [0007](0007-console-manager-api-boundary.md) | Console reads Manager's API | P0 | Proposed | No |
| [0008](0008-command-target-binding-schema-2.md) | Command target binding: schema 2 everywhere | P0 | Accepted (Linux), Proposed (platform) | No |
| [0009](0009-durable-delivery-and-loss.md) | Durable delivery and explicit loss | P0 | Proposed | No |
| [0010](0010-lab-and-test-architecture.md) | Lab and test architecture | P1 | Proposed | **Yes**: hardware, `panopticon-lab` repository |
| [0011](0011-provider-and-fallback-model.md) | Providers, fallbacks, declared capability | P1 | Accepted (Linux), Proposed (platform) | No |
| [0012](0012-detection-contract.md) | Detection contract (CDE, Detection, Incident) | P1 | Proposed | **Yes**: Detection Engine owner |
| [0013](0013-response-authorization.md) | Response authorization: three gates, signed commands | P1 | Proposed | **Yes**: signatures required for `enforce` |
| [0014](0014-command-and-result-model.md) | Command and result model | P1 | Proposed | No |
| [0015](0015-forensic-artifact-storage.md) | Forensic artifact storage | P1 | Proposed | No |
| [0016](0016-health-and-coverage-model.md) | Health and coverage | P1 | Proposed | No |
| [0017](0017-e2e-test-architecture.md) | End-to-end test architecture | P1 | Proposed | No |
| [0018](0018-scale-out-strategy.md) | Scale-out strategy | P2 | Proposed | No |
| [0019](0019-clickhouse-migration-criteria.md) | ClickHouse migration criteria | P2 | Proposed | No |
| [0020](0020-distributed-detection-engine.md) | Distributed Detection Engine criteria | P2 | Proposed | No |
| [0021](0021-observability-stack.md) | Observability stack | P2 | Proposed | No |

## Supersession map

| Earlier decision or document | Effect | By |
|---|---|---|
| `panopticon-linux-agent` ADR 007, canonical endpoint model 1.0 and process identity | Identity derivation superseded; internal model kept | 0004, 0002 |
| `panopticon-linux-agent` ADR 017, the Linux endpoint record is its own contract | Superseded once endpoint-record 2.0 ships; 1.0 stays accepted as legacy | 0002 |
| `panopticon-linux-agent` ADR 008 / 018, WAL and uplink cursor | Kept; generalized as the platform delivery rule | 0009 |
| `panopticon-linux-agent` ADR 024, command channel, "schema 1 has no boot_id" gap | Gap closed for process actions | 0008 |
| `panopticon-agent` ADR 003, process identity from host, PID and start time | Superseded: the boot is added, ticks become native resolution, `process-key-v3` | 0004 |
| `panopticon-manager` ADR 002, wire protocol and ack semantics | Superseded for endpoint records; kept for legacy `/api/v1/ingest` until it is retired | 0009, 0002 |
| `panopticon-manager` ADR 003, single worker, sync handlers, events table as queue | Storage and worker parts superseded; one deployable kept | 0005, 0018 |
| `panopticon-manager` ADR 004 (two files share the number 004) | Renumbering one of them is recommended; no content change | — |
| `panopticon-response-engine` ADR 002, start-time threading for KILL_PROCESS | Extended with the boot scope | 0008, 0004 |
| contracts `WINDOWS_PROCESS_COMMAND_2`, "Windows only" scope | Becomes the process command contract for every endpoint | 0008 |
| `panopticon-console` reading the Detection Engine NDJSON alert file | Superseded | 0007 |
| Detection Engine README, "ingestion via `POST /api/v1/ingest`" | That route is Manager's; the engine is a library | 0006 |
| Workspace `CLAUDE.md`, "Current verified state" section | Out of date (rule counts, integration status, Manager existence); see the system design §1 | System design |

## Writing a new platform ADR

Use the next free number. Every section is required:

- Status
- Context (current evidence)
- Decision
- Alternatives considered
- Consequences
- Migration
- What remains provisional

Cite code by repository and revision. Cite runs by date and environment.
