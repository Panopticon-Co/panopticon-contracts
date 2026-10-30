"""Validate actual native response-profile output against its central version."""

import base64
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]


def closed_pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate runtime profile field")
        value[key] = item
    return value


def validate(raw):
    if len(base64.b64encode(raw)) > 4096:
        raise ValueError("runtime profile exceeds authenticated header budget")
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=closed_pairs)
    if not isinstance(value, dict) or value.get("schema_version") not in {"1", "2"}:
        raise ValueError("unsupported runtime profile version")
    schema = json.loads((ROOT / ("schema/response-profile-v" + value["schema_version"] + ".schema.json")).read_text())
    Draft202012Validator(schema).validate(value)
    if not set(value["allowed_actions"]) <= set(value["implemented_actions"]):
        raise ValueError("runtime policy cannot allow an unimplemented action")
    return value


if __name__ == "__main__":
    validate(Path(sys.argv[1]).read_bytes().strip())
    print("Native response profile matches central version, action set and header bounds")
