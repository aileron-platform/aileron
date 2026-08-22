from __future__ import annotations

import ssl
from pathlib import Path

import pytest
from celery import Celery
from redis import Redis

from app.config.settings import Settings


@pytest.mark.parametrize(
    ("file_field", "property_name"),
    [
        ("REDIS_URL_FILE", "redis_url"),
        ("CELERY_BROKER_URL_FILE", "celery_broker_url"),
        ("CELERY_RESULT_BACKEND_FILE", "celery_result_backend"),
    ],
)
def test_redis_connections_read_complete_urls_from_mounted_secrets(
    tmp_path: Path,
    file_field: str,
    property_name: str,
) -> None:
    secret_file = tmp_path / f"{file_field.lower()}.txt"
    secret_file.write_text("redis://acl-user:secret@redis.example.test:6379/7\n")

    settings = Settings(**{file_field: str(secret_file)})

    assert getattr(settings, property_name) == (
        "redis://acl-user:secret@redis.example.test:6379/7"
    )


@pytest.mark.parametrize(
    ("file_value", "message"),
    [
        (None, "must reference a readable file"),
        ("", "must not be empty"),
        ("postgresql://db.example.test/aileron", "standalone redis:// or rediss://"),
        ("redis+sentinel://redis.example.test/0", "standalone redis:// or rediss://"),
        (
            "redis://redis-a.example.test:6379,redis-b.example.test:6379/0",
            "one standalone Redis endpoint",
        ),
        ("redis://redis.example.test", "one numeric logical database"),
        ("redis://redis.example.test/0/1", "one numeric logical database"),
    ],
)
def test_redis_connection_rejects_missing_empty_or_unsupported_secret(
    tmp_path: Path,
    file_value: str | None,
    message: str,
) -> None:
    url_file = tmp_path / "redis-url"
    if file_value is not None:
        url_file.write_text(file_value, encoding="utf-8")

    settings = Settings(REDIS_URL_FILE=str(url_file))

    with pytest.raises(ValueError, match=message):
        _ = settings.redis_url


def test_rediss_connection_uses_only_the_separate_mounted_ca(
    tmp_path: Path,
) -> None:
    url_file = tmp_path / "redis-url"
    url_file.write_text(
        "rediss://acl-user:secret@redis.example.test:6380/9?socket_timeout=4",
        encoding="utf-8",
    )
    ca_file = tmp_path / "redis-ca.crt"
    ca_file.write_text("test-ca", encoding="utf-8")
    settings = Settings(
        REDIS_URL_FILE=str(url_file),
        REDIS_CA_CERT_FILE=str(ca_file),
    )

    resolved = settings.redis_url
    connection_kwargs = Redis.from_url(resolved).connection_pool.connection_kwargs

    assert connection_kwargs["ssl_ca_certs"] == str(ca_file)
    assert connection_kwargs["ssl_cert_reqs"] == "required"
    assert connection_kwargs["socket_timeout"] == 4.0

    celery_app = Celery(broker=resolved, backend=resolved)
    try:
        backend_kwargs = celery_app.backend.client.connection_pool.connection_kwargs
        assert backend_kwargs["ssl_ca_certs"] == str(ca_file)
        assert backend_kwargs["ssl_cert_reqs"] == ssl.CERT_REQUIRED
    finally:
        celery_app.close()


def test_redis_connection_rejects_url_embedded_tls_trust(tmp_path: Path) -> None:
    url_file = tmp_path / "redis-url"
    url_file.write_text(
        "rediss://redis.example.test:6380/0?ssl_cert_reqs=none",
        encoding="utf-8",
    )
    settings = Settings(REDIS_URL_FILE=str(url_file))

    with pytest.raises(ValueError, match="must not configure TLS trust in the URL"):
        _ = settings.redis_url


def test_plaintext_redis_connection_rejects_ca_configuration(tmp_path: Path) -> None:
    url_file = tmp_path / "redis-url"
    url_file.write_text("redis://redis.example.test:6379/0", encoding="utf-8")
    ca_file = tmp_path / "redis-ca.crt"
    ca_file.write_text("test-ca", encoding="utf-8")
    settings = Settings(
        REDIS_URL_FILE=str(url_file),
        REDIS_CA_CERT_FILE=str(ca_file),
    )

    with pytest.raises(ValueError, match="cannot configure a CA for redis://"):
        _ = settings.redis_url
