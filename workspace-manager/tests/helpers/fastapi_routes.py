"""FastAPI route inspection helpers."""

from __future__ import annotations

from collections.abc import Sequence

from fastapi.routing import APIRoute, iter_route_contexts
from starlette.routing import BaseRoute


def registered_api_route_methods(
    routes: Sequence[BaseRoute],
) -> set[tuple[str, str]]:
    """Return flattened API route path and method pairs."""
    return {
        (route_context.path, method)
        for route_context in iter_route_contexts(routes)
        if isinstance(route_context.original_route, APIRoute)
        and route_context.path is not None
        for method in route_context.methods or ()
        if method not in {"HEAD", "OPTIONS"}
    }


def registered_api_route_paths(routes: Sequence[BaseRoute]) -> set[str]:
    """Return flattened API route paths."""
    return {
        route_context.path
        for route_context in iter_route_contexts(routes)
        if isinstance(route_context.original_route, APIRoute)
        and route_context.path is not None
    }
