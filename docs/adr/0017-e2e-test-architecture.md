# ADR 0017: End-to-end test architecture

## Status

Proposed. Date: 2026-10-06.

## Context (current evidence)

End-to-end evidence today is manual:

- shell scripts run over `vagrant ssh` against a Manager started by hand;
- results are checked by reading SQLite and logs.

The scripts did find real defects:

- a 27 s clock skew;
- the Manager schema-version downgrade (ADR 0008);
- Manager fixtures in the wrong stream.

They are not repeatable by anyone else.

## Decision

1. **A scenario runner** lives in `panopticon-lab/harness`. A scenario is a YAML file that lists:
   - the topology it needs (which VMs, endpoint configurations);
   - actions on hosts, run over SSH or WinRM (benign simulations of attacker behaviour, Atomic Red
     Team tests where suitable);
   - **expected outcomes for each hop**, each with a timeout:

     | Hop | Expected |
     |---|---|
     | Records | Category and process key present in the raw store |
     | Delivery | No quarantine and no unexpected gaps |
     | Detection | Rule fired with the expected evidence |
     | Incident | Formed |
     | Recommendation | Present |
     | Approval | Performed by the harness as a test analyst |
     | Command | Delivered and result succeeded |
     | Ground truth | Checked independently on the host (the process is gone) |
     | Console | API shows the incident |
2. **The harness uses only public interfaces:** the Manager API, the endpoint hosts as a user
   would, and the Console API. It never reads Manager's database directly; a missing API is a gap
   to fix.
3. **Each run exports an evidence bundle:** the scenario, revisions, host facts, the per-hop
   timings and results, and the relevant records.
4. **Suites:**

   | Suite | When it runs | What it covers |
   |---|---|---|
   | `smoke` | Every merge, on Lab A or CI with one Linux VM | |
   | `nightly` | Nightly | All scenarios, both operating systems |
   | `chaos` | Weekly, and before a release | kill -9 of the agent and of Manager; Manager down for 10 minutes; network partition; full disk; clock skew; duplicate and reordered batches |
   | `perf` | | Sustained rate, burst, backlog drain after an outage; CPU, RSS, WAL size and Manager latency budgets |
   | `demo` | Before every demonstration | The demo scenario 3 times from snapshot |

## Alternatives considered

- **pytest with fixtures that drive VMs.** Workable, but scenarios as data are easier for the
  detection owner to add to.
- **Robot Framework.** It adds another language.

## Consequences

- Manager must expose the read API (ADR 0007) before the runner can assert detections without
  reading the database. This is a deliberate forcing function.

## Migration

1. Port `cmdtest.sh` and `cmdtest2.sh` into the first two scenarios (Linux response, boot
   binding).
2. Add the Linux process-exec detection scenario.
3. Add Windows once a Windows VM is in the lab.

## What remains provisional

- The scenario format details.
- The attack-simulation tool set.
