from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
from types import ModuleType
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text


def _load_preflight_module() -> ModuleType:
    script_path = Path("/helm/aileron/files/data-service-preflight.py")
    spec = importlib.util.spec_from_file_location("data_service_preflight", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_production_data_service_preflight_cleans_probe_objects(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_url = os.environ["AUTOMATION_TEST_DATABASE_URL"]
    database_url_file = tmp_path / "database-url"
    database_url_file.write_text(database_url, encoding="utf-8")
    scope = f"integration:{uuid4()}"
    digest = hashlib.sha256(scope.encode("utf-8")).hexdigest()[:16]

    monkeypatch.setenv("PREFLIGHT_SCOPE", scope)
    monkeypatch.setenv("PLATFORM_DATABASE_URL_FILE", str(database_url_file))
    monkeypatch.setenv("GENERAL_REDIS_URL", "redis://redis-test:6379/10")
    monkeypatch.setenv("JOB_QUEUE_REDIS_URL", "redis://redis-test:6379/11")
    monkeypatch.setenv("JOB_RESULT_REDIS_URL", "redis://redis-test:6379/12")

    module = _load_preflight_module()
    module.main()

    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            assert (
                connection.execute(
                    text("SELECT count(*) FROM pg_roles WHERE rolname LIKE :prefix"),
                    {"prefix": f"aileron_pf_{digest}_%"},
                ).scalar_one()
                == 0
            )
            assert (
                connection.execute(
                    text(
                        "SELECT count(*) FROM pg_namespace WHERE nspname LIKE :prefix"
                    ),
                    {"prefix": f"aileron_pf_{digest}_%"},
                ).scalar_one()
                == 0
            )
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    ("connection_url", "message"),
    [
        (
            "redis+sentinel://redis.example.test/0",
            "standalone redis:// or rediss://",
        ),
        (
            "redis://redis-a.example.test:6379,redis-b.example.test:6379/0",
            "one standalone Redis endpoint",
        ),
        ("redis://redis.example.test", "one numeric logical database"),
        ("redis://redis.example.test/0/1", "one numeric logical database"),
    ],
)
def test_data_service_preflight_rejects_non_standalone_redis_topology(
    monkeypatch,
    connection_url: str,
    message: str,
) -> None:
    monkeypatch.setenv("GENERAL_REDIS_URL", connection_url)

    with pytest.raises(RuntimeError, match=message):
        _load_preflight_module().verify_redis("GENERAL_REDIS", "integration:test")


def test_data_service_preflight_rejects_unknown_database_mode(monkeypatch) -> None:
    monkeypatch.setenv("PLATFORM_DATABASE_MODE", "legacy")

    with pytest.raises(RuntimeError, match="Unsupported platform database mode"):
        _load_preflight_module().verify_postgres("integration:test")
