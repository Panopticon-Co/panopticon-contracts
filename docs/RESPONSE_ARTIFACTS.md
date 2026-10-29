# Structured investigation artifact transfer

Version1 transports exact UTF-8 JSON bytes from existing approved collection
actions. Process/network snapshots, file metadata/hash and execution reports
are separate kinds. This does not expand COLLECT_FILE into raw file acquisition.
No arbitrary execution command or new response action is introduced.

The agent POSTs the schema/response-artifact-v1.schema.json envelope to
/api/v1/agents/{agent_id}/commands/{command_id}/artifacts over its authenticated
channel. Bytes are at most 1 MiB, strict Base64, bounded UTF-8 JSON object/array;
content_bytes and SHA-256 must agree with decoded exact bytes. The ID is stable
on retry, normally art_ followed by SHA-256 over length-prefixed command ID,
correlation ID, kind and content SHA-256. No user path becomes a server filename.

Manager requires an owned previously dispatched command, matching original and
current host, correlation and action/kind. Scope is independent of terminal
outcome: late artifacts may arrive after execution ended. Reusing an agent/ID
with different metadata/bytes is 409. Enforce per-artifact, per-command and global
quotas atomically. Never silently evict evidence to accept new work.

Success returns artifact_id, sha256 and retained=true. Agents must verify those
values before retiring durable local bytes. Transport errors, malformed receipts,
conflicts and storage refusals preserve the original for operator recovery/retry.
Persist artifacts before claiming successful durable collection completion.

Analyst downloads are authenticated, recorded and attachment-only with no-sniff
headers. Manifest previews are bounded; exact bytes remain separately downloadable.
Append-only custody events chain canonical event metadata and the previous event
hash. This detects internal inconsistency; it is not proof of uncompromised native
execution or externally anchored nonrepudiation. Command lifecycle remains driven
by command receipts; artifact arrival never synthesizes execution success.
