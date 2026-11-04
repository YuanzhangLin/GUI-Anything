import json
import re
import tempfile
import unittest
from pathlib import Path

from app.cli import write_standalone_html


class CliTests(unittest.TestCase):
    def test_review_html_embeds_map_without_external_assets(self):
        graph = {
            "schema_version": 2,
            "project_name": "Example </script><script>alert(1)</script>",
            "screens": [],
            "transitions": [],
            "containments": [],
        }
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            output = Path(directory) / "map.html"
            write_standalone_html(graph, output)
            html = output.read_text(encoding="utf-8")
        payload = re.search(r'<script id="embedded-map" type="application/json">(.*?)</script>', html, re.S)
        self.assertIsNotNone(payload)
        self.assertEqual(json.loads(payload.group(1)), graph)
        self.assertNotIn('<script src=', html)
        self.assertNotIn('<link rel="stylesheet"', html)
        self.assertNotIn('</script><script>alert(1)', html)

    def test_runtime_review_html_embeds_trace_and_screenshot(self):
        graph = {"schema_version": 2, "project_name": "Fixture", "screens": [], "transitions": [], "containments": []}
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            base = Path(directory)
            assets = base / "trace"
            assets.mkdir()
            (assets / "001-after.png").write_bytes(b"\x89PNG\r\n")
            trace = {"schema_version": 1, "project_name": "Fixture", "steps": [
                {"index": 1, "edge_id": "example", "after": {"screenshot": "trace/001-after.png"}}]}
            output = base / "trace.html"
            write_standalone_html(graph, output, trace=trace, trace_base=base)
            html = output.read_text(encoding="utf-8")
        payload = re.search(r'<script id="embedded-trace" type="application/json">(.*?)</script>', html, re.S)
        self.assertIsNotNone(payload)
        embedded = json.loads(payload.group(1))
        self.assertTrue(embedded["steps"][0]["after"]["screenshot_data"].startswith("data:image/png;base64,"))


if __name__ == "__main__":
    unittest.main()
