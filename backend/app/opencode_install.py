"""Install and locate the GUI-Anything managed OpenCode CLI."""
from __future__ import annotations

import os
import shutil
import subprocess
import threading
from pathlib import Path

PACKAGE = "opencode-ai"
VERSION = "1.19.5"
_lock = threading.Lock()


def root() -> Path:
    configured = os.getenv("GUI_MANAGED_TOOLS_DIR")
    base = Path(configured).expanduser() if configured else Path.home() / ".gui-anything" / "tools"
    return base / "opencode" / VERSION


def executable() -> str | None:
    install_root = root()
    candidates = (
        install_root / "node_modules" / PACKAGE / "bin" / "opencode.exe",
        install_root / "node_modules" / ".bin" / "opencode.cmd",
        install_root / "node_modules" / ".bin" / "opencode",
        install_root / "bin" / "opencode",
    )
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return None


def _version(binary: str) -> str:
    result = subprocess.run([binary, "--version"], capture_output=True, timeout=30)
    if result.returncode:
        detail = (result.stderr or result.stdout).decode("utf-8", "replace").strip()
        raise RuntimeError(f"OpenCode validation failed: {detail or result.returncode}")
    return result.stdout.decode("utf-8", "replace").strip().splitlines()[0]


def install() -> dict:
    with _lock:
        current = executable()
        if current:
            return {"status": "ready", "managed": True, "reused": True, "path": current, "version": _version(current)}
        npm = shutil.which("npm")
        if not npm:
            raise RuntimeError("Node.js/npm is required for the managed OpenCode install")
        install_root = root()
        install_root.mkdir(parents=True, exist_ok=True)
        command = [npm, "install", "--prefix", str(install_root), "--no-audit", "--no-fund", "--save-exact", f"{PACKAGE}@{VERSION}"]
        try:
            result = subprocess.run(command, capture_output=True, timeout=600)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("Managed OpenCode install timed out after 10 minutes") from exc
        if result.returncode:
            detail = (result.stderr or result.stdout).decode("utf-8", "replace").strip()[-2000:]
            raise RuntimeError(f"Managed OpenCode install failed: {detail or result.returncode}")
        binary = executable()
        if not binary:
            raise RuntimeError("OpenCode package installed but its executable was not found")
        return {"status": "ready", "managed": True, "reused": False, "path": binary, "version": _version(binary)}
