"""Read-only OpenCode CLI adapter for platform chat sessions."""

import asyncio
import json
import os
import shutil
import tempfile
from pathlib import Path

from app.services.code_manager import CodeManager
from app.paths import BACKEND_ROOT


def executable_path() -> str | None:
    configured = os.getenv("OPENCODE_BIN")
    found = shutil.which(configured or "opencode")
    if os.name == "nt" and (not found or Path(found).suffix.lower() in {".cmd", ".ps1"}):
        base = Path(found).parent if found else Path(os.getenv("APPDATA", "")) / "npm"
        native = base / "node_modules/opencode-ai/bin/opencode.exe"
        if native.is_file(): return str(native)
    return found


def available() -> bool:
    return bool(executable_path())


async def ask(message: str, app_id: str) -> str:
    executable = executable_path()
    if not executable:
        raise RuntimeError("OpenCode is not installed on the backend")
    repo = CodeManager().get_repo_path(app_id)
    if not os.path.isdir(repo):
        raise ValueError("Project source is unavailable; import or sync the project first")
    config = {"permission": {"edit": "deny", "bash": "deny"}}
    env = {**os.environ, "OPENCODE_CONFIG_CONTENT": json.dumps(config)}
    prompt = (
        "You are analyzing an Android app for GUI-Anything. The main unit of the map is "
        "the user-visible screen and action path. Activity and Fragment names are evidence. "
        "Read the gui-anything skill in this project if available. "
        "Read-only analysis: do not change project files. "
        "Treat the existing map as static evidence, not runtime confirmation.\n\n"
        + message
    )
    skill_path = os.path.join(os.path.dirname(BACKEND_ROOT), "agent-skills", "gui-anything", "SKILL.md")
    command = [executable, "run", "--dir", repo]
    if os.getenv("OPENCODE_MODEL"):
        command.extend(["--model", os.environ["OPENCODE_MODEL"]])
    if os.path.isfile(skill_path):
        command.extend(["--file", skill_path])
    with tempfile.TemporaryDirectory(prefix="gui-anything-request-") as temporary:
        request_path = Path(temporary) / "request.txt"
        request_path.write_text(prompt, encoding="utf-8")
        command.extend(["--file", str(request_path), "--", "Read the attached request.txt and follow its response protocol. The other attachment is the GUI-Anything skill."])
        return await _run_command(command, env)


async def _run_command(command, env):
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=env,
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
        raise RuntimeError("OpenCode analysis timed out after 5 minutes")
    if process.returncode:
        detail = stderr.decode("utf-8", errors="replace").strip()[-1000:]
        raise RuntimeError(f"OpenCode failed: {detail or process.returncode}")
    result = stdout.decode("utf-8", errors="replace").strip()
    if not result:
        raise RuntimeError("OpenCode returned an empty answer")
    return result
