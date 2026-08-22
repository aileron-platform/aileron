"""Provider-neutral Identity conformance evidence tests."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from product_conformance import driver
from product_conformance.contract import CAPABILITY_KEYS, Evidence
from product_conformance.driver import _external_oidc_evidence


class ExternalOidcEvidenceTest(unittest.TestCase):
    def test_transaction_workspace_commands_are_executable_driver_modes(self) -> None:
        with (
            patch.object(sys, "argv", ["driver", "prepare-transaction-workspace"]),
            patch.object(driver, "prepare_transaction_workspace", return_value=0) as prepare,
        ):
            self.assertEqual(driver.main(), 0)
        prepare.assert_called_once_with()

        with (
            patch.object(sys, "argv", ["driver", "cleanup-transaction-workspace"]),
            patch.object(driver, "cleanup_transaction_workspace", return_value=0) as cleanup,
        ):
            self.assertEqual(driver.main(), 0)
        cleanup.assert_called_once_with()

    def test_logout_transport_failure_does_not_erase_scenario_results(self) -> None:
        async def execute(_, report):
            for key in CAPABILITY_KEYS:
                if key != "externalOidcAuthorizationCodeJit":
                    report.pass_capability(key, oidc_evidence)

        with tempfile.TemporaryDirectory() as directory:
            report_path = Path(directory) / "report.json"
            settings = SimpleNamespace(
                run_id="run-1",
                namespace="test-ns",
                report_path=report_path,
            )
            context = Mock()
            context.assert_prerequisites = Mock()
            context.verify_logout.side_effect = RuntimeError("manager unavailable")
            oidc_evidence = [
                Evidence(
                    kind="oidc",
                    ref="https://fixture.example.test",
                    assertion="authorization flow completed",
                    observed={},
                )
            ]
            with (
                patch.object(driver, "_load_kubernetes_config"),
                patch.object(driver, "_load_optional_scenarios"),
                patch.object(driver.ProductConfig, "from_environment", return_value=settings),
                patch.object(driver, "ProductContext", return_value=context),
                patch.object(driver, "_external_oidc_evidence", return_value=oidc_evidence),
                patch.object(driver, "_execute_conformance", side_effect=execute),
            ):
                result = driver.run_conformance()

            report = json.loads(report_path.read_text(encoding="utf-8"))

        self.assertEqual(result, 1)
        self.assertIn(
            "logout verification failed",
            report["capabilities"]["externalOidcAuthorizationCodeJit"]["failure"],
        )
        self.assertTrue(report["capabilities"]["managerApiLifecycle"]["passed"])
        context.close.assert_called_once_with()

    def test_missing_actual_callback_and_jit_evidence_fails(self) -> None:
        context = SimpleNamespace(
            settings=SimpleNamespace(oidc_issuer_url="https://fixture.example.test"),
            external_oidc_observation={
                "fixture": "provider-neutral-non-keycloak",
                "authorizationEndpoint": "https://fixture.example.test/authorize",
                "actors": {},
            },
        )

        with self.assertRaisesRegex(AssertionError, "evidence is incomplete"):
            _external_oidc_evidence(context)

    def test_actual_authorization_callback_session_and_jit_evidence_passes(self) -> None:
        context = SimpleNamespace(
            settings=SimpleNamespace(oidc_issuer_url="https://fixture.example.test"),
            external_oidc_observation={
                "fixture": "provider-neutral-non-keycloak",
                "authorizationEndpoint": "https://fixture.example.test/authorize",
                "callbackPath": "/api/v1/oauth2/callback",
                "actors": {
                    "owner": {
                        "subject": "fixture-subject",
                        "sessionIssued": True,
                        "jitWorkspaceListAccepted": True,
                    }
                },
            },
        )

        evidence = _external_oidc_evidence(context)

        self.assertEqual(evidence[0].observed["actors"]["owner"]["subject"], "fixture-subject")


if __name__ == "__main__":
    unittest.main()
