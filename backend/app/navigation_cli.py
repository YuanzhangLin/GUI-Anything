"""Agent-facing commands for planning and ADB-backed step verification."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.cli import write_standalone_html
from app.navigation.device import AdbDevice
from app.navigation.planner import plan_path
from app.navigation.session import run_session


def _load_map(path: Path) -> dict:
    graph = json.loads(path.read_text(encoding="utf-8"))
    if graph.get("schema_version") != 2 or not isinstance(graph.get("screens"), list):
        raise ValueError("Expected a schema-v2 Map JSON")
    return graph


def _reviews(path: Path | None, graph: dict) -> dict:
    if not path:
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("project_name") != graph.get("project_name"):
        raise ValueError("Review file belongs to a different project")
    if data.get("source_commit") and graph.get("source_commit") and data["source_commit"] != graph["source_commit"]:
        raise ValueError("Review file belongs to a different source commit")
    return data.get("reviews", {}) if isinstance(data.get("reviews"), dict) else {}


def inspect_edge(graph: dict, edge_id: str, repo: Path, *, context: int = 6) -> str:
    """Return the map claim and bounded source excerpts, without leaving the repo."""
    edge = next((item for item in graph.get("transitions", []) if item.get("id") == edge_id), None)
    if edge is None:
        raise ValueError(f"Unknown edge ID: {edge_id}")
    root = repo.resolve()
    lines = [f"{edge['from']} -> {edge['to']}", f"Action: {edge.get('action')}",
             f"Trigger: {edge.get('trigger')}", f"Verification: {edge.get('verification')}"]
    for evidence in edge.get("evidence", []):
        relative = evidence.get("file_path")
        if not relative:
            continue
        source = (root / relative).resolve()
        if not source.is_relative_to(root):
            lines.append(f"Source outside repository skipped: {relative}")
            continue
        if not source.is_file():
            lines.append(f"Source unavailable: {relative}")
            continue
        text = source.read_text(encoding="utf-8", errors="replace").splitlines()
        line = evidence.get("line")
        if not isinstance(line, int) or line < 1:
            lines.append(f"Source: {relative} (no line number)")
            continue
        start, end = max(1, line - context), min(len(text), line + context)
        lines.append(f"Source: {relative}:{line} [{evidence.get('method', 'unknown')}]")
        lines.extend(f"{number:>5} | {text[number - 1]}" for number in range(start, end + 1))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Plan and verify navigation using a GUI-Anything Map")
    modes = parser.add_subparsers(dest="mode", required=True)
    plan = modes.add_parser("plan", help="Plan without a device")
    plan.add_argument("--map", type=Path, required=True)
    plan.add_argument("--from", dest="start", required=True, help="Exact screen ID")
    plan.add_argument("--to", dest="goal", required=True, help="Exact screen ID")
    plan.add_argument("--reviews", type=Path)
    inspect = modes.add_parser("inspect", help="Show evidence and source context for one path")
    inspect.add_argument("--map", type=Path, required=True)
    inspect.add_argument("--repo", type=Path, required=True)
    inspect.add_argument("--edge", required=True, help="Exact transition ID")
    inspect.add_argument("--context", type=int, default=6)
    run = modes.add_parser("run", help="Observe and perform uniquely grounded actions through ADB")
    run.add_argument("--map", type=Path, required=True)
    run.add_argument("--goal", required=True, help="Exact target screen ID")
    run.add_argument("--trace", type=Path, required=True)
    run.add_argument("--reviews", type=Path)
    run.add_argument("--serial")
    run.add_argument("--max-steps", type=int, default=12)
    run.add_argument("--execute", action="store_true", help="Required to send input actions to the device")
    args = parser.parse_args(argv)
    try:
        graph = _load_map(args.map)
        if args.mode == "inspect":
            if not 0 <= args.context <= 30:
                raise ValueError("context must be between 0 and 30 lines")
            print(inspect_edge(graph, args.edge, args.repo, context=args.context))
            return 0
        reviews = _reviews(args.reviews, graph)
        if args.mode == "plan":
            route = plan_path(graph, args.start, args.goal, reviews=reviews)
            for index, edge in enumerate(route, 1):
                evidence = (edge.get("evidence") or [{}])[0]
                source = f"{evidence.get('file_path', '?')}:{evidence.get('line') or '?'}"
                trigger = (edge.get("trigger") or {}).get("status", "unknown")
                print(f"{index}. {edge['from']} -> {edge['to']} | {edge.get('action')} | {trigger} | {source} | {edge['id']}")
            if not route:
                print("Already at the target screen")
            return 0
        if not args.execute:
            parser.error("run sends input actions; pass --execute after reviewing the target device and task")
        result = run_session(graph, AdbDevice(args.serial), args.goal, args.trace,
                             max_steps=args.max_steps, reviews=reviews)
        review_html = args.trace.with_suffix(".html")
        write_standalone_html(graph, review_html, trace=result, trace_base=args.trace.resolve().parent)
        print(json.dumps({"status": result["status"], "reason": result.get("reason"),
                          "steps": len(result["steps"]), "trace": str(args.trace.resolve()),
                          "review_html": str(review_html.resolve())}, ensure_ascii=False))
        return 0 if result["status"] == "completed" else 2
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(2, f"Navigation error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
