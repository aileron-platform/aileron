"""Scenario registration contract tests."""

from __future__ import annotations

import inspect
import unittest

from product_conformance.contract import CAPABILITY_KEYS
from product_conformance.scenarios_jobs import SCENARIOS as JOB_SCENARIOS
from product_conformance.scenarios_realtime import SCENARIOS as REALTIME_SCENARIOS
from product_conformance.scenarios_workspace import SCENARIOS as WORKSPACE_SCENARIOS


class ScenarioRegistryTest(unittest.TestCase):
    def test_every_non_setup_capability_has_one_async_scenario(self) -> None:
        registries = (JOB_SCENARIOS, WORKSPACE_SCENARIOS, REALTIME_SCENARIOS)
        keys = [key for registry in registries for key in registry]

        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(set(keys), set(CAPABILITY_KEYS) - {"managerApiLifecycle"})
        self.assertTrue(
            all(
                inspect.iscoroutinefunction(scenario)
                for registry in registries
                for scenario in registry.values()
            )
        )


if __name__ == "__main__":
    unittest.main()
