# Compatibility matrix

This tracks, per repository, whether its implementation has been checked against
this repository's fixtures, and any known gap. "Checked" means a human or an
automated test in that repo's own test suite has compared its behavior against a
fixture here -- this repository does not run other repos' code itself (see
`README.md`: no runtime dependency is introduced).

| Repository | Language | Implements | Checked against these fixtures | Known gaps |
|---|---|---|---|---|
| `panopticon-response-engine` | Python (Pydantic) | `Command`, `CommandResult`, `ResponseActionState` lifecycle, `translate_recommendation` | Source of truth -- fixtures in this repo were derived FROM its behavior, so it is compatible by construction. `scripts/validate_fixtures.py` re-derives this by validating every fixture against `schema/*.schema.json`, which were themselves reconciled against `response_engine/contract.py`. | `Command.model_dump()` does not itself include `host_id`/`schema_version` -- those are Manager's responsibility. This is documented, not a defect. |
| `panopticon-manager` | Python (FastAPI + sqlite3) | HTTP transport, `host_id`/`schema_version` injection, persistence, tiering/authorization, lifecycle across two tables | `tests/test_response_engine.py`, `tests/test_response_actions_route.py` (existing, not yet extended to load fixtures from this repo directly) | Not yet wired to import fixtures from this repo directly as test data (see "Next step" below). |
| `panopticon-linux-agent` | C++20 | `command.hpp`/`command.cpp`: `parse_command_json`, `command_gate`, all 7 action handlers, `serialize_command_result` | `tests/*` (existing CTest suite covers decode/reject cases matching this repo's `fixtures/commands/invalid/*` in spirit, written independently before this repo existed) | Not yet wired to load this repo's fixture files directly (see "Next step"). |
| `panopticon-agent` (Windows/"Officer") | C++20 | `response/command.hpp`/`command.cpp`: same shape, Win32 execution | `tests/response_tests.cpp` (existing, 18 assertions, written independently before this repo existed) | Not yet wired to load this repo's fixture files directly (see "Next step"). Live enrollment/execution unverified in any CI environment (requires elevation) -- see that repo's `RESPONSE.md`. |
| `panopticon-detection-engine` (eyedetect) | Python | `ActiveResponseAction`/`ProcessTree` recommendation vocabulary (`TERMINATE_PROCESS`, `ISOLATE_HOST`, `BLOCK_FIREWALL_IP`) -- upstream of this contract, not a contract implementer itself | `tests/test_active_response_start_time.py` (existing) verifies the fields `response_engine.translate_recommendation` requires (`target_pid`, `target_start_time_ticks`) are correctly populated | This repository does not fixture eyedetect's recommendation vocabulary directly, since it is not part of the closed 7-action contract -- only the translation *boundary* (`docs/CONTRACT.md` section 4) is in scope here. |

## Result-outcome collapse parity

Both native agents collapse their richer local diagnostic vocabulary onto the same
three wire values (`succeeded`/`failed`/`rejected`). `panopticon-linux-agent`'s
mapping is reproduced verbatim in `docs/CONTRACT.md` section 3, read directly from
`src/command.cpp`. `panopticon-agent` (Windows) was not independently re-read
field-by-field for this document's collapse table; its `RESPONSE.md` states the same
architecture ("every command result is a typed, bounded receipt") but a byte-level
diff of its `serialize_command_result`-equivalent against the Linux mapping is
recorded here as a **known gap**, not assumed identical.

## Next step (not yet done by this initial pass)

Each of `panopticon-manager`, `panopticon-linux-agent`, and `panopticon-agent` should
grow a small test that loads this repository's fixture files (via a git submodule,
a vendored copy, or a build-time fetch -- whichever fits that repo's existing test
infrastructure with the least new machinery) and asserts its own encode/decode
matches the fixture byte-for-byte for the JSON shape, and semantically for
accept/reject outcomes. This repository provides the fixtures and this document
records the plan; wiring each individual repo's test suite to consume them is
tracked as follow-up work in each repo's own state-tracking document
(`panopticon-manager/docs/RESPONSE_ENGINE_STATE.md` is the existing precedent for
this kind of tracking).
