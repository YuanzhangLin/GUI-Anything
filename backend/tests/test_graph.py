import unittest
import json
from pathlib import Path

from app.engine.uimapgenerate.graph import build_graph
from app.services.uimap_report import build_report_from_map_json


class GraphTests(unittest.TestCase):
    def test_demo_contains_only_a_fixed_map(self):
        path = Path(__file__).resolve().parents[1] / "data" / "demo.json"
        demo = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(demo["source"], "android_repository")
        self.assertEqual(len(demo["screens"]), 13)
        self.assertEqual(len(demo["transitions"]), 20)
        self.assertEqual(len(demo["containments"]), 3)
        self.assertNotIn("units", demo)
        self.assertNotIn("discussion", demo)
        self.assertTrue(all(edge["evidence"] and edge["evidence"][0].get("file_path") for edge in demo["transitions"]))
        self.assertEqual({edge["trigger"]["status"] for edge in demo["transitions"]},
                         {"resolved", "event_only", "unknown"})
        manage_to_edit = [edge for edge in demo["transitions"]
                          if edge["from"].endswith("ManageActivity") and edge["to"].endswith("EditActivity")]
        self.assertEqual(len(manage_to_edit), 2)
        self.assertEqual({edge["trigger"]["event"] for edge in manage_to_edit},
                         {"menu_select", "item_click"})

    def test_navigation_keeps_source_evidence_and_rejects_unknown_target(self):
        units = [
            {
                "unit_id": "HomeActivity", "unit_type": "Activity", "is_entry_point": True,
                "file_path": "app/src/main/java/HomeActivity.java", "all_layouts": ["activity_home"],
                "ui_elements": [
                    {"id": "open", "text": "Open details", "interaction": {"type": "NAVIGATE_TO", "target_unit": "DetailActivity"},
                     "evidence": {"file_path": "app/src/main/java/HomeActivity.java", "line": 12, "method": "explicit_intent"}},
                    {"id": "unknown", "interaction": {"type": "NAVIGATE_TO", "target_unit": "MissingActivity"}},
                ],
            },
            {"unit_id": "DetailActivity", "unit_type": "Activity", "file_path": "app/src/main/java/DetailActivity.java", "ui_elements": []},
        ]
        graph = build_graph(units, mode="fast", source="android_repository")
        self.assertEqual(graph["schema_version"], 2)
        self.assertEqual(len(graph["screens"]), 2)
        self.assertEqual(len(graph["transitions"]), 1)
        self.assertEqual(graph["transitions"][0]["verification"], "source_rule")
        self.assertEqual(graph["transitions"][0]["evidence"][0]["line"], 12)
        report = build_report_from_map_json({"project_name": "sample", **graph})
        self.assertIn("HomeActivity → DetailActivity", report)
        self.assertIn("HomeActivity.java:12", report)


if __name__ == "__main__":
    unittest.main()
