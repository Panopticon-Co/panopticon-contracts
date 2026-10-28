# Negotiated command authority

`schema/signed-command.schema.json` defines the separately negotiated ES256
extension over the seven-action version 1 / boot-bound process version 2 envelopes.
It requires a closed `authorization` object: `algorithm="ES256"`, a 16-character
lowercase hexadecimal key ID, and a base64 IEEE P1363 64-byte P-256 signature.
Unsigned schemas remain unchanged for existing strict decoders.

`fixtures/commands/signing-vectors.json` is imported from the organization's
Manager `feat/linux-command-signing` branch. Its provenance names the Linux
sensor's reference signer. These retained vectors are static unit-test material,
not a new native/E2E qualification claim.

Signing input is UTF-8 `panopticon-command-auth/1\n`, followed by ordered fields
`schema_version`, `command_id`, `correlation_id`, `agent_id`, `host_id`, `action`,
`created_at`, `expires_at`, `pid`, `start_time_ticks`, `boot_id`, `path`.
Each field is `name:<UTF-8 byte length>:<value>\n`. Times use whole epoch seconds;
non-applicable numbers are 0, non-applicable strings are empty. Aware timestamps,
positive lifetime no longer than 900 seconds, and exact target semantics are
validated in code. Signing describes parsed values, not JSON whitespace/order.
The key ID is the first 16 hex characters of SHA-256 of the uncompressed 65-byte
P-256 public point. Key files contain private authority and must remain private.

Manager signs once at authorization and retains the envelope. Only authenticated
polls requesting `command_auth=ES256` receive this extension. Existing decoders
receive their original unsigned shape. The Linux sensor independently requires
and verifies the signature using its pinned keys; transport negotiation does not
change endpoint policy. An ES256 poll must never receive an unsigned command.
No signing occurs at delivery to conceal a changed stored command. Pinning and
key distribution remain explicit deployment operations.
