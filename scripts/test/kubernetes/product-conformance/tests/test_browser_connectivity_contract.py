"""Product-level conformance for the shared browser connectivity contract."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[5]
CONTRACT_ROOT = REPO_ROOT / "contracts" / "browser-connectivity"


class BrowserConnectivityContractTest(unittest.TestCase):
    def test_generated_bundle_contains_exact_schema_and_vectors(self) -> None:
        bundle = self._load("generated/contract-bundle.json")["contracts"]

        for name in (
            "turn-reachability-profile.schema.json",
            "schema-conformance-vectors.json",
        ):
            with self.subTest(name=name):
                self.assertEqual(bundle[name], self._load(name))

    def test_turn_profile_vectors_match_draft_2020_12_schema(self) -> None:
        schema = self._load("turn-reachability-profile.schema.json")
        validator = Draft202012Validator(schema)
        vectors = self._load("schema-conformance-vectors.json")["vectors"]

        self.assertTrue(vectors)
        for vector in vectors:
            with self.subTest(name=vector["name"]):
                errors = list(validator.iter_errors(vector["profile"]))
                self.assertEqual(not errors, vector["valid"])

    @staticmethod
    def _load(relative_path: str) -> object:
        return json.loads((CONTRACT_ROOT / relative_path).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
