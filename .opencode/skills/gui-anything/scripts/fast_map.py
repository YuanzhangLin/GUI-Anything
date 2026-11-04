"""Run the GUI-Anything Fast engine from a portable skill location."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def find_home() -> Path:
    configured = os.environ.get("GUI_ANYTHING_HOME")
    if configured:
        return Path(configured).expanduser().resolve()
    for parent in Path(__file__).resolve().parents:
        if (parent / "backend" / "app" / "cli.py").is_file() or (parent / "app" / "cli.py").is_file():
            return parent
    raise SystemExit("GUI-Anything engine not found. Set GUI_ANYTHING_HOME to the GUI-Anything repository root.")


def main() -> int:
    home = find_home()
    backend = home / "backend" if (home / "backend" / "app" / "cli.py").is_file() else home
    if not (backend / "app" / "cli.py").is_file():
        raise SystemExit(f"GUI-Anything engine not found under {backend}")
    sys.path.insert(0, str(backend))
    from app.cli import main as cli_main

    return cli_main(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
