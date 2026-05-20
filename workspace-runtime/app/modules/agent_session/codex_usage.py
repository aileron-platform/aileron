"""Helpers for normalizing Codex SDK usage payloads."""

from __future__ import annotations

from typing import Any


def codex_usage_totals(raw_response: dict[str, Any]) -> dict[str, Any]:
    """Return the total Codex usage bucket from supported raw response shapes."""
    token_usage = raw_response.get("token_usage")
    if isinstance(token_usage, dict):
        total = token_usage.get("total")
        if isinstance(total, dict):
            return {
                **total,
                "service_tier": total.get("service_tier", token_usage.get("service_tier")),
                "cost_usd": total.get("cost_usd", token_usage.get("cost_usd")),
            }
        return token_usage

    response = raw_response.get("response", {})
    if not isinstance(response, dict):
        return {}
    turn = response.get("turn", {})
    if not isinstance(turn, dict):
        return {}
    usage = turn.get("usage", {})
    if not isinstance(usage, dict):
        return {}
    costs = turn.get("costs", {})
    cost = (
        costs.get("total_cost", costs.get("total_cost_usd"))
        if isinstance(costs, dict)
        else None
    )
    if cost is None:
        return usage
    return {**usage, "cost_usd": cost}


def codex_context_usage(raw_response: dict[str, Any]) -> int | None:
    """Return Codex current context usage from the latest model response."""
    token_usage = raw_response.get("token_usage")
    if isinstance(token_usage, dict):
        last = token_usage.get("last")
        if isinstance(last, dict) and "total_tokens" in last:
            return last.get("total_tokens", 0)

        total = token_usage.get("total")
        if isinstance(total, dict) and "total_tokens" in total:
            return total.get("total_tokens", 0)

        if "total_tokens" in token_usage:
            return token_usage.get("total_tokens", 0)

    response = raw_response.get("response", {})
    if not isinstance(response, dict):
        return None
    turn = response.get("turn", {})
    if not isinstance(turn, dict):
        return None
    usage = turn.get("usage", {})
    if not isinstance(usage, dict):
        return None
    if "total_tokens" in usage:
        return usage["total_tokens"]
    return usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
