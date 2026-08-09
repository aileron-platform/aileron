"""Fresh PostgreSQL schema contract for product-conformance queries."""

from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

import psycopg
from product_conformance.database import ProductDatabase


class ProductDatabaseWaitContractTest(unittest.TestCase):
    def test_wait_job_fails_immediately_on_unexpected_terminal_status(self) -> None:
        database = ProductDatabase("postgresql://unused")
        failed_job = {
            "id": "job-1",
            "status": "failed",
            "error_code": "WORKSPACE_CUSTOM_RESOURCE_NOT_READY",
        }

        with patch.object(database, "get_job", return_value=failed_job) as get_job:
            with self.assertRaisesRegex(
                AssertionError,
                "reached terminal status 'failed'.*WORKSPACE_CUSTOM_RESOURCE_NOT_READY",
            ):
                database.wait_job(
                    "job-1",
                    "succeeded",
                    timeout_seconds=60,
                )

        get_job.assert_called_once_with("job-1")


class ProductDatabaseFreshSchemaContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dsn = os.environ["PRODUCT_CONFORMANCE_TEST_POSTGRES_DSN"]
        cls.database = ProductDatabase(cls.dsn)
        cls.database.ping()

    def setUp(self) -> None:
        self.workspace_id = "product-db-workspace"
        self.knowledge_base_id = "product-db-kb"
        self.attachment_id = "product-db-attachment"
        self.user_id = "product-db-user"
        self.active_snapshot = [
            {
                "attachmentId": self.attachment_id,
                "knowledgeBaseId": self.knowledge_base_id,
                "mountAlias": "active-kb",
                "attachedById": self.user_id,
            }
        ]
        self.candidate_snapshot = [
            {
                "attachmentId": self.attachment_id,
                "knowledgeBaseId": self.knowledge_base_id,
                "mountAlias": "candidate-kb",
                "attachedById": self.user_id,
            }
        ]
        with psycopg.connect(self.dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute("TRUNCATE TABLE users CASCADE")
                cursor.execute(
                    """
                    INSERT INTO users (id, username)
                    VALUES (%s, %s)
                    """,
                    (self.user_id, "product-db-user"),
                )
                cursor.execute(
                    """
                    INSERT INTO knowledge_bases (id, slug, name, owner_id)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        self.knowledge_base_id,
                        "product-db-kb",
                        "Product DB KB",
                        self.user_id,
                    ),
                )
                cursor.execute(
                    """
                    INSERT INTO workspaces (
                        id,
                        owner_id,
                        name,
                        provisioner,
                        target_namespace,
                        runtime_status,
                        runtime_instance_id,
                        knowledge_base_mount_active_revision,
                        knowledge_base_mount_desired_revision,
                        knowledge_base_mount_observed_revision,
                        knowledge_base_mount_sync_status,
                        knowledge_base_mount_active_snapshot,
                        knowledge_base_mount_candidate_snapshot
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s::jsonb, %s::jsonb
                    )
                    """,
                    (
                        self.workspace_id,
                        self.user_id,
                        "Product DB Workspace",
                        "kubernetes",
                        "product-db",
                        "running",
                        "11111111-1111-4111-8111-111111111111",
                        7,
                        8,
                        7,
                        "applying",
                        json.dumps(self.active_snapshot),
                        json.dumps(self.candidate_snapshot),
                    ),
                )
                cursor.execute(
                    """
                    INSERT INTO workspace_knowledge_base_attachments (
                        id,
                        workspace_id,
                        kb_id,
                        mount_alias,
                        attached_by_id
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        self.attachment_id,
                        self.workspace_id,
                        self.knowledge_base_id,
                        "active-kb",
                        self.user_id,
                    ),
                )

    def test_runner_queries_execute_against_fresh_schema(self) -> None:
        workspace = self.database.get_workspace(self.workspace_id)

        self.assertIsNotNone(workspace)
        assert workspace is not None
        self.assertEqual(workspace["knowledge_base_mount_active_revision"], 7)
        self.assertEqual(workspace["knowledge_base_mount_desired_revision"], 8)
        self.assertEqual(workspace["knowledge_base_mount_observed_revision"], 7)
        self.assertEqual(workspace["knowledge_base_mount_sync_status"], "applying")
        self.assertEqual(
            workspace["knowledge_base_mount_active_snapshot"],
            self.active_snapshot,
        )
        self.assertEqual(
            workspace["knowledge_base_mount_candidate_snapshot"],
            self.candidate_snapshot,
        )
        self.assertIsNone(workspace["knowledge_base_mount_failed_snapshot"])
        self.assertNotIn("knowledge_base_mount_revision", workspace)
        self.assertNotIn("knowledge_base_mount_status", workspace)

        attachments = self.database.list_active_attachments(self.workspace_id)
        self.assertEqual(len(attachments), 1)
        self.assertEqual(
            {
                key: attachments[0][key]
                for key in (
                    "id",
                    "workspace_id",
                    "kb_id",
                    "mount_alias",
                    "attached_by_id",
                )
            },
            {
                "id": self.attachment_id,
                "workspace_id": self.workspace_id,
                "kb_id": self.knowledge_base_id,
                "mount_alias": "active-kb",
                "attached_by_id": self.user_id,
            },
        )
        self.assertNotIn("state", attachments[0])
        self.assertNotIn("detach_target_revision", attachments[0])
        self.assertEqual(
            self.database.list_attachment_kb_ids(self.workspace_id),
            [self.knowledge_base_id],
        )

    def test_database_exposes_only_canonical_mount_columns(self) -> None:
        rows = self.database.fetch_all("""
            SELECT column_name
              FROM information_schema.columns
             WHERE table_schema = 'public'
               AND table_name IN (
                   'workspaces',
                   'workspace_knowledge_base_attachments'
               )
            """)
        columns = {str(row["column_name"]) for row in rows}

        self.assertTrue(
            {
                "knowledge_base_mount_active_revision",
                "knowledge_base_mount_desired_revision",
                "knowledge_base_mount_observed_revision",
                "knowledge_base_mount_sync_status",
                "knowledge_base_mount_active_snapshot",
                "knowledge_base_mount_candidate_snapshot",
                "knowledge_base_mount_failed_snapshot",
                "attached_by_id",
            }.issubset(columns)
        )
        self.assertTrue(
            {
                "knowledge_base_mount_revision",
                "knowledge_base_mount_status",
                "state",
                "detach_target_revision",
            }.isdisjoint(columns)
        )


if __name__ == "__main__":
    unittest.main()
