from __future__ import annotations

import os
from typing import Any, Dict, Optional

from app.services.code_manager import CodeManager
from app.engine.uimapgenerate.src.analyzer.project_analyzer import ProjectAnalyzer
from app.engine.uimapgenerate.src.analyzer.topology_builder import TopologyBuilder
from app.engine.uimapgenerate.src.llm.llm_client import LLMClient


def _detect_main_source_set(repo_root: str) -> str:
    """
    Heuristic detection for Android main source set directory.
    Typical: app/src/main
    """
    candidates = [
        os.path.join(repo_root, "app", "src", "main"),
        os.path.join(repo_root, "src", "main"),
    ]
    for c in candidates:
        if os.path.exists(os.path.join(c, "AndroidManifest.xml")):
            return os.path.relpath(c, repo_root)
        if os.path.exists(os.path.join(c, "res")):
            return os.path.relpath(c, repo_root)

    # fallback: first match of */src/main that contains AndroidManifest.xml
    for root, dirs, files in os.walk(repo_root):
        if root.endswith(os.path.join("src", "main")) and "AndroidManifest.xml" in files:
            return os.path.relpath(root, repo_root)
        # pruning
        if any(p in root for p in (".git", "build", ".idea", "node_modules")):
            dirs[:] = []

    return "app/src/main"


def _sort_units_by_inheritance_depth(units: list[dict], class_index: dict) -> list[str]:
    def get_inheritance_depth(unit_id: str) -> int:
        depth = 0
        curr = unit_id
        visited = set()
        while curr in class_index:
            if curr in visited:
                break
            visited.add(curr)
            parent = class_index[curr].get("super_class")
            if not parent or parent not in class_index:
                break
            depth += 1
            curr = parent
        return depth

    return sorted([u["unit_id"] for u in units], key=get_inheritance_depth)


def generate_uimap(
    *,
    app_id: str,
    project_config: Optional[Dict[str, Any]] = None,
    secrets_path: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Real UI Map generation entrypoint.

    Input:
    - app_id: project id in GUI-Anything
    - project_config: optional override, otherwise inferred from downloaded repo path

    Output:
    - dict compatible with frontend `parseAndroidJson` (expects `units` list)
    """
    if project_config is None:
        code_manager = CodeManager()
        repo_root = code_manager.get_repo_path(app_id)
        if not os.path.exists(repo_root):
            raise FileNotFoundError(
                f"Repo not found for app_id={app_id}. Expected at {repo_root}."
            )
        main_source_set = _detect_main_source_set(repo_root)
        project_config = {
            "name": app_id,
            "root": repo_root,
            "main_source_set": main_source_set,
        }

    analyzer = ProjectAnalyzer(project_config=project_config)
    analyzer.analyze()
    all_units = analyzer.results

    llm_client = LLMClient(secrets_path) if secrets_path else LLMClient()
    builder = TopologyBuilder(all_units, llm_client)
    sorted_unit_ids = _sort_units_by_inheritance_depth(all_units, analyzer.class_index)
    builder.build_parallel(sorted_unit_ids, max_workers=8)

    return {"project_name": project_config.get("name", app_id), "units": all_units}

