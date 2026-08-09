"""PostgreSQL non-overlap contract for named platform task leases."""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine

from app.core.task_lease import task_lease


@pytest.mark.integration
def test_task_lease_is_exclusive_and_reusable() -> None:
    database_url = os.environ.get("AUTOMATION_TEST_DATABASE_URL")
    if not database_url or not database_url.startswith("postgresql"):
        pytest.skip("PostgreSQL integration database is required")
    engine = create_engine(database_url, pool_pre_ping=True)
    lease_name = "platform-resources-integration-lease"
    try:
        with task_lease(engine, lease_name) as first_acquired:
            assert first_acquired is True
            with task_lease(engine, lease_name) as second_acquired:
                assert second_acquired is False
        with task_lease(engine, lease_name) as reacquired:
            assert reacquired is True
    finally:
        engine.dispose()


@pytest.mark.integration
def test_distinct_lease_names_do_not_block_each_other() -> None:
    database_url = os.environ.get("AUTOMATION_TEST_DATABASE_URL")
    if not database_url or not database_url.startswith("postgresql"):
        pytest.skip("PostgreSQL integration database is required")
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with task_lease(engine, "platform-resources-integration-a") as first:
            assert first is True
            with task_lease(engine, "platform-resources-integration-b") as second:
                assert second is True
    finally:
        engine.dispose()
