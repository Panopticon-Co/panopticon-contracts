# ADR 0010: Lab and test architecture

## Status

Proposed. Hardware and the new repository need team approval. Date: 2026-10-06.

## Context (current evidence)

- **Development machine.** One Windows 11 Home laptop: i7-13700HX (24 threads), 16 GB, 195 GB
  free disk.
  - VBS (virtualization-based security) is running, so the Windows hypervisor owns VT-x.
  - Hyper-V Manager is not available on Home.
  - WSL2 Docker Desktop is installed and stopped.
- **Virtualization in use.** VirtualBox 7.2.14 with Vagrant 2.4.9, running on the Windows
  Hypervisor Platform. One `generic/ubuntu2204` VM (6 vCPU, 4 GB, NAT).
- **What this setup has produced.** All Linux kernel-level validation so far: eBPF, fanotify,
  audit netlink, pidfd response, WAL crash recovery, and the live command channel.
- **What has gone wrong.**
  - A 27 s VM clock skew made every command `not_yet_valid` in the first live run.
  - Integration scripts live in a personal scratch directory, with tokens inline.
  - Manager cross-repository tests locate `panopticon-agent` and `panopticon-contracts` by
    relative sibling path.
  - No Windows VM, multi-host, chaos or performance run has been done.

## Decision

1. **Hypervisors.**

   | Where | Hypervisor | Why |
   |---|---|---|
   | Laptops | VirtualBox + Vagrant | Already proven; free; scripted |
   | Laptops, fallback | VMware Workstation | Only if Windows guests prove too slow under VBS |
   | Shared lab machine | Proxmox VE | KVM, snapshots and linked clones, isolated bridges, API for automation, no licence |

   Hyper-V is not used: it is unavailable on the laptop edition, and it would add a second
   toolchain.
2. **Containers** (Docker or Podman) are for server components only: PostgreSQL, Manager,
   Console, MinIO. **Endpoint tests never run in containers.** A container shares the host kernel,
   so it cannot validate kernel collection, and response actions in it would act on the wrong
   host.
3. **Three lab tiers**, as specified in the system design §5:
   - A: laptop, 16 GB minimum, 32 GB for two endpoints;
   - B: team Proxmox box, 64 GB recommended;
   - C: flagship validation lab, Lab B plus ARM64 hardware and a performance node.
4. **Every endpoint VM synchronizes time** (chrony, against the Manager VM or the host). The lab
   harness checks skew before it runs anything.
5. **A new repository, `panopticon-lab`**, holds:
   - Vagrantfiles and Packer templates for the VMs;
   - compose files for the server stack;
   - the harness (Python; it talks only to public APIs and to SSH or WinRM on the VMs);
   - scenarios, chaos and performance scripts;
   - release manifests.

   It holds no secrets: tokens are generated per lab run, and test certificates are generated at
   setup.
6. **Cross-repository tests take their paths from environment variables**
   (`PANOPTICON_CONTRACTS_DIR`, `PANOPTICON_AGENT_DIR`, ...) and skip with a clear message when a
   variable is unset. CI sets them explicitly.

## Alternatives considered

- **`panopticon-integration` as the repository name.** It is equivalent; "lab" is chosen because
  the repository also provisions infrastructure.
- **Lab scripts inside each product repository.** Integration needs all of them at pinned
  revisions, so the scripts belong outside every product repository.
- **Cloud-only lab.** It costs money, is slow to iterate, and Windows kernel-level testing still
  needs dedicated VMs. It is used only for the C-tier distro and architecture matrix.

## Consequences

- Moving existing scratch scripts (`vm_enroll.sh`, `cmdtest.sh`, `cmdtest2.sh`, the e2e stack
  launcher) is the first commit to `panopticon-lab`.
- Hardware requests: laptop RAM to 32 GB, and one lab server.

## Migration

1. Create `panopticon-lab` (needs organisation approval).
2. Import the scripts, parametrized, with tokens removed.
3. Add the compose stack and Vagrantfiles.
4. Wire the harness into a self-hosted runner once Lab B exists.

## What remains provisional

- The CI runner topology.
- Whether Packer images are built in CI or by hand.
- The ARM64 hardware choice.
