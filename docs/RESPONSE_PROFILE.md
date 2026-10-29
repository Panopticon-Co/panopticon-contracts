# Current response runtime profile

Agents send a standard padded Base64 of compact UTF-8 JSON in the
`X-Panopticon-Response-Profile` header on every
command poll. The body follows `schema/response-profile-v1.schema.json`, is at
most 4096 bytes and contains no credentials, local file paths or command text.
`allowed_actions` must be a subset of `implemented_actions` (runtime invariant).
It describes actual loaded configuration, not advertised product capability.

Manager binds the snapshot to the authenticated agent and current enrolled host,
and records receive time atomically with the poll. A later poll without a profile
invalidates prior profile freshness. Reports older than 300 seconds are stale.
This channel bypasses queued telemetry and its event clocks. It proves an
endpoint-reported runtime state at a recent interaction, not successful execution.
Current native checks remain authoritative and must run for every command.

Fresh reports may block unsupported/disallowed actions, off mode, mismatched
process boot and changing actions in dry-run mode at authorization and delivery.
Read-only collection remains usable in dry-run mode. Missing or stale reports
remain explicit unknowns for backward compatibility, never affirmative support.
A required signature cannot be bypassed by dropping signature negotiation.
Reports cannot weaken existing signing requirements or approval checks.
