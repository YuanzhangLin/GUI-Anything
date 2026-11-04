"""Bounded Java listener tracing; unsupported or ambiguous callbacks stay unresolved."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path


METHOD = re.compile(
    r"\b(?:public|protected|private)\s+(?:(?:static|final|synchronized)\s+)*"
    r"[\w.<>?\[\]]+\s+(\w+)\s*\([^;{}]*\)\s*(?:throws\s+[\w.,\s]+)?\{"
)


def code_only(code: str) -> str:
    # Preserve offsets/line numbers while excluding comments, literals and their braces.
    return re.sub(r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'',
                  lambda m: re.sub(r"[^\n]", " ", m.group()), code)


def methods(code: str):
    clean = code_only(code)
    for match in METHOD.finditer(clean):
        depth = 1
        end = match.end()
        while end < len(clean) and depth:
            depth += (clean[end] == "{") - (clean[end] == "}")
            end += 1
        if depth == 0:
            yield match.group(1), match.start(), match.end(), end - 1


def listener_trigger(repo: Path, sources: dict[str, Path], source_id: str,
                     source: Path, code: str, position: int, *, cache: dict | None = None):
    """Resolve a single external onClick that delegates directly to this Activity.

    A matching resource field, listener receiver/constructor and callback are all
    required. This deliberately does not infer conditional or multi-hop callbacks.
    """
    cache = cache if cache is not None else {}
    parsed = cache.setdefault("parsed", {})
    if source_id not in parsed:
        parsed[source_id] = (code_only(code), list(methods(code)))
    clean, source_methods = parsed[source_id]
    enclosing = [m for m in source_methods if m[2] <= position < m[3]]
    if len(enclosing) != 1:
        return None
    target_method = enclosing[0][0]
    # Overloads cannot be distinguished by a parameterless callback here.
    if sum(m[0] == target_method for m in source_methods) != 1:
        return None
    package = source_id.rpartition(".")[0]
    activity_name = source_id.rsplit(".", 1)[-1]

    def evidence(path, text, offset, method):
        return {"file_path": path.relative_to(repo).as_posix(),
                "line": text.count("\n", 0, offset) + 1, "method": method}

    matches = []
    bindings = re.finditer(r"\.setOnClickListener\s*\(\s*new\s+([\w.]+)\s*\(\s*this\s*\)\s*\)", clean)
    for binding in bindings:
        raw_listener = binding.group(1)
        listener_id = raw_listener if "." in raw_listener else f"{package}.{raw_listener}"
        listener_path = sources.get(listener_id)
        if not listener_path:
            continue
        listener = listener_path.read_text(encoding="utf-8", errors="replace")
        body = code_only(listener)
        if not re.search(r"\bimplements\s+(?:android\.view\.)?View\.OnClickListener\b", body):
            continue
        callbacks = [m for m in methods(listener) if m[0] == "onClick"]
        if len(callbacks) != 1:
            continue
        callback = callbacks[0]
        call = re.fullmatch(r"\s*(?:this\.)?(\w+)\." + re.escape(target_method) + r"\s*\(\s*\)\s*;\s*",
                            body[callback[2]:callback[3]])
        if not call:
            continue
        field = call.group(1)
        type_pattern = r"(?:" + re.escape(source_id) + "|" + re.escape(activity_name) + r")"
        if not re.search(r"\bfinal\s+" + type_pattern + r"\s+" + re.escape(field) + r"\s*;", body):
            continue
        constructor = re.search(r"\b" + re.escape(raw_listener.rsplit('.', 1)[-1]) +
                                r"\s*\(\s*" + type_pattern + r"\s+(\w+)\s*\)\s*\{\s*"
                                r"this\." + re.escape(field) + r"\s*=\s*\1\s*;\s*\}", body)
        if not constructor:
            continue
        start = max(clean.rfind(";", 0, binding.start()), clean.rfind("{", 0, binding.start())) + 1
        start += len(clean[start:binding.start()]) - len(clean[start:binding.start()].lstrip())
        expression = clean[start:binding.start()].strip()
        # Direct resource lookup, optionally cast to a View subclass.
        lookup = re.fullmatch(r"\(*\s*(?:\([\w.]+\)\s*)?(\w+)\s*\(\s*([\w.]+)\.(\w+)\s*\)\s*\)*", expression)
        if not lookup:
            continue
        getter, resource_class, resource_name = lookup.groups()
        if getter != "findViewById":
            accessors = [m for m in source_methods if m[0] == getter
                         and re.search(r"\(\s*int\s+\w+\s*\)", clean[m[1]:m[2]])]
            if len(accessors) != 1:
                continue
            accessor = accessors[0]
            parameter = re.search(r"\(\s*int\s+(\w+)\s*\)", clean[accessor[1]:accessor[2]])
            if not parameter or not re.search(r"\bfindViewById\s*\(\s*" + re.escape(parameter.group(1)) + r"\s*\)", clean[accessor[2]:accessor[3]]):
                continue
        proof = [evidence(source, code, start, "listener_binding"),
                 evidence(listener_path, listener, constructor.start(), "listener_receiver"),
                 evidence(listener_path, listener, callback[2] + call.start(1), "listener_delegate")]
        if not resource_class.endswith("R.id"):
            if "public_ids" not in cache:
                public_ids = {}
                for xml_path in repo.rglob("res/values/public.xml"):
                    try:
                        for item in ET.parse(xml_path).getroot().findall("public"):
                            if item.get("type") == "id":
                                public_ids[item.get("name")] = int(item.get("id"), 0)
                    except (ET.ParseError, ValueError, TypeError):
                        continue
                cache["public_ids"] = public_ids
            public_ids = cache["public_ids"]
            resource_path = sources.get(resource_class)
            if not resource_path or resource_name not in public_ids:
                continue
            resource_code = resource_path.read_text(encoding="utf-8", errors="replace")
            field_match = re.search(r"\bint\s+" + re.escape(resource_name) + r"\s*=\s*(0x[0-9a-fA-F]+|[0-9]+)\s*;", code_only(resource_code))
            if not field_match or int(field_match.group(1), 0) != public_ids[resource_name]:
                continue
            proof.append(evidence(resource_path, resource_code, field_match.start(), "resource_id_field"))
        matches.append((resource_name, proof))
    return matches[0] if len(matches) == 1 else None
