# Panopticon system design (current direction)

**Status:** Proposed for team adoption · **Date:** 2026-10-06

**Basis:** this document is built from the code and the live test runs listed in §1, not from the
earlier planning documents. Where it disagrees with an older plan, this document and the platform
ADRs in [`docs/adr/`](../adr/README.md) (0002 and later) state the intended architecture. The
older text is marked superseded in the ADR index.

## 1. What exists today (evidence)

| Component | Repository and revision examined | What it actually is |
|---|---|---|
| Linux endpoint | `panopticon-linux-agent` `feat/flagship-endpoint` `c84a6dc` | `panopticon-sensord`, a resident sensor. It has eBPF, fanotify, audit and netlink providers with fallbacks, an entity graph and a segmented CRC-framed WAL. It uploads over HTTPS (`linux-endpoint/1.0`, `POST /api/v2/linux-endpoint/records`). It has a command channel with a durable ledger (Linux ADR 024) that accepts schema-1 and schema-2 (boot-bound) process commands. Verified on Ubuntu 22.04 / 5.15 / x86_64 against a real Manager. |
| Windows endpoint | `panopticon-agent` `snapshot/windows-endpoint-dev` | Officer. Collects through ETW and Sysmon. Sends canonical `endpoint-record/1.0` (`POST /api/v2/endpoint/records`) alongside legacy schema 0.x (`POST /api/v1/ingest`). Supports boot-bound schema-2 process response with native execution evidence. |
| Manager | `panopticon-manager`: `main` `d3c1176`, `feat/linux-endpoint-ingest` `bceea18`, `snapshot/windows-endpoint-dev` `dc5f6b8` | FastAPI on one SQLite file (WAL mode). Handles enrollment and three ingest protocols. A `DetectionWorker` claim/lease loop runs the vendored Detection Engine in-process. Includes the Response Engine module (tiers, analyst approval), the command queue and the command lifecycle. |
| Detection Engine | `panopticon-detection-engine`: `main` (`eee2dc2`), Sokhi's `phase-2/behavioral-rarity-baseline` `d744c2a`, Windows snapshot `a535f1d` | A Python library and CLI. Three lines that all descend from `f089331` (see D3). |
| Response Engine | `panopticon-response-engine`: `main` `cc61fcc` (vendored by Manager `main` and the Linux branch), Windows snapshot `99add09` (adds command/result schema 2) | Pydantic `Command` / `CommandResult` contract, a closed set of 7 actions, and approval-tier policy. It is not a service. |
| Console | `panopticon-console` `main` | A small Python server that reads the Detection Engine's alert **NDJSON file**, plus one read-only proxy route to Manager. |
| Contracts | `panopticon-contracts`: `master`, `feat/linux-endpoint-record` `241e315`, `snapshot/windows-endpoint-dev` `1d96f73` | JSON Schemas and fixtures for both endpoint record contracts, commands (schema 1, and schema 2 for Windows), results (schemas 1 and 2) and enrollment. |
| Lab | One Windows 11 Home laptop (i7-13700HX, 24 threads, 16 GB, VBS on) running VirtualBox 7.2 + Vagrant. One Ubuntu 22.04 VM (6 vCPU, 4 GB). Manager runs natively on the host and is reached over VirtualBox NAT (`10.0.2.2:8553`). | Live tests are shell scripts in a personal scratch directory. |

### Divergences found: the reasons the architecture must change

**D1. Two endpoint record contracts.**

| | Linux `linux-endpoint/1.0` | Windows `endpoint-record/1.0` |
|---|---|---|
| Shape | Flat record: `type` plus a body per telemetry family | Generic envelope: `kind`, `category`, `endpoint`, `provenance`, `subject`, `data` |
| Ordering | `seq` per sensor | `sequence` inside `provenance` |

- Each contract has its own route, its own tables and its own code path in Manager.
- The Detection Engine consumes neither as its primary input. It normalizes Officer schema 0.x.

**D2. Three Manager lines.**

- `main` is at `d3c1176`; Sokhi's prune-under-load work merged 2026-10-06. The Linux branch
  (`bceea18`) and the Windows branch (`dc5f6b8`) both fork from `75ebac6` and are 2 commits
  behind `main`.
- A trial merge of the Windows branch into the Linux branch has one trivial conflict (router
  registration in `app.py`) and passes 208 Manager tests (22 skipped).
- The Linux tables are created outside the migration chain (`linux_endpoint_store.py`), so
  schema management is split.
- Manager `main` and the Linux branch vendor response-engine `cc61fcc`, which has no command
  `schema_version`, and stamp every command `"1"`. Schema 2 exists only on the Windows lineage
  (response-engine `99add09`, Manager `dc5f6b8`). Against the Linux branch, a boot-bound command
  was delivered as schema 1 and the endpoint refused it. The live schema-2 run used a trial merge.

**D3. Detection Engine lines.**

- Engine `main` is `f089331` + Sokhi's `eee2dc2` ("make the outputs and rule metadata truthful",
  merged 2026-10-06).
- Sokhi's unmerged `phase-2/behavioral-rarity-baseline` adds five commits on top: causal
  incidents, stateful rules, the rarity baseline, schema 0.5, and documentation.
- The Windows snapshot `a535f1d` is `f089331` + one commit that adds `endpoint_adapter` (the
  canonical endpoint-record path). It overlaps `eee2dc2` in one file (`provenance/identity.py`)
  and Sokhi's phase-2 work in six.
- Manager vendors a different engine revision on each line: `main` vendors `eee2dc2`, the Linux
  branch `db4981a` and the Windows branch `a535f1d`.
- Separately, `feat/ml-telemetry-ingest` (Sokhi, unmerged) teaches Manager schema 0.5.

**D4. Four process identities.**

| Producer | Identity |
|---|---|
| Linux | First 32 hex characters of sha256(`host\|boot\|pid\|start_ticks`) |
| Windows (first id) | `proc_` + sha256 over host, pid and start time in milliseconds, with no boot |
| Windows (second id) | `proc_` + sha256 over the Sysmon process GUID |
| Detection Engine | Resolves `(host, pid, timestamp)` through per-PID intervals, because the agent ids are not consistent across event families |

**D5. Command target binding.** Windows uses boot-bound schema 2. Linux used schema 1 until `c84a6dc`. Schema 2 is documented as Windows-only.

**D6. The Console reads a detection file**, not Manager.

**D7. Storage.**

- One SQLite file holds control state, telemetry, the detection queue and command state.
- Detection Engine correlation state lives only in process memory.

**D8. Tests.**

- Cross-repository tests find sibling repositories by relative path.
- Live lab scripts are not under version control.
- No multi-host, chaos or performance runs exist.

## 2. Target architecture

```
                   ┌────────── attack / simulation (isolated lab network) ──────────┐
                   ▼                                                                ▼
        Windows endpoint (Officer)                                  Linux endpoint (sensord)
        ETW/Sysmon → journal/spool                                  eBPF/fanotify/audit → WAL
                   │  endpoint-record 2.0 (common envelope), HTTPS, at-least-once   │
                   └───────────────────────────────┬─────────────────────────────────┘
                                                   ▼
┌───────────────────────────────────────── Manager (one deployable) ────────────────────────────────────────┐
│ ingest API ─► strict validation ─► raw record store ─► normalize ─► canonical detection event (CDE)        │
│                 │ reject → per-line receipt (endpoint quarantines)            │                            │
│                 ▼                                                             ▼                            │
│          host / entity / health projections                 detection queue (claim/lease, per host)        │
│                                                                               │                            │
│                                    Detection Engine library (Sokhi) ◄─────────┘                            │
│                                    rules · stateful · provenance graph · incidents · scoring               │
│                                                         │ Detection / Incident + recommendation            │
│                                                         ▼                                                  │
│      Response Engine module: closed action set → exact target → tier (AUTO_SAFE | ANALYST_APPROVAL)        │
│                                                         │ authorized command (schema-2 targets)            │
│                                     command queue ◄─────┘                                                  │
│  read API: hosts, health, coverage, records, detections, incidents, commands, approvals, artifacts         │
└──────────────┬──────────────────────────────────────┬────────────────────────────────┬────────────────────┘
               │ PostgreSQL (relational + telemetry)   │ artifact store (fs → S3/MinIO) │
               ▼                                       ▼                                ▼
       Console (Manager read API + approval actions)                     endpoints POLL commands, verify,
                                                                         execute, send results and an
                                                                         audit record back through ingest
```

The design has four planes in one Manager deployable:

1. **Telemetry plane.** Endpoint durable log → ingest → raw store → projections and CDE. Delivery
   is at-least-once, and loss is explicit (ADR 0009).
2. **Detection plane.** CDE → Detection Engine → Detection/Incident (ADR 0006, 0012).
3. **Response plane.** Recommendation → Manager authorization → command → endpoint local
   authorization → execution → result and audit record (ADR 0013, 0014). The three gates are
   independent:
   - detection never executes;
   - Manager never trusts an endpoint result it cannot bind;
   - the endpoint never trusts a command it cannot verify.
4. **Read plane.** Manager read API over PostgreSQL. The Console is a client of it (ADR 0007).

Nothing becomes a separate network service until a measurement requires it (ADR 0018). There is
no Kafka, Redis or search cluster at this scale.

## 3. Ownership

| Concern | Owner | Notes |
|---|---|---|
| Collection, local durability, local response authorization, target verification, execution evidence | Each endpoint (Linux, Windows) | The implementations differ deliberately (§7). |
| Wire contracts: envelope, CDE, Detection/Incident, Command/Result, enrollment | `panopticon-contracts` | Changed only together with the producer and consumer updates, in the same change set. |
| Ingest, validation, raw store, projections, normalization to CDE, detection queue, persistence of detections and incidents, entity lookup API | Manager | |
| Rules, evaluator, stateful windows, provenance graph, incidents, scoring, baselines, recommendation | Detection Engine (Sokhi) | A library with a stable API, and also a standalone CLI for datasets and research. |
| Action vocabulary, approval tiers, translation of a recommendation into an exact target | Response Engine module in Manager | |
| Analyst identity, approval decisions, command lifecycle, audit | Manager | |
| Presentation | Console | Holds no business logic. Every change is a Manager API call. |
| Lab, scenarios, E2E harness, chaos and performance tooling | `panopticon-lab` (new) | |

Any team member may change any repository when an integration needs it; the owner reviews.

## 4. Storage (ADR 0005, 0015, 0019)

| Data | Store |
|---|---|
| Unacknowledged telemetry, rejected-record quarantine, command ledger | Endpoint-local files (Linux WAL and ledger; Windows journal/spool) |
| Agents, enrollment, credentials, commands, results, approvals, audit | PostgreSQL |
| Raw records, as received, in JSONB | PostgreSQL, partitioned by day. ClickHouse only once the ADR 0019 criteria are met. |
| Host, entity, inventory, health and coverage projections | PostgreSQL "current" tables |
| Detection queue | PostgreSQL table, claim/lease with `FOR UPDATE SKIP LOCKED` |
| Detections, incidents, evidence references | PostgreSQL |
| Detection Engine working state | Process memory, rebuilt on start by replaying the raw-store window. Snapshot only if replay is measured to be too slow. |
| Forensic artifacts | Content-addressed blobs (sha256): the filesystem in the laptop lab, the S3 API (MinIO) in the team lab. Metadata and custody in PostgreSQL. |
| Unit tests | SQLite remains acceptable during the migration, but only behind the same repository layer |

## 5. Labs (ADR 0010)

### Hypervisor decision

The decision follows from the actual constraints:

- **The laptop runs Windows 11 Home, so Hyper-V Manager is not available.** VBS is already on, so
  VirtualBox runs on the Windows Hypervisor Platform. This works — every Linux result so far was
  produced this way — at some CPU cost and without nested virtualization.
- **VirtualBox 7.2 + Vagrant stays the laptop hypervisor.** It is free and scriptable, it is
  already proven with real eBPF, fanotify and audit kernels, and it runs Windows guests.
- **VMware Workstation is the fallback** if Windows guests are too slow. It is free for personal
  use, but its licence terms have changed recently, and Vagrant support needs a paid-for utility.
- **Proxmox VE is used for any shared or dedicated lab machine.** It gives KVM with real kernels,
  virtio Windows guests, linked clones and snapshots, isolated bridges, and an API for Packer and
  Terraform, with no licence.
- **Docker is used only for server components** (PostgreSQL, Manager, Console, MinIO): WSL2 on
  the laptop, Docker Engine in the lab. **It is never used for endpoint testing.** A container
  shares the host kernel, so it cannot validate kernel collection, and a response action inside it
  would act on the wrong host.

### A. Minimum laptop lab (one developer)

| Layer | Allocation |
|---|---|
| Physical | The current laptop. With 16 GB it runs Linux VM + Manager, or Windows VM + Manager, but not both with headroom. **32 GB** is needed for the two-endpoint flow. 100 GB of free disk. |
| Host (Windows) | IDE, git, Windows agent build (MSVC/vcpkg), and Manager from source for fast iteration. |
| WSL2 Docker | `postgres:16`, plus the composed Manager + Console for integration runs. |
| VM `lin-dev` | Ubuntu 22.04 / 5.15, 3 GB, 4 vCPU. Builds and runs `sensord`. |
| VM `lin-k6` (on demand) | Ubuntu 24.04 / 6.8, 3 GB. Cross-kernel checks. |
| VM `win-ep` (on demand) | Windows 11 or Server 2022 evaluation, 4 GB. Runs Officer + Sysmon. Response runs in `enforce` only here, never on the host. |
| Network | VirtualBox NAT plus a host-only network (`192.168.56.0/24`), so endpoints reach a fixed Manager address. Time is synchronized to the host: a 27 s skew has already broken one live run. |

### B. Team lab (recommended)

| Layer | Allocation |
|---|---|
| Physical | One dedicated box: 8+ cores, **64 GB** (32 GB minimum), 1 TB NVMe. Developer laptops stay workstations. |
| Hypervisor | Proxmox VE. |
| Server VMs | `mgr` (Ubuntu 24.04, 8 GB): a compose of PostgreSQL, Manager, Console and MinIO, plus a chrony server. |
| Linux endpoint VMs | `lin-2204` (5.15), `lin-2404` (6.8), `rocky9` (5.14, SELinux enforcing), `deb12`. |
| Windows endpoint VMs | `win11`, `win2022`. |
| Support VMs | `attack` (Kali, isolated network only); `runner` (self-hosted CI runner + the `panopticon-lab` harness). |
| Networks | `mgmt`: NAT, with internet for builds. `lab`: isolated, holding the endpoints, `mgr` and `attack`, with no internet egress. |
| Sharing | Manager, Detection, Response, PostgreSQL and Console share `mgr`. Every endpoint is its own VM. The attack host is only on `lab`. |

### C. Flagship validation lab

Lab B, plus:

- a second Proxmox node for performance and soak runs;
- **ARM64 hardware** (a Raspberry Pi 5 or an ARM cloud instance), because x86 hypervisors cannot validate aarch64;
- a nightly distro/kernel matrix built from cloud images;
- an `obs` VM (Prometheus, Grafana, Loki);
- demo snapshots kept separate from development snapshots.

## 6. Development → test → demonstration pipeline

| Stage | Runs on | Evidence |
|---|---|---|
| Build | Workstation (Windows agent, Python); `lin-dev` (Linux sensor) | Compiler output |
| Unit | Same machines; CI (GitHub-hosted runners) on every push | Test reports |
| Component | A `lin-*` VM as root (sensor with real kernel hooks, fake Manager); Manager with a PostgreSQL service container in CI | Test reports |
| Contract | `panopticon-contracts` CI validates the fixtures. Producer CI validates real output against a pinned contracts revision. Consumer CI loads the same fixtures. | Validator output |
| Real endpoint | `lin-*` / `win-*` VMs (laptop or lab runner) | Records for scripted actions, compared with ground truth |
| Integration | `mgr` stack + endpoint VMs | Manager rows, receipts, quarantine counts |
| Detection, response, database and Console | `mgr` stack | Harness assertions through the Manager API |
| E2E attack scenario | Lab B (`attack` + endpoints + `mgr`), nightly and before every demonstration | Evidence bundle for each hop (ADR 0017) |
| Demonstration | Lab B demo snapshots, with tagged revisions from a release manifest | Three consecutive clean scenario runs |

## 7. Common semantics vs per-OS implementation

**Common.** Defined in contracts and enforced by both agents and by Manager:

- host, enrolled agent, installation;
- boot scope (`boot_` + 64 hex);
- stream (`installation`, `boot`, collector epoch, sequence);
- record id and digest-idempotent delivery;
- observed time and event time;
- provenance (provider, mechanism, confidence/resolution);
- process key (ADR 0004);
- loss and gap;
- health and coverage;
- command, result, response audit, evidence reference.

**Per OS:**

- collection mechanisms and their fallbacks;
- local durability format;
- OS-specific record bodies, as `data` by category: namespaces, LSM and netfilter on Linux; registry, services and ETW specifics on Windows;
- executor internals;
- how execution evidence is represented.

## 8. Demonstration

**Topology.** The Lab B `lab` network: `attack`, `win11`, `lin-2204`, `mgr`. The Console is
opened from a workstation on `mgmt` through `mgr`.

**Scenario** (scripted in `panopticon-lab/scenarios/two-host-intrusion`):

1. On Windows, an Office-like parent spawns encoded PowerShell, which downloads and starts a
   payload.
2. On Linux, a `curl | bash` stager runs a payload from a memfd, persists through a systemd user
   unit and connects out to `attack`.
3. The endpoints record the activity and Manager accepts it with nothing quarantined. Detections
   fire on both hosts, and the Detection Engine groups each host's chain into an incident.
4. Recommendations follow:
   - `COLLECT_PROCESS_INFO` is AUTO_SAFE and runs immediately;
   - `KILL_PROCESS` needs ANALYST_APPROVAL and uses a schema-2 boot-bound target.
5. The analyst approves in the Console. Each endpoint verifies boot, PID and start time, acts,
   and returns results and audit records. The harness independently confirms the processes are
   gone.
6. The Console shows:
   - both hosts' health and coverage;
   - the incident timelines with evidence links;
   - the approval;
   - the command lifecycle through to `SUCCEEDED`;
   - the stored results.

**Reproducibility.**

- Revisions are pinned in `panopticon-lab/releases/<tag>.yaml`.
- VMs are reverted to demo snapshots, and time is synchronized.
- The scenario runner asserts every hop with timeouts and exports an evidence bundle.
- The demonstration is ready when three consecutive runs pass from snapshot.

**Prerequisites not yet built:**

- Endpoint-record 2.0, or a Manager mapping of Linux families into the CDE. Today only
  `process.exec` reaches detection.
- Detection Engine lineage reconciliation.
- The Console on the Manager API, with approval actions.
- Linux memfd, persistence and network rules.
- The lab harness.

## 9. Test architecture (ADR 0010, 0017)

| Layer | Exists today | Missing |
|---|---|---|
| Unit | All repos | — |
| Component | Linux sensor (root, real kernel); Manager (SQLite) | Manager on PostgreSQL; Windows component suite in CI |
| Contract | Fixtures + validators; Linux fixtures taken from real records | A pinned contracts revision in every producer and consumer CI; CDE and Detection contracts |
| Integration | Linux endpoint ↔ real Manager (manual scripts) | A version-controlled harness; Windows ↔ Manager in the same harness |
| Real VM | Ubuntu 22.04 / 5.15 / x86_64 | 6.x, SELinux, other distros, aarch64; a Windows 11/Server matrix |
| Multi-host | — | Both endpoints on one Manager |
| Chaos | Unit level only (ledger/WAL corruption, hostile replies) | kill -9, power loss, Manager crash, network partition, full disk, clock skew and duplicate batches, as scripted lab runs |
| Performance | — | Sustained load, bursts, backlog after a Manager outage, resource budgets |
| E2E attack | — | A scenario runner (ADR 0017) |
| Demonstration | — | Demo snapshots + a release manifest |

Live scripts move out of personal scratch directories into `panopticon-lab`, under `lab/`,
`stacks/`, `harness/`, `scenarios/`, `chaos/`, `perf/` and `releases/`. Cross-repository tests
take sibling locations from environment variables (`PANOPTICON_CONTRACTS_DIR`, ...) instead of
relative paths.

## 10. Decisions that need the team

1. Adopt the common envelope (ADR 0002/0003). This changes both agents' wire format.
2. Reconcile the two Detection Engine lineages, and move the engine onto the CDE with exact
   process keys (ADR 0004, 0006). This is Sokhi's call, together with the Windows author.
3. Bring the Linux and Windows Manager branches onto `main` (D2), each vendoring the reconciled
   engine: decide who integrates, and in what order.
4. Move Manager to PostgreSQL (ADR 0005). This touches every Manager module.
5. Hardware: upgrade the laptop to 32 GB of RAM; get a lab server for Lab B.
6. Create the `panopticon-lab` repository in the organisation.
7. Require per-command signatures before `enforce` is used anywhere outside the lab (ADR 0013).
