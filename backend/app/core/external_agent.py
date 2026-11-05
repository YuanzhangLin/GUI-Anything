"""A configured CLI Agent adapter; arguments are never passed through a shell."""

import asyncio
import json
import os
import shutil
import tempfile
from pathlib import Path

from app.services.code_manager import CodeManager


def available() -> bool:
    command = os.getenv("GUI_AGENT_EXECUTABLE", "")
    return bool(command and shutil.which(command))


async def ask(message: str, app_id: str) -> str:
    command = os.getenv("GUI_AGENT_EXECUTABLE", "")
    executable = shutil.which(command) if command else None
    if not executable:
        raise RuntimeError("External Agent executable is not configured or installed")
    repo = CodeManager().get_repo_path(app_id)
    if not os.path.isdir(repo):
        raise ValueError("Project source is unavailable")
    try:
        templates = json.loads(os.getenv("GUI_AGENT_ARGS", '["{prompt}"]'))
    except json.JSONDecodeError as exc:
        raise ValueError("GUI_AGENT_ARGS must be a JSON array") from exc
    if not isinstance(templates, list) or not all(isinstance(item, str) for item in templates):
        raise ValueError("GUI_AGENT_ARGS must be a JSON array of strings")
    with tempfile.TemporaryDirectory(prefix="gui-anything-agent-") as temporary:
        prompt_file = Path(temporary) / "request.txt"
        prompt_file.write_text(message, encoding="utf-8")
        arguments = [item.replace("{repo}", repo).replace("{prompt_file}", str(prompt_file)).replace("{prompt}", message) for item in templates]
        if os.name == "nt" and sum(len(item) + 3 for item in [executable, *arguments]) > 30000:
            raise ValueError("Agent command is too long; configure GUI_AGENT_ARGS with {prompt_file} instead of {prompt}")
        return await _run_command(executable, arguments, repo)


async def _run_command(executable, arguments, repo):
    process = await asyncio.create_subprocess_exec(
        executable, *arguments, cwd=repo,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=300)
    except asyncio.CancelledError:
        if process.returncode is None:
            try: process.kill()
            except ProcessLookupError: pass
        await process.communicate()
        raise
    except asyncio.TimeoutError:
        if process.returncode is None:
            try: process.kill()
            except ProcessLookupError: pass
        await process.communicate()
        raise RuntimeError("External Agent timed out after 5 minutes")
    if process.returncode:
        raise RuntimeError(f"External Agent failed: {stderr.decode('utf-8', errors='replace')[-1000:]}")
    result = stdout.decode("utf-8", errors="replace").strip()
    if not result:
        raise RuntimeError("External Agent returned an empty answer")
    return result
