"""Product conformance evidence contract tests."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from product_conformance.contract import (
    CAPABILITY_KEYS,
    ConformanceReport,
    Evidence,
)


class ConformanceReportTest(unittest.TestCase):
    def test_exact_product_capability_keys_are_fail_closed(self) -> None:
        report = ConformanceReport(run_id="run-1", namespace="test")

        self.assertEqual(len(CAPABILITY_KEYS), 13)
        self.assertEqual(tuple(report.capabilities), CAPABILITY_KEYS)
        self.assertFalse(report.passed)
        self.assertTrue(
            all(not result.passed for result in report.capabilities.values())
        )

    def test_capability_cannot_pass_without_evidence(self) -> None:
        report = ConformanceReport(run_id="run-1", namespace="test")

        with self.assertRaisesRegex(ValueError, "cannot pass without evidence"):
            report.pass_capability("managerApiLifecycle", [])

    def test_capability_rejects_empty_or_unobserved_evidence(self) -> None:
        report = ConformanceReport(run_id="run-1", namespace="test")

        with self.assertRaisesRegex(ValueError, "metadata cannot be empty"):
            report.pass_capability(
                "managerApiLifecycle",
                [Evidence(kind="", ref="api", assertion="checked", observed=True)],
            )
        with self.assertRaisesRegex(ValueError, "observed value"):
            report.pass_capability(
                "managerApiLifecycle",
                [Evidence(kind="api", ref="api", assertion="checked", observed=None)],
            )

    def test_report_passes_only_after_all_thirteen_assertions(self) -> None:
        report = ConformanceReport(run_id="run-1", namespace="test")
        evidence = [
            Evidence(
                kind="api",
                ref="POST /api/v1/workspaces",
                assertion="response is persisted",
                observed={"status": 201},
            )
        ]

        for key in CAPABILITY_KEYS:
            report.pass_capability(key, evidence)

        document = report.to_dict()
        self.assertTrue(report.passed)
        self.assertEqual(document["result"], "passed")
        self.assertTrue(
            all(item["passed"] for item in document["capabilities"].values())
        )

    def test_report_normalizes_database_timestamps_for_json_evidence(self) -> None:
        report = ConformanceReport(run_id="run-1", namespace="test")
        observed_at = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)
        evidence = [
            Evidence(
                kind="postgresql",
                ref="workspace_runtime_jobs/job-1",
                assertion="job has a terminal timestamp",
                observed={"finishedAt": observed_at},
            )
        ]
        report.pass_capability("durableJobs", evidence)

        document = report.to_dict()

        self.assertEqual(
            document["capabilities"]["durableJobs"]["evidence"][0]["observed"],
            {"finishedAt": "2026-07-20T12:00:00+00:00"},
        )


if __name__ == "__main__":
    unittest.main()
