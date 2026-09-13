#!/usr/bin/env python3
"""Validates every fixture in fixtures/ against schema/*.schema.json and checks
the security invariants documented in docs/SECURITY.md. Run from the repository
root: `python scripts/validate_fixtures.py`. Exits non-zero on any failure.

No third-party dependency beyond `jsonschema` (already a transitive dependency of
panopticon-manager/panopticon-response-engine via pydantic's tooling, and small
enough to add directly here without introducing build complexity).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import jsonschema
except ImportError:  # pragma: no cover
    print("This script requires the 'jsonschema' package: pip install jsonschema", file=sys.stderr)
    sys.exit(2)

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = ROOT / "schema"
FIXTURES_DIR = ROOT / "fixtures"

ACTIONS = (
    "KILL_PROCESS",
    "COLLECT_PROCESS_INFO",
    "COLLECT_NETWORK_CONNECTIONS",
    "COLLECT_FILE",
    "QUARANTINE_FILE",
    "ISOLATE_HOST",
    "RELEASE_HOST_ISOLATION",
)

BANNED_PATTERNS = (
    "system(", "popen(", "exec(", "execl", "execlp", "execv", "execvp",
    "/bin/sh", "/bin/bash", "bash -c", "sh -c", "EXECUTE_COMMAND",
)

# Directories that hold vendored/third-party/build code, not this project's own
# response-path source -- scanning them produces noise (their own legitimate use
# of exec()/system(), unrelated to Panopticon's response actions) rather than signal.
EXCLUDED_DIR_NAMES = {
    ".venv", "venv", "vendor", "node_modules", "build", ".git", "__pycache__",
    "vcpkg", "vcpkg_installed", ".claude",
}



def _load(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def validate_command_schema() -> list[str]:
    errors: list[str] = []
    command_schema = _load(SCHEMA_DIR / "command.schema.json")
    result_schema = _load(SCHEMA_DIR / "command_result.schema.json")

    if set(command_schema["properties"]["action"]["enum"]) != set(ACTIONS):
        errors.append(
            f"command.schema.json's action enum does not match the closed 7-action "
            f"set exactly: {sorted(command_schema['properties']['action']['enum'])}"
        )
    if len(command_schema["properties"]["action"]["enum"]) != 7:
        errors.append("command.schema.json's action enum must have exactly 7 entries")

    valid_commands = _load(FIXTURES_DIR / "commands" / "valid.json")
    for action, entry in valid_commands.items():
        if action.startswith("$"):
            continue
        try:
            jsonschema.validate(entry["command"], command_schema)
        except jsonschema.ValidationError as exc:
            errors.append(f"fixtures/commands/valid.json[{action}] should be VALID but failed: {exc.message}")

    if set(valid_commands.keys()) - {"$comment"} != set(ACTIONS):
        errors.append("fixtures/commands/valid.json must have exactly one entry per closed action")

    invalid_commands = _load(FIXTURES_DIR / "commands" / "invalid.json")
    # expired_command and non_utc_timestamp are semantic checks the agents perform
    # against wall-clock time / offset parsing, not structural JSON Schema checks --
    # schema/command.schema.json's expires_at is `format: date-time`, which validates
    # RFC 3339 *shape* only and has no concept of "now" or "must be Z". Both are
    # documented as known schema-vs-implementation gaps in docs/SECURITY.md.
    schema_checkable = {
        k: v for k, v in invalid_commands.items()
        if k not in ("$comment", "malformed_command", "replay_detected_scenario",
                     "cross_agent_mismatch", "correlation_mismatch", "non_utc_timestamp",
                     "expired_command")
    }
    for name, entry in schema_checkable.items():
        try:
            jsonschema.validate(entry["command"], command_schema)
            errors.append(f"fixtures/commands/invalid.json[{name}] should be INVALID but schema accepted it")
        except jsonschema.ValidationError:
            pass  # expected

    # non_utc_timestamp is documented as a known schema limitation: schema
    # validation alone will (incorrectly) ACCEPT it. Assert that documented gap
    # explicitly rather than silently skipping it.
    non_utc = invalid_commands["non_utc_timestamp"]["command"]
    try:
        jsonschema.validate(non_utc, command_schema)
    except jsonschema.ValidationError:
        errors.append(
            "fixtures/commands/invalid.json[non_utc_timestamp]: schema now rejects this -- "
            "update docs/SECURITY.md's 'Schema limitation' note, it may be stale"
        )

    malformed_raw = invalid_commands["malformed_command"]["raw"]
    try:
        json.loads(malformed_raw)
        errors.append("fixtures/commands/invalid.json[malformed_command].raw parsed as valid JSON -- it must not")
    except json.JSONDecodeError:
        pass  # expected

    valid_results = _load(FIXTURES_DIR / "results" / "valid.json")
    rejected_results = _load(FIXTURES_DIR / "results" / "rejected.json")
    for name, entry in valid_results.items():
        if name.startswith("$"):
            continue
        try:
            jsonschema.validate(entry["result"], result_schema)
        except jsonschema.ValidationError as exc:
            errors.append(f"fixtures/results/valid.json[{name}] should be VALID but failed: {exc.message}")
    for name, entry in rejected_results.items():
        if name.startswith("$"):
            continue
        try:
            jsonschema.validate(entry["result"], result_schema)
        except jsonschema.ValidationError as exc:
            errors.append(f"fixtures/results/rejected.json[{name}] should be VALID but failed: {exc.message}")
        if entry["result"]["outcome"] != "rejected":
            errors.append(f"fixtures/results/rejected.json[{name}] must have outcome 'rejected'")

    return errors


def validate_lifecycle() -> list[str]:
    errors: list[str] = []
    transitions = _load(FIXTURES_DIR / "lifecycle" / "transitions.json")
    terminal = {"SUCCEEDED", "FAILED", "REJECTED", "CANCELLED", "EXPIRED"}
    # Sanity: every valid_transitions entry's "from" must not be terminal.
    for t in transitions["valid_transitions"]:
        if t["from"] in terminal:
            errors.append(f"valid_transitions has an outbound transition from terminal state {t['from']}")
    for t in transitions["expiry_transitions"]:
        if t["from"] in terminal:
            errors.append(f"expiry_transitions has an outbound transition from terminal state {t['from']}")
    return errors


def grep_repos(paths: list[Path]) -> list[str]:
    errors: list[str] = []
    for repo_path in paths:
        if not repo_path.exists():
            errors.append(f"--grep-repos: path does not exist: {repo_path}")
            continue
        for file in repo_path.rglob("*"):
            if not file.is_file() or file.suffix not in {".py", ".cpp", ".hpp", ".cc", ".h"}:
                continue
            if any(part in EXCLUDED_DIR_NAMES for part in file.parts):
                continue
            # A test file asserting a banned action/pattern is *rejected* is the
            # desired regression coverage, not a violation -- see
            # panopticon-response-engine/tests/test_contract.py and
            # panopticon-linux-agent/tests/core_tests.cpp, both of which construct
            # an EXECUTE_COMMAND payload only to assert it is refused.
            is_test_file = "test" in file.stem.lower() or "tests" in [p.lower() for p in file.parts]
            try:
                text = file.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for pattern in BANNED_PATTERNS:
                if pattern in text and not is_test_file:
                    errors.append(f"BANNED PATTERN '{pattern}' found in {file}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--grep-repos", nargs="*", type=Path, default=[],
        help="Optional local repo checkouts to scan for banned execution patterns (docs/SECURITY.md).",
    )
    args = parser.parse_args()

    errors = validate_command_schema() + validate_lifecycle()
    if args.grep_repos:
        errors += grep_repos(args.grep_repos)

    if errors:
        print(f"FAILED: {len(errors)} problem(s) found:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print("OK: all fixtures validated against schema, lifecycle sanity checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
