# Artifact access policy 1 / analyst role policy 2

Artifact retrieval requires both `artifact:read` and an explicit grant for the
authenticated analyst credential, the originating alert (case), and the endpoint
host. No wildcard, inherited grant, critical-asset exemption or role-only access
exists. Every request, including custody, manifest/key context and resumed chunks,
must recheck the live credential, role and grant on Manager. A Console session is
only a browser identity transport; it cannot authorize retrieval itself.

Migration 30 installs an empty grant table: existing analysts receive no access.
Responder, approver and analyst roles gain `artifact:read` eligibility, not a grant.
The dedicated `artifact_admin` role manages grants but cannot request or approve
response actions. Its enrollment requires the separate operator-held
`PANOPTICON_ARTIFACT_ADMIN_ENROLLMENT_TOKEN`; ordinary enrollment cannot create or
replace that identity. Neither secret belongs in the browser. Changing/reissuing
an analyst credential invalidates its old grants; the new credential needs an
explicit new grant. Revocation takes effect on the next retrieval request.

Grant/revoke requests use the closed versioned schemas in this directory. Retry
identities belong to the authenticated administrator and operation; the same
request and payload returns the original result without new state or audit.
Conflicting reuse fails closed. Re-granting after revocation creates a new history
record. Immutable grant identity, actor, reason, policy version and revoke history
are retained. All transitions use the hardened response audit writer and can be
queried by operation request ID, actor, asset and time.

Case and incident exports must omit artifact metadata and custody outside scope.
Grant administration does not implicitly permit content access: administrators
also need a case/host grant. Compromise flags remain visible to scoped analysts;
normal content retrieval refuses compromised signatures and preserves evidence.
