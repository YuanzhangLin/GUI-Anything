"""Load the GUI-Anything navigation CLI from any installed skill location."""

from __future__ import annotations

import sys

from fast_map import find_home


def main() -> int:
    home = find_home()
    backend = home / "backend" if (home / "backend" / "app" / "navigation_cli.py").is_file() else home
    sys.path.insert(0, str(backend))
    from app.navigation_cli import main as navigation_main

    return navigation_main(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
