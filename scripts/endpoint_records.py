#!/usr/bin/env python3
"""Validates endpoint-record 1.0 records: envelope schema, family data schema,
identity-digest proofs and payload/reference agreement.

Usage (from the repository root, or with paths):
    python scripts/endpoint_records.py [--current-producer] [FILE_OR_DIR ...]

--current-producer additionally requires fields that every current Officer
producer emits but older 1.0 records may lack (absent = predates the field).

With no arguments it validates fixtures/endpoint-record/1.0. Accepted inputs are
a JSON list of records, or {"records": [...]} (optionally with "fixture"
metadata), or a directory of such files. Files under an "invalid" directory
must FAIL validation; everything else must pass.

Exit codes: 0 all expectations met, 1 a record broke its expectation,
2 the jsonschema package is unavailable.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

try:
    import jsonschema
    from referencing import Registry, Resource
except ImportError:  # pragma: no cover
    print("This script requires the 'jsonschema' package: pip install jsonschema", file=sys.stderr)
    sys.exit(2)

ROOT = Path(__file__).resolve().parent.parent
ENVELOPE_PATH = ROOT / "schema" / "endpoint-record" / "1.0.schema.json"
FAMILY_DIR = ROOT / "schema" / "endpoint-record" / "1.0" / "families"
DEFAULT_FIXTURES = ROOT / "fixtures" / "endpoint-record" / "1.0"


def _load(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


class EndpointRecordValidator:
    def __init__(self) -> None:
        envelope = _load(ENVELOPE_PATH)
        resources = [(envelope["$id"], Resource.from_contents(envelope))]
        for path in sorted(FAMILY_DIR.glob("*.schema.json")):
            schema = _load(path)
            jsonschema.Draft202012Validator.check_schema(schema)
            resources.append((schema["$id"], Resource.from_contents(schema)))
        self.registry = Registry().with_resources(resources)
        self.envelope = jsonschema.Draft202012Validator(envelope, registry=self.registry)
        index = _load(FAMILY_DIR / "index.json")
        self.families = {}
        for entry in index["families"]:
            schema = _load(FAMILY_DIR / entry["schema"])
            self.families[(entry["kind"], entry["category"])] = (
                entry, jsonschema.Draft202012Validator(schema, registry=self.registry))

    def family_for(self, record: dict):
        return self.families.get((record.get("kind"), record.get("category")))

    def errors(self, record: dict, current_producer: bool = False) -> list[str]:
        """Every contract violation in one record; empty when it conforms."""
        problems = [f"envelope {list(e.absolute_path)}: {e.message}" for e in self.envelope.iter_errors(record)]
        if problems:
            return problems
        family = self.family_for(record)
        if family:
            _, validator = family
            problems += [f"data {list(e.absolute_path)}: {e.message[:300]}" for e in validator.iter_errors(record["data"])]
        problems += self._identity_errors(record)
        if current_producer:
            problems += _current_producer_errors(record)
        return problems

    def _identity_errors(self, record: dict) -> list[str]:
        problems: list[str] = []
        host = record["endpoint"]["host_id"]
        boot = record["endpoint"]["boot_id"]

        def check(reference, where: str) -> None:
            if reference is None:
                return
            if reference["boot_id"] != boot:
                problems.append(f"{where}: reference boot scope disagrees with endpoint")
            resolution = reference["resolution"]
            if resolution in ("unresolved", "native_unscoped"):
                if reference["entity_id"] is not None:
                    problems.append(f"{where}: {resolution} reference invented an entity")
                return
            if resolution == "native_exact":
                if not reference["boot_id"] or not reference["native_creation_ticks"] or not int(reference["native_creation_ticks"]):
                    problems.append(f"{where}: native_exact lacks boot scope or creation ticks")
                    return
                fields = ["native-process-instance-v1", host, reference["boot_id"], str(reference["observed_pid"]),
                          reference["native_creation_ticks"]]
            else:
                fields = ["source-process-instance-v1", host, reference["boot_id"] or "unknown",
                          reference["source_namespace"], str(reference["observed_pid"]), reference["source_guid"]]
            canonical = "".join(str(len(value.encode("utf-8"))) + ":" + value for value in fields)
            if reference["entity_id"] != "proc_" + hashlib.sha256(canonical.encode("utf-8")).hexdigest():
                problems.append(f"{where}: identity digest contradicts its exact facts")

        subject = record["subject"]
        check(subject, "subject")
        event = record["data"].get("event") if isinstance(record.get("data"), dict) else None
        if record["kind"] == "observation" and isinstance(event, dict) and event.get("category") != record["category"]:
            problems.append("data.event.category contradicts the envelope category")
        if record["kind"] == "observation" and isinstance(event, dict) and event.get("timestamp") != record["observed_at"]:
            problems.append("data.event.timestamp contradicts envelope observed_at")
        data = record["data"]
        process = data.get("process") if isinstance(data, dict) else None
        if isinstance(process, dict) and record["kind"] in ("observation", "evidence") and "entity_id" in process:
            expected = subject["entity_id"] if subject else None
            if process["entity_id"] != expected:
                problems.append("data.process.entity_id contradicts subject.entity_id")
            if subject and process.get("pid") != subject["observed_pid"]:
                problems.append("data.process.pid contradicts subject.observed_pid")
            parent = process.get("parent") or {}
            if parent.get("identity") is not None:
                check(parent["identity"], "data.process.parent.identity")
                if parent.get("entity_id") != parent["identity"]["entity_id"]:
                    problems.append("data.process.parent.entity_id contradicts its identity")
            elif parent.get("entity_id") is not None:
                problems.append("parent entity without an identity reference")
            if "identity" in process:
                check(process["identity"], "data.process.identity")
                if subject and process["identity"] != subject:
                    problems.append("data.process.identity differs from subject")
        family_block = data.get(record["category"]) if isinstance(data, dict) else None
        if isinstance(family_block, dict) and isinstance(family_block.get("target"), dict):
            target = family_block["target"]
            check(target.get("identity"), f"data.{record['category']}.target.identity")
            if target.get("identity") and target.get("entity_id") != target["identity"]["entity_id"]:
                problems.append("target entity_id contradicts its identity")
        lifecycle = data.get("lifecycle") if isinstance(data, dict) else None
        if isinstance(lifecycle, dict) and subject and lifecycle.get("identity") != subject:
            problems.append("lifecycle.identity differs from subject")
        return problems


def _current_producer_errors(record: dict) -> list[str]:
    """Fields optional for older 1.0 records but always emitted by current Officer."""
    facts = record["data"].get("source_facts") if isinstance(record.get("data"), dict) else None
    if not isinstance(facts, dict) or record["kind"] != "observation":
        return []
    problems = []
    for key in ("process", "target"):
        context = facts.get(key)
        if isinstance(context, dict) and "start_time_ticks" not in context:
            problems.append(f"current producer omitted source_facts.{key}.start_time_ticks")
    if record["category"] == "process_stop" and "event" not in record["data"]:
        problems.append("current producer omitted data.event on process_stop")
    if record["category"] == "process" and "operation" not in facts:
        problems.append("current producer omitted source_facts.operation")
    if record["category"] == "file" and isinstance(facts.get("file"), dict):
        problems += [f"current producer omitted source_facts.file.{key}" for key in ("phase", "status") if key not in facts["file"]]
    return problems


def _records(path: Path):
    content = _load(path)
    if isinstance(content, dict):
        return content.get("records", [])
    return content


def _files(arguments: list[str]) -> list[Path]:
    targets = [Path(argument) for argument in arguments] or [DEFAULT_FIXTURES]
    files: list[Path] = []
    for target in targets:
        files += sorted(target.rglob("*.json")) if target.is_dir() else [target]
    return files


def validate_paths(arguments: list[str], current_producer: bool = False) -> tuple[list[str], dict]:
    validator = EndpointRecordValidator()
    failures: list[str] = []
    summary = {"records": 0, "family_validated": 0, "envelope_only": set()}
    for path in _files(arguments):
        expect_invalid = "invalid" in path.parts
        for index, record in enumerate(_records(path)):
            summary["records"] += 1
            problems = validator.errors(record, current_producer)
            if validator.family_for(record):
                summary["family_validated"] += 1
            else:
                summary["envelope_only"].add(f"{record.get('kind')}/{record.get('category')}")
            if expect_invalid and not problems:
                failures.append(f"{path.name}[{index}]: invalid fixture was accepted")
            elif not expect_invalid and problems:
                failures.append(f"{path.name}[{index}] {record.get('kind')}/{record.get('category')}: " + "; ".join(problems[:4]))
    return failures, summary


def main(argv: list[str]) -> int:
    arguments = [argument for argument in argv[1:] if argument != "--current-producer"]
    failures, summary = validate_paths(arguments, "--current-producer" in argv[1:])
    for failure in failures:
        print("FAIL", failure)
    print(f"endpoint records: {summary['records']} checked, {summary['family_validated']} against a family schema, "
          f"envelope-only families: {sorted(summary['envelope_only']) or 'none'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
