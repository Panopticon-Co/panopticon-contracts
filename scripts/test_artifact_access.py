import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]


class AccessContractTests(unittest.TestCase):
    def test_scope_cannot_be_implicit_wildcard_policy_or_extra_authority(self):
        schema = json.loads((ROOT / "schema/artifact-access-grant-v1.schema.json").read_text())
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        value = {"schema_version": "1", "policy_version": 1, "request_id": "grant-1",
                 "analyst_id": "reader", "alert_id": "case-1", "host_id": "host-1",
                 "reason": "Assigned investigation"}
        self.assertTrue(validator.is_valid(value))
        for field, invalid in (("policy_version", True), ("policy_version", 2),
                               ("reason", "  "), ("auto_grant", True)):
            self.assertFalse(validator.is_valid({**value, field: invalid}))
        self.assertFalse(validator.is_valid({k: v for k, v in value.items() if k != "host_id"}))

    def test_revocation_requires_auditable_versioned_intent(self):
        schema = json.loads((ROOT / "schema/artifact-access-revoke-v1.schema.json").read_text())
        validator = Draft202012Validator(schema)
        value = {"schema_version": "1", "policy_version": 1, "request_id": "revoke-1",
                 "reason": "Assignment ended"}
        self.assertTrue(validator.is_valid(value))
        self.assertFalse(validator.is_valid({**value, "reason": ""}))
        self.assertFalse(validator.is_valid({**value, "policy_version": 2}))
        self.assertFalse(validator.is_valid({**value, "grant_all_hosts": True}))
