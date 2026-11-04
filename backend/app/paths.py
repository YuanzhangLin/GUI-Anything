"""与进程 cwd 无关的资源路径（backend/data、backend/app 等）。"""
import os
import re

_APP_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_ROOT = os.path.abspath(os.path.join(_APP_DIR, ".."))
DATA_DIR = os.path.join(BACKEND_ROOT, "data")


def validate_app_id(app_id: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", app_id):
        raise ValueError("Invalid app ID")
    return app_id
