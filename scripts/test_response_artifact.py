import base64
import hashlib
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator


class ArtifactContractTests(unittest.TestCase):
    def test_closed_bounded_artifact(self):
        root = Path(__file__).resolve().parents[1]
        schema = json.loads((root / "schema/response-artifact-v1.schema.json").read_text())
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        data = b'{"pid":42}'
        artifact = {"schema_version": "1", "artifact_id": "art_" + "a" * 64,
                    "command_id": "command-1", "correlation_id": "correlation-1", "host_id": "host-1",
                    "kind": "process_snapshot", "media_type": "application/json",
                    "content_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                    "content_base64": base64.b64encode(data).decode()}
        self.assertTrue(validator.is_valid(artifact))
        for key, value in [("content_bytes", 1048577), ("content_bytes", True),
                           ("kind", "script"), ("media_type", "text/html"),
                           ("artifact_id", "../path"), ("sha256", "bad"), ("extra", "x")]:
            bad = dict(artifact)
            bad[key] = value
            self.assertFalse(validator.is_valid(bad), key)
