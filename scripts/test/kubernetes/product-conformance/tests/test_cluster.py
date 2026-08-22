"""Unit tests for Kubernetes product conformance helpers."""

import unittest

from product_conformance.cluster import (
    _workspace_storage_cleanup_args,
    _workspace_storage_preparer_args,
)


class ProductClusterTest(unittest.TestCase):
    def test_workspace_directory_preparer_sets_group_writable_mode(self) -> None:
        workspace_id = "11111111-1111-4111-8111-111111111111"

        self.assertEqual(
            _workspace_storage_preparer_args(workspace_id),
            [
                'umask 0007; mkdir -p "$1" "$2"; chmod 2770 "$1" "$2"',
                "--",
                f"/workspaces/{workspace_id}",
                f"/runtime-homes/{workspace_id}",
            ],
        )

    def test_workspace_storage_cleanup_targets_both_workspace_directories(self) -> None:
        workspace_id = "11111111-1111-4111-8111-111111111111"

        self.assertEqual(
            _workspace_storage_cleanup_args(workspace_id),
            [
                'rm -rf -- "$1" "$2"',
                "--",
                f"/workspaces/{workspace_id}",
                f"/runtime-homes/{workspace_id}",
            ],
        )


if __name__ == "__main__":
    unittest.main()
