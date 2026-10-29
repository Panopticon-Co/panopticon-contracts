import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]


class ResponseProfileTests(unittest.TestCase):
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
