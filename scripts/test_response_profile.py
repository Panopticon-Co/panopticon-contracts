import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator
from validate_response_profile import validate

ROOT = Path(__file__).resolve().parents[1]


class ResponseProfileTests(unittest.TestCase):
    def test_artifact_capability_requires_an_explicit_version_and_cannot_invent_signature_support(self):
        for platform in ("windows", "linux"):
            value = {"schema_version": "2", "platform": platform, "host_id": "host-1",
                     "boot_id": "boot_" + "a" * 64, "mode": "enforce",
                     "implemented_actions": ["COLLECT_FILE"], "allowed_actions": ["COLLECT_FILE"],
                     "require_boot_binding": True, "require_signature": platform == "linux",
                     "artifact_protocol": "signed-json-v2-resume-v1"}
            self.assertEqual(validate(json.dumps(value).encode()), value)
            for change in ({"schema_version": "1"}, {"artifact_protocol": True},
                           {"artifact_protocol": "unsigned-files"}):
                with self.subTest(platform=platform, change=change):
                    self.assertFalse(Draft202012Validator(json.loads(
                        (ROOT / "schema/response-profile-v2.schema.json").read_text()
                    )).is_valid({**value, **change}))
            self.assertEqual(validate(json.dumps({**value, "artifact_protocol": None}).encode())[
                "artifact_protocol"], None)
            with self.assertRaises(ValueError):
                validate(b'{"schema_version":"2","schema_version":"2"}')

    def test_closed_runtime_profile(self):
        schema = json.loads((ROOT / "schema/response-profile-v1.schema.json").read_text())
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        profile = {"schema_version": "1", "platform": "linux", "host_id": "host-1", "boot_id": "boot_" + "a" * 64,
                   "mode": "dry_run", "implemented_actions": ["KILL_PROCESS"],
                   "allowed_actions": ["KILL_PROCESS"], "require_boot_binding": True,
                   "require_signature": True}
        self.assertTrue(validator.is_valid(profile))
        for field, value in [("mode", "unknown"), ("allowed_actions", ["EXECUTE_COMMAND"]),
                             ("require_signature", 1), ("extra", True),
                             ("boot_id", "raw-boot-uuid")]:
            bad = copy.deepcopy(profile)
            bad[field] = value
            self.assertFalse(validator.is_valid(bad), field)
