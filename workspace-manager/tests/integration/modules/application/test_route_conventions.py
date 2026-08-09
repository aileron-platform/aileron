from __future__ import annotations

from app.main import app
from tests.helpers.fastapi_routes import registered_api_route_methods


def _registered_routes() -> set[tuple[str, str]]:
    return registered_api_route_methods(app.routes)


def test_removed_rest_routes_are_not_registered() -> None:
    routes = _registered_routes()

    removed_routes = {
        ("/api/v1/health", "GET"),
        ("/api/v1/health/oidc", "GET"),
        ("/api/v1/marketplace/registry/init", "POST"),
        ("/api/v1/marketplace/registry/repository", "GET"),
        ("/api/v1/marketplace/registry/diff", "GET"),
        ("/api/v1/marketplace/registry/commits", "GET"),
        ("/api/v1/marketplace/registry/commits/{commit_id}/files", "GET"),
        ("/api/v1/marketplace/registry/commits/{commit_id}/diff", "GET"),
        ("/api/v1/marketplace/registry/files/history", "GET"),
        ("/api/v1/marketplace/registry/files/history/{entry_id}/restore", "POST"),
        ("/api/v1/marketplace/registry/ssh-key", "GET"),
        ("/api/v1/marketplace/registry/ssh-key", "POST"),
        ("/api/v1/marketplace/registry/git-identity", "PUT"),
        ("/api/v1/marketplace/version-control/git-identity", "PUT"),
        ("/api/v1/marketplace/registry/branches", "POST"),
        ("/api/v1/marketplace/registry/checkout", "POST"),
        ("/api/v1/marketplace/registry/merge", "POST"),
        ("/api/v1/marketplace/registry/rebase", "POST"),
        ("/api/v1/marketplace/registry/cherry-pick", "POST"),
        ("/api/v1/marketplace/registry/stash", "POST"),
        ("/api/v1/marketplace/registry/conflicts/resolve", "POST"),
        ("/api/v1/knowledge-bases/{kb_id}/files", "PATCH"),
        ("/api/v1/knowledge-bases/{kb_id}/files/copy", "POST"),
        ("/api/v1/knowledge-bases/{kb_id}/files/extract/{operation_id}", "GET"),
        ("/api/v1/knowledge-bases/{kb_id}/git/repository/status", "GET"),
        ("/api/v1/knowledge-bases/{kb_id}/git/repository/enable", "POST"),
        ("/api/v1/knowledge-bases/{kb_id}/git/lfs/enable", "POST"),
        ("/api/v1/knowledge-bases/{kb_id}/git/remote-url", "POST"),
        (
            "/api/v1/knowledge-bases/{kb_id}/version-control/branches/{branch_name:path}/checkout",
            "POST",
        ),
        ("/api/v1/knowledge-bases/{kb_id}/version-control/revert", "POST"),
        ("/api/v1/knowledge-bases/{kb_id}/version-control/rollback", "POST"),
        ("/api/v1/users", "POST"),
        ("/api/v1/users/{user_id}", "GET"),
        ("/api/v1/users/{user_id}", "PUT"),
        ("/api/v1/users/{user_id}", "PATCH"),
        ("/api/v1/users/{user_id}", "DELETE"),
        ("/api/v1/teams", "GET"),
        ("/api/v1/teams", "POST"),
        ("/api/v1/teams/{team_id}", "GET"),
        ("/api/v1/teams/{team_id}", "PUT"),
        ("/api/v1/teams/{team_id}", "DELETE"),
    }

    assert routes.isdisjoint(removed_routes)


def test_restful_replacement_routes_are_registered() -> None:
    routes = _registered_routes()

    expected_routes = {
        ("/health", "GET"),
        ("/health/oidc", "GET"),
        ("/api/v1/marketplace/version-control/init", "POST"),
        ("/api/v1/marketplace/version-control/repository", "GET"),
        ("/api/v1/marketplace/version-control/diff", "GET"),
        ("/api/v1/marketplace/version-control/commits", "GET"),
        ("/api/v1/marketplace/version-control/commits/{commit_id}/files", "GET"),
        ("/api/v1/marketplace/version-control/commits/{commit_id}/diff", "GET"),
        ("/api/v1/marketplace/version-control/files/history", "GET"),
        (
            "/api/v1/marketplace/version-control/files/history/{entry_id}/restore",
            "POST",
        ),
        ("/api/v1/knowledge-bases/{kb_id}/files/move", "POST"),
        ("/api/v1/knowledge-bases/{kb_id}/files/conflicts/preflight", "POST"),
        ("/api/v1/knowledge-bases/{kb_id}/files/upload", "POST"),
        ("/api/v1/knowledge-bases/{kb_id}/files/paste", "POST"),
        ("/api/v1/knowledge-bases/{kb_id}/files/extract", "POST"),
        (
            "/api/v1/marketplace/packages/{provider}/{package_id}/files/conflicts/preflight",
            "POST",
        ),
        (
            "/api/v1/marketplace/packages/{provider}/{package_id}/files/upload",
            "POST",
        ),
        (
            "/api/v1/marketplace/packages/{provider}/{package_id}/files/paste",
            "POST",
        ),
        (
            "/api/v1/marketplace/packages/{provider}/{package_id}/files/extract",
            "POST",
        ),
        ("/api/v1/knowledge-bases/{kb_id}/version-control/repository", "GET"),
        ("/api/v1/knowledge-bases/{kb_id}/version-control/init", "POST"),
        ("/api/v1/knowledge-bases/{kb_id}/version-control/clone", "POST"),
        ("/api/v1/knowledge-bases/{kb_id}/version-control/lfs", "POST"),
        ("/api/v1/knowledge-bases/{kb_id}/version-control/lfs", "GET"),
        ("/api/v1/knowledge-bases/{kb_id}/version-control/lfs/preview", "POST"),
        ("/api/v1/knowledge-bases/{kb_id}/version-control/lfs/convert", "POST"),
        ("/api/v1/knowledge-bases/{kb_id}/version-control/remote", "GET"),
        ("/api/v1/knowledge-bases/{kb_id}/version-control/remote", "PUT"),
        ("/api/v1/knowledge-bases/{kb_id}/version-control/operation/cancel", "POST"),
        ("/api/v1/knowledge-bases/{kb_id}/version-control/branches", "GET"),
        ("/api/v1/knowledge-bases/{kb_id}/version-control/branches/create", "POST"),
        ("/api/v1/knowledge-bases/{kb_id}/version-control/branches/switch", "POST"),
        ("/api/v1/knowledge-bases/{kb_id}/version-control/branches/rename", "POST"),
        ("/api/v1/knowledge-bases/{kb_id}/version-control/branches/delete", "POST"),
        ("/api/v1/knowledge-bases/{kb_id}/version-control/branches/publish", "POST"),
        ("/api/v1/marketplace/version-control/branches", "GET"),
        ("/api/v1/marketplace/version-control/branches/create", "POST"),
        ("/api/v1/marketplace/version-control/branches/switch", "POST"),
        ("/api/v1/marketplace/version-control/branches/rename", "POST"),
        ("/api/v1/marketplace/version-control/branches/delete", "POST"),
        ("/api/v1/marketplace/version-control/branches/publish", "POST"),
        ("/api/v1/marketplace/version-control/lfs", "POST"),
        ("/api/v1/marketplace/version-control/lfs", "GET"),
        ("/api/v1/marketplace/version-control/lfs/preview", "POST"),
        ("/api/v1/marketplace/version-control/lfs/convert", "POST"),
        ("/api/v1/marketplace/version-control/remote", "GET"),
        ("/api/v1/marketplace/version-control/remote", "PUT"),
        ("/api/v1/marketplace/version-control/operation/cancel", "POST"),
        ("/api/v1/marketplace/version-control/blob", "GET"),
        ("/api/v1/marketplace/version-control/discard", "POST"),
        ("/api/v1/marketplace/version-control/conflicts/mark-resolved", "POST"),
        ("/api/v1/marketplace/version-control/conflicts/abort", "POST"),
        ("/api/v1/marketplace/version-control/commits/revert", "POST"),
        ("/api/v1/knowledge-bases/{kb_id}/version-control/conflicts/mark-resolved", "POST"),
        ("/api/v1/knowledge-bases/{kb_id}/version-control/conflicts/abort", "POST"),
        ("/api/v1/knowledge-bases/{kb_id}/version-control/commits/revert", "POST"),
    }

    assert expected_routes.issubset(routes)


def test_collection_routes_do_not_use_trailing_slash() -> None:
    routes = _registered_routes()

    assert ("/api/v1/users/", "GET") not in routes
    assert ("/api/v1/workspaces/", "GET") not in routes
    assert ("/api/v1/users", "GET") in routes
    assert ("/api/v1/workspaces", "GET") in routes
