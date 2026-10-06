# ADR 0008: Command target binding — schema 2 for every endpoint

## Status

Accepted for the Linux endpoint (implemented and live-verified). Proposed as the platform rule.
Date: 2026-10-06.

## Context (current evidence)

- Command schema 1 names a process as `{pid, start_time_ticks}`. That is exact within one boot,
  but a reboot resets ticks, so a stale command could in principle match a new process with the
  same PID and the same small tick value.
- Windows already uses schema 2 (`WINDOWS_PROCESS_COMMAND_2`): `{pid, start_time_ticks (canonical
  uint64 decimal string), boot_id ("boot_" + 64 hex)}`. It is documented as Windows-only.
- **Linux `c84a6dc`** (`panopticon-linux-agent`) accepts schema 2:
  - The boot scope is `"boot_" + sha256_hex(kernel boot_id text)`.
  - The parse is strict: canonical uint64 ticks, a lowercase 69-character scope, an exact key set.
    File and targetless actions are refused under schema 2.
  - The decision order is `wrong_endpoint` → `boot_unavailable` → `boot_mismatch` →
    `boot_binding_required` → the existing checks.
  - `response_require_boot_binding=true` refuses schema-1 process targets.
- **Live run, 2026-10-06** (Ubuntu 22.04 / 5.15, real Manager):

  | Command | Outcome |
  |---|---|
  | Schema 2, another boot | `REJECTED` / `boot_mismatch` |
  | Schema 2 collect | `SUCCEEDED` |
  | Schema 2 kill | `SUCCEEDED`; the process is gone |
  | Unbound schema-1 kill, binding required | `REJECTED` / `boot_binding_required` |

  All four `response.action` audit records were accepted.
- **Manager defect found by the same run.** The Linux Manager branch's `authorize_and_enqueue`
  overwrites `schema_version` with `"1"` (`payload.update({"schema_version": "1", ...})`). Against
  that branch, a schema-2 command was delivered as schema 1 with a boot field and refused as
  invalid. The Windows branch preserves the version, so the run used a trial merge.

## Decision

1. **Process actions on every endpoint use schema 2.** The target is the exact process key from
   ADR 0004.
2. **Each endpoint derives its own boot scope locally** and refuses a mismatch. The Manager takes
   the scope from that host's records. It never computes it from wall time or uptime.
3. Endpoints keep accepting schema 1 for process actions only while
   `response_require_boot_binding=false`. Lab and demo configurations set it to `true`.
4. **Manager must carry the command's schema version end to end.** A Manager that rewrites the
   version is non-conformant. A contract test enqueues a schema-2 command and asserts that the
   delivered JSON is byte-for-byte schema 2.
5. Non-process actions keep schema 1 until each one defines an exact target of its own (for
   example, a file by device + inode + content digest).

## Alternatives considered

- **PID + start time without a boot.** Not exact across reboots.
- **The raw kernel UUID as the boot field.** Linux-specific, and it would make Windows and Linux
  scopes different in form. Hashing gives one shape.
- **Manager-side verification only.** The endpoint is the only party that can see the live
  process, so verification has to happen there.

## Consequences

- Linux ADR 024's known gap ("Schema 1 has no boot_id") is closed for process actions.
- Contracts' `WINDOWS_PROCESS_COMMAND_2` becomes `PROCESS_COMMAND_2`, with a Linux boot-scope
  section.

## Migration

1. Fix the Linux Manager branch to preserve `schema_version`, or integrate it with the Windows
   branch, which already does.
2. Manager's Response Engine builds schema-2 targets from the CDE process key (ADR 0004).
3. Turn on `response_require_boot_binding` in lab and demo configurations.

## What remains provisional

- Schema 3 for file and network targets.
- Per-command signatures (ADR 0013).
