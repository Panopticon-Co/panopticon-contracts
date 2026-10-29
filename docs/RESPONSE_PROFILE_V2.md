# Response runtime profile 2

Version 2 adds the mandatory `artifact_protocol` field to the existing closed
runtime profile. `signed-json-v2-resume-v1` means this installed agent implements
the signed manifest v2, protected durable outbox and resumable-transfer protocol.
`null` explicitly means that capability is unavailable. It reports implementation
support, not proof that a collection succeeded or that an enrollment key is healthy.
Manager also checks active enrollment/key eligibility before automated collection.

The reported `allowed_actions` and response mode continue to describe loaded
endpoint policy. Artifact capability never makes an action allowed. Unknown boot
identity remains null. Windows continues to truthfully report
`require_signature:false` for its existing authenticated TLS command channel;
the artifact signature is a separate ES256 capability. Linux's existing command
signature requirements remain unchanged.

Manager accepts closed version-1 reports for existing manual response behavior.
Version 1 cannot claim the new field; it supplies no artifact-delivery capability
to auto-triage. A newer version-1 poll replaces a previous version-2 observation,
so a downgraded or reimaged endpoint cannot inherit stale artifact capability.
Version 2 without the field, an unknown protocol, or a malformed type is refused.

Native producer fixtures are emitted by both agents and validated in CI using
`scripts/validate_response_profile.py`. This also enforces closed versions,
unique/supported action sets, policy-subset consistency, duplicate JSON rejection
and the 4096-byte Base64 header budget. Existing action and isolation behavior is
unchanged by this report.
