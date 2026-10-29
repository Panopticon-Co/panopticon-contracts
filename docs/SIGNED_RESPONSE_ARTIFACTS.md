# Signed investigation artifact manifests, version 2

This contract adds authenticity to the existing bounded JSON collection artifact.
It does not change the closed seven actions or expand COLLECT_FILE beyond file
metadata/hash. Raw file bytes, memory contents and arbitrary execution are absent.

The manifest is separate from transfer framing. It contains no content_base64.
It is immutable once signed and persisted with the exact collected bytes before
reporting successful collection. A transport may retry/resume those same bytes;
it must not recollect, resign with a new timestamp or replace evidence on retry.

## Signing bytes

Use ES256 (ECDSA P-256/SHA-256), raw 64-byte r||s, padded standard Base64. The
key ID is the first 16 lowercase hex characters of SHA-256 of the uncompressed
65-byte public point. Do not accept a public key supplied by an upload as trust.

The input starts with UTF-8 `panopticon-response-artifact-auth/2\n` then the
following fields in exactly this order, each as UTF-8
`name:<decimal UTF-8 byte length>:<value>\n`:

```text
schema_version artifact_id agent_id host_id command_id correlation_id kind
media_type content_bytes sha256 produced_at_unix algorithm key_id
```

Numeric values use unsigned decimal without leading zeroes (except zero itself).
Algorithm is ES256. Neither signature bytes nor transport chunks are included.
The whole-content SHA-256 and byte count bind all chunks to the signed manifest.
The producer timestamp is an endpoint claim, not a trusted time attestation.

Manager verifies the closed schema, signature against enrolled key history,
active endpoint and dispatched command/case binding before admitting a session.
Completion rechecks key status, binding, byte count and whole-content hash.
Failures are audited and never promoted to verified evidence. Incomplete or
mismatched content cannot become a normal analyst download.

## Enrollment and historical key identity

Initial enrollment keeps existing one-use nonce proof of possession. The verified
public key is retained as artifact signing key version 1 for that agent/host
enrollment. Private keys remain local: protected CNG storage on Windows, private
key files on Linux. Missing/corrupt keys refuse artifact production; never silently
replace a key belonging to an enrolled identity.

Rotation requires a versioned, domain-separated rotation request signed by both
the active old key and proposed new key, bound to agent, host, both key IDs,
one-use challenge, expiry and retry identity. An authorized operator explicitly
approves it before activation. An unknown key cannot self-enroll by uploading a
manifest. Key material and versions are never overwritten or deleted.

Retired keys remain usable for verifying already-retained artifacts. A transfer
session admitted before retirement may finish; a new session under a retired key
is refused. Operators should drain endpoint outboxes before rotation. Failed or
blocked outbox entries remain retained and visible rather than silently lost.

Compromised-key revocation immediately refuses new sessions and completion of
existing sessions under that key. Already-accepted evidence remains immutable,
but its queryable trust status becomes `compromised_key` and identifies the key,
revocation time and reason. Ordinary verified retrieval must refuse it pending
explicit privileged evidence review. Cryptographic signature validity remains
distinguishable from trust status. Endpoint timestamps cannot establish that a
signature predates compromise, so all artifacts under that key are flagged.

After reimage, revoke the old enrollment and use a new agent ID and key. A trusted
operator releases the old host binding before replacement enrollment. Do not reuse
a revoked agent ID or redirect its old commands to the new identity. Historical
artifacts/keys remain attached to the old enrollment and original cases. Enrollment
revocation alone prevents new uploads; compromise is a separate explicit flag.

## Console verification and custody

Evidence retrieval requires per-browser actor identity, artifact permission and
case/endpoint scope. A package includes the immutable manifest, enrolled public-key
version, current trust metadata and exact content. Console verifies against trusted
Manager-supplied enrollment history over its authenticated channel, never an
arbitrary upload-provided key. It verifies the signature and content hash before
offering evidence. Offline verification requires independently pinned key history.

Record requested, endpoint-reported produced, transferred, signature verified,
hash verified and actor access facts in the hardened audit path. Retain original
server/endpoint timestamps separately. An access event proves delivery to an actor,
not that a human read or understood the content. Revocation changes are also audited.
