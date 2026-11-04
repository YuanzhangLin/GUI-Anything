"""Parse Android UI hierarchy and ground a proposed trigger conservatively."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any


BOUNDS = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")
ACTIVITY = re.compile(r"(?:mResumedActivity|topResumedActivity|mCurrentFocus).*?\s([\w.]+)/([\w.$]+)")


def parse_activity(dumpsys: str) -> str | None:
    match = ACTIVITY.search(dumpsys)
    if not match:
        return None
    package, name = match.groups()
    return package + name if name.startswith(".") else name if "." in name else f"{package}.{name}"


def parse_hierarchy(xml: str) -> list[dict[str, Any]]:
    root = ET.fromstring(xml)
    result = []
    for item in root.iter("node"):
        match = BOUNDS.fullmatch(item.get("bounds", ""))
        if not match:
            continue
        x1, y1, x2, y2 = map(int, match.groups())
        result.append({
            "resource_id": item.get("resource-id", ""),
            "text": item.get("text", ""),
            "description": item.get("content-desc", ""),
            "class": item.get("class", ""),
            "clickable": item.get("clickable") == "true",
            "bounds": [x1, y1, x2, y2],
            "center": [(x1 + x2) // 2, (y1 + y2) // 2],
        })
    return result


def identify_screen(graph: dict[str, Any], activity: str | None, nodes: list[dict[str, Any]]) -> str | None:
    """Identify only a unique component match; UI text is too weak for automatic confirmation."""
    if not activity:
        return None
    matches = [screen["id"] for screen in graph.get("screens", [])
               if any(component.get("name") == activity for component in screen.get("components", []))]
    return matches[0] if len(matches) == 1 else None


def locate_trigger(edge: dict[str, Any], nodes: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Auto-ground only a unique, visible, clickable node with the exact resource ID."""
    trigger_info = edge.get("trigger") or {}
    if (trigger_info.get("status") != "resolved" or trigger_info.get("event") not in {"click", "menu_select", "long_press"} or not edge.get("trigger_id")):
        return None
    trigger = edge["trigger_id"]
    candidates = [item for item in nodes if item["resource_id"].rsplit("/", 1)[-1] == trigger
                  and item["clickable"] and item["bounds"][2] > item["bounds"][0]
                  and item["bounds"][3] > item["bounds"][1]]
    return candidates[0] if len(candidates) == 1 else None
