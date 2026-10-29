import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]


class DownloadContractTests(unittest.TestCase):
    def test_context_uses_signed_manifest_and_separate_case_key_identity(self):
        manifest_schema = json.loads((ROOT / "schema/response-artifact-manifest-v2.schema.json").read_text())
        registry = Registry().with_resource(manifest_schema["$id"], Resource.from_contents(manifest_schema))
        schema = json.loads((ROOT / "schema/artifact-download-context-v1.schema.json").read_text())
        validator = Draft202012Validator(schema, registry=registry)
        vector = json.loads((ROOT / "fixtures/artifacts/signing-v2.json").read_text())
        manifest = vector["manifest"]
        trusted = {k: manifest[k] for k in ("artifact_id", "agent_id", "host_id", "command_id", "correlation_id")}
        trusted.update(alert_id="alert-1", response_id="response-1", key_id=manifest["authorization"]["key_id"],
                       key_version=1, public_key=vector["public_key"], trust_status="active_key")
        value = {"schema_version": "1", "artifact_id": manifest["artifact_id"], "manifest": manifest,
                 "manifest_sha256": "a" * 64, "chunk_bytes": 65536, "trusted": trusted}
        self.assertTrue(validator.is_valid(value))
        self.assertFalse(validator.is_valid({**value, "trusted": {}}))
        self.assertFalse(validator.is_valid({**value, "content_base64": "plain-content-in-context"}))

    def test_download_chunk_cannot_be_unbounded_or_claim_verification(self):
        schema = json.loads((ROOT / "schema/artifact-download-chunk-v1.schema.json").read_text())
        validator = Draft202012Validator(schema)
        value = {"schema_version": "1", "artifact_id": "art_" + "a" * 64,
                 "manifest_sha256": "b" * 64, "offset": 0, "content_bytes": 2,
                 "sha256": "c" * 64, "content_base64": "e30=", "next_offset": 2, "complete": True}
        self.assertTrue(validator.is_valid(value))
        for field, invalid in (("content_bytes", 65537), ("content_bytes", True),
                               ("complete", 1), ("verified", True), ("offset", -1)):
            self.assertFalse(validator.is_valid({**value, field: invalid}))

    def test_view_acknowledgement_has_closed_version_and_idempotent_intent(self):
        schema = json.loads((ROOT / "schema/artifact-view-request-v1.schema.json").read_text())
        validator = Draft202012Validator(schema)
        value = {"schema_version": "1", "request_id": "view-1", "manifest_sha256": "a" * 64,
                 "operation": "view"}
        self.assertTrue(validator.is_valid(value))
        self.assertFalse(validator.is_valid({**value, "actor": "untrusted-browser-actor"}))
        self.assertFalse(validator.is_valid({**value, "operation": "execute"}))
        self.assertFalse(validator.is_valid({**value, "request_id": ""}))
