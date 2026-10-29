# Scoped signed evidence retrieval, version 1

All routes require the individual analyst credential, `artifact:read`, and a live
grant for the original case/endpoint. Unsigned upload routes and unsigned legacy
content downloads return 410. Legacy originals remain retained and labelled;
they cannot be re-attested to create fictitious historical signing provenance.

GET `/api/v1/response-artifacts/{artifact_id}/context` returns the closed context
schema, signed v2 manifest, opaque canonical-manifest digest and a separately
authenticated enrolled key/context. Manager re-verifies stored content and the
original attestation before returning context. Compromise status is available
here so scoped analysts can see the flag; content retrieval is refused.

GET `.../chunks?offset=0&manifest_sha256=...` returns a closed download-chunk
envelope. Frames are 65,536 bytes except the remainder. Manager rechecks identity,
scope, key status, original signature and whole-content hash on every frame.
Only aligned offsets below the declared length are accepted. Exact rereads return
the same frame; each actual transfer is a distinct custody observation. No partial
upload is exposed. Chunk `complete` denotes byte delivery, never verification.

The browser retains partial frames only in bounded memory tied to its current
identity and selected case. A retry fetches fresh context before resuming; any
identity, case, manifest, key or trust mismatch discards the partial content. After
all frames arrive, the browser verifies every frame, full byte count, whole SHA-256
and ES256 signature using the separately retrieved case/enrollment context. It
does not trust a key supplied by an evidence package. It fetches fresh context and
rechecks authorization before exposing verified JSON or exporting the signed
bundle. Signed context and content remain independently verifiable after export;
current trust/revocation status requires a fresh authenticated Manager lookup.

POST `.../view` with the view-request schema acknowledges an analyst-initiated
verified view or signed-bundle download. Manager rechecks all access and integrity
requirements before recording `artifact_viewed`, original response/case, actor,
endpoint, time, manifest digest and intent. This is an analyst acknowledgement,
not cryptographic proof of what a browser displayed. Request IDs are credential-
scoped and immutable; exact retries create one receipt/event, conflicting reuse
is refused. The Console must withhold display/export if this audit write fails.
Custody remains available through the bounded paged `/custody` route. All these
events enter the same hardened response chain, queryable by response request,
actor, asset and time. No artifact content is written to these audit entries.
