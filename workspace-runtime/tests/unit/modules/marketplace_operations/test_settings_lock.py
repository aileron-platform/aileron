from __future__ import annotations

import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import pytest
from fastapi import APIRouter, FastAPI, Response
from fastapi.testclient import TestClient

from app.middleware import provider_settings_lock
from app.middleware.provider_settings_lock import ProviderSettingsMutationMiddleware
from app.modules.claude_code.router import router as claude_code_router
from app.modules.cli_settings.router import router as cli_settings_router
from app.modules.marketplace_operations.errors import MarketplaceOperationError
from app.modules.marketplace_operations.gate import MarketplaceProviderGate
from app.modules.marketplace_operations.state import MarketplaceMutationStore


_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}


def _provider_route_cases() -> list[tuple[str, str, str]]:
    cases: list[tuple[str, str, str]] = []
    for router in (claude_code_router, cli_settings_router):
        for route in router.routes:
            path = getattr(route, "path", "")
            provider = (
                "claude-code"
                if "/claude-code" in path
                else "codex" if "/codex" in path else None
            )
            if provider is None:
                continue
            concrete = re.sub(r"\{[^}]+\}", "sample", path)
            for method in sorted(set(getattr(route, "methods", ())) & _METHODS):
                cases.append((method, concrete, provider))
    return sorted(set(cases))


class _BlockingGate:
    def __init__(self) -> None:
        self.providers: list[str] = []

    @contextmanager
    def settings_mutation_scope(self, provider: str) -> Iterator[None]:
        self.providers.append(provider)
        raise MarketplaceOperationError(
            "marketplace.install.lock_timeout",
            http_status=409,
        )
        yield


def _catch_all_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(ProviderSettingsMutationMiddleware)
    router = APIRouter()

    @router.api_route(
        "/{path:path}",
        methods=sorted(_METHODS),
    )
    def catch_all(path: str) -> dict[str, str]:
        return {"path": path}

    app.include_router(router)
    return app


@pytest.mark.parametrize(
    ("method", "path", "provider"),
    _provider_route_cases(),
)
def test_only_public_provider_mutations_take_the_provider_lock(
    monkeypatch: pytest.MonkeyPatch,
    method: str,
    path: str,
    provider: str,
) -> None:
    gate = _BlockingGate()
    monkeypatch.setattr(
        provider_settings_lock,
        "get_marketplace_provider_gate",
        lambda: gate,
    )

    response = TestClient(_catch_all_app()).request(
        method,
        f"/api/v1{path}",
    )

    bypasses_lock = method == "GET" or path.endswith("/codex/rules/validate")
    if bypasses_lock:
        assert response.status_code == 200
        assert gate.providers == []
    else:
        assert response.status_code == 409
        assert response.json() == {"errorCode": "marketplace.install.lock_timeout"}
        assert gate.providers == [provider]


def _mutation_app(
    gate: MarketplaceProviderGate,
    *,
    provider: str,
    inner_mutation: bool = False,
) -> tuple[FastAPI, list[int]]:
    app = FastAPI()
    app.add_middleware(ProviderSettingsMutationMiddleware)
    active = 0
    maximum = [0]
    active_lock = threading.Lock()

    @app.post(f"/api/v1/workspaces/{{workspace_id}}/{provider}/test-mutation")
    def mutate(workspace_id: str) -> dict[str, str]:
        nonlocal active
        _ = workspace_id

        def write() -> None:
            nonlocal active
            with active_lock:
                active += 1
                maximum[0] = max(maximum[0], active)
            time.sleep(0.05)
            with active_lock:
                active -= 1

        if inner_mutation:
            gate.run_settings_mutation(provider, write)
        else:
            write()
        return {"status": "ok"}

    @app.post(f"/api/v1/workspaces/{{workspace_id}}/{provider}/test-failure")
    def fail(workspace_id: str) -> Response:
        _ = workspace_id
        return Response(status_code=409)

    return app, maximum


@pytest.mark.parametrize("provider", ["claude-code", "codex"])
def test_concurrent_public_mutations_share_provider_lock_and_generation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
) -> None:
    store = MarketplaceMutationStore(tmp_path / "state")
    gate = MarketplaceProviderGate(store)
    monkeypatch.setattr(
        provider_settings_lock,
        "get_marketplace_provider_gate",
        lambda: gate,
    )
    app, maximum = _mutation_app(gate, provider=provider)

    def request() -> int:
        return (
            TestClient(app)
            .post(f"/api/v1/workspaces/workspace-1/{provider}/test-mutation")
            .status_code
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(lambda _item: request(), range(2)))

    assert statuses == [200, 200]
    assert maximum == [1]
    assert gate.generation(provider) == 2


@pytest.mark.parametrize("provider", ["claude-code", "codex"])
def test_inner_settings_mutation_does_not_double_advance_generation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
) -> None:
    gate = MarketplaceProviderGate(MarketplaceMutationStore(tmp_path / "state"))
    monkeypatch.setattr(
        provider_settings_lock,
        "get_marketplace_provider_gate",
        lambda: gate,
    )
    app, _maximum = _mutation_app(
        gate,
        provider=provider,
        inner_mutation=True,
    )

    response = TestClient(app).post(
        f"/api/v1/workspaces/workspace-1/{provider}/test-mutation"
    )

    assert response.status_code == 200
    assert gate.generation(provider) == 1


@pytest.mark.parametrize("provider", ["claude-code", "codex"])
def test_failed_public_mutation_does_not_advance_generation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
) -> None:
    gate = MarketplaceProviderGate(MarketplaceMutationStore(tmp_path / "state"))
    monkeypatch.setattr(
        provider_settings_lock,
        "get_marketplace_provider_gate",
        lambda: gate,
    )
    app, _maximum = _mutation_app(gate, provider=provider)

    response = TestClient(app).post(
        f"/api/v1/workspaces/workspace-1/{provider}/test-failure"
    )

    assert response.status_code == 409
    assert gate.generation(provider) == 0


@pytest.mark.parametrize("provider", ["claude-code", "codex"])
def test_settings_request_and_marketplace_operation_share_same_flock(
    tmp_path: Path,
    provider: str,
) -> None:
    store = MarketplaceMutationStore(tmp_path / "state")
    gate = MarketplaceProviderGate(store)
    acquired = threading.Event()

    def acquire_operation_lock() -> None:
        with store.provider_lock(
            provider=provider,
        ):
            acquired.set()

    with gate.settings_mutation_scope(provider):
        thread = threading.Thread(target=acquire_operation_lock)
        thread.start()
        assert acquired.wait(0.1) is False

    assert acquired.wait(1) is True
    thread.join(timeout=1)
    assert thread.is_alive() is False
