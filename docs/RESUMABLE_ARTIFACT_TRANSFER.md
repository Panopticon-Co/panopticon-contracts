# Resumable signed JSON investigation uploads, version 1

This framing carries the unchanged v2 signed artifact manifest and exact content.
It adds no action, shell, script or raw file acquisition. Maximum content remains
1 MiB. The endpoint durably retains the original signature, timestamp and bytes;
neither a retry nor reconnect may recollect or resign the artifact.

All routes require the owning enrolled agent's bearer credential over verified TLS.
Agent/host/command/correlation/kind and key status are rechecked transactionally on
admission, each chunk, and completion. Late evidence for a previously dispatched
terminal command is allowed without changing command lifecycle state.

1. POST `/api/v1/agents/{agent}/commands/{command}/artifact-transfers` with the
   closed `artifact-transfer-request-v1.schema.json` body. Repeating the same
   signed manifest resumes the existing received offset. A changed manifest for
   the same artifact ID is a conflict. Admission authenticates the signature,
   reserves the declared content budget and records server admission time.
2. PUT the next raw content chunk to
   `.../artifact-transfers/{artifact_id}/chunks/{offset}`, Content-Type
   `application/octet-stream`, header `X-Panopticon-Chunk-SHA256` containing its
   lowercase SHA-256. Chunks are 65,536 bytes, except the final remainder.
   Only the next offset is admitted. An identical duplicate is idempotent;
   changed bytes at an existing offset and out-of-order chunks are refused.
3. POST `.../artifact-transfers/{artifact_id}/complete` using the closed completion
   body and manifest digest returned by admission. Manager assembles at most 1 MiB,
   verifies exact byte count, whole-content hash, bounded JSON and signature/key
   eligibility, then retains evidence/attestation/custody in one transaction.
   Only the exact `{artifact_id, sha256, retained:true}` final receipt permits
   endpoint outbox retirement. Progress acknowledgements never do.

`artifact-transfer-progress-v1.schema.json` describes admission/chunk responses.
Offsets, hashes and artifact identity must match the endpoint's retained original.
The manifest digest is SHA-256 of compact sorted-key UTF-8 JSON, ensure_ascii=false,
of the entire signed manifest including authorization. It is a server-issued
session binding, not a second signature representation. Endpoint clients retain
and echo it; the endpoint signature uses the separate length-prefixed v2 format.

Incomplete sessions expire 24 hours after server admission. Bounded cleanup
removes only unverified partial chunks, retains immutable manifest identity and
audits byte counts/chunk hashes. Verified artifacts are never evicted by this
cleanup. The endpoint still owns the durable original and may restart at offset
zero under an active key. Retired keys may finish sessions admitted before
retirement; they cannot reopen expired sessions. Compromised keys and revoked
enrollments cannot upload or complete any session. Historical evidence is retained
and compromise status stays queryable.

Admission has limits of four open sessions per agent and 128 globally, eight
artifacts/4 MiB per command, 100,000 historical transfer identities, and the
configured shared artifact-storage budget. Declared bytes reserve capacity,
including across Manager restarts, before accepting partial data. One-shot uploads
also respect reservations. Quota refusal preserves existing verified evidence.
Audit facts use the hardened response chain and are queryable by response request,
actor, endpoint and time. No partial chunk is downloadable as verified evidence.
