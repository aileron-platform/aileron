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

from app.middleware import target_client_settings_lock
from app.middleware.target_client_settings_lock import TargetClientSettingsMutationMiddleware
from app.modules.claude_code.router import router as claude_code_router
from app.modules.cli_settings.router import router as cli_settings_router
from app.modules.marketplace_operations.errors import MarketplaceOperationError
from app.modules.marketplace_operations.gate import MarketplaceTargetClientGate
from app.modules.marketplace_operations.state import MarketplaceMutationStore


_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}


def _target_client_route_cases() -> list[tuple[str, str, str]]:
    cases: list[tuple[str, str, str]] = []
    for router in (claude_code_router, cli_settings_router):
        for route in router.routes:
            path = getattr(route, "path", "")
            target_client = (
                "claude-code"
                if "/claude-code" in path
                else "codex" if "/codex" in path else None
            )
            if target_client is None:
                continue
            concrete = re.sub(r"\{[^}]+\}", "sample", path)
            for method in sorted(set(getattr(route, "methods", ())) & _METHODS):
                cases.append((method, concrete, target_client))
    return sorted(set(cases))


class _BlockingGate:
    def __init__(self) -> None:
        self.target_clients: list[str] = []

    @contextmanager
    def settings_mutation_scope(self, target_client: str) -> Iterator[None]:
        self.target_clients.append(target_client)
        raise MarketplaceOperationError(
            "marketplace.install.lock_timeout",
            http_status=409,
        )
        yield


def _catch_all_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(TargetClientSettingsMutationMiddleware)
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
    ("method", "path", "target_client"),
    _target_client_route_cases(),
)
def test_only_public_target_client_mutations_take_the_target_client_lock(
    monkeypatch: pytest.MonkeyPatch,
    method: str,
    path: str,
    target_client: str,
) -> None:
    gate = _BlockingGate()
    monkeypatch.setattr(
        target_client_settings_lock,
        "get_marketplace_target_client_gate",
        lambda: gate,
    )

    response = TestClient(_catch_all_app()).request(
        method,
        f"/api/v1{path}",
    )

    bypasses_lock = method == "GET" or path.endswith("/codex/rules/validate")
    if bypasses_lock:
        assert response.status_code == 200
        assert gate.target_clients == []
    else:
        assert response.status_code == 409
        assert response.json() == {"errorCode": "marketplace.install.lock_timeout"}
        assert gate.target_clients == [target_client]


def _mutation_app(
    gate: MarketplaceTargetClientGate,
    *,
    target_client: str,
    inner_mutation: bool = False,
) -> tuple[FastAPI, list[int]]:
    app = FastAPI()
    app.add_middleware(TargetClientSettingsMutationMiddleware)
    active = 0
    maximum = [0]
    active_lock = threading.Lock()

    @app.post(f"/api/v1/workspaces/{{workspace_id}}/{target_client}/test-mutation")
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
            gate.run_settings_mutation(target_client, write)
        else:
            write()
        return {"status": "ok"}

    @app.post(f"/api/v1/workspaces/{{workspace_id}}/{target_client}/test-failure")
    def fail(workspace_id: str) -> Response:
        _ = workspace_id
        return Response(status_code=409)

    return app, maximum


@pytest.mark.parametrize("target_client", ["claude-code", "codex"])
def test_concurrent_public_mutations_share_target_client_lock_and_generation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    target_client: str,
) -> None:
    store = MarketplaceMutationStore(tmp_path / "state")
    gate = MarketplaceTargetClientGate(store)
    monkeypatch.setattr(
        target_client_settings_lock,
        "get_marketplace_target_client_gate",
        lambda: gate,
    )
    app, maximum = _mutation_app(gate, target_client=target_client)

    def request() -> int:
        return (
            TestClient(app)
            .post(f"/api/v1/workspaces/workspace-1/{target_client}/test-mutation")
            .status_code
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(lambda _item: request(), range(2)))

    assert statuses == [200, 200]
    assert maximum == [1]
    assert gate.generation(target_client) == 2


@pytest.mark.parametrize("target_client", ["claude-code", "codex"])
def test_inner_settings_mutation_does_not_double_advance_generation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    target_client: str,
) -> None:
    gate = MarketplaceTargetClientGate(MarketplaceMutationStore(tmp_path / "state"))
    monkeypatch.setattr(
        target_client_settings_lock,
        "get_marketplace_target_client_gate",
        lambda: gate,
    )
    app, _maximum = _mutation_app(
        gate,
        target_client=target_client,
        inner_mutation=True,
    )

    response = TestClient(app).post(
        f"/api/v1/workspaces/workspace-1/{target_client}/test-mutation"
    )

    assert response.status_code == 200
    assert gate.generation(target_client) == 1


@pytest.mark.parametrize("target_client", ["claude-code", "codex"])
def test_failed_public_mutation_does_not_advance_generation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    target_client: str,
) -> None:
    gate = MarketplaceTargetClientGate(MarketplaceMutationStore(tmp_path / "state"))
    monkeypatch.setattr(
        target_client_settings_lock,
        "get_marketplace_target_client_gate",
        lambda: gate,
    )
    app, _maximum = _mutation_app(gate, target_client=target_client)

    response = TestClient(app).post(
        f"/api/v1/workspaces/workspace-1/{target_client}/test-failure"
    )

    assert response.status_code == 409
    assert gate.generation(target_client) == 0


@pytest.mark.parametrize("target_client", ["claude-code", "codex"])
def test_settings_request_and_marketplace_operation_share_same_flock(
    tmp_path: Path,
    target_client: str,
) -> None:
    store = MarketplaceMutationStore(tmp_path / "state")
    gate = MarketplaceTargetClientGate(store)
    acquired = threading.Event()

    def acquire_operation_lock() -> None:
        with store.target_client_lock(
            target_client=target_client,
        ):
            acquired.set()

    with gate.settings_mutation_scope(target_client):
        thread = threading.Thread(target=acquire_operation_lock)
        thread.start()
        assert acquired.wait(0.1) is False

    assert acquired.wait(1) is True
    thread.join(timeout=1)
    assert thread.is_alive() is False
