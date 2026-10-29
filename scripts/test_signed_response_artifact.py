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
