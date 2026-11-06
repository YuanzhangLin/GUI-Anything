"""Small ADB observation/action boundary; core planning does not depend on ADB."""

from __future__ import annotations

import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from app.navigation.observation import parse_activity, parse_hierarchy
from app.local_services import discover_adb


@dataclass
class Observation:
    activity: str | None
    hierarchy: str
    nodes: list[dict]
    screenshot: bytes | None = None


class AdbDevice:
    def __init__(self, serial: str | None = None, *, screenshot: bool = True):
        executable = discover_adb()
        if not executable:
            raise RuntimeError("ADB is not installed or not on PATH")
        self.prefix = [executable, *(["-s", serial] if serial else [])]
        self.screenshot = screenshot

    def _run(self, *args: str, timeout: int = 25) -> bytes:
        try:
            result = subprocess.run([*self.prefix, *args], capture_output=True, timeout=timeout, check=False)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"ADB timed out: {' '.join(args)}") from exc
        except OSError as exc:
            raise RuntimeError(f"Cannot start ADB: {exc}") from exc
        if result.returncode:
            detail = result.stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"ADB failed: {detail or ' '.join(args)}")
        return result.stdout

    def observe(self) -> Observation:
        activity = parse_activity(self._run("shell", "dumpsys", "activity", "activities").decode("utf-8", errors="replace"))
        dumped = self._run("shell", "uiautomator", "dump", "/sdcard/gui-anything-window.xml")
        if b"ERROR" in dumped.upper():
            raise RuntimeError(f"ADB UI dump failed: {dumped.decode('utf-8', errors='replace').strip()}")
        hierarchy = self._run("exec-out", "cat", "/sdcard/gui-anything-window.xml").decode("utf-8", errors="replace")
        try:
            nodes = parse_hierarchy(hierarchy)
        except ET.ParseError as exc:
            raise RuntimeError("ADB returned an invalid UI hierarchy") from exc
        screenshot = self._run("exec-out", "screencap", "-p") if self.screenshot else None
        return Observation(activity=activity, hierarchy=hierarchy, nodes=nodes, screenshot=screenshot)

    def tap(self, x: int, y: int) -> None:
        self._run("shell", "input", "tap", str(x), str(y))

    def long_press(self, x: int, y: int) -> None:
        self._run("shell", "input", "swipe", str(x), str(y), str(x), str(y), "800")

    def open_menu(self) -> None:
        """Explicit legacy options-menu preparation; callers verify the result."""
        self._run("shell", "input", "keyevent", "82")
