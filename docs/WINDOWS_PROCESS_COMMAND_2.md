# Windows process command 2

`schema/windows-process-command-v2.schema.json` describes the schema-2 wire
envelope for `KILL_PROCESS` and `COLLECT_PROCESS_INFO`. It preserves the existing
closed action vocabulary. Other actions still use schema 1.

The exact target is `{pid, start_time_ticks, boot_id}`. PID is a positive uint32.
Creation ticks are canonical positive uint64 decimal **strings**, without signs,
leading zeros, spaces or exponent notation. Values above 18446744073709551615
are invalid; typed implementations enforce this semantic upper bound in addition
to the schema's bounded decimal pattern. Boot ID is `boot_` followed by 64 lowercase
hex digits, the Windows endpoint's native boot digest. It is never reconstructed
from wall time/uptime or guessed from a PID/source GUID/latest state.

Manager supplies enrolled host ID and dispatch creation time, preserving schema 2
and the target unchanged. It emits UTC expiry with original fractional precision.
Windows accepts UTC `Z`/`+00:00` timestamps with optional 1-9 fractional digits,
checks exact creation/expiry order, and refuses expired commands conservatively
at its existing whole-second gate. Host/agent authentication and replay checks
remain mandatory. This version is a process-target contract, not a new leased
command protocol or a qualified durable outcome contract.

Before process access, Windows re-queries native boot and refuses missing,
unavailable or mismatched boot scope. It checks exact native creation ticks on the
retained kernel process handle. Termination additionally requires observed safety
facts and observed exit. Windows refuses legacy unscoped process actions; it
does not attach a current boot to old targets. Linux source and schema-1 behavior
have not been changed. Canonical Detection recommendations now map only when the
native subject digest and recommendation PID/ticks agree; Manager rechecks the
retained target/context and enrolled agent/host before authorization. Source-scoped
or unresolved actors never promote to executable targets. Capability negotiation
and Console targets remain open; select this version only for Windows
endpoints with this capability. Schema-1 recommendations currently fail closed
on Windows process handlers.

Tests cover Response contract bounds and malformed inputs, Manager authorized
stored/polled wire preservation, published schema validation and decoding with
the actual compiled Windows test decoder. The native runtime regression exercises
wrong/missing/current boot against an inert child created by that test. Neither
fixture parsing nor this owned process test qualifies reboot/OS matrix, process
protection failures, leases, signatures, command redelivery or crash outcomes.
