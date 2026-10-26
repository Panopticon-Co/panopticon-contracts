#!/usr/bin/env python3
"""Consumer-compatibility report: feeds endpoint-record 1.0 family fixtures
through a Detection Engine checkout's real Officer adapter, without modifying it.

    python scripts/detection_compat.py --engine PATH_TO_DETECTION_ENGINE [--json]

For legacy-derived families the canonical `data` (plus the schema_version the
legacy wire used) is the adapter's documented input. For each family the report
states whether the adapter accepted it and which producer facts survived. It is
a report, not a gate: it exits 1 only if a legacy-derived family that the
engine claims to support raises or loses its identity/category facts.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FAMILIES = ROOT / "fixtures" / "endpoint-record" / "1.0" / "families"
LEGACY_DERIVED = {"process", "network", "file", "registry", "image_load"}


def legacy_event(record: dict) -> dict:
    """The adapter input a legacy-derived canonical record carries in `data`."""
    event = {key: value for key, value in record["data"].items() if key not in ("source_facts", "enrichment")}
    event["schema_version"] = "0.3"
    return event


def _scalars(value):
    """Every scalar anywhere in the adapter output, excluding the retained raw copy."""
    if isinstance(value, dict):
        for key, item in value.items():
            if key != "_raw_officer_event":
                yield from _scalars(item)
    elif isinstance(value, list):
        for item in value:
            yield from _scalars(item)
    elif isinstance(value, (str, int, float, bool)):
        yield value


def check(adapter, record: dict) -> dict:
    category = record["category"]
    result = {"category": category, "source_kind": record["provenance"]["kind"], "resolution": (record["subject"] or {}).get("resolution")}
    data = record["data"]
    if category not in LEGACY_DERIVED:
        result["input"] = "canonical data as-is (no legacy shape exists for this family)"
        candidate = dict(data)
    else:
        result["input"] = "legacy event carried in data"
        candidate = legacy_event(record)
    try:
        out = adapter.transform_officer_event(candidate)
    except Exception as error:  # report, do not hide
        result.update(status="rejected", error=f"{type(error).__name__}: {error}")
        return result
    result["event_type"] = out.get("event_type")
    lost = []
    process = out.get("process", {}) if isinstance(out.get("process"), dict) else {}
    expected_process = data.get("process", {})
    if process.get("pid") != expected_process.get("pid"):
        lost.append("process.pid")
    if process.get("entity_id", out.get("entity_id")) != expected_process.get("entity_id"):
        lost.append("process.entity_id")
    ticks = process.get("start_time_ticks", out.get("start_time_ticks"))
    if expected_process.get("start_time_ticks") is not None:
        if ticks is None:
            lost.append("process.start_time_ticks")
        elif not isinstance(ticks, int):
            result["start_time_ticks_type"] = type(ticks).__name__
    block = data.get(category if category != "image_load" else "image_load")
    if isinstance(block, dict) and category not in ("process",):
        values = set(_scalars(out))
        for key in ("path", "destination_ip", "key_path", "query_name", "granted_access", "start_address"):
            value = block.get(key)
            if isinstance(value, str) and value and value not in values:
                lost.append(f"{category}.{key}")
        if isinstance(block.get("target"), dict) and block["target"].get("pid") not in values:
            lost.append(f"{category}.target")
    if category == "file":
        facts = data["source_facts"]["file"]
        if facts.get("phase") not in (None, "reported"):
            lost.append("file outcome (phase/status) - lives in source_facts, which the legacy shape omits")
    result.update(status="accepted" if not lost else "accepted_with_loss", lost=lost)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", required=True, type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    sys.path.insert(0, str(args.engine.resolve()))
    adapter = importlib.import_module("panopticon_detection.ingestion.officer_adapter").OfficerIngestionAdapter
    families = getattr(importlib.import_module("panopticon_detection.ingestion.telemetry"), "TELEMETRY_FAMILIES", ())
    report = []
    for path in sorted(FAMILIES.glob("*.json")):
        fixture = json.loads(path.read_text(encoding="utf-8"))
        for record in fixture["records"]:
            if record["kind"] != "observation":
                continue
            entry = check(adapter, record)
            entry["fixture"] = path.stem
            entry["engine_declares_family"] = record["category"] in families
            report.append(entry)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for entry in report:
            detail = entry.get("error") or ", ".join(entry.get("lost", [])) or "-"
            extra = f" ticks_type={entry['start_time_ticks_type']}" if "start_time_ticks_type" in entry else ""
            print(f"{entry['fixture']:16} {entry['category']:15} {entry['status']:19} event_type={entry.get('event_type')}{extra} lost={detail}")
    regressions = [entry for entry in report if entry["category"] in LEGACY_DERIVED and entry["engine_declares_family"]
                   and (entry["status"] == "rejected" or any(item in ("process.pid", "process.entity_id") for item in entry.get("lost", [])))]
    return 1 if regressions else 0


if __name__ == "__main__":
    sys.exit(main())
