"""Fast Android source mapper: Manifest pages and explicit code navigation only."""

from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from app.engine.uimapgenerate.graph import SCHEMA_VERSION
from app.services.code_manager import CodeManager


ANDROID = "{http://schemas.android.com/apk/res/android}"
APP = "{http://schemas.android.com/apk/res-auto}"
INTENT = re.compile(r"\bIntent\s*\([^;\n]*?,\s*([\w.]+)\s*(?:::class\.java|::class|\.class)\s*\)")
IMPORT = re.compile(r"(?m)^\s*import\s+([\w.]+)\s*;?")
ADD_FRAGMENT = re.compile(r"\baddFragment\s*\(\s*new\s+(\w+)\s*\(\s*\)\s*,\s*getResources\(\)\.getString\(R\.string\.(\w+)\)")
MENU_CASE = re.compile(r"case\s+R\.id\.(\w+)\s*:")
METHOD_HEAD = re.compile(r"\b(?:public|protected|private)\s+(?:static\s+)?[\w<>?.\[\]]+\s+(\w+)\s*\([^;{}]*\)\s*\{")
PACKAGE = re.compile(r"(?m)^\s*package\s+([\w.]+)\s*;?")
CLASS = re.compile(r"\bclass\s+([A-Za-z_][\w]*)\b")
LAYOUT = re.compile(r"\bR\.layout\.([A-Za-z_][\w]*)")
MENU = re.compile(r"\bR\.menu\.([A-Za-z_][\w]*)")
INTERACTIVE_TAGS = ("Button", "EditText", "Switch", "CheckBox", "RadioButton", "Spinner", "SeekBar", "SearchView", "TabLayout", "RecyclerView", "ListView")
DISPLAY_TAGS = ("TextView", "ImageView", "ProgressBar")


def _fqcn(name: str, package: str) -> str:
    if name.startswith("."):
        return package + name
    if "." not in name:
        return f"{package}.{name}" if package else name
    return name


def _manifest_paths(repo: Path) -> list[Path]:
    return sorted(p for p in repo.rglob("AndroidManifest.xml") if "build" not in p.parts and ".git" not in p.parts and ("src" in p.parts or "resources" in p.parts))


def _source_index(repo: Path) -> dict[str, Path]:
    result = {}
    for root, dirs, files in os.walk(repo):
        dirs[:] = sorted(d for d in dirs if d not in {"build", ".git", "test", "androidTest", "node_modules", ".gradle"})
        for filename in sorted(files):
            path = Path(root) / filename
            if path.suffix not in (".java", ".kt"):
                continue
            try:
                with path.open("r", encoding="utf-8") as source_file:
                    prefix = source_file.read(8192)
            except (UnicodeError, OSError):
                continue
            package = PACKAGE.search(prefix)
            class_name = CLASS.search(prefix)
            name = class_name.group(1) if class_name else path.stem
            result[_fqcn(name, package.group(1) if package else "")] = path
    return result


def _manifest_name(raw_name: str, package: str, sources: dict) -> str:
    name = _fqcn(raw_name, package)
    if name in sources or package:
        return name
    # Modern manifests can omit package; resolve a unique matching source class.
    suffix = "." + raw_name.lstrip(".")
    matches = [candidate for candidate in sources if candidate.endswith(suffix)]
    return matches[0] if len(matches) == 1 else name


def _string_resources(repo: Path) -> dict[str, str]:
    values = {}
    for path in sorted(repo.rglob("res/values/strings.xml"), key=lambda item: ("main" not in item.parts, item.as_posix())):
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError:
            continue
        for element in root.findall("string"):
            name = element.get("name")
            if name and name not in values:
                values[name] = "".join(element.itertext()).strip()
    return values


def _title(label: str | None, fallback: str, strings: dict[str, str]) -> str:
    if not label:
        return fallback
    seen = set()
    while label.startswith("@string/"):
        key = label.split("/", 1)[1]
        if key in seen:
            return fallback
        seen.add(key)
        label = strings.get(key, fallback)
    if label.startswith("@"):
        return fallback
    return label


def _resolve_target(raw: str, source_id: str, code: str, candidates: dict) -> str | None:
    if raw in candidates:
        return raw
    imports = {item.rsplit(".", 1)[-1]: item for item in IMPORT.findall(code)}
    imported = imports.get(raw)
    if imported in candidates:
        return imported
    local = _fqcn(raw, source_id.rpartition(".")[0])
    if local in candidates:
        return local
    matches = [item for item in candidates if item.endswith("." + raw)]
    return matches[0] if len(matches) == 1 else None


def _intent_launched(code: str, match: re.Match[str]) -> bool:
    prefix = code[max(0, match.start() - 120):match.start()]
    if re.search(r"startActivity\s*\(\s*new\s*$", prefix):
        return True
    assignment = re.search(r"\b(?:Intent\s+)?(\w+)\s*=\s*new\s*$", prefix)
    if not assignment:
        return False
    tail = code[match.end():match.end() + 700]
    launch = re.search(r"\bstartActivity\s*\(\s*" + re.escape(assignment.group(1)) + r"\s*\)", tail)
    return bool(launch and tail[:launch.start()].count("\n") <= 18)


def _menu_labels(repo: Path, strings: dict[str, str]) -> dict[str, str]:
    labels = {}
    for path in sorted(repo.rglob("res/menu/*.xml")):
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError:
            continue
        for item in root.iter("item"):
            item_id = item.get(ANDROID + "id", "").rsplit("/", 1)[-1]
            if item_id and item_id not in labels:
                labels[item_id] = _title(item.get(ANDROID + "title"), item_id, strings)
    return labels


def _trigger_for_intent(code: str, position: int, target_title: str,
                        menu_labels: dict[str, str]) -> tuple[str, str | None, dict[str, str]]:
    methods = list(METHOD_HEAD.finditer(code, 0, position))
    method = methods[-1] if methods else None
    if method:
        name = method.group(1)
        if name == "onOptionsItemSelected":
            cases = list(MENU_CASE.finditer(code, method.end(), position))
            if cases:
                element_id = cases[-1].group(1)
                label = menu_labels.get(element_id, element_id.replace("_", " "))
                return (f"点击“{label}”菜单项 → {target_title}", element_id,
                        {"status": "resolved", "event": "menu_select", "label": label})
        elif name == "onItemClick":
            return (f"点击列表项 → {target_title}", None,
                    {"status": "event_only", "event": "item_click", "label": "列表项"})
        elif name == "onItemLongClick":
            return (f"长按列表项 → {target_title}", None,
                    {"status": "event_only", "event": "item_long_press", "label": "列表项"})
        elif name == "onLongClick":
            return (f"长按控件 → {target_title}", None,
                    {"status": "event_only", "event": "long_press", "label": "具体控件未确认"})
    scope_start = method.end() if method else 0
    listeners = list(re.compile(r"\b(\w+)\.setOnClickListener\s*\(").finditer(code, scope_start, position))
    if listeners:
        listener = listeners[-1]
        body = code[listener.end():position]
        if body.count("{") > body.count("}"):
            variable = listener.group(1)
            bindings = list(re.compile(r"\b" + re.escape(variable) + r"\s*=\s*findViewById\s*\(\s*R\.id\.(\w+)").finditer(
                code, scope_start, listener.start()))
            if bindings:
                element_id = bindings[-1].group(1)
                return (f"点击控件 {element_id} → {target_title}", element_id,
                        {"status": "resolved", "event": "click", "label": element_id})
            return (f"点击控件 → {target_title}", None,
                    {"status": "event_only", "event": "click", "label": "具体控件未确认"})
    return (f"代码跳转 → {target_title}", None,
            {"status": "unknown", "event": "unknown", "label": "触发方式未定位"})


def _resource_files(repo: Path, folder: str) -> dict[str, Path]:
    result = {}
    for path in sorted(repo.rglob(f"res/{folder}/*.xml"), key=lambda item: ("main" not in item.parts, item.as_posix())):
        result.setdefault(path.stem, path)
    return result


def _elements_for_screen(repo: Path, layouts: list[str], menu_names: list[str],
                         layout_files: dict[str, Path], menu_files: dict[str, Path],
                         strings: dict[str, str]) -> list[dict[str, Any]]:
    elements: dict[str, dict[str, Any]] = {}
    visited_layouts = set()
    visited_menus = set()

    def add_element(element: ET.Element, path: Path, kind: str) -> None:
        raw_id = element.get(ANDROID + "id", "")
        element_id = raw_id.rsplit("/", 1)[-1] if "/" in raw_id else ""
        if not element_id or element_id in elements:
            return
        tag = element.tag.rsplit("}", 1)[-1].rsplit(".", 1)[-1]
        label = (element.get(ANDROID + "contentDescription") or element.get(ANDROID + "text")
                 or element.get(ANDROID + "title") or element.get(ANDROID + "hint"))
        elements[element_id] = {
            "id": element_id,
            "label": _title(label, element_id.replace("_", " "), strings),
            "type": tag,
            "kind": kind,
            "evidence": {"file_path": path.relative_to(repo).as_posix(), "method": "resource_xml"},
        }

    def read_menu(name: str) -> None:
        if name in visited_menus or name not in menu_files:
            return
        visited_menus.add(name)
        path = menu_files[name]
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError:
            return
        for item in root.iter("item"):
            add_element(item, path, "menu_item")

    def read_layout(name: str) -> None:
        if name in visited_layouts or name not in layout_files:
            return
        visited_layouts.add(name)
        path = layout_files[name]
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError:
            return
        for element in root.iter():
            tag = element.tag.rsplit("}", 1)[-1].rsplit(".", 1)[-1]
            interactive = (tag.endswith(INTERACTIVE_TAGS)
                           or element.get(ANDROID + "clickable") == "true"
                           or bool(element.get(ANDROID + "onClick")))
            if interactive:
                add_element(element, path, "layout_control")
            elif tag.endswith(DISPLAY_TAGS):
                add_element(element, path, "display_element")
            include = element.get("layout", "")
            if include.startswith("@layout/"):
                read_layout(include.split("/", 1)[1])
            menu = element.get(APP + "menu", "")
            if menu.startswith("@menu/"):
                read_menu(menu.split("/", 1)[1])

    for name in layouts:
        read_layout(name)
    for name in menu_names:
        read_menu(name)
    priority = {"layout_control": 0, "menu_item": 1, "display_element": 2}
    return sorted(elements.values(), key=lambda item: (priority.get(item["kind"], 3), item["label"], item["id"]))


def generate_fast_map(app_id: str, *, repo_path: str | Path | None = None) -> dict[str, Any]:
    """Build a deterministic map without importing or calling any model client."""
    repo = Path(repo_path) if repo_path is not None else Path(CodeManager().get_repo_path(app_id))
    if not repo.is_dir():
        raise FileNotFoundError(f"Repository for {app_id} has not been downloaded")
    manifests = _manifest_paths(repo)
    if not manifests:
        raise ValueError("No AndroidManifest.xml found in an Android source set")

    sources = _source_index(repo)
    strings = _string_resources(repo)
    menu_labels = _menu_labels(repo, strings)
    screens: dict[str, dict[str, Any]] = {}
    for manifest in manifests:
        root = ET.parse(manifest).getroot()
        package = root.get("package", "")
        application = root.find("application")
        application_label = application.get(ANDROID + "label") if application is not None else None
        for activity in root.findall("./application/activity"):
            raw_name = activity.get(ANDROID + "name")
            if not raw_name:
                continue
            name = _manifest_name(raw_name, package, sources)
            if name in screens:
                continue
            source = sources.get(name)
            entry = any(
                any(a.get(ANDROID + "name") == "android.intent.action.MAIN" for a in filt.findall("action"))
                and any(c.get(ANDROID + "name") == "android.intent.category.LAUNCHER" for c in filt.findall("category"))
                for filt in activity.findall("intent-filter")
            )
            try:
                code = source.read_text(encoding="utf-8") if source else ""
            except (UnicodeError, OSError):
                code = ""
            layouts = sorted(set(LAYOUT.findall(code)))
            screens[name] = {
                "id": name,
                "title": _title(activity.get(ANDROID + "label") or (application_label if entry else None), name.rsplit(".", 1)[-1], strings),
                "kind": "screen_candidate",
                "entry": entry,
                "components": [{
                    "name": name,
                    "type": "Activity",
                    "file_path": source.relative_to(repo).as_posix() if source else manifest.relative_to(repo).as_posix(),
                }],
                "layouts": layouts,
            }
    if not screens:
        raise ValueError("No Activity declarations found in AndroidManifest.xml")

    transitions = []
    containments = []
    from_apk = (repo / "source.apk").is_file()
    verification = "decompiled_rule" if from_apk else "source_rule"

    # ViewPager tab declarations create user-visible pages even when the app
    # does not use Android Navigation XML.
    for activity_id, activity in list(screens.items()):
        source = sources.get(activity_id)
        if not source:
            continue
        try:
            code = source.read_text(encoding="utf-8")
        except (UnicodeError, OSError):
            continue
        for match in ADD_FRAGMENT.finditer(code):
            fragment_id = _resolve_target(match.group(1), activity_id, code, sources)
            if not fragment_id:
                continue
            title = strings.get(match.group(2), fragment_id.rsplit(".", 1)[-1])
            screens.setdefault(fragment_id, {
                "id": fragment_id, "title": title, "kind": "screen_candidate", "entry": False,
                "components": [{"name": fragment_id, "type": "Fragment", "file_path": sources[fragment_id].relative_to(repo).as_posix()}],
                "layouts": [],
            })
            evidence = {"file_path": source.relative_to(repo).as_posix(), "line": code.count("\n", 0, match.start()) + 1, "method": "viewpager_tab"}
            containments.append({
                "id": f"{activity_id}:hosts-tab:{fragment_id}",
                "parent": activity_id, "child": fragment_id, "kind": "tab_host",
                "verification": verification, "evidence": [evidence],
            })
            transitions.append({
                "id": f"{activity_id}:tab:{fragment_id}", "from": activity_id, "to": fragment_id,
                "action": f"切换到“{title}”标签", "trigger_id": None, "verification": verification,
                "trigger": {"status": "event_only", "event": "tab_select", "label": title},
                "evidence": [evidence],
            })
    # Android Navigation XML describes Fragment destinations and explicit
    # actions without requiring a model to guess the user's route.
    for nav_path in sorted(repo.rglob("res/navigation/*.xml")):
        try:
            nav_root = ET.parse(nav_path).getroot()
        except ET.ParseError:
            continue
        destinations = {}
        for destination in nav_root.iter():
            if destination.tag.rsplit("}", 1)[-1] not in {"fragment", "activity"}:
                continue
            resource_id = destination.get(ANDROID + "id", "").rsplit("/", 1)[-1]
            class_name = destination.get(ANDROID + "name", "")
            if not resource_id or not class_name:
                continue
            screen_id = _manifest_name(class_name, "", sources)
            destinations[resource_id] = screen_id
            if screen_id not in screens:
                source = sources.get(screen_id)
                screens[screen_id] = {
                    "id": screen_id, "title": _title(destination.get(ANDROID + "label"), screen_id.rsplit(".", 1)[-1], strings),
                    "kind": "screen_candidate", "entry": False,
                    "components": [{"name": screen_id, "type": "Fragment",
                                    "file_path": source.relative_to(repo).as_posix() if source else nav_path.relative_to(repo).as_posix()}],
                    "layouts": [],
                }
        for destination in nav_root.iter():
            source_resource = destination.get(ANDROID + "id", "").rsplit("/", 1)[-1]
            source_id = destinations.get(source_resource)
            if not source_id:
                continue
            for action in destination.findall("action"):
                target_resource = action.get(APP + "destination", "").rsplit("/", 1)[-1]
                target_id = destinations.get(target_resource)
                if target_id and target_id != source_id:
                    transitions.append({
                        "id": f"{source_id}:navigation:{target_id}", "from": source_id, "to": target_id,
                        "action": action.get(ANDROID + "id", "").rsplit("/", 1)[-1] or f"Open {screens[target_id]['title']}",
                        "trigger_id": None, "verification": verification,
                        "trigger": {"status": "unknown", "event": "navigation_action", "label": "触发控件未定位"},
                        "evidence": [{"file_path": nav_path.relative_to(repo).as_posix(), "line": None, "method": "navigation_xml"}],
                    })
        start_id = destinations.get(nav_root.get(APP + "startDestination", "").rsplit("/", 1)[-1])
        if start_id:
            for activity_id, activity in list(screens.items()):
                if activity["components"][0]["type"] != "Activity":
                    continue
                for layout_name in activity.get("layouts", []):
                    for layout_path in repo.rglob(f"res/layout/{layout_name}.xml"):
                        try:
                            layout_text = layout_path.read_text(encoding="utf-8")
                        except (OSError, UnicodeError):
                            continue
                        if f"@navigation/{nav_path.stem}" in layout_text:
                            for destination_id in destinations.values():
                                if screens[destination_id]["components"][0]["type"] != "Fragment":
                                    continue
                                containments.append({
                                    "id": f"{activity_id}:hosts-navigation:{destination_id}",
                                    "parent": activity_id, "child": destination_id,
                                    "kind": "navigation_host", "verification": verification,
                                    "evidence": [{"file_path": layout_path.relative_to(repo).as_posix(), "line": None, "method": "navigation_host"},
                                                 {"file_path": nav_path.relative_to(repo).as_posix(), "line": None, "method": "navigation_destination"}],
                                })
                            transitions.append({
                                "id": f"{activity_id}:host:{start_id}", "from": activity_id, "to": start_id,
                                "action": "Open initial page", "trigger_id": None,
                                "verification": verification,
                                "trigger": {"status": "event_only", "event": "navigation_start", "label": "导航容器初始页面"},
                                "evidence": [{"file_path": layout_path.relative_to(repo).as_posix(), "line": None, "method": "navigation_host"}],
                            })
    for source_id, screen in sorted(screens.items()):
        source = sources.get(source_id)
        if not source:
            continue
        path = source
        try:
            code = path.read_text(encoding="utf-8")
        except (UnicodeError, OSError):
            continue
        for match in INTENT.finditer(code):
            target_id = _resolve_target(match.group(1), source_id, code, screens)
            if target_id not in screens or target_id == source_id:
                continue
            if not _intent_launched(code, match):
                continue
            line = code.count("\n", 0, match.start()) + 1
            action, trigger_id, trigger = _trigger_for_intent(code, match.start(), screens[target_id]["title"], menu_labels)
            transitions.append({
                "id": f"{source_id}:intent:{target_id}:{line}",
                "from": source_id,
                "to": target_id,
                "action": action,
                "trigger_id": trigger_id,
                "trigger": trigger,
                "verification": verification,
                "evidence": [{"file_path": path.relative_to(repo).as_posix(), "line": line, "method": "decompiled_intent" if from_apk else "explicit_intent"}],
            })

    # Shared navigation can be implemented in a base Activity. Represent its
    # routes from the launcher so the overview stays readable instead of
    # drawing the same menu edge from every subclass.
    entry_ids = [screen_id for screen_id, screen in screens.items() if screen["entry"]]
    for entry_id in entry_ids:
        entry_source = sources.get(entry_id)
        if not entry_source:
            continue
        try:
            entry_code = entry_source.read_text(encoding="utf-8")
        except (UnicodeError, OSError):
            continue
        parent = re.search(r"\bclass\s+\w+\s+extends\s+(\w+)", entry_code)
        base_id = _resolve_target(parent.group(1), entry_id, entry_code, sources) if parent else None
        base_path = sources.get(base_id) if base_id else None
        if not base_path:
            continue
        try:
            base_code = base_path.read_text(encoding="utf-8")
        except (UnicodeError, OSError):
            continue
        cases = list(MENU_CASE.finditer(base_code))
        seen = set()
        for index, case in enumerate(cases):
            body = base_code[case.end():cases[index + 1].start() if index + 1 < len(cases) else len(base_code)]
            for intent in INTENT.finditer(body):
                target_id = _resolve_target(intent.group(1), base_id, base_code, screens)
                if not target_id or target_id == entry_id or (entry_id, target_id) in seen:
                    continue
                if not _intent_launched(body, intent):
                    continue
                seen.add((entry_id, target_id))
                transitions.append({
                    "id": f"{entry_id}:shared-menu:{target_id}", "from": entry_id, "to": target_id,
                    "action": f"导航菜单：{menu_labels.get(case.group(1), screens[target_id]['title'])}",
                    "trigger_id": case.group(1), "verification": verification,
                    "trigger": {"status": "resolved", "event": "menu_select", "label": menu_labels.get(case.group(1), case.group(1))},
                    "evidence": [{"file_path": base_path.relative_to(repo).as_posix(), "line": base_code.count("\n", 0, case.start()) + 1, "method": "inherited_navigation"}],
                })

    layout_files = _resource_files(repo, "layout")
    menu_files = _resource_files(repo, "menu")
    for screen_id, screen in screens.items():
        source = sources.get(screen_id)
        try:
            code = source.read_text(encoding="utf-8") if source else ""
        except (UnicodeError, OSError):
            code = ""
        layouts = sorted(set(screen.get("layouts", []) + LAYOUT.findall(code)))
        menu_names = MENU.findall(code)
        if screen["components"][0]["type"] == "Activity":
            parent = re.search(r"\bclass\s+\w+\s+extends\s+(\w+)", code)
            parent_id = _resolve_target(parent.group(1), screen_id, code, sources) if parent else None
            parent_path = sources.get(parent_id) if parent_id else None
            if parent_path:
                try:
                    parent_code = parent_path.read_text(encoding="utf-8")
                    layouts.extend(LAYOUT.findall(parent_code))
                    menu_names.extend(MENU.findall(parent_code))
                except (UnicodeError, OSError):
                    pass
        screen["layouts"] = sorted(set(layouts))
        screen["elements"] = _elements_for_screen(repo, screen["layouts"], menu_names,
                                                  layout_files, menu_files, strings)

    return {
        "project_name": app_id,
        "schema_version": SCHEMA_VERSION,
        "mode": "fast",
        "source": "apk_decompiled" if from_apk else "android_repository",
        "screens": sorted(screens.values(), key=lambda screen: screen["id"]),
        "transitions": transitions,
        "containments": sorted({relation["id"]: relation for relation in containments}.values(), key=lambda item: item["id"]),
    }
