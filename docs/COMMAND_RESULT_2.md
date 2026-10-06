# Command result 2

`schema/command-result-v2.schema.json` specifies a bounded result with mandatory
schema_version `2` and correlation_id. Outcomes are succeeded, failed, rejected
and indeterminate. Indeterminate preserves uncertainty when execution may have
occurred but completion was not observed. Result IDs must be immutable for a
particular outcome; native Windows uses bounded SHA-256-derived IDs.

Windows process termination now supplies typed execution state, stage, initiation,
observed completion and optional native error to its receipt mapper. No diagnostic
keyword determines outcome. Optional `execution` now retains those facts as a closed
object with representation `windows_process_termination_v1`, named stage, strict
Boolean `action_initiated`/`completion_observed`, and required `native_error` as
uint32 or explicit null. Completion stage requires initiated action; observed
completion requires succeeded; initiated unobserved completion requires indeterminate;
uninitiated action permits failed/rejected only. Native error permits failed or
indeterminate only. Manager binds this representation to queued KILL_PROCESS commands.
Unknown fields/coerced facts and contradictory outcomes refuse validation. The
published JSON Schema and Python contract enforce the same semantic invariants;
Python also refuses float/coerced integers. Native serialization validates before
emitting the object. Interrupted recovery without conclusive action facts omits it.
The facts are endpoint-authored claims, not independent proof of OS execution.

Evidence is optional for existing version-2 results and forbidden for version 1.
Explicit `execution:null` is invalid. Absent evidence stays absent in serialization
and Manager canonicalization, preserving old immutable receipt digests. Adding or
changing evidence under a previously retained result ID returns 409. Mixed-version
capability negotiation, typed other-action APIs, full target/evidence provenance
and Console consumption remain open. Golden execution fixtures cover observed
success, timeout, wait error, open error, target refusal and contradictory input.

The authenticated result endpoint returns exactly `{result_id, accepted, retained}`.
Version-2 disposition requires matching result ID and Boolean accepted/retained
both true. Manager retains the entire canonicalized result with agent, command
and SHA-256 before commit/acknowledgment. Same-ID payload/identity changes return
409. Late results are evidence and remain retainable after expiry; they never
rewrite expiry or an earlier terminal command state. Legacy result behavior is
unchanged. Duplicate receipts acknowledge the same immutable retained evidence.

Windows now implements a committed encrypted result outbox and command inbox with
execution intent and conservative interrupted recovery. Coordinated durable polling
redelivers until acceptance, terminal result or expiry. This is not yet a complete
leased command protocol. Native HTTPS transport and OS-action crash qualification,
interrupted operation reconciliation, cancellation,
lease fencing, signing, corrupt-record handling, Console and operational tests
must be qualified separately. See the Windows endpoint's COMMAND_INBOX.md and RESULT_OUTBOX.md for
the implemented durability boundary and explicit crash windows.
