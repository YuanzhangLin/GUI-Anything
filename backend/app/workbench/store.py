"""Version-bound source targets and durable local Run definitions."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import subprocess
import uuid
from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator
from app.engine.uimapgenerate.listeners import methods

SOURCE_SUFFIXES = {".java", ".kt", ".xml"}
SKIP = {".git", "build", ".gradle", "node_modules", ".idea"}

class TargetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    file_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    symbol: str | None = None

    @model_validator(mode="after")
    def ordered(self):
        if self.end_line < self.start_line:
            raise ValueError("Line range is reversed")
        return self

class SuccessCondition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["coverage", "ui", "business"]
    description: str = Field(min_length=1, max_length=2000)
    selector: dict[str, str] | None = None
    expected_count: int = Field(default=1, ge=0)
    check: str | None = None
    parameters: list[str] = Field(default_factory=list)
    expected_rows: list[dict] | None = None

class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    goal: str = Field(min_length=1, max_length=4000)
    target: TargetRequest
    conditions: list[SuccessCondition] = Field(min_length=1, max_length=20)
    device_serial: str | None = None
    agent: Literal["opencode", "external", "manual"] = "opencode"
    action_budget: int = Field(default=60, ge=1, le=1000)
    time_budget_seconds: int = Field(default=1800, ge=30, le=14400)

class Source:
    def __init__(self, root: Path):
        self.root = root.resolve()
        if not self.root.is_dir():
            raise FileNotFoundError("Project source is not available")

    def resolve(self, relative: str) -> Path:
        raw = Path(relative)
        path = (self.root / raw).resolve()
        if raw.is_absolute() or not path.is_relative_to(self.root) or any(x in SKIP for x in raw.parts):
            raise ValueError("Source path must remain inside the project")
        if path.suffix not in SOURCE_SUFFIXES:
            raise ValueError("Only Java, Kotlin and XML source files are supported")
        return path

    def tree(self):
        files = []
        for directory, dirs, names in os.walk(self.root, followlinks=False):
            dirs[:] = sorted(x for x in dirs if x not in SKIP and not (Path(directory)/x).is_symlink())
            for name in sorted(names):
                path = Path(directory)/name
                if path.suffix in SOURCE_SUFFIXES and not path.is_symlink():
                    files.append(path.relative_to(self.root).as_posix())
                    if len(files) >= 20000:
                        return {"files": files, "truncated": True}
        return {"files": files, "truncated": False}

    def revision(self):
        def git(*args):
            result = subprocess.run(["git", "-C", str(self.root), *args], capture_output=True, timeout=10)
            return result.stdout.decode("utf-8", "replace").strip() if result.returncode == 0 else None
        # Do not attribute a parent repository's commit to an unversioned imported app.
        top = git("rev-parse", "--show-toplevel")
        if not top or Path(top).resolve() != self.root:
            return {"commit": None, "dirty": None}
        return {"commit": git("rev-parse", "HEAD"), "dirty": bool(git("status", "--porcelain"))}

    def read(self, relative):
        path = self.resolve(relative)
        if path.stat().st_size > 2_000_000:
            raise ValueError("Source file exceeds 2 MB")
        data = path.read_bytes()
        text = data.decode("utf-8-sig")
        return {"path": path.relative_to(self.root).as_posix(), "text": text,
                "file_sha256": hashlib.sha256(data).hexdigest(), "revision": self.revision(),
                "line_count": len(text.splitlines()), "symbols": [
                    {"name": name, "signature": " ".join(text[start:body-1].split()),
                     "start_line": text.count("\n",0,start)+1, "end_line": text.count("\n",0,end)+1}
                    for name,start,body,end in methods(text)] if path.suffix == ".java" else []}

    def target(self, request: TargetRequest):
        source = self.read(request.path)
        if source["file_sha256"] != request.file_sha256:
            raise ValueError("Source changed since it was opened; reload before selecting a target")
        if request.end_line > source["line_count"]:
            raise ValueError("Target range exceeds source length")
        excerpt = "\n".join(source["text"].splitlines()[request.start_line-1:request.end_line])
        enclosing = [symbol for symbol in source["symbols"] if symbol["start_line"] <= request.start_line and symbol["end_line"] >= request.end_line]
        symbol = enclosing[0] if len(enclosing) == 1 else None
        return {**request.model_dump(), "symbol": symbol, "path": source["path"], "revision": source["revision"],
                "excerpt": excerpt, "excerpt_sha256": hashlib.sha256(excerpt.encode()).hexdigest()}

class RunStore:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def create(self, app_id, owner, source: Source, request: RunRequest, map_snapshot=None):
        target = source.target(request.target)
        definitions = {}
        for condition in request.conditions:
            if condition.kind == "business" and condition.check:
                config_dir = os.getenv("GUI_COVERAGE_CONFIG_DIR")
                if not config_dir: raise ValueError("Business checks are not configured")
                config = json.loads((Path(config_dir)/(app_id+".json")).read_text(encoding="utf-8"))
                definition = config.get("business_checks", {}).get(condition.check)
                if not definition: raise ValueError("Unknown operator-configured business check")
                definitions[condition.check] = {**definition, "package": config["package"]}
        run_id = uuid.uuid4().hex
        run = {"schema_version": 1, "id": run_id, "app_id": app_id, "owner": owner,
               "created_at": datetime.now(timezone.utc).isoformat(), "status": "draft",
               **request.model_dump(exclude={"target"}), "target": target,
               "map_snapshot": map_snapshot, "assertion_definitions": definitions, "results": {"coverage": "not_checked", "business": "not_checked"}}
        temporary=self.root/(run_id+".tmp")
        with temporary.open("x", encoding="utf-8") as f:
            json.dump(run, f, ensure_ascii=False, indent=2)
            f.flush();os.fsync(f.fileno())
        os.replace(temporary,self.root/(run_id+".json"))
        return run

    def read(self, run_id, owner):
        if len(run_id) != 32 or any(c not in "0123456789abcdef" for c in run_id):
            raise ValueError("Invalid Run ID")
        run = json.loads((self.root/(run_id+".json")).read_text(encoding="utf-8"))
        if run["owner"] != owner:
            raise FileNotFoundError("Run not found")
        return run

    def list(self, app_id, owner):
        runs = [json.loads(p.read_text(encoding="utf-8")) for p in self.root.glob("*.json")]
        return sorted([r for r in runs if r["owner"] == owner and r["app_id"] == app_id],
                      key=lambda r: r["created_at"], reverse=True)

    def check_source(self, run, source):
        try:
            current = source.read(run["target"]["path"])
            return {"matches": current["file_sha256"] == run["target"]["file_sha256"]
                    and current["revision"]["commit"] == run["target"]["revision"]["commit"],
                    "current_revision": current["revision"], "current_sha256": current["file_sha256"]}
        except (ValueError, FileNotFoundError):
            return {"matches": False, "reason": "Target source is missing or no longer accessible"}
