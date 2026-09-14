# Security Policy

`panopticon-contracts` is the wire-contract backbone for Panopticon&Co's
detection-to-response pipeline. It ships no runtime service of its own, but a
flaw here — a schema gap, a missing invariant, an incorrect fixture, or a
weakened check in `scripts/validate_fixtures.py` — can silently affect every
repository that implements or is checked against this contract:
`panopticon-response-engine`, `panopticon-manager`, `panopticon-linux-agent`,
`panopticon-agent`, and (upstream of the contract) `panopticon-detection-engine`.
Please scope your report accordingly: note which of those repos you believe are
affected, not just this one.

## Reporting a vulnerability

**Do not open a public GitHub issue for a security report.** Instead, report it
privately using GitHub Security Advisories:

<https://github.com/Panopticon-Co/panopticon-contracts/security/advisories/new>

Include, where possible:

- The specific schema, fixture, or invariant affected (e.g. a gap in
  `schema/command.schema.json`, a missing check in `docs/SECURITY.md`, or a
  weakened assertion in `scripts/validate_fixtures.py`).
- Which downstream repositories you believe are exposed as a result, and how.
- Steps to reproduce or a minimal example fixture/payload demonstrating the
  issue.
- Any suggested fix, if you have one.

## Response expectations

This is a capstone/research security project maintained on a best-effort basis.
There is no formal SLA. We aim to acknowledge reports promptly and will keep the
reporter informed as the issue is triaged and, if confirmed, fixed and
coordinated across affected downstream repositories.

## Scope

In scope: the JSON Schemas, fixtures, documented security invariants
(`docs/SECURITY.md`), and validation tooling (`scripts/validate_fixtures.py`) in
this repository, including gaps between what is documented and what each
implementer repository actually enforces.

Out of scope: vulnerabilities purely within a downstream implementer's own code
that do not stem from this contract (e.g. a memory-safety bug in
`panopticon-agent` unrelated to command parsing) — please report those in the
relevant repository instead. If you are unsure which repository a finding
belongs to, report it here and we will help route it.
