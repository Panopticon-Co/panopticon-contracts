# Analyst response governance

`schema/analyst-enrollment.schema.json` and `analyst-response-request.schema.json`
govern analyst API bodies. Target context/identity checks remain mandatory in
Manager; schema acceptance alone never permits dispatch.

Roles: `viewer` reads; `responder` requests actions and updates incidents;
`approver` decides/cancels responses and updates incidents; `analyst` has both
request and decision permissions (the backward-compatible default). Only the
bootstrap-authorized enrollment endpoint assigns roles. Unknown roles grant no
mutation permissions. Role assignment does not create host/tenant scoping.

An optional separate-approver deployment policy refuses self-approval of manual
requests. Request identity is `(authenticated analyst, request_id)`: replaying the
same normalized body returns the original response, including after completion;
a changed body returns conflict. This is not a new endpoint command identity.

Decision audit records staging, rejection, expiry, authorization and queued
cancellation atomically with state changes. Existing history is not invented on
upgrade. Manager's database rejects audit-row update/delete. This is local
application immutability, not external tamper-proof storage against a database
administrator. Command execution audit/receipts remain separate facts.
