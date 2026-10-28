#!/usr/bin/env python3
"""Validates the Linux endpoint record contract (schema/linux-endpoint/1.0.schema.json).

* every file in fixtures/linux-endpoint/valid/ must validate;
* every file in fixtures/linux-endpoint/invalid/ must be rejected;
* with --ndjson FILE, every line of that file (for example the output of
  `panopticon-sensord --stdout`) must validate.

Run from the repository root: python scripts/validate_linux_endpoint.py [--ndjson FILE]
Exits non-zero on any failure. Needs the `jsonschema` package.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from jsonschema import Draft202012Validator
except ImportError:  # pragma: no cover
    print("This script requires the 'jsonschema' package: pip install jsonschema", file=sys.stderr)
    sys.exit(2)

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "schema" / "linux-endpoint" / "1.0.schema.json"
FIXTURES = ROOT / "fixtures" / "linux-endpoint"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ndjson", help="validate every line of this NDJSON file as well")
    args = parser.parse_args()

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    failures = 0

    valid = sorted((FIXTURES / "valid").glob("*.json"))
    if not valid:
        print("no valid fixtures found", file=sys.stderr)
        return 1
    for path in valid:
        errors = list(validator.iter_errors(json.loads(path.read_text(encoding="utf-8"))))
        if errors:
            failures += 1
            print(f"FAIL valid fixture {path.name}: {errors[0].message}")
    for path in sorted((FIXTURES / "invalid").glob("*.json")):
        case = json.loads(path.read_text(encoding="utf-8"))
        if validator.is_valid(case["record"]):
            failures += 1
            print(f"FAIL invalid fixture {path.name} was accepted ({case['why']})")

    checked = 0
    if args.ndjson:
        with open(args.ndjson, encoding="utf-8") as stream:
            for number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                checked += 1
                errors = list(validator.iter_errors(json.loads(line)))
                if errors:
                    failures += 1
                    where = "/".join(str(p) for p in errors[0].absolute_path)
                    print(f"FAIL {args.ndjson}:{number} {where}: {errors[0].message[:160]}")

    print(f"{len(valid)} valid fixtures, {len(list((FIXTURES / 'invalid').glob('*.json')))} invalid fixtures, "
          f"{checked} ndjson records, {failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
