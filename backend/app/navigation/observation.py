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
    parents = {child: parent for parent in root.iter() for child in parent}
    indices = {}
    for item in root.iter("node"):
        match = BOUNDS.fullmatch(item.get("bounds", ""))
        if not match:
            continue
        x1, y1, x2, y2 = map(int, match.groups())
        indices[item] = len(result)
        result.append({
            "parent_index": indices.get(parents.get(item)),
            "resource_id": item.get("resource-id", ""),
            "text": item.get("text", ""),
            "description": item.get("content-desc", ""),
            "class": item.get("class", ""),
            "clickable": item.get("clickable") == "true",
            "enabled": item.get("enabled", "true") == "true",
            "focused": item.get("focused") == "true",
            "scrollable": item.get("scrollable") == "true",
            "long_clickable": item.get("long-clickable") == "true",
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


def _visible(node: dict[str, Any]) -> bool:
    return (node.get("enabled", True) and node["bounds"][2] > node["bounds"][0]
            and node["bounds"][3] > node["bounds"][1])


def trigger_present(edge: dict[str, Any], nodes: list[dict[str, Any]]) -> bool:
    """Also count disabled/ambiguous matches, so preparation cannot bypass them."""
    selector = (edge.get("trigger") or {}).get("selector")
    if isinstance(selector, dict):
        fields = {k: v for k, v in selector.items() if k != "target"}
        if (set(fields) - {"resource_id", "text", "description"}
                or any(not isinstance(v, str) or not v for v in fields.values())
                or selector.get("target", "self") not in {"self", "nearest_clickable_ancestor", "list_item"}):
            return True
        return not fields or any(all(n.get(k) == v for k, v in fields.items()) for n in nodes)
    trigger = edge.get("trigger_id")
    if selector is not None or not isinstance(trigger, str) or not trigger:
        return True
    return any(n["resource_id"] == trigger if "/" in trigger
               else n["resource_id"].rsplit("/", 1)[-1] == trigger for n in nodes)


def locate_trigger(edge: dict[str, Any], nodes: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Ground an exact ID or an explicit selector; never fall back to fuzzy text."""
    trigger_info = edge.get("trigger") or {}
    if (trigger_info.get("status") != "resolved" or trigger_info.get("event") not in {"click", "menu_select", "long_press", "item_click"}):
        return None
    selector = trigger_info.get("selector")
    if selector is None:
        if trigger_info.get("event") == "item_click":
            return None
        trigger = edge.get("trigger_id")
        if not trigger:
            return None
        candidates = [item for item in nodes if
                      (item["resource_id"] == trigger if "/" in trigger else item["resource_id"].rsplit("/", 1)[-1] == trigger)
                      and item["clickable"] and _visible(item)]
        return candidates[0] if len(candidates) == 1 else None
    allowed = {"resource_id", "text", "description", "target"}
    if not isinstance(selector, dict) or set(selector) - allowed:
        return None
    fields = {key: value for key, value in selector.items() if key != "target"}
    if not fields or any(not isinstance(value, str) or not value for value in fields.values()):
        return None
    target = selector.get("target", "self")
    if target not in {"self", "nearest_clickable_ancestor", "list_item"}:
        return None
    candidates = [item for item in nodes if all(item.get(key) == value for key, value in fields.items())
                  and _visible(item)]
    # Check uniqueness before walking parents: duplicate labels are ambiguous.
    if len(candidates) != 1:
        return None
    node = candidates[0]
    seen = set()
    if target == "list_item":
        if trigger_info.get("event") not in {"menu_select", "item_click"}:
            return None
        # AdapterView dispatches item clicks even when row.clickable is false.
        # Require an explicitly selected, enabled row directly under a ListView.
        while True:
            parent_index = node.get("parent_index")
            if not isinstance(parent_index, int) or parent_index in seen or not 0 <= parent_index < len(nodes):
                return None
            seen.add(parent_index)
            parent = nodes[parent_index]
            if not _visible(node) or not _visible(parent):
                return None
            if parent.get("class") == "android.widget.ListView":
                a, b = node["bounds"], parent["bounds"]
                bounds = [max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])]
                if bounds[2] <= bounds[0] or bounds[3] <= bounds[1]:
                    return None
                return {**node, "bounds": bounds,
                        "center": [(bounds[0] + bounds[2]) // 2, (bounds[1] + bounds[3]) // 2]}
            node = parent
    while not node["clickable"]:
        parent = node.get("parent_index")
        if target != "nearest_clickable_ancestor" or not isinstance(parent, int) or parent in seen or not 0 <= parent < len(nodes):
            return None
        seen.add(parent)
        node = nodes[parent]
        if not _visible(node):
            return None
    return node if _visible(node) else None
