# Fixture conventions

All fixtures in this directory are deterministic JSON, grouped by category rather
than split one-fixture-per-file, to keep the fixture set reviewable as a whole
(each file's top-level `$comment` explains the grouping and cross-references
`docs/SECURITY.md`'s invariant numbers or `docs/CONTRACT.md`'s sections it proves).

## Which fields are intentionally fixed vs. variable

- `command_id`, `result_id`, `correlation_id`, `agent_id`, `host_id`: fixed,
  synthetic values (`cmd-0001`, `agent-linux-01`, ...) chosen for readability and
  cross-fixture cross-referencing (e.g. `fixtures/results/valid.json`'s `succeeded`
  entry deliberately reuses `fixtures/commands/valid.json`'s `COLLECT_PROCESS_INFO`
  command's `command_id`/`correlation_id` to show the two are a matched pair). A
  consuming test may substitute its own IDs freely -- nothing in the contract
  requires these specific strings -- but should preserve the *pairing* between a
  command and the result/scenario that references it by ID.
- `expires_at` and other timestamps: fixed values in the past (`2020-...`) or an
  arbitrary point in the future (`2026-01-01T00:10:00Z`) relative to no particular
  "now". A consuming test must supply its own notion of "current time" to its
  expiry check (e.g. via a mockable clock, as both native agents' `command_gate`
  constructors already take an injectable clock function) rather than comparing
  against wall-clock time when validating these fixtures -- that is what makes an
  `expired_command`-style fixture reusable indefinitely rather than expiring for
  real a few years after it's written.
- `target.pid` / `target.start_time_ticks`: fixed synthetic integers. These are
  never meant to correspond to a real process on any real machine; they exist only
  to exercise the shape/type rules in `schema/command.schema.json`.
- `target.path`: fixed synthetic paths under `/var/lib/panopticon/evidence/`. These
  do not need to exist on disk -- fixtures test the wire contract, not filesystem
  behavior (path-jailing/`resolve_within_allowed_root` is agent-side and
  OS-specific, out of scope per `README.md`).

## What "validated" means for a fixture

`scripts/validate_fixtures.py` validates every `command` object inside
`fixtures/commands/valid.json` against `schema/command.schema.json` and asserts
success, and every `command` object inside `fixtures/commands/invalid.json` against
the same schema and asserts failure (with one documented exception --
`non_utc_timestamp`, which schema validation alone cannot catch; see
`docs/SECURITY.md`'s "Schema limitation" note). `malformed_command`'s `raw` string
is asserted to fail `json.loads` outright, not schema validation, since it is not
well-formed JSON in the first place. Scenario-shaped entries (`replay_detected_
scenario`, `cross_agent_mismatch`, `correlation_mismatch`, and everything in
`fixtures/lifecycle/transitions.json`) describe multi-step or stateful behavior a
static schema cannot express alone; they are validated by asserting their
referenced `command`/`result` objects are individually well-formed, with the
documented expected outcome intended to be asserted by each consuming repo's own
integration test (see `docs/COMPATIBILITY.md`'s "Next step" section).
