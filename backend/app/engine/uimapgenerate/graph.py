"""Stable, evidence-aware map format shared by Fast, Deep, and future APK inputs."""

from __future__ import annotations

from typing import Any


SCHEMA_VERSION = 2


def build_graph(units: list[dict[str, Any]], *, mode: str, source: str) -> dict[str, Any]:
    """Normalize legacy analyzer units into screens and navigations.

    A component is a screen candidate until runtime evidence can confirm that it
    corresponds to a distinct user-visible page. This prevents overstating what
    static source analysis knows.
    """
    screens = []
    transitions = []
    known = {unit.get("unit_id") for unit in units}

    for unit in sorted(units, key=lambda item: str(item.get("unit_id", ""))):
        screen_id = unit.get("unit_id")
        if not screen_id:
            continue
        screen = {
            "id": screen_id,
            "title": screen_id,
            "kind": "screen_candidate",
            "entry": bool(unit.get("is_entry_point")),
            "components": [{
                "name": screen_id,
                "type": unit.get("unit_type", "Unknown"),
                "file_path": unit.get("file_path"),
            }],
            "layouts": sorted(set(unit.get("all_layouts") or ([unit["layout"]] if unit.get("layout") else []))),
            "elements": [
                {
                    "id": element.get("id") or f"element_{index}",
                    "label": element.get("text") or element.get("id") or "Unnamed element",
                    "type": element.get("type") or element.get("element_type") or "Unknown",
                    "kind": "legacy_element",
                    "evidence": element.get("evidence") or {},
                }
                for index, element in enumerate(unit.get("ui_elements") or [])
                if isinstance(element, dict)
            ],
        }
        screens.append(screen)
        for element in unit.get("ui_elements") or []:
            interaction = element.get("interaction") or {}
            target = interaction.get("target_unit")
            if interaction.get("type") != "NAVIGATE_TO" or target not in known:
                continue
            evidence = element.get("evidence") or {}
            if not evidence and unit.get("file_path"):
                evidence = {"file_path": unit["file_path"], "method": "legacy_semantic"}
            transitions.append({
                "id": f"{screen_id}:{element.get('id', 'unknown')}:{target}",
                "from": screen_id,
                "to": target,
                "action": element.get("text") or element.get("id") or "Navigate",
                "trigger_id": element.get("id"),
                "verification": "source_rule" if evidence.get("method") == "explicit_intent" else "unverified",
                "evidence": [evidence] if evidence else [],
            })

    return {
        "schema_version": SCHEMA_VERSION,
        "mode": mode,
        "source": source,
        "screens": screens,
        "transitions": sorted(transitions, key=lambda item: item["id"]),
        "containments": [],
    }
