import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]


class TransferContractTests(unittest.TestCase):
    def test_admission_uses_exact_closed_signed_manifest(self):
        schema = json.loads((ROOT / "schema/artifact-transfer-request-v1.schema.json").read_text())
        manifest_schema = json.loads((ROOT / "schema/response-artifact-manifest-v2.schema.json").read_text())
        registry = Registry().with_resource(manifest_schema["$id"], Resource.from_contents(manifest_schema))
        validator = Draft202012Validator(schema, registry=registry)
        manifest = json.loads((ROOT / "fixtures/artifacts/signing-v2.json").read_text())["manifest"]
        value = {"schema_version": "1", "manifest": manifest}
        self.assertTrue(validator.is_valid(value))
        self.assertFalse(validator.is_valid({**value, "admitted_at": "client-chosen-time"}))
        self.assertFalse(validator.is_valid({**value, "schema_version": "2"}))
        self.assertFalse(validator.is_valid({"schema_version": "1", "manifest": {}}))

    def test_progress_is_not_an_evidence_receipt(self):
        schema = json.loads((ROOT / "schema/artifact-transfer-progress-v1.schema.json").read_text())
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        value = {"schema_version": "1", "artifact_id": "art_" + "a" * 64,
                 "sha256": "b" * 64, "manifest_sha256": "c" * 64, "received_bytes": 65536,
                 "chunk_bytes": 65536, "complete": False, "expires_at": "2026-10-30T00:00:00Z"}
        self.assertTrue(validator.is_valid(value))
        for field, invalid in (("received_bytes", True), ("received_bytes", 1048577),
                               ("complete", 1), ("chunk_bytes", 1048576), ("retained", True)):
            self.assertFalse(validator.is_valid({**value, field: invalid}), field)

    def test_completion_requires_manifest_binding(self):
        schema = json.loads((ROOT / "schema/artifact-transfer-complete-v1.schema.json").read_text())
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        value = {"schema_version": "1", "manifest_sha256": "a" * 64}
        self.assertTrue(validator.is_valid(value))
        self.assertFalse(validator.is_valid({"schema_version": "1"}))
        self.assertFalse(validator.is_valid({**value, "content_base64": "unbounded"}))
