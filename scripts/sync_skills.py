"""Keep the canonical Agent Skill and editor-specific discovery copies identical."""

from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "agent-skills" / "gui-anything"
TARGETS = [ROOT / ".cursor" / "skills" / "gui-anything", ROOT / ".opencode" / "skills" / "gui-anything"]


def main() -> None:
    for target in TARGETS:
        target.mkdir(parents=True, exist_ok=True)
        for source in SOURCE.rglob("*"):
            if source.is_file() and "__pycache__" not in source.parts and source.suffix != ".pyc":
                destination = target / source.relative_to(SOURCE)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
        print(f"Synced {target.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
