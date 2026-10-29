import base64
import copy
import hashlib
import json
import unittest
from pathlib import Path

from artifact_signing import SCHEMA, signing_input
from jsonschema import Draft202012Validator, ValidationError


class SignedArtifactContractTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1]
        self.vector = json.loads((root / "fixtures/artifacts/signing-v2.json").read_text())

    def test_exact_signing_representation_and_content(self):
        Draft202012Validator.check_schema(SCHEMA)
        manifest = self.vector["manifest"]
        content = base64.b64decode(self.vector["content_base64"], validate=True)
        self.assertEqual(hashlib.sha256(content).hexdigest(), manifest["sha256"])
        self.assertEqual(len(content), manifest["content_bytes"])
        self.assertEqual(signing_input(manifest),
                         base64.b64decode(self.vector["signing_input_base64"], validate=True))
        point = base64.b64decode(self.vector["public_key"], validate=True)
        self.assertEqual(hashlib.sha256(point).hexdigest()[:16],
                         manifest["authorization"]["key_id"])

    def test_closed_manifest_refuses_unsigned_oversize_and_ambiguous_types(self):
        for field, value in (("content_bytes", True), ("content_bytes", 1048577),
                             ("produced_at_unix", -1), ("schema_version", "1"),
                             ("content_base64", "e30="), ("kind", "raw_file")):
            invalid = copy.deepcopy(self.vector["manifest"])
            invalid[field] = value
            with self.assertRaises(ValidationError):
                signing_input(invalid)
        missing = copy.deepcopy(self.vector["manifest"])
        del missing["authorization"]
        with self.assertRaises(ValidationError):
            signing_input(missing)

    def test_identity_and_length_prefix_boundaries_are_signed(self):
        original = self.vector["manifest"]
        for field in ("agent_id", "host_id", "command_id", "correlation_id"):
            changed = copy.deepcopy(original)
            changed[field] += ":é\n"
            self.assertNotEqual(signing_input(original), signing_input(changed))

    def test_closed_versioned_key_rotation_proposal(self):
        root = Path(__file__).resolve().parents[1]
        schema = json.loads((root / "schema/artifact-key-rotation-v1.schema.json").read_text())
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        signature = self.vector["manifest"]["authorization"]["signature"]
        proposal = {"schema_version": "1", "request_id": "rotation-1",
                    "old_key_id": self.vector["manifest"]["authorization"]["key_id"],
                    "new_public_key": self.vector["public_key"],
                    "nonce": base64.b64encode(bytes(32)).decode(),
                    "old_signature": signature, "new_signature": signature}
        self.assertTrue(validator.is_valid(proposal))
        for field, value in (("schema_version", "2"), ("new_signature", ""),
                             ("old_signature", None), ("shell", "forbidden")):
            bad = {**proposal, field: value}
            self.assertFalse(validator.is_valid(bad))
