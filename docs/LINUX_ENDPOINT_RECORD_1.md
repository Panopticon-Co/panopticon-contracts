# Linux endpoint record 1.0

The wire contract for what `panopticon-sensord` (the Linux endpoint agent) emits, one JSON object per
line. Machine-readable definition: `schema/linux-endpoint/1.0.schema.json`. Fixtures:
`fixtures/linux-endpoint/valid` (real sensord output, trimmed) and `fixtures/linux-endpoint/invalid`.
Check with `python scripts/validate_linux_endpoint.py [--ndjson FILE]`.

This contract is separate from `schema/endpoint-record/1.0.schema.json` (the generic envelope used for
Windows records). The two are not interchangeable; a consumer routes on `schema_version` plus the
presence of `record_type`, and an adapter between them is a consumer concern, not a reason to bend
either schema.

Everything below was checked against records produced by a real sensord on Ubuntu 22.04, kernel
5.15 (508 records, 28 record types, zero validation failures). Types listed under "defined, not yet
emitted" are not in the schema.

## Envelope

Closed object (`additionalProperties: false`). Always present:

| Field | Meaning |
| --- | --- |
| `schema_version` | constant `"1.0"` |
| `record_type` | `event`, `state`, `health` or `loss` |
| `id` | 32 hex, derived from sensor id, boot id and `seq`: stable, so a replayed record keeps its id |
| `seq` | per-sensor monotonically increasing sequence, assigned when the record is written to the durable log; a gap is a detectable loss |
| `type` | `process.exec`, `file.create`, `state.users`, ... |
| `time` | when the thing happened (RFC 3339 UTC, nanoseconds) |
| `observed_time` | when the sensor saw it; `time <= observed_time` for kernel events |
| `host` | `id`, `boot_id`, `hostname` |
| `sensor` | `id`, `version`, `policy_version` |
| `provenance` | `provider`, `mechanism`, `confidence` (`observed`, `reconstructed`, `inferred`, `user_space_reported`) |
| `unavailable` | `[{field, reason}]`: what could not be filled in and why. Absent data is never silently null |

## The nine kinds of information

1. **Raw observations** stay inside the sensor (kernel ring buffers, netlink datagrams). They never
   cross the wire: provenance is carried instead.
2. **Normalized events** (`record_type: event`): `process.*`, `file.*`, `network.*`, `auth.*`,
   `kernel.*`, `mount.changed`. Each carries the actor `process` (full entity, or a `{pid}` stub with
   an `unavailable` entry when the actor exited first), and one body object named after the domain.
3. **Maintained state** (`record_type: state`, `type: state.<object>`): inventories sent in numbered
   parts (`part`, `parts`, `snapshot_id`): `processes`, `host`, `posture`, `users`, `groups`,
   `interfaces`, `mounts`, `modules`, `persistence`. Process items are fully specified. Items of the
   other objects are open objects documented in the telemetry catalog; their fields may grow within
   1.x.
4. **Derived events**: `fim.baseline`, `fim.changed` (a change found by comparing states, with the
   actor attached only when a file event named one), `hash.computed` (a digest arriving after the
   `process.exec` it belongs to; joined on `process.entity_id` + `exec_gen`).
5. **Detections**: defined, not yet emitted by the endpoint. Local policy decisions are produced by
   the policy engine but have no wire record yet.
6. **Evidence**: defined, not yet emitted (forensic acquisition is a later slice).
7. **Commands** and 8. **command results**: unchanged; they use the existing command and
   command-result contracts, which are not part of this schema.
9. **Health and coverage** (`record_type: health`, `loss`): provider states with reasons, a
   `coverage` map of capability to the provider currently supplying it (`null` when nothing does),
   resource use, kernel capabilities, and `loss` records that account for dropped events by stage and
   type. Silence must be explainable from these.

## Process identity

A process is `entity_id` (32 hex, stable for one process lifetime on one boot) with `exec_gen`
(increments on every exec, so a record before and after `execve` are distinguishable) plus `pid` and
`start_ticks`. The pair (`pid`, `start_ticks`) within a `host.boot_id` is the identity the response
path verifies before signalling anything. `confidence.identity` and `confidence.attributes` say
separately whether the identity and the descriptive attributes were observed or reconstructed.

## Delivery, rejection and loss

A record moves through distinct states, and the stream says which one it reached:

`observed` -> `accepted by the sensor` -> `durably committed` (WAL) -> `sent` -> `accepted by the Manager`.

A Manager HTTP 200 does not mean every record in the batch was stored. The acknowledgement
accounts for each record exactly once (`accepted`, `duplicates`, or `rejected` at a named line).
A record rejected permanently is quarantined at the sensor with its reason and sequence number,
the stream continues, and the sequence gap is never renumbered. The sensor then emits a `loss`
record with `stage: manager_rejected`, a count and the sequence numbers, so a rejection can be
told apart from ordinary loss (`kernel`, `queue`, `wal`, `governor`, `transport`).

The `health` body carries machine-readable coverage: providers with `state`, `reason`, `family` and
`tier` (`primary` or `fallback`), `coverage` (capability to serving provider, empty when
uncovered), `wal` (`next_seq`, `durable_seq`, `acknowledged_seq`, `dropped_records`), `totals`
(records, events, loss records, sink errors, uptime, from which rates follow between two health
records), `delivery` (state, acknowledged sequence, retries, refusals, quarantined counts and the
last quarantined sequence numbers) and `kernel` capability flags. `wal`, `totals` and `delivery`
and provider `family` and `tier` are optional so earlier 1.0 sensors remain valid.

## Versioning

Because the envelope is closed, a new field requires a schema release and a coordinated consumer
update, even when the change is additive. Additive changes (new optional fields, new event types,
new `unavailable.reason` values) are minor releases; a removed or retyped field is a new major
version.

## Inventory changes

`posture.changed`, `interface.changed`, `account.changed`, `package.changed`, `device.changed` and
`firewall.changed` are events with a `change` body: the differences between two consecutive
inventories of one host-state object (`object`, `total`, `part`/`parts`, `truncated`, and
`entries` of `{key, kind, before?, after?}` where `kind` is `added`, `removed` or `modified`). The
first inventory of an object is a baseline and produces no change. A change found by comparing
inventories names no acting process (`unavailable` lists `process`). Posture changes are per
setting (`sysctl.kernel/yama/ptrace_scope`), and a setting that could not be read is never reported
as removed. `before` and `after` are JSON values.

## Container context

A `process` object may carry `container`: `{id, runtime, pod_uid?}`. It is derived by the endpoint
from the process cgroup path (Docker, containerd, CRI-O and Podman scopes, and Kubernetes pod
slices), so it is present exactly when the path names a container and absent for host processes.
`runtime` is `kubernetes` when the path names a pod but not the runtime behind it. It is a claim
made by whoever created the cgroup, which is why `cgroup` is always kept next to it.

## UDP flows

`network.udp_flow` is the first datagram of a UDP flow from a process to a destination, once per
destination per 60 seconds per process. It uses the same `network` body as `network.connect`
(`direction` is `outbound`, `state` is empty).

## Executable memory and eBPF loads

`memory.exec_mapping` reports a request to make memory that no file on disk backs executable, and
`kernel.bpf_load` a request to load or attach an eBPF program. Both carry the requesting `process`
(a `{pid}` stub plus an `unavailable` entry when it had exited) and one body object.

| Body | Fields |
| --- | --- |
| `memory` | `operation` (`mmap` or `mprotect`), `backing` (`anonymous`, `memfd`, `file`), `write_exec` (the mapping is writable as well as executable), and for `mprotect` only `address` and `length` of the mapping the call touched. An `mmap` has no address at the kernel hook, so `memory.range` is listed as unavailable. |
| `bpf` | `command` (`prog_load`, `prog_attach`, `raw_tracepoint_open`, `link_create`), `program_type` for `prog_load`, `attach_type` for `prog_attach` and `link_create`, `name` (the program name, or the tracepoint for `raw_tracepoint_open`). |

Both are requests observed before the kernel acts (LSM call sites), so a later security module may
still refuse them. Reporting is deduplicated in the kernel per process, operation and backing over
five seconds, so a JIT that maps thousands of pages is one record. File-backed `mmap` and a
read-only `mprotect` of a file mapping are not reported. Creating eBPF maps is not reported. The
sensor never reports its own eBPF loads.

Checked against records from a real sensord on Ubuntu 22.04 / 5.15: an anonymous RWX `mmap`, an
`mprotect` to executable, an executable `memfd` mapping and a socket-filter `BPF_PROG_LOAD`, each
attributed to the exact process.

## Namespace changes

`process.ns_change` reports a task that moved into other namespaces with `setns(2)` or `unshare(2)`.
It carries the acting `process` and one `ns_change` body.

| Field | Meaning |
| --- | --- |
| `scope` | `process` when the thread group leader moved (the process entity's namespaces change); `thread` when only one thread moved and the process keeps its namespaces. |
| `thread_id` | The task that made the call. |
| `changes[]` | One entry per namespace that actually changed: `ns` (`mnt`, `pid_for_children`, `net`, `uts`, `ipc`, `cgroup`), `from` and `to` inode numbers. |

A call that leaves every namespace the same (for example `nsenter` into the host's own namespaces)
is not reported. `nsenter` with several namespace flags performs one `setns` per type and so
produces one record per type. The pid entry is the namespace the task's children will be created in:
`unshare(CLONE_NEWPID)` changes it, not the task's own pid namespace. User namespaces live in the
credentials, not the namespace proxy, and are listed as unavailable (`ns_change.user`).

Container runtimes legitimately produce these records: `runc` enters all six namespaces of a new
container, and a daemon that locks an OS thread to a container network namespace (dockerd does)
produces thread-scope `net` records in pairs. A rule needs the process identity, not the event alone.

Checked against records from a real sensord on Ubuntu 22.04 / 5.15: `unshare --uts --ipc`, a docker
container start (`runc` entering the container's six namespaces, inode numbers equal to the
container's `/proc/<pid>/ns`), and `nsenter` into that container.

## DNS queries

`dns.query` reports a plain DNS question a process sent over UDP to port 53. It carries the asking
`process` (a `{pid}` stub plus an `unavailable` entry when it had exited) and one `dns` body.

| Field | Meaning |
| --- | --- |
| `name` | The queried name in presentation form, exactly as sent: case is preserved (some resolvers randomise it), no trailing dot, `.` for the root. A `.` or `\` inside a label is escaped with a backslash and any byte outside printable ASCII is written `\DDD`. At most 1020 characters. |
| `type`, `class` | The record type (`A`, `AAAA`, `TXT`, `HTTPS`, ... or `TYPE<n>`) and class (`IN`, `CH`, ... or `CLASS<n>`). |
| `transaction_id`, `recursion_desired` | From the message header. |
| `transport` | Always `udp`. DNS over TLS or HTTPS is not visible here; it appears as an ordinary connection. |
| `family`, `server`, `local` | The address family and the two endpoints of the datagram. |

The record is the question as it left the process, not an answer: there is no resolved address and
no response code. A stub resolver makes two records for one lookup, one from the application to the
stub (for example `127.0.0.53`) and one from the stub to its upstream; each names its own process.
Reporting is deduplicated in the kernel per process and question over five seconds (the transaction
id is ignored, so a retry is a duplicate). Only the first buffer of a datagram is read, so a question
split across several `sendmsg` buffers is not reported, and datagrams to port 53 that are not a DNS
question yield no `dns.query` (the UDP flow record still names them).

Checked against records from a real sensord on Ubuntu 22.04 / 5.15: `getent` to the local stub, the
stub's own upstream queries (including DNSSEC `DNSKEY` and `DS`), and a direct `TXT` query to a
resolver from a script.

## Mandatory access control and firewall changes

`lsm.denial` reports an access that AppArmor or SELinux refused, or would have refused. It carries
the `process` that was denied (a `{pid}` stub plus an `unavailable` entry when it had exited) and an
`lsm` body: `module` (`apparmor` or `selinux`), `operation` (`open`, `mknod`, `exec`, `capable`, or
the first SELinux permission), `outcome` (`denied`, or `would_deny` when the module only logs: an
AppArmor profile in complain mode, an SELinux domain that is permissive), and, when the kernel gave
them, `object` (the path, capability or peer), `requested` and `denied` (the access, `r`, `w`, `c`,
or the SELinux permissions), `profile` (the AppArmor profile or the SELinux source context),
`target_context` and `object_class` (SELinux), and `comm`. `sanitized` is true when a string
contained bytes outside printable ASCII or was cut at its limit.

`lsm.policy` reports a change to the module itself: an AppArmor profile loaded, replaced or removed
(`operation` `profile_load`, `profile_replace`, `profile_remove`, `object` the profile name, `process`
the loader, usually `apparmor_parser`), or an SELinux policy load or mode change (`policy_load`,
`enforcing`, `permissive`, `enabled`, `disabled`, with no process: the kernel record does not name
one). A policy change has no `outcome`.

`netfilter.config_change` reports one change to the packet filter rules, taken from the kernel audit
record for a netfilter table change: `subsystem` (`nft` for nftables, including the `iptables`
front end that uses it, `xtables` for the legacy tables), `operation` (`nft_register_rule`,
`nft_unregister_chain`, `xt_replace`, ...), `table`, `family`, `entries` (how many objects the
transaction touched), `generation` (nftables: the ruleset generation after the change) and `comm`.
The `process` is the one that made the change (`iptables`, `nft`, a container runtime). It does not
carry the rule: the record says that a table changed and who changed it, not what the rule says.
`firewall.changed` remains the inventory difference between two snapshots and has a different body.

These come from the kernel audit stream, so they exist only on a host where auditing is enabled and
the sensor can join the audit multicast group; the audit provider reports it in `health` when it
sees nothing. AppArmor reports the thread group id as `pid`, so a denial raised by any thread
resolves to its process. SELinux records are read from the documented message formats and unit tests;
they have not been captured from a live SELinux host.

Checked against records from a real sensord on Ubuntu 22.04 / 5.15: a temporary AppArmor profile that
was loaded, replaced and removed and that denied a read and a file creation, and `iptables` and `nft`
adding and removing chains, rules and a table.

## Response actions

A `response.action` record is the endpoint's audit of one command it handled. It is evidence that the
endpoint decided, and what it decided. It is not the command result, which travels on the command channel
(`command-results`, schema 2) and is what moves the Manager's command lifecycle. Both are sent for every
handled command, accepted or refused.

`response` carries `command_id`, `correlation_id`, `action` (the closed set of seven actions, or `UNKNOWN`
for a command that could not be parsed), `outcome` (`succeeded`, `failed`, `rejected`, `indeterminate`), a
lowercase `reason` code (`ok`, `dry_run`, `target_mismatch`, `target_protected`, `expired`,
`not_yet_valid`, `lifetime_exceeded`, `unsupported_action`, `replay`, `rate_limited`, ...), `dry_run`
and `executed`. `executed` means the executor was invoked; whether the host changed is
`executed && !dry_run && outcome == "succeeded"`. A signal action also carries `target`
(`pid` + `start_time_ticks`, the identity that was verified) and `mode` (`pidfd`, or `pid_fallback`
if the kernel has no pidfd); `affected` and `detail` (at most 512 characters) are optional.
`detail` is the same text as the command result so the two can be compared.

Checked against records produced by a real sensord on Ubuntu 22.04 / 5.15 acting on commands that a real
Manager authorised and dispatched: a verified dry-run kill, a kill of a sacrificial process, a start-time
mismatch, a protected PID, a lifetime refusal, an unsupported action and a process-info collection.
