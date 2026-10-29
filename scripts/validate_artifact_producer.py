"""Validate native producer output against the central closed schema and exact vector."""
import argparse
import base64
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    value = json.loads(args.path.read_text(encoding="utf-8"))
    schema = json.loads((ROOT / "schema/response-artifact-v1.schema.json").read_text())
    Draft202012Validator(schema).validate(value)
    raw = base64.b64decode(value["content_base64"], validate=True)
    if len(raw) != value["content_bytes"] or hashlib.sha256(raw).hexdigest() != value["sha256"]:
        raise ValueError("native artifact digest/byte count mismatch")
    expected = json.loads((ROOT / "fixtures/artifacts/producer-vector.json").read_text())
    if value != expected:
        raise ValueError("native producer differs from central exact-byte artifact vector")
    print("Native artifact agrees with central schema, exact bytes, SHA-256 and identity vector")


if __name__ == "__main__":
    main()
