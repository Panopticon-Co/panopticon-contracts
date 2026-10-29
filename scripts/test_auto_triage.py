import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]


class AutoTriageContractTests(unittest.TestCase):
    def setUp(self):
        self.schema = json.loads((ROOT / "schema/auto-triage-policy-v1.schema.json").read_text())
        self.fixtures = json.loads((ROOT / "fixtures/triage/policy-v1.json").read_text())
        Draft202012Validator.check_schema(self.schema)
        self.validator = Draft202012Validator(self.schema)

    def test_explicit_versioned_policy_examples(self):
        for case in self.fixtures["valid"]:
            with self.subTest(case=case["name"]):
                self.validator.validate(case["policy"])

    def test_forbidden_actions_critical_auto_paths_budget_coercion_and_duplicate_decisions(self):
        for case in self.fixtures["invalid"]:
            with self.subTest(case=case["name"]):
                self.assertFalse(self.validator.is_valid(case["policy"]))

    def test_every_budget_dimension_is_bounded_and_refuses_boolean_coercion(self):
        original = self.fixtures["valid"][1]["policy"]
        for key in original["budget"]:
            with self.subTest(budget=key):
                value = {**original, "budget": {**original["budget"], key: True}}
                self.assertFalse(self.validator.is_valid(value))

    def test_decisions_are_closed_and_always_reference_the_rule_and_policy_version(self):
        schema = json.loads((ROOT / "schema/auto-triage-decision-v1.schema.json").read_text())
        validator = Draft202012Validator(schema)
        value = {"rule_id": "RULE-1", "policy_version": 1, "action": "COLLECT_FILE",
                 "asset_class": "standard", "decision": "skip", "reason": "action_not_supported"}
        self.assertTrue(validator.is_valid(value))
        for update in ({"action": "KILL_PROCESS"}, {"decision": "force_execute"},
                       {"script": "unrecognized field"}, {"policy_version": True},
                       {"policy_version": 0}, {"schema_version": "2"}, {"reason": ""}):
            self.assertFalse(validator.is_valid({**value, **update}))
        self.assertFalse(validator.is_valid({k: v for k, v in value.items() if k != "policy_version"}))
