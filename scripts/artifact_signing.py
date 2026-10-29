"""Reference signing representation for the closed v2 artifact manifest."""

import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schema/response-artifact-manifest-v2.schema.json").read_text())
FIELDS = ("schema_version", "artifact_id", "agent_id", "host_id", "command_id",
          "correlation_id", "kind", "media_type", "content_bytes", "sha256",
          "produced_at_unix", "algorithm", "key_id")


def signing_input(manifest):
    Draft202012Validator(SCHEMA).validate(manifest)
    values = {**manifest, **manifest["authorization"]}
    result = bytearray(b"panopticon-response-artifact-auth/2\n")
    for name in FIELDS:
        value = str(values[name]).encode("utf-8")
        result.extend(name.encode() + b":" + str(len(value)).encode() + b":" + value + b"\n")
    return bytes(result)
