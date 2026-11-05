"""Local, model-free map generation for Agent skills and human review."""

from __future__ import annotations

import argparse
import base64
import copy
import json
from pathlib import Path

from app.engine.uimapgenerate.fast import generate_fast_map


SOURCE_ROOT = Path(__file__).resolve().parents[2]
WEBSITE = (SOURCE_ROOT / "website") if (SOURCE_ROOT / "website" / "viewer.html").is_file() else (SOURCE_ROOT / "app" / "website")


def write_standalone_html(graph: dict, destination: Path, *, trace: dict | None = None,
                          trace_base: Path | None = None) -> None:
    """Embed the graph and viewer assets in one file that opens without a server."""
    template = (WEBSITE / "viewer.html").read_text(encoding="utf-8")
    styles = (WEBSITE / "viewer.css").read_text(encoding="utf-8")
    script = (WEBSITE / "viewer.js").read_text(encoding="utf-8")
    i18n = (WEBSITE / "i18n.js").read_text(encoding="utf-8")
    payload = json.dumps(graph, ensure_ascii=False).replace("<", "\\u003c")
    template = template.replace('<link rel="icon" href="./mark.svg" type="image/svg+xml" />', "")
    template = template.replace('<link rel="stylesheet" href="./viewer.css" />', f"<style>\n{styles}\n</style>")
    template = template.replace('<script id="embedded-map" type="application/json"></script>',
                                f'<script id="embedded-map" type="application/json">{payload}</script>')
    if trace is not None:
        embedded_trace = copy.deepcopy(trace)
        if trace_base is not None:
            base = trace_base.resolve()
            observations = [embedded_trace.get("start") or {}]
            for step in embedded_trace.get("steps", []):
                observations.extend([step.get("before") or {}, step.get("after") or {}])
            for observation in observations:
                image = observation.get("screenshot")
                if image:
                    path = (base / image).resolve()
                    if path.is_relative_to(base) and path.is_file():
                        observation["screenshot_data"] = "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")
        trace_payload = json.dumps(embedded_trace, ensure_ascii=False).replace("<", "\\u003c")
        template = template.replace('<script id="embedded-trace" type="application/json"></script>',
                                    f'<script id="embedded-trace" type="application/json">{trace_payload}</script>')
    template = template.replace('<script src="./i18n.js" defer></script>', f"<script>\n{i18n}\n</script>")
    template = template.replace('<script src="./viewer.js" defer></script>', f"<script>\n{script}\n</script>")
    template = template.replace('href="./index.html"', 'href="#"').replace('<img src="./mark.svg" alt="" /> ', '')
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(template, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate an Android UI Map and a self-contained review page")
    parser.add_argument("--repo", type=Path, required=True, help="Android source or JADX output directory")
    parser.add_argument("--output", type=Path, required=True, help="Destination Map JSON")
    parser.add_argument("--no-html", action="store_true", help="Do not write the companion review HTML")
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    if not repo.is_dir():
        parser.error(f"Repository does not exist: {repo}")
    graph = generate_fast_map(repo.name, repo_path=repo)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(graph, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Map JSON: {output}")
    print(f"Screens: {len(graph['screens'])}; paths: {len(graph['transitions'])}; containments: {len(graph['containments'])}")
    if not args.no_html:
        html = output.with_suffix(".html")
        write_standalone_html(graph, html)
        print(f"Review HTML: {html}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
