# ADR 0013: Response authorization — three independent gates

## Status

Proposed. Per-command signatures need team approval before any `enforce` use outside the lab.
Date: 2026-10-06.

## Context (current evidence)

- **Detection** recommends only (the engine's principle; Manager ADR 004-response-engine).
- **Manager's Response Engine module** maps a recommendation to a tier:
  - `AUTO_SAFE` is enqueued immediately;
  - `ANALYST_APPROVAL` waits for a human.

  The command enqueue API is protected by a shared token header (`X-Panopticon-Command-Token`).
  There is no analyst identity: approvals are not attributed to a person.
- **Endpoints** each authorize locally, for example Linux ADR 024:
  - endpoint and host binding, boot binding (ADR 0008), expiry, skew, a lifetime cap, a mode
    (off, dry_run, enforce), an action allow-list, a rate limit, and a single-use durable ledger;
  - Windows has equivalent gates (protected processes, allowed roots for file actions).
- **Transport** is TLS plus the enrolled agent identity (ECDSA P-256 enrollment contract). There
  is no per-command signature, so anyone who can write to Manager's command table, or who
  compromises Manager, can issue any action the endpoint permits.

## Decision

1. **Gate 1: Detection.** It never produces commands, only recommendations (ADR 0012).
2. **Gate 2: Manager.**
   - Every command is created by the Response Engine module from a recommendation or from an
     analyst request.
   - Every command carries `requested_by`: an analyst, or `policy:auto_safe:<rule>`.
   - An `ANALYST_APPROVAL` command requires an authenticated analyst approval, recorded with
     identity and time.
   - The shared command token is retired for analyst flows. It remains only for lab automation,
     scoped to the lab.
3. **Gate 3: Endpoint.** Each endpoint keeps its local policy (mode, allow-list, rate,
   protection lists, boot and identity binding, ledger). Endpoint policy always wins; Manager
   cannot override it.
4. **Per-command signature.**
   - Manager signs the canonical command bytes with a dedicated response-signing key (ECDSA
     P-256, raw r‖s, as in the enrollment contract).
   - Endpoints pin the public key at enrollment and refuse unsigned commands when
     `response_mode=enforce`.
   - The signing key is separate from the TLS key, and can live in an HSM or KMS later.
5. Destructive actions (`KILL_PROCESS`, `QUARANTINE_FILE`, `ISOLATE_HOST`) are never `AUTO_SAFE`
   by default. Collection actions may be.

## Alternatives considered

- **TLS only.** This is the current state. It is acceptable in the lab, but not for `enforce` on
  real hosts.
- **Endpoint-side approval prompts.** They do not suit servers.

## Consequences

- Manager gains analyst authentication (ADR 0007), approval records and a signing service.
- Both agents gain signature verification. The Linux side already has the sha256 and the strict
  canonical parser it needs; ECDSA verification would come from the system OpenSSL.

## Migration

1. Analyst identity and approvals in Manager.
2. Signing in Manager.
3. Verification in the agents, behind `response_require_signature`.
4. Required in lab and demo configurations.

## What remains provisional

- Key rotation.
- Multi-party approval for isolation.
- Whether `COLLECT_FILE` content upload (ADR 0015) counts as destructive for privacy reasons.
