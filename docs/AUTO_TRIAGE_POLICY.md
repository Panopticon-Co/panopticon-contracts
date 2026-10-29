# Automated collection triage policy, version 1

Only `COLLECT_PROCESS_INFO`, `COLLECT_NETWORK_CONNECTIONS` and `COLLECT_FILE` can
appear in this policy. The seven-action vocabulary is unchanged. Destructive
actions and arbitrary execution are invalid policy inputs, including when a rule
is disabled. `COLLECT_FILE` remains metadata/hash JSON rather than binary transfer.

Each immutable revision belongs to one exact detection rule ID. The policy matrix
contains at most one decision for each collection action × asset class. Decisions
are `auto_dispatch`, `skip`, or `require_approval`. Missing tuples skip; a newer
revision must be created for a toggle or any policy/budget change. Rule disablement
does not disable its detection. Existing rules receive no new automatic behavior
from merely installing this schema. New default policies are disabled.

```typescript
type CollectAction = "COLLECT_PROCESS_INFO" | "COLLECT_NETWORK_CONNECTIONS" | "COLLECT_FILE";
type AssetClass = "standard" | "critical" | "unknown";
type Decision = "auto_dispatch" | "skip" | "require_approval";
interface Entry {
  action: CollectAction;
  asset_class: AssetClass;
  decision: Decision;
  file_paths?: { platform: "windows" | "linux"; path: string }[];
}
interface CollectionBudgetV1 {
  reserved_bytes_per_action: 1048576;
  max_actions_per_alert: number;
  max_bytes_per_alert: number;
  endpoint_window_seconds: number;
  max_actions_per_endpoint_window: number;
  max_bytes_per_endpoint_window: number;
  max_active_per_endpoint: number;
  workflow_ttl_seconds: number;
}
interface AutoTriagePolicyV1 {
  schema_version: "1";
  rule_id: string;
  version: number; // server-owned immutable revision
  enabled: boolean;
  entries: Entry[];
  budget: CollectionBudgetV1;
}
// Evaluation also requires current endpoint capability/policy, signed delivery,
// verified targets and durable usage. These can restrict, never broaden, Entry.
```

Asset classification is Manager-owned. Endpoint/alert-provided labels cannot make
an endpoint eligible for automatic execution. Critical and unknown/unclassified
assets cannot be configured for auto-dispatch; the default matrix requires analyst
approval for them. Standard assets default to automatic process/network collection
only after the disabled rule is explicitly enabled. File collection requires
approval unless a standard-asset entry explicitly lists the exact absolute native
path and platform. No prefixes, wildcard/glob expansion, relative paths, traversal,
device/UNC paths, alternate streams or ambiguous Windows filename aliases are
accepted. The endpoint's own action/path policy remains authoritative at execution.

Capability evaluation requires a fresh authenticated report, enforcement mode,
implemented and locally allowed collection action, an authenticated command channel, and
`signed-json-v2-resume-v1` artifact delivery. Missing/stale reports, unsupported
actions or missing signed delivery skip with an explicit reason. Process collection
also requires verified PID/start-time/boot identity; file targets must come from the
retained alert and match the policy exactly for automatic collection. No target is
invented when evidence is insufficient.

## Collection budget definition

A collection budget bounds actions, reserved output bytes, endpoint frequency,
concurrency and workflow lifetime. Before authorizing each collection, Manager must
reserve its full native 1 MiB output maximum in a durable transaction. Actual small
results do not make an already-admitted workflow eligible to evade this window's
frequency/byte limits. Policies cannot claim a smaller collector bound that an
installed agent does not implement. Storage reservations for transfer remain a
separate Feature 2 enforcement layer.

| Field | Default | Hard policy bounds |
|---|---:|---:|
| `reserved_bytes_per_action` | 1,048,576 | fixed 1 MiB |
| `max_actions_per_alert` | 3 | 1–3 |
| `max_bytes_per_alert` | 3,145,728 | 1–3 MiB |
| `endpoint_window_seconds` | 900 | 60–86,400 |
| `max_actions_per_endpoint_window` | 12 | 1–64 |
| `max_bytes_per_endpoint_window` | 12,582,912 | 1–64 MiB |
| `max_active_per_endpoint` | 3 | 1–8 |
| `workflow_ttl_seconds` | 300 | 30–900 |

An additional server hard ceiling is 128 active automatic collections globally.
Counts/bytes are shared across triage rules targeting an endpoint, so switching rule
IDs cannot bypass the endpoint limit. Quota exhaustion skips explicitly. Lifetime,
window and live classification/capability checks must be re-evaluated before queued
dispatch; a stored decision is not permission to ignore a subsequent policy change.

## Lifecycle and cancellation contract

Every automated workflow is idempotent per originating alert and pinned policy
revision; replaying an alert cannot create a second workflow or consume budget twice.
All automatic lifecycle facts reference actor `system/auto-triage`, the rule and
policy revision, original response request, endpoint and time. Actual agent-reported
actor/receipt provenance is retained alongside the correlated automation facts.
Created → authorized → dispatched → accepted → result → audited all use Manager's
hardened response ledger. No parallel or weaker audit writer is permitted.

Cancellation reuses the existing response-request queued-command cancellation
path. An analyst can stop remaining queued work in an active workflow; commands
already dispatched/accepted are reported as in flight and are not falsely claimed
to be recalled. Their late signed evidence remains attached and auditable. Case
access and artifact retrieval continue using the existing exact analyst/case/host
grants; automatic collection never grants an analyst evidence access implicitly.

These schemas define the policy/evaluation foundation. Runtime orchestration and
Console controls are implemented and qualified as subsequent Feature 1 items; the
schema itself does not enable detection-triggered collection.
