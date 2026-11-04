import io
import json
import re
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from app.navigation.device import Observation
from app.navigation.observation import identify_screen, locate_trigger, parse_activity, parse_hierarchy
from app.navigation.planner import plan_path
from app.navigation.session import run_session
from app.navigation_cli import inspect_edge, main as navigation_main


def screen(name):
    return {"id": f"example.{name}", "title": name,
            "components": [{"name": f"example.{name}", "type": "Activity"}]}


def edge(source, target, element, *, status="resolved", event="click"):
    return {"id": f"{source}>{target}:{element}", "from": f"example.{source}", "to": f"example.{target}",
            "action": element, "trigger_id": element if status == "resolved" else None,
            "trigger": {"status": status, "event": event, "label": element},
            "evidence": [{"file_path": "src/A.java", "line": 10}]}


def observation(name, element):
    xml = f'<hierarchy><node resource-id="example:id/{element}" text="" content-desc="" class="android.widget.Button" clickable="true" bounds="[0,0][100,100]"/></hierarchy>'
    return Observation(f"example.{name}", xml, parse_hierarchy(xml))


class FakeDevice:
    def __init__(self, observations):
        self.observations = iter(observations)
        self.taps = []

    def observe(self):
        return next(self.observations)

    def tap(self, x, y):
        self.taps.append((x, y))


class NavigationTests(unittest.TestCase):
    def test_cli_run_writes_trace_and_standalone_replay(self):
        graph = {"schema_version": 2, "project_name": "Fixture", "screens": [screen("A"), screen("B")],
                 "transitions": [edge("A", "B", "open_b")], "containments": []}
        device = FakeDevice([observation("A", "open_b"), observation("B", "done")])
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            root = Path(directory)
            map_path = root / "map.json"
            trace_path = root / "trace.json"
            map_path.write_text(json.dumps(graph), encoding="utf-8")
            with patch("app.navigation_cli.AdbDevice", return_value=device), \
                 patch("app.navigation.session.time.sleep", return_value=None), \
                 redirect_stdout(io.StringIO()):
                code = navigation_main(["run", "--map", str(map_path), "--goal", "example.B",
                                        "--trace", str(trace_path), "--execute"])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(trace_path.read_text(encoding="utf-8"))["status"], "completed")
            html = trace_path.with_suffix(".html").read_text(encoding="utf-8")
            payload = re.search(r'<script id="embedded-trace" type="application/json">(.*?)</script>', html, re.S)
            self.assertIsNotNone(payload)
            self.assertEqual(json.loads(payload.group(1))["steps"][0]["status"], "verified")

    def test_inspect_edge_shows_source_context_without_leaving_repo(self):
        graph = {"transitions": [edge("A", "B", "open_b")]}
        graph["transitions"][0]["evidence"] = [{"file_path": "src/A.java", "line": 2, "method": "explicit_intent"}]
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            root = Path(directory)
            (root / "src").mkdir()
            (root / "src" / "A.java").write_text("one\nstartActivity(next);\nthree\n", encoding="utf-8")
            output = inspect_edge(graph, "A>B:open_b", root, context=1)
            self.assertIn("2 | startActivity(next);", output)
            graph["transitions"][0]["evidence"] = [{"file_path": "../outside.java", "line": 1}]
            self.assertIn("outside repository skipped", inspect_edge(graph, "A>B:open_b", root))

    def test_prefers_grounded_route_and_excludes_incorrect_review(self):
        graph = {"screens": [screen("A"), screen("B"), screen("C")], "transitions": [
            edge("A", "C", "uncertain", status="unknown"), edge("A", "B", "open_b"), edge("B", "C", "open_c")],
            "containments": [{"parent": "example.A", "child": "example.C"}]}
        path = plan_path(graph, "example.A", "example.C")
        self.assertEqual([item["to"] for item in path], ["example.B", "example.C"])
        path = plan_path(graph, "example.A", "example.C", reviews={"A>B:open_b": {"status": "incorrect"}})
        self.assertEqual([item["to"] for item in path], ["example.C"])

    def test_only_unique_exact_control_can_be_executed(self):
        nodes = parse_hierarchy('<hierarchy><node resource-id="example:id/open" clickable="true" bounds="[0,0][40,40]"/></hierarchy>')
        self.assertEqual(locate_trigger(edge("A", "B", "open"), nodes)["center"], [20, 20])
        self.assertIsNone(locate_trigger(edge("A", "B", "open", event="item_click"), nodes))
        self.assertIsNone(locate_trigger(edge("A", "B", "open"), nodes + nodes))
        self.assertEqual(parse_activity("mResumedActivity: ActivityRecord{a u0 example/.A t1}"), "example.A")

    def test_mismatch_blocks_edge_and_replans_from_observation(self):
        graph = {"project_name": "Fixture", "screens": [screen("A"), screen("B"), screen("C")],
                 "transitions": [edge("A", "B", "open_b"), edge("B", "C", "open_c"),
                                 edge("A", "C", "open_c_direct", status="event_only")], "containments": []}
        device = FakeDevice([observation("A", "open_b"), observation("A", "open_b")])
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            trace_path = Path(directory) / "trace.json"
            result = run_session(graph, device, "example.C", trace_path, max_steps=3, settle=lambda: None)
            self.assertTrue(trace_path.is_file())
            self.assertTrue((Path(directory) / "trace" / "001-after.xml").is_file())
        self.assertEqual(device.taps, [(50, 50)])
        self.assertEqual(result["steps"][0]["status"], "mismatch")
        self.assertEqual(result["steps"][1]["status"], "needs_review")
        self.assertEqual(result["status"], "needs_review")

    def test_verified_navigation_completes(self):
        graph = {"project_name": "Fixture", "screens": [screen("A"), screen("B")],
                 "transitions": [edge("A", "B", "open_b")], "containments": []}
        device = FakeDevice([observation("A", "open_b"), observation("B", "done")])
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            result = run_session(graph, device, "example.B", Path(directory) / "trace.json", settle=lambda: None)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["steps"][0]["status"], "verified")


if __name__ == "__main__":
    unittest.main()
