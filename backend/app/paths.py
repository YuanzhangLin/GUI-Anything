"""与进程 cwd 无关的资源路径（backend/data、backend/app 等）。"""
import os

_APP_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_ROOT = os.path.abspath(os.path.join(_APP_DIR, ".."))
DATA_DIR = os.path.join(BACKEND_ROOT, "data")
