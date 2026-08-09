"""Unit tests for Kubernetes product conformance helpers."""

import unittest

from product_conformance.cluster import _workspace_directory_preparer_args


class ProductClusterTest(unittest.TestCase):
    def test_workspace_directory_preparer_sets_group_writable_mode(self) -> None:
        workspace_id = "11111111-1111-4111-8111-111111111111"

        self.assertEqual(
            _workspace_directory_preparer_args(workspace_id),
            [
                'umask 0007; mkdir -p "$1"; chmod 2770 "$1"',
                "--",
                f"/workspaces/{workspace_id}",
            ],
        )


if __name__ == "__main__":
    unittest.main()
