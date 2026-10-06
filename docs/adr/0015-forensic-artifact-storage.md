# ADR 0015: Forensic artifact storage

## Status

Proposed. Date: 2026-10-06.

## Context (current evidence)

- No endpoint uploads file content today. Windows `COLLECT_FILE` sends path, size and sha256 only,
  and Linux does not implement it.
- Process info and network collection results are small JSON documents stored with the command
  result.
- Investigation needs actual samples: binaries, scripts, memory regions.

## Decision

1. **Artifacts are content-addressed by sha256** and immutable.
2. **Storage is behind one interface.**

   | Lab | Backend |
   |---|---|
   | Laptop | Filesystem directory |
   | Team and flagship | S3 API, with MinIO in the lab |

   Metadata goes in PostgreSQL (`artifact` schema): hash, size, type, source host, command id,
   collection time, and a chain of custody listing who requested, approved, downloaded and
   deleted it.
3. **Upload** is a separate authenticated endpoint (`PUT /api/v1/agents/{id}/artifacts/{sha256}`)
   that the endpoint calls after a collection command.
   - It is bounded in size and resumable.
   - Manager verifies the hash on receipt.
   - The command result refers to the artifact by hash.
4. **Content upload is a separate action variant** (`COLLECT_FILE` with `include_content=true`).
   It requires `ANALYST_APPROVAL`; hash-only collection does not.
5. **Downloads** through the Console go through Manager and are audited. Malware samples are
   served as encrypted archives so they cannot be executed by accident.

## Alternatives considered

- **Blobs in PostgreSQL.** This is fine for kilobytes, but bloats backups and the WAL at
  megabyte scale.
- **Uploading directly to S3 with pre-signed URLs.** Fewer hops, but endpoints would need access
  to the object store's network, and custody tracking gets harder. This can be reconsidered at
  scale.

## Consequences

- MinIO joins the team-lab compose stack.

## Migration

None needed: nothing exists today. This is built together with Linux `COLLECT_FILE`.

## What remains provisional

- Retention.
- Encryption at rest beyond the storage layer.
- Memory acquisition.
