# Wave 6 transport contract, 2026-10-27

`schema/command_result.schema.json` is the current Windows result contract,
**schema_version `"2"`**. `schema/command-result-v2.schema.json` is its explicit
versioned name; the fixture validator checks that the two schemas stay identical
apart from `$id`. This is a breaking wire revision under VERSIONING.md.

Version 2 requires command correlation and admits `indeterminate`: an action may
have started without proof of completion. Optional `execution` is a closed,
strictly typed `windows_process_termination_v1` object. It must not contradict
the outcome. An absent object supports restart recovery; explicit null is invalid.
Manager accepts this evidence only for a queued KILL_PROCESS, retains the whole
result immutably, and projects `INDETERMINATE` as a terminal lifecycle state.

`schema/command-result-v1.schema.json` archives the original result contract.
The Linux agent's unversioned, three-outcome results remain revision 1; this
change does not claim the Linux producer emits revision 2. Manager and Response
Engine already explicitly decode these two result revisions. This records that
existing compatibility behavior, rather than adding version negotiation.
Command revision 1 remains the seven-action baseline. Windows command revision 2
is the existing boot-bound process-target contract with decimal uint64 ticks.
Canonical endpoint records retain their independent version `"1.0"`; transport
uses protocol `"2"`. These three version numbers are not interchangeable.

Versioned result fixtures are under `fixtures/v1/results/` and
`fixtures/v2/results/`. The pre-existing `fixtures/results/` paths remain legacy
test inputs for existing consumers. The v2 matrix includes restart recovery with
no execution evidence and rejects missing correlation, explicit-null evidence,
wrong versions, and contradictory execution facts.

ACQUIRE_FILE is an **internal Windows agent extension** for the protected local
forensic store. It is not a Manager-dispatchable action and is not part of the
shared seven-action command vocabulary. Manager and Response Engine reject it.
Exposing it remotely requires a separately versioned target and authorization
contract; COLLECT_FILE must not be silently translated to ACQUIRE_FILE.

Source fixtures under `fixtures/endpoint-record/1.0/families/` cover minifilter,
API-hook and kernel-ETW transport. They are synthetic production-pipeline outputs,
marked `real_capture: false` and provisional. The hook example is a file-open
transport record, not a finalized API-call schema. No driver, hook interception,
kernel-network collector, or live Windows VM evidence is established by them.
