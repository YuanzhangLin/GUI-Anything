"""Plan, observe, ground, act, and verify one map-guided navigation task."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from app.navigation.device import Observation
from app.navigation.observation import identify_screen, locate_trigger, trigger_present
from app.navigation.planner import plan_path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_session(graph: dict[str, Any], device: Any, goal: str, trace_path: Path, *,
                max_steps: int = 12, reviews: dict[str, Any] | None = None,
                settle: Callable[[], None] | None = None) -> dict[str, Any]:
    """Execute only uniquely grounded taps; stop with evidence when uncertain."""
    if max_steps < 1:
        raise ValueError("max_steps must be positive")
    trace_path = trace_path.resolve()
    assets = trace_path.with_suffix("")
    assets.mkdir(parents=True, exist_ok=True)
    trace: dict[str, Any] = {
        "schema_version": 1,
        "project_name": graph.get("project_name"),
        "source_commit": graph.get("source_commit"),
        "goal": goal,
        "status": "running",
        "started_at": _now(),
        "steps": [],
    }
    blocked: set[str] = set()
    prepared: set[str] = set()
    settle = settle or (lambda: time.sleep(1))

    def save() -> None:
        trace["updated_at"] = _now()
        trace_path.parent.mkdir(parents=True, exist_ok=True)
        trace_path.write_text(json.dumps(trace, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def capture(index: int, phase: str) -> tuple[Observation, str | None]:
        observation = device.observe()
        stem = f"{index:03d}-{phase}"
        xml_path = assets / f"{stem}.xml"
        xml_path.write_text(observation.hierarchy, encoding="utf-8")
        if observation.screenshot:
            (assets / f"{stem}.png").write_bytes(observation.screenshot)
        screen = identify_screen(graph, observation.activity, observation.nodes)
        return observation, screen

    try:
        observation, current = capture(0, "start")
        trace["start"] = {"activity": observation.activity, "screen": current,
                          "hierarchy": f"{assets.name}/000-start.xml",
                          "screenshot": f"{assets.name}/000-start.png" if observation.screenshot else None}
        save()
        if not current:
            trace["status"] = "needs_review"
            trace["reason"] = "Current screen could not be identified uniquely from the Activity"
            save()
            return trace
        for index in range(1, max_steps + 1):
            if current == goal:
                trace["status"] = "completed"
                save()
                return trace
            try:
                route = plan_path(graph, current, goal, blocked=blocked, reviews=reviews)
            except ValueError as exc:
                trace["status"] = "needs_review"
                trace["reason"] = str(exc)
                save()
                return trace
            edge = route[0]
            target = edge["to"]
            action_edge = edge
            target_node = locate_trigger(edge, observation.nodes)
            preparation = edge.get("preparation")
            if (not target_node and not trigger_present(edge, observation.nodes)
                    and (edge.get("trigger") or {}).get("status") == "resolved"
                    and isinstance(preparation, dict) and preparation.get("evidence")
                    and edge["id"] not in prepared):
                prepared.add(edge["id"])
                preparation_node = locate_trigger(preparation, observation.nodes)
                preparation_trigger = preparation.get("trigger") or {}
                menu_key = (preparation_trigger.get("status") == "resolved"
                            and preparation_trigger.get("event") == "key_menu"
                            and not preparation_trigger.get("selector") and not preparation.get("trigger_id"))
                if preparation_node or menu_key:
                    action_edge = preparation
                    target_node = preparation_node
                    target = current
            is_preparation = action_edge is not edge
            is_menu_key = is_preparation and (action_edge.get("trigger") or {}).get("event") == "key_menu"
            step: dict[str, Any] = {
                "index": index, "edge_id": edge["id"], "from": current, "to": target,
                "phase": "prepare" if is_preparation else "navigate",
                "intended_destination": edge["to"],
                "action": action_edge.get("action"), "trigger": action_edge.get("trigger"),
                "evidence": action_edge.get("evidence", []),
                "before": {"activity": observation.activity, "screen": current,
                           "hierarchy": f"{assets.name}/{index - 1:03d}-{'start' if index == 1 else 'after'}.xml",
                           "screenshot": f"{assets.name}/{index - 1:03d}-{'start' if index == 1 else 'after'}.png" if observation.screenshot else None},
                "status": "planned", "at": _now(),
            }
            trace["steps"].append(step)
            if not target_node and not is_menu_key:
                step["status"] = "needs_review"
                step["reason"] = "Trigger is unknown, absent, or not unique in the current UI hierarchy"
                trace["status"] = "needs_review"
                trace["reason"] = step["reason"]
                save()
                return trace
            gesture = "key_menu" if is_menu_key else "long_press" if (action_edge.get("trigger") or {}).get("event") == "long_press" else "tap"
            step["input"] = {"gesture": gesture, "keycode": 82} if is_menu_key else {
                "gesture": gesture, "x": target_node["center"][0], "y": target_node["center"][1],
                "resource_id": target_node["resource_id"]}
            save()
            if is_menu_key:
                device.open_menu()
            elif gesture == "long_press":
                device.long_press(*target_node["center"])
            else:
                device.tap(*target_node["center"])
            step["status"] = "acted"
            save()
            settle()
            observation, observed = capture(index, "after")
            step["after"] = {"activity": observation.activity, "screen": observed,
                             "hierarchy": f"{assets.name}/{index:03d}-after.xml",
                             "screenshot": f"{assets.name}/{index:03d}-after.png" if observation.screenshot else None}
            if is_preparation and (observed != target or not locate_trigger(edge, observation.nodes)):
                step["status"] = "needs_review"
                step["reason"] = "Preparation did not expose a unique target on the same screen"
                trace["status"] = "needs_review"
                trace["reason"] = step["reason"]
                save()
                return trace
            if observed == target:
                step["status"] = "verified"
                current = observed
            else:
                step["status"] = "mismatch"
                step["reason"] = "Observed page differs from the map target"
                blocked.add(edge["id"])
                if not observed:
                    trace["status"] = "needs_review"
                    trace["reason"] = "Post-action screen could not be identified uniquely"
                    save()
                    return trace
                current = observed
            save()
            if current == goal:
                trace["status"] = "completed"
                save()
                return trace
        trace["status"] = "needs_review"
        trace["reason"] = f"Stopped at the {max_steps}-step limit"
        save()
        return trace
    except (RuntimeError, OSError, ValueError) as exc:
        trace["status"] = "error"
        trace["reason"] = str(exc)
        save()
        return trace
