from __future__ import annotations

import json
import unittest
from pathlib import Path

from jsonschema import Draft7Validator


CONTRACT_DIR = Path(__file__).resolve().parents[1]


class IdentityInstallationProfileTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        schema = json.loads((CONTRACT_DIR / "profile.schema.json").read_text(encoding="utf-8"))
        cls.validator = Draft7Validator(schema)
        cls.vectors = json.loads(
            (CONTRACT_DIR / "conformance-vectors.json").read_text(encoding="utf-8")
        )

    def test_conformance_vectors(self) -> None:
        for vector in self.vectors:
            with self.subTest(vector=vector["name"]):
                errors = list(self.validator.iter_errors(vector["profile"]))
                self.assertEqual(vector["valid"], not errors, [error.message for error in errors])

    def test_external_provider_is_not_keycloak_specific(self) -> None:
        external = next(vector for vector in self.vectors if vector["name"] == "valid external OIDC")
        self.assertEqual("externalOidc", external["profile"]["mode"])
        self.assertIn("authentik", external["profile"]["externalOidc"]["issuerUrl"])
        self.assertNotIn("keycloak", json.dumps(external["profile"]).lower())


if __name__ == "__main__":
    unittest.main()
