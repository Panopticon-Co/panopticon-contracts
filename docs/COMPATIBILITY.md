# Compatibility matrix

This tracks, per repository, whether its implementation has been checked against
this repository's fixtures, and any known gap. "Checked" means a human or an
automated test in that repo's own test suite has compared its behavior against a
fixture here -- this repository does not run other repos' code itself (see
`README.md`: no runtime dependency is introduced).

| Repository | Language | Implements | Checked against these fixtures | Known gaps |
|---|---|---|---|---|
| `panopticon-response-engine` | Python (Pydantic) | `Command`, `CommandResult`, `ResponseActionState` lifecycle, `translate_recommendation` | Source of truth by construction, AND now independently re-checked: vendored as a test-only git submodule (`tests/vendor/panopticon-contracts`); `tests/test_contract_fixtures.py` proves `Command` accepts every valid fixture (after stripping the three Manager-injected fields) and rejects every schema-invalid one, and `CommandResult` accepts every valid/rejected-outcome result fixture. Verified green on real GitHub Actions CI (Python 3.10/3.11/3.12). | None remaining for this repo's own model surface. |
| `panopticon-manager` | Python (FastAPI + sqlite3) | HTTP transport, `host_id`/`schema_version`/`created_at` injection, persistence, tiering/authorization, lifecycle across two tables | `tests/test_response_contract.py` (sibling-repo-checkout convention, matching the existing `test_ingest_contract.py` pattern for `panopticon-agent`'s event schema): for every closed action's valid fixture, calls the REAL `authorize_and_enqueue()` path and validates the actual stored `commands.command_json` -- the exact bytes an agent's `poll()` receives -- against `schema/command.schema.json`. Verified green on real GitHub Actions CI. | None remaining for the dispatch-payload surface this test covers; lifecycle-transition and rejection-scenario fixtures (replay/cross-agent/correlation-mismatch) are still exercised only by this repo's own pre-existing tests, not fixture-driven yet. |
| `panopticon-linux-agent` | C++20 | `command.hpp`/`command.cpp`: `parse_command_json`, `command_gate`, all 7 action handlers, `serialize_command_result` | Direct source audit (not fixture-file-loading, since this repo has no JSON-file-reading test infrastructure yet) found and fixed a real gap: `parse_command_json` did not reject unrecognized top-level keys the way `panopticon-agent` and `response_engine.contract.Command` do. Fixed with an explicit `has_only_known_top_level_keys` check plus a regression test (`core_tests.cpp`) reproducing the exact `smuggled_shell_field` fixture scenario. A second regression test locks the full `receipt_code` -> wire `outcome` collapse this document's section 3 table depends on. Verified via Docker (`ubuntu:24.04`) build+CTest and real GitHub Actions CI (including the ASan/UBSan sanitized job). | Not yet wired to load this repo's fixture *files* directly (would need a JSON library dependency this repo doesn't currently have); fixture *scenarios* are instead hand-reproduced as literal test cases, which is functionally equivalent but requires manual upkeep if fixtures change. |
| `panopticon-agent` (Windows/"Officer") | C++20 | `response/command.hpp`/`command.cpp`: same shape, Win32 execution | `tests/response_tests.cpp` now directly loads this repository's fixture files (checked out as a CI sibling, same convention as `panopticon-manager`; resolved via a `PANOPTICON_CONTRACTS_DIR` CMake compile definition). Proves every valid.json fixture parses for all seven actions and every parse-level invalid.json fixture is rejected. A second test independently traced (not assumed) this agent's `ReceiptCode` -> wire `outcome` collapse via direct source read of `serialize_command_result` and locked it with a regression test -- confirmed byte-for-byte identical to `panopticon-linux-agent`'s mapping. Verified via a real MSVC build (`x64-windows` triplet) + CTest, all 9 suites passing. | Live enrollment/execution unverified in any CI environment (requires elevation) -- see that repo's `RESPONSE.md`; this remains ENVIRONMENT-BLOCKED, not a contract gap. |
| `panopticon-detection-engine` (eyedetect) | Python | `ActiveResponseAction`/`ProcessTree` recommendation vocabulary (`TERMINATE_PROCESS`, `ISOLATE_HOST`, `BLOCK_FIREWALL_IP`) -- upstream of this contract, not a contract implementer itself | `tests/test_active_response_start_time.py` (existing) verifies the fields `response_engine.translate_recommendation` requires (`target_pid`, `target_start_time_ticks`) are correctly populated | This repository does not fixture eyedetect's recommendation vocabulary directly, since it is not part of the closed 7-action contract -- only the translation *boundary* (`docs/CONTRACT.md` section 4) is in scope here. |

## Result-outcome collapse parity

Both native agents collapse their richer local diagnostic vocabulary onto the same
three wire values (`succeeded`/`failed`/`rejected`). Both mappings were independently
verified by direct source read (not assumed) and are byte-for-byte identical:
`succeeded -> succeeded`, `execution_failed -> failed`, every other code (
`invalid_command`, `expired`, `replay_detected`, `target_mismatch`,
`target_protected`, `unsupported_action`) `-> rejected`. Each implementation now has
its own regression test locking this mapping (`panopticon-linux-agent`'s
`core_tests.cpp`, `panopticon-agent`'s `response_tests.cpp`), so the two cannot
silently drift apart in the future without a test failure.

## Status: Priority 1 (wire golden fixtures into implementer tests) -- complete

All four implementer repositories now demonstrably prove compatibility with this
repository's canonical fixtures, verified on real CI (not local-only) for every one:
`panopticon-response-engine` (submodule + fixture-driven tests), `panopticon-manager`
(sibling checkout + a real-dispatch-path test), `panopticon-linux-agent` (source audit
+ hand-reproduced fixture scenarios, since it lacks a JSON-file-reading test harness),
and `panopticon-agent` (sibling checkout + direct fixture-file loading). No runtime
dependency was introduced anywhere -- every consumption path is test-only.
