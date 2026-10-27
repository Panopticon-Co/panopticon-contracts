# Versioning policy

## Current revisions (Wave 6, 2026-10-27)

The current Windows result revision is **`"2"`**, published through
`schema/command_result.schema.json` and `schema/command-result-v2.schema.json`.
It adds `indeterminate`, required correlation and optional typed execution
evidence. The original schema is archived as `command-result-v1.schema.json`.
Result fixtures are versioned under `fixtures/v1/results` and `fixtures/v2/results`;
older paths remain inputs for existing consumer tests.

Windows process commands use revision `"2"` for boot-bound targets; the shared
seven-action command baseline and Linux result producer remain revision `"1"`.
Canonical records independently use `"1.0"` over endpoint protocol `"2"`.
The existing Manager and Response Engine explicitly decode both result revisions.
This records the compatibility exception to the original single-revision policy
below; there is still no negotiation. Deploy Windows agent, Manager and Response
Engine v2 support together. See [WAVE6.md](WAVE6.md) for exact fields and boundaries.

The sections below record the original revision-1 policy and explain why the
Windows changes require a breaking revision.

## Schema version format

`schema_version` on the wire `Command` envelope is a plain string, currently always
`"1"` (see `manager/routers/commands.py`). This repository treats it as an integer
counter, not semver: `"1"`, `"2"`, ... A change big enough to need a new version is
a change that an agent built against the old version could not safely ignore.

## Additive (does NOT require a version bump)

- A new golden fixture that exercises existing contract behavior more thoroughly.
- A new document clarifying existing behavior.
- A new optional field would only qualify if every consuming decoder tolerates
  unknown top-level keys. **They currently do not**: both native agents'
  `parse_command_json` reject any JSON object with a key outside their fixed
  known-key set, and `response_engine.contract.Command`/`CommandResult` are
  `extra="forbid"`. Until that changes, treat "additive" as aspirational --
  in this codebase today, any new field is a breaking change in practice and must
  bump `schema_version` and land in every consumer in the same change.

## Breaking (REQUIRES a version bump)

- Adding, removing, or renaming a field on `Command` or `CommandResult`.
- Changing a field's type or valid range.
- Adding an eighth action, removing one of the seven, or changing an action's
  target shape.
- Changing the `outcome` vocabulary on `CommandResult`.
- Changing a lifecycle transition rule.
- Changing the semantics of `start_time_ticks` (e.g. making it interpretable by a
  consumer other than the originating host's own agent).

A breaking change ships as: a new `schema_version` value, updated
`schema/*.schema.json`, new fixtures under `fixtures/` demonstrating the new shape,
an updated `docs/CONTRACT.md`, and coordinated updates to every consuming repo
(`panopticon-response-engine`, `panopticon-manager`, `panopticon-linux-agent`,
`panopticon-agent`) landed together -- not a rolling migration, since Panopticon
currently has no version-negotiation mechanism (Manager does not send agents a
capability list, and agents do not advertise a supported version). This is a
deliberate simplicity choice: the closed one-deployable-backend architecture means
Manager and its agents are versioned and deployed together in practice during this
project's phase, so there is no need to build distributed version negotiation, a
schema registry, or backward-compatible dual-decode paths. If Panopticon ever needs
independently-upgradable agents in the field, that need justifies revisiting this
policy with its own ADR -- do not build it preemptively.

## Fixture versioning

Fixtures live under `fixtures/` with no per-version subdirectory today, because
there is only one schema version. When `schema_version` is bumped, fixtures move to
`fixtures/v1/` and `fixtures/v2/` (or similar) at that time, not before. Fixture
timestamps and IDs are fixed, synthetic values (`cmd-0001`, `2026-01-01T...`) chosen
for readability and reproducibility, not because they must match live production
data -- `fixtures/README.md` documents exactly which fields are intentionally
variable in a live system versus fixed for comparison purposes.

## Deprecation

There is no deprecation window today: this is a two-endpoint, one-backend capstone
system without independently-versioned agents in the field, so a breaking change is
rolled out atomically. A future multi-tenant or field-deployed-agent phase would need
a real deprecation policy (e.g. Manager accepting both `schema_version: "1"` and
`"2"` for a bounded window) -- explicitly out of scope until that phase is justified.

## Agent/Manager compatibility expectations

An agent and the Manager it talks to must run the same `schema_version` at all
times. There is no compatibility shim, no dual-decode path, and no capability
negotiation handshake. This is enforced today only by operational discipline
(deploy agent and Manager builds together), not by code -- a future phase could add
an explicit version-mismatch rejection (Manager refusing to enroll/dispatch to an
agent reporting an unrecognized `schema_version`), which would be a good, small,
additive hardening step once agents actually report a version during enrollment.

## Endpoint records

Endpoint-record 1.0 evolution (family revisions, optional-for-old/required-for-current fields) is defined in [ENDPOINT_TELEMETRY_CATALOG.md](ENDPOINT_TELEMETRY_CATALOG.md#12-evolution-rules).
