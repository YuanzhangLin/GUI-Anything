import os
import subprocess
from typing import List, Optional, Dict, Any

from app.services.code_manager import CodeManager


def _ensure_safe_relpath(path: str) -> str:
    # Prevent absolute paths and traversal.
    p = (path or "").replace("\\", "/").lstrip("/")
    if ".." in p.split("/"):
        raise ValueError("Invalid path: path traversal is not allowed")
    return p


def repo_list_files(app_id: str, limit: int = 400) -> List[str]:
    """
    List tracked files of the downloaded repo for an app_id.
    Uses `git ls-files` when available; falls back to walking the directory.
    """
    cm = CodeManager()
    repo_root = cm.get_repo_path(app_id)
    if not os.path.isdir(repo_root):
        raise FileNotFoundError(f"Repo not found: {repo_root}")

    # Prefer git index for speed and to avoid huge vendor folders.
    try:
        r = subprocess.run(
            ["git", "-C", repo_root, "ls-files"],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        files = [line.strip() for line in r.stdout.splitlines() if line.strip()]
        return files[: max(1, min(int(limit), 5000))]
    except Exception:
        out: List[str] = []
        for root, dirs, files in os.walk(repo_root):
            # prune noisy dirs
            dirs[:] = [
                d
                for d in dirs
                if d not in (".git", "build", "dist", "node_modules", ".idea", ".gradle")
            ]
            for f in files:
                rel = os.path.relpath(os.path.join(root, f), repo_root)
                out.append(rel)
                if len(out) >= limit:
                    return out
        return out


def repo_search(app_id: str, query: str, glob: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Search in repo using ripgrep if available.
    Returns list of {path, line, text}.
    """
    cm = CodeManager()
    repo_root = cm.get_repo_path(app_id)
    if not os.path.isdir(repo_root):
        raise FileNotFoundError(f"Repo not found: {repo_root}")
    if not query:
        return []

    limit = max(1, min(int(limit), 200))

    cmd = ["rg", "--line-number", "--no-heading", "--color", "never", query, repo_root]
    if glob:
        cmd = ["rg", "--line-number", "--no-heading", "--color", "never", "--glob", glob, query, repo_root]

    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        # rg returns 1 when no matches
        lines = [ln for ln in r.stdout.splitlines() if ln.strip()]
        results: List[Dict[str, Any]] = []
        for ln in lines[:limit]:
            # format: path:line:text
            try:
                p, line_no, text = ln.split(":", 2)
                results.append(
                    {
                        "path": os.path.relpath(p, repo_root),
                        "line": int(line_no),
                        "text": text,
                    }
                )
            except Exception:
                continue
        return results
    except FileNotFoundError:
        # rg not installed
        return [{"error": "ripgrep (rg) not available in runtime"}]


def repo_read_file(app_id: str, path: str, max_chars: int = 12000) -> Dict[str, Any]:
    """
    Read a file from the downloaded repo (UTF-8 best effort).
    Returns {path, truncated, content}.
    """
    cm = CodeManager()
    repo_root = cm.get_repo_path(app_id)
    if not os.path.isdir(repo_root):
        raise FileNotFoundError(f"Repo not found: {repo_root}")

    rel = _ensure_safe_relpath(path)
    abs_path = os.path.normpath(os.path.join(repo_root, rel))
    if not abs_path.startswith(os.path.abspath(repo_root) + os.sep):
        raise ValueError("Invalid path")
    if not os.path.isfile(abs_path):
        raise FileNotFoundError(f"File not found: {rel}")

    max_chars = max(200, min(int(max_chars), 40000))
    with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read(max_chars + 1)
    truncated = len(content) > max_chars
    if truncated:
        content = content[:max_chars]
    return {"path": rel, "truncated": truncated, "content": content}

