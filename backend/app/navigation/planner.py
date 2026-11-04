"""Deterministic path planning over a static UI map."""

from __future__ import annotations

import heapq
import itertools
from typing import Any


TRIGGER_COST = {"resolved": 1, "event_only": 3, "unknown": 6}


def plan_path(graph: dict[str, Any], start: str, goal: str, *,
              blocked: set[str] | None = None, reviews: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Prefer short, actionable paths; never treat containment as an action."""
    screens = {item["id"] for item in graph.get("screens", [])}
    if start not in screens or goal not in screens:
        raise ValueError("Start and goal must be screen IDs in the map")
    if start == goal:
        return []
    blocked = blocked or set()
    reviews = reviews or {}
    adjacency: dict[str, list[dict[str, Any]]] = {}
    for edge in graph.get("transitions", []):
        edge_id = edge.get("id")
        if not edge_id or edge_id in blocked or edge.get("from") not in screens or edge.get("to") not in screens:
            continue
        if (reviews.get(edge_id) or {}).get("status") == "incorrect":
            continue
        adjacency.setdefault(edge["from"], []).append(edge)
    for edges in adjacency.values():
        edges.sort(key=lambda item: item["id"])
    order = itertools.count()
    frontier: list[tuple[int, int, int, str, list[dict[str, Any]]]] = [(0, 0, next(order), start, [])]
    best: dict[str, tuple[int, int]] = {start: (0, 0)}
    while frontier:
        cost, hops, _, current, path = heapq.heappop(frontier)
        if current == goal:
            return path
        if (cost, hops) > best.get(current, (10**9, 10**9)):
            continue
        for edge in adjacency.get(current, []):
            status = (edge.get("trigger") or {}).get("status", "unknown")
            review = (reviews.get(edge["id"]) or {}).get("status")
            edge_cost = TRIGGER_COST.get(status, 6) + (2 if review == "questionable" else 0)
            candidate = (cost + edge_cost, hops + 1)
            target = edge["to"]
            if candidate < best.get(target, (10**9, 10**9)):
                best[target] = candidate
                heapq.heappush(frontier, (*candidate, next(order), target, path + [edge]))
    raise ValueError(f"No usable path from {start} to {goal}")
