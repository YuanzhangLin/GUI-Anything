"""Read-only OpenCode CLI adapter for platform chat sessions."""

import asyncio
import json
import os
import shutil

from app.services.code_manager import CodeManager
from app.paths import BACKEND_ROOT


def available() -> bool:
    return bool(shutil.which(os.getenv("OPENCODE_BIN", "opencode")))


async def ask(message: str, app_id: str) -> str:
    executable = shutil.which(os.getenv("OPENCODE_BIN", "opencode"))
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
    process = await asyncio.create_subprocess_exec(
        *command, prompt,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=env,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=300)
    except asyncio.TimeoutError:
        process.kill()
        await process.communicate()
        raise RuntimeError("OpenCode analysis timed out after 5 minutes")
    if process.returncode:
        detail = stderr.decode("utf-8", errors="replace").strip()[-1000:]
        raise RuntimeError(f"OpenCode failed: {detail or process.returncode}")
    result = stdout.decode("utf-8", errors="replace").strip()
    if not result:
        raise RuntimeError("OpenCode returned an empty answer")
    return result
