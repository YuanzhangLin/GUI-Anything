import sqlite3
import json
import logging
import os
import yaml
import uuid
import asyncio
import tempfile
import hashlib
from contextlib import closing
from pathlib import Path
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Depends, Header, UploadFile, File, Form
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from fastapi.responses import StreamingResponse
from app.core.agent import GuiAgent
from app.core.opencode_agent import ask as ask_opencode, available as opencode_available
from app.core.external_agent import ask as ask_external, available as external_available
from app.core.auth import current_user, hash_password, verify_password, issue_token, revoke_token, require_admin, is_admin
from app.paths import BACKEND_ROOT, DATA_DIR, validate_app_id
from app.services.code_manager import CodeManager
from app.services.uimap_report import build_report_from_map_json
from app.services.apk_import import import_apk_file, MAX_APK_BYTES
app = FastAPI(title="GUI-Anything Multi-Project")
from app.workbench.api import router as workbench_router
app.include_router(workbench_router)
from app.agents.settings import router as conversation_settings_router
app.include_router(conversation_settings_router)
from app.agents.device_tools import router as agent_tools_router
app.include_router(agent_tools_router)
agent = GuiAgent()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _data_json_path(app_id: str, prefix: str = "") -> str:
    try:
        return os.path.join(DATA_DIR, f"{prefix}{validate_app_id(app_id)}.json")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid app ID")

DB_PATH = os.getenv('GUI_DB_PATH', os.path.join(BACKEND_ROOT, 'gui_anything.db'))

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT)')
    columns = {row[1] for row in cursor.execute('PRAGMA table_info(users)')}
    if 'role' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")
        cursor.execute("UPDATE users SET role='admin' WHERE username=(SELECT username FROM users ORDER BY rowid LIMIT 1)")
    cursor.execute('CREATE TABLE IF NOT EXISTS auth_tokens (token_hash TEXT PRIMARY KEY, username TEXT NOT NULL, expires_at INTEGER NOT NULL)')
    cursor.execute('''CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at TEXT NOT NULL
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS project_apps (
        id TEXT PRIMARY KEY, project_id TEXT NOT NULL, name TEXT NOT NULL,
        source_type TEXT NOT NULL DEFAULT 'source', repo_url TEXT,
        description TEXT, source_revision TEXT, created_at TEXT NOT NULL,
        FOREIGN KEY(project_id) REFERENCES projects(id)
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS maps (
        id TEXT PRIMARY KEY, app_id TEXT NOT NULL, source_revision TEXT,
        mode TEXT NOT NULL, path TEXT NOT NULL, created_at TEXT NOT NULL
    )''')
    # 增加 app_id 字段
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY, 
            title TEXT, 
            username TEXT,
            app_id TEXT
        )
    ''')
    session_columns = {row[1] for row in cursor.execute('PRAGMA table_info(sessions)')}
    if 'project_id' not in session_columns:
        cursor.execute("ALTER TABLE sessions ADD COLUMN project_id TEXT")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            session_id TEXT, 
            role TEXT, 
            content TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    legacy_apps = []
    try:
        with open(os.path.join(DATA_DIR, "app_list.yml"), "r", encoding="utf-8") as file:
            legacy_apps.extend((yaml.safe_load(file) or {}).get("apps", []) or [])
    except (OSError, yaml.YAMLError):
        pass
    imported_path = Path(DATA_DIR) / "imported_apps.json"
    if imported_path.is_file():
        try: legacy_apps.extend(json.loads(imported_path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError): pass
    now = datetime.now(timezone.utc).isoformat()
    for legacy in legacy_apps:
        app_id = legacy.get("id")
        if not app_id: continue
        project_id = legacy.get("project_id") or app_id
        cursor.execute("INSERT OR IGNORE INTO projects (id,name,created_at) VALUES (?,?,?)", (project_id,legacy.get("project_name") or legacy.get("name") or project_id,now))
        cursor.execute("""INSERT OR IGNORE INTO project_apps
            (id,project_id,name,source_type,repo_url,description,source_revision,created_at)
            VALUES (?,?,?,?,?,?,?,?)""", (app_id,project_id,legacy.get("name") or app_id,legacy.get("source_type") or "source",legacy.get("repo_url"),legacy.get("description"),legacy.get("source_revision"),now))
    cursor.execute("UPDATE sessions SET project_id=app_id WHERE project_id IS NULL AND app_id IS NOT NULL")

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS map_tasks (
            id TEXT PRIMARY KEY,
            app_id TEXT,
            status TEXT,
            progress INTEGER,
            message TEXT,
            result_path TEXT,
            created_at TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

class AuthRequest(BaseModel):
    username: str
    password: str

class ModelChoice(BaseModel):
    providerID: str
    modelID: str

class AvdCreateRequest(BaseModel):
    name: str = Field(min_length=1,max_length=80)
    image: str
    device: str = 'pixel'
    install_image: bool = False

class SourceImportRequest(BaseModel):
    app_id: str
    name: str = Field(min_length=1,max_length=120)
    repo_url: str = Field(min_length=8,max_length=2000)
    project_id: Optional[str] = None
    project_name: Optional[str] = Field(default=None,max_length=120)
    new_project: bool = False
    map_mode: Literal["none","fast","full"] = "none"
    full_confirmed: bool = False
    model: Optional[ModelChoice] = None

from app.workbench.store import RunRequest

class ChatRequest(BaseModel):
    device_task: Optional[RunRequest] = None
    model: Optional[ModelChoice] = None
    message: str
    session_id: str
    username: str
    app_id: str # 新增：告知后端当前是哪个APP
    project_id: Optional[str] = None
    tool_rounds: Optional[int] = 6
    force_no_tools: Optional[bool] = False
    provider: Literal["opencode", "builtin", "external"] = "opencode"
    device_screenshot: Optional[str] = Field(default=None,max_length=8_000_000,pattern=r'^data:image/png;base64,[A-Za-z0-9+/=\r\n]+$')
    selected_device_serial: Optional[str] = Field(default=None,max_length=200)


@app.get("/api/agents")
async def get_agents(username: str = Depends(current_user)):
    from app.agents.opencode import OpenCodeConnection
    import httpx
    ready = False
    reason = "OpenCode 服务未连接"
    try:
        health = await OpenCodeConnection().health()
        ready = bool(health.get("healthy"))
        reason = "服务已连接；模型可用性需验证"
    except httpx.HTTPError:
        pass
    return {"default": "opencode", "agents": [
        {"id": "opencode", "name": "OpenCode", "available": ready,
         "installed": opencode_available(), "reason": reason,
         "capabilities": {"sessions": True, "streaming": True, "tools": True, "abort": True, "device_actions": True}},
        {"id": "builtin", "name": "内置 Agent", "available": bool(os.getenv("OPENAI_API_KEY")),
         "capabilities": {"sessions": False, "streaming": True, "tools": False, "abort": False, "device_actions": False}},
        {"id": "external", "name": "自定义 Agent", "available": external_available(),
         "capabilities": {"sessions": False, "streaming": False, "tools": False, "abort": False, "device_actions": False}},
    ]}

@app.get("/api/environment/diagnostics")
async def environment_diagnostics(username: str = Depends(current_user)):
    from app.environment import diagnose
    return await asyncio.to_thread(diagnose)

@app.post("/api/environment/opencode/install")
async def install_managed_opencode(username: str = Depends(require_admin)):
    from app.opencode_install import install
    try:
        return await asyncio.to_thread(install)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

@app.get("/api/environment/avds")
async def avd_inventory(username: str = Depends(current_user)):
    from app.avd_manager import inventory
    return await asyncio.to_thread(inventory)

@app.get("/api/environment/system-images")
async def avd_images(username: str = Depends(current_user)):
    from app.avd_manager import system_images
    try:return await asyncio.to_thread(system_images)
    except RuntimeError as exc:raise HTTPException(409,str(exc)) from exc

@app.post("/api/environment/avds",status_code=201)
async def avd_create(request: AvdCreateRequest, username: str = Depends(current_user)):
    from app.avd_manager import create
    try:return await asyncio.to_thread(create,request.name,request.image,request.device,request.install_image)
    except (ValueError,RuntimeError) as exc:raise HTTPException(409,str(exc)) from exc

@app.post("/api/environment/avds/{name}/start")
async def avd_start(name: str, username: str = Depends(current_user)):
    from app.avd_manager import start
    try:return await asyncio.to_thread(start,name)
    except (ValueError,RuntimeError) as exc:raise HTTPException(409,str(exc)) from exc

@app.post("/api/environment/avds/{name}/stop")
async def avd_stop(name: str, username: str = Depends(current_user)):
    from app.avd_manager import stop
    try:return await asyncio.to_thread(stop,name)
    except (ValueError,RuntimeError) as exc:raise HTTPException(409,str(exc)) from exc

@app.post("/api/environment/avds/{name}/erase")
async def avd_erase(name: str, username: str = Depends(current_user)):
    from app.avd_manager import erase
    try:return await asyncio.to_thread(erase,name)
    except (ValueError,RuntimeError) as exc:raise HTTPException(409,str(exc)) from exc

@app.delete("/api/environment/avds/{name}")
async def avd_delete(name: str, username: str = Depends(current_user)):
    from app.avd_manager import delete
    try:return await asyncio.to_thread(delete,name)
    except (ValueError,RuntimeError) as exc:raise HTTPException(409,str(exc)) from exc

@app.get("/api/apps")
async def get_app_list():
    with closing(sqlite3.connect(DB_PATH)) as conn:
        rows = conn.execute("SELECT id,project_id,name,source_type,repo_url,description,source_revision FROM project_apps ORDER BY created_at,id").fetchall()
    return [{"id":row[0],"project_id":row[1],"name":row[2],"source_type":row[3],"repo_url":row[4],"description":row[5],"source_revision":row[6]} for row in rows]

@app.get("/api/projects")
async def get_projects(username: str = Depends(current_user)):
    apps = await get_app_list()
    by_project = {}
    with closing(sqlite3.connect(DB_PATH)) as conn:
        for project_id,name,created_at in conn.execute("SELECT id,name,created_at FROM projects ORDER BY created_at,id"):
            by_project[project_id] = {"id":project_id,"name":name,"created_at":created_at,"apps":[]}
    for app_info in apps:
        if app_info["project_id"] in by_project: by_project[app_info["project_id"]]["apps"].append(app_info)
    return list(by_project.values())

def resolve_project_id(app_id: str, requested_project_id: Optional[str] = None) -> str:
    with closing(sqlite3.connect(DB_PATH)) as conn:
        row = conn.execute("SELECT project_id FROM project_apps WHERE id=?", (app_id,)).fetchone()
    if not row: raise HTTPException(status_code=404, detail="App does not exist")
    if requested_project_id and requested_project_id != row[0]:
        raise HTTPException(status_code=409, detail="App does not belong to the selected project")
    return row[0]

def _project_exists(project_id: str) -> bool:
    with closing(sqlite3.connect(DB_PATH)) as conn:
        return bool(conn.execute("SELECT 1 FROM projects WHERE id=?", (project_id,)).fetchone())

def _register_app(app_id: str, project_id: str, name: str, source_type: str, repo_url: Optional[str], project_name: Optional[str] = None):
    now = datetime.now(timezone.utc).isoformat()
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.execute("INSERT OR IGNORE INTO projects (id,name,created_at) VALUES (?,?,?)", (project_id,project_name or name,now))
        conn.execute("""INSERT INTO project_apps (id,project_id,name,source_type,repo_url,description,created_at)
            VALUES (?,?,?,?,?,?,?)""", (app_id,project_id,name,source_type,repo_url,"Imported APK" if source_type == "apk" else "Imported source repository",now))
        conn.commit()

def _source_revision(app_id: str) -> str:
    root = Path(code_manager.get_repo_path(app_id))
    apk = root / "source.apk"
    if apk.is_file():
        digest = hashlib.sha256()
        with apk.open("rb") as file:
            for chunk in iter(lambda:file.read(1024*1024),b""): digest.update(chunk)
        return "apk-sha256:" + digest.hexdigest()
    try:
        from app.workbench.store import Source
        revision = Source(root).revision()
        if revision.get("commit"): return "git:" + revision["commit"] + (":dirty" if revision.get("dirty") else "")
    except (OSError,ValueError): pass
    return "unversioned:" + datetime.now(timezone.utc).isoformat()


@app.post("/api/import/apk")
async def import_apk(app_id: str = Form(), app_name: Optional[str] = Form(None), project_id: Optional[str] = Form(None), project_name: Optional[str] = Form(None), new_project: bool = Form(False), map_mode: Literal["none","fast"] = Form("none"), file: UploadFile = File(), username: str = Depends(require_admin)):
    try:
        validate_app_id(app_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid app ID")
    if not file.filename or not file.filename.lower().endswith(".apk"):
        raise HTTPException(status_code=400, detail="Select an APK file")
    if any(app.get("id") == app_id for app in await get_app_list()):
        raise HTTPException(status_code=409, detail="App ID already exists")
    resolved_project_id = project_id or app_id
    try: validate_app_id(resolved_project_id)
    except ValueError: raise HTTPException(status_code=400, detail="Invalid project ID")
    if project_id and not new_project and not _project_exists(project_id): raise HTTPException(status_code=404, detail="Project does not exist")
    if new_project and _project_exists(resolved_project_id): raise HTTPException(status_code=409,detail="Project ID already exists")
    repos_root = Path(code_manager.repos_root)
    temporary = tempfile.NamedTemporaryFile(prefix="upload-", suffix=".apk", dir=repos_root, delete=False)
    temp_path = Path(temporary.name)
    try:
        size = 0
        with temporary:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_APK_BYTES:
                    raise HTTPException(status_code=413, detail="APK exceeds 100 MiB")
                temporary.write(chunk)
        await asyncio.to_thread(import_apk_file, app_id, temp_path, repos_root)
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    finally:
        await file.close()
        temp_path.unlink(missing_ok=True)
    imported_path = Path(DATA_DIR) / "imported_apps.json"
    entries = json.loads(imported_path.read_text(encoding="utf-8")) if imported_path.exists() else []
    resolved_name = app_name or file.filename[:-4]
    app_entry = {"id": app_id, "project_id": resolved_project_id, "name": resolved_name, "source_type": "apk", "description": "Imported APK"}
    entries.append(app_entry)
    imported_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    _register_app(app_id,resolved_project_id,resolved_name,"apk",None,project_name)
    _db_execute("UPDATE project_apps SET source_revision=? WHERE id=?",(_source_revision(app_id),app_id))
    map_task_id = _queue_map_task(app_id,"fast") if map_mode == "fast" else None
    return {"project_id": resolved_project_id, "app_id": app_id, "status": "ready", "stage": "decompiled", "map_task_id": map_task_id}

@app.post("/api/import/source")
async def import_source(request: SourceImportRequest, username: str = Depends(require_admin)):
    try: validate_app_id(request.app_id)
    except ValueError: raise HTTPException(status_code=400,detail="Invalid App ID")
    project_id = request.project_id or request.app_id
    try: validate_app_id(project_id)
    except ValueError: raise HTTPException(status_code=400,detail="Invalid project ID")
    if any(app.get("id") == request.app_id for app in await get_app_list()): raise HTTPException(status_code=409,detail="App ID already exists")
    if request.project_id and not request.new_project and not _project_exists(request.project_id): raise HTTPException(status_code=404,detail="Project does not exist")
    if request.new_project and _project_exists(project_id): raise HTTPException(status_code=409,detail="Project ID already exists")
    if request.map_mode == "full" and not request.full_confirmed: raise HTTPException(status_code=409,detail="Full Map requires explicit model and cost confirmation")
    if request.map_mode == "full": await _validate_full_map_model(request.model)
    result = await asyncio.to_thread(code_manager.download_repo,request.repo_url,request.app_id)
    if result.get("status") != "success": raise HTTPException(status_code=400,detail=result.get("message") or "Repository import failed")
    _register_app(request.app_id,project_id,request.name,"source",request.repo_url,request.project_name)
    _db_execute("UPDATE project_apps SET source_revision=? WHERE id=?",(_source_revision(request.app_id),request.app_id))
    map_task_id = _queue_map_task(request.app_id,"deep" if request.map_mode == "full" else request.map_mode,request.model.model_dump() if request.model else None) if request.map_mode != "none" else None
    return {"project_id":project_id,"app_id":request.app_id,"status":"ready","stage":"cloned","map_task_id":map_task_id}


@app.get("/api/demo/map")
async def get_demo_map():
    with open(os.path.join(DATA_DIR, "demo.json"), "r", encoding="utf-8") as f:
        return json.load(f)

@app.get("/api/issues/{app_id}")
async def list_cached_issues(app_id: str, username: str = Depends(current_user)):
    """Compatibility read path for historical Issue cache data."""
    cache_path = _data_json_path(app_id, "issues_")
    if not os.path.exists(cache_path):
        return []
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error("读取 Issue 缓存失败: %s", e)
        return []


@app.get("/api/map/{app_id}")
async def get_map(app_id: str, username: str = Depends(current_user)):
    file_path = _data_json_path(app_id)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Map file not found")
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/api/map_summary/{app_id}")
async def get_map_summary(app_id: str, username: str = Depends(current_user)):
    """将 UI Map JSON 转为人类可读的文本报告，供对话附件使用（避免整份 JSON）。"""
    file_path = _data_json_path(app_id)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Map file not found")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        summary = build_report_from_map_json(data)
        return {"app_id": app_id, "summary": summary}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("生成 UI Map 摘要失败: %s", e)
        raise HTTPException(status_code=500, detail="生成摘要失败")


@app.get("/api/map_status/{app_id}")
async def get_map_status(app_id: str, username: str = Depends(current_user)):
    """轻量查询：是否已生成 UI Map（不返回大 JSON）。"""
    file_path = _data_json_path(app_id)
    if not os.path.exists(file_path):
        return {"app_id": app_id, "exists": False}
    try:
        stat = os.stat(file_path)
        with open(file_path,"r",encoding="utf-8") as file:data=json.load(file)
        return {
            "app_id": app_id,
            "map_id": data.get("id"),
            "exists": True,
            "bytes": stat.st_size,
            "updated_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        }
    except Exception:
        return {"app_id": app_id, "exists": True}


class MapGenerateRequest(BaseModel):
    mode: Literal["fast", "deep"] = "fast"
    model: Optional[ModelChoice] = None


async def _validate_full_map_model(model: Optional[ModelChoice]):
    if model is None:
        raise HTTPException(status_code=400,detail="Full Map requires an explicit OpenCode model")
    from app.agents.settings import catalog
    providers={provider['id']:provider for provider in (await catalog())['providers']}
    provider=providers.get(model.providerID)
    if not provider or model.modelID not in {item['id'] for item in provider['models']}:
        raise HTTPException(status_code=400,detail="Unknown Full Map model")
    if not provider['connected']:
        raise HTTPException(status_code=400,detail="Configure this model provider in Model Services before Full Map generation")


def _db_execute(sql: str, params: tuple = ()):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(sql, params)
    conn.commit()
    conn.close()


def _db_fetchone(sql: str, params: tuple = ()):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(sql, params)
    row = cur.fetchone()
    conn.close()
    return row


def _agent_context(app_id: str, message: str, previous_messages: list[tuple[str, str]]) -> str:
    context = "\n".join(f"{role}: {content[:3000]}" for role, content in reversed(previous_messages))
    parts = []
    map_path = Path(_data_json_path(app_id))
    if map_path.is_file():
        try:
            summary = build_report_from_map_json(json.loads(map_path.read_text(encoding="utf-8")))
            parts.append("Current UI map summary (static evidence):\n" + summary[:16000])
        except (OSError, ValueError, KeyError):
            logger.warning("Could not include map summary for %s", app_id)
    if context:
        parts.append("Recent conversation:\n" + context)
    parts.append("Current user request:\n" + message)
    return "\n\n".join(parts)


async def _run_map_task(task_id: str, app_id: str, mode: str, model: Optional[dict] = None):
    try:
        _db_execute(
            "UPDATE map_tasks SET status=?, progress=?, message=? WHERE id=?",
            ("running", 5, f"Generating {mode} UI map...", task_id)
        )
        if mode == "fast":
            from app.engine.uimapgenerate.fast import generate_fast_map
            result = await asyncio.to_thread(generate_fast_map, app_id)
        else:
            from app.engine.uimapgenerate.service import generate_uimap
            from app.engine.uimapgenerate.graph import build_graph
            result = await asyncio.to_thread(generate_uimap, app_id=app_id, model=model)
            result.update(build_graph(result["units"], mode="deep", source="android_repository"))
        source_revision=_source_revision(app_id)
        result={"id":task_id,"app_id":app_id,"source_revision":source_revision,"model":model,
                "created_at":datetime.now(timezone.utc).isoformat(),**result}
        os.makedirs(DATA_DIR, exist_ok=True)
        result_path = os.path.join(DATA_DIR, f"{validate_app_id(app_id)}.json")
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        _db_execute(
            "UPDATE map_tasks SET status=?, progress=?, message=?, result_path=? WHERE id=?",
            ("success", 100, "UI Map generated.", result_path, task_id)
        )
        _db_execute("INSERT OR REPLACE INTO maps (id,app_id,source_revision,mode,path,created_at) VALUES (?,?,?,?,?,?)",
                    (task_id,app_id,source_revision,mode,result_path,result["created_at"]))
    except Exception as e:
        logger.exception("map task failed: %s", e)
        _db_execute(
            "UPDATE map_tasks SET status=?, message=? WHERE id=?",
            ("error", str(e), task_id)
        )

def _queue_map_task(app_id: str, mode: str, model: Optional[dict] = None) -> str:
    task_id = uuid.uuid4().hex
    _db_execute(
        "INSERT INTO map_tasks (id, app_id, status, progress, message, result_path, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (task_id, app_id, "queued", 0, "Queued.", "", datetime.now(timezone.utc).isoformat())
    )
    asyncio.create_task(_run_map_task(task_id, app_id, mode, model))
    return task_id


@app.post("/api/map/{app_id}/generate")
async def generate_map(app_id: str, payload: MapGenerateRequest, username: str = Depends(current_user)):
    if payload.mode == "deep" and not is_admin(username):
        raise HTTPException(status_code=403, detail="Admin role required for Deep generation")
    try:
        validate_app_id(app_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid app ID")
    if payload.mode == "deep" and (Path(code_manager.get_repo_path(app_id)) / "source.apk").is_file():
        raise HTTPException(status_code=400, detail="Deep map generation for APK projects is not supported; use Fast map and Agent chat")
    if payload.mode == "deep": await _validate_full_map_model(payload.model)
    task_id = _queue_map_task(app_id,payload.mode,payload.model.model_dump() if payload.model else None)
    return {"task_id": task_id, "status": "queued"}


@app.get("/api/map/tasks/{task_id}")
async def get_map_task(task_id: str, username: str = Depends(current_user)):
    row = _db_fetchone(
        "SELECT id, app_id, status, progress, message, result_path, created_at FROM map_tasks WHERE id=?",
        (task_id,)
    )
    if not row:
        raise HTTPException(status_code=404, detail="Task not found")
    (tid, app_id, status, progress, message, result_path, created_at) = row
    return {
        "task_id": tid,
        "app_id": app_id,
        "status": status,
        "progress": progress,
        "message": message,
        "result_path": result_path,
        "created_at": created_at,
        "result_available": bool(result_path) and status == "success"
    }

@app.post("/api/register")
async def register(req: AuthRequest):
    if not req.username.strip() or len(req.password) < 8:
        raise HTTPException(status_code=400, detail="Username required and password must have at least 8 characters")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        role = 'admin' if cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0 else 'user'
        cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", (req.username.strip(), hash_password(req.password), role))
        conn.commit()
        return {"message": "success"}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="User exists")
    finally: conn.close()

@app.post("/api/login")
async def login(req: AuthRequest):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT username, password FROM users WHERE username=?", (req.username,))
    user = cursor.fetchone()
    valid = bool(user and verify_password(req.password, user[1]))
    if valid and not user[1].startswith("pbkdf2_sha256$"):
        cursor.execute("UPDATE users SET password=? WHERE username=?", (hash_password(req.password), req.username))
        conn.commit()
    conn.close()
    if valid:
        return {"username": user[0], "token": issue_token(user[0]), "is_admin": is_admin(user[0])}
    raise HTTPException(status_code=401)


@app.post("/api/logout")
async def logout(username: str = Depends(current_user), authorization: str = Header()):
    revoke_token(authorization[7:])
    return {"message": "success"}


@app.get("/api/me")
async def me(username: str = Depends(current_user)):
    return {"username": username, "is_admin": is_admin(username)}

@app.post("/api/chat")
async def chat(request: ChatRequest, username: str = Depends(current_user)):
    request.project_id = resolve_project_id(validate_app_id(request.app_id), request.project_id)
    if request.provider == "opencode":
        from app.agents.conversations import chat as conversation_chat
        return await conversation_chat(DB_PATH, request, username, CodeManager().get_repo_path(validate_app_id(request.app_id)))
    if request.provider == "builtin" and not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=503, detail="Deep analysis is not configured; Fast map remains available")
    if request.provider == "opencode" and not opencode_available():
        raise HTTPException(status_code=503, detail="OpenCode is not installed on the backend")
    if request.provider == "external" and not external_available():
        raise HTTPException(status_code=503, detail="External Agent is not configured")
    if request.username != username:
        raise HTTPException(status_code=403, detail="Cannot write another user's session")
    # 1. 依然先记录用户消息到数据库
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    owner = cursor.execute("SELECT username FROM sessions WHERE id=?", (request.session_id,)).fetchone()
    if owner and owner[0] != username:
        conn.close()
        raise HTTPException(status_code=403, detail="Cannot write another user's session")
    previous_messages = cursor.execute(
        "SELECT role, content FROM messages WHERE session_id=? ORDER BY rowid DESC LIMIT 6",
        (request.session_id,),
    ).fetchall()
    cursor.execute("INSERT OR IGNORE INTO sessions (id, title, username, app_id, project_id) VALUES (?, ?, ?, ?, ?)",
                   (request.session_id, request.message[:15], request.username, request.app_id, request.project_id))
    cursor.execute("INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)", 
                   (request.session_id, 'user', request.message))
    conn.commit()
    conn.close()

    # 2. 返回一个生成器对象
    async def event_generator():
        full_reply = ""
        try:
            if request.provider == "opencode":
                full_reply = await ask_opencode(_agent_context(request.app_id, request.message, previous_messages), request.app_id)
                yield full_reply
            elif request.provider == "external":
                full_reply = await ask_external(_agent_context(request.app_id, request.message, previous_messages), request.app_id)
                yield full_reply
            else:
                async for chunk in agent.chat_stream(
                    request.message, request.session_id, request.app_id,
                    tool_rounds=request.tool_rounds or 6,
                    force_no_tools=bool(request.force_no_tools),
                ):
                    if chunk:
                        full_reply += chunk
                        yield chunk
        except (RuntimeError, ValueError) as exc:
            full_reply = f"Agent error: {exc}"
            yield full_reply
        
        # 3. 迭代结束后，将完整的 AI 回复存入数据库
        conn_inner = sqlite3.connect(DB_PATH)
        cursor_inner = conn_inner.cursor()
        cursor_inner.execute("INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)", 
                             (request.session_id, 'assistant', full_reply))
        conn_inner.commit()
        conn_inner.close()

    return StreamingResponse(event_generator(), media_type="text/plain")

@app.get("/api/conversations/{session_id}/events")
def conversation_events(session_id: str, after: int = 0, username: str = Depends(current_user)):
    from app.agents.conversations import read_events
    return read_events(DB_PATH, session_id, username, max(0,after))

@app.post("/api/conversations/{session_id}/abort")
async def abort_conversation(session_id: str, username: str = Depends(current_user)):
    from app.agents.conversations import stop
    return await stop(DB_PATH, session_id, username)

@app.get("/api/history/{username}")
async def get_history(username: str, authenticated_user: str = Depends(current_user)):
    if username != authenticated_user:
        raise HTTPException(status_code=403, detail="Cannot read another user's history")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, app_id, project_id FROM sessions WHERE username=?", (username,))
    sessions_list = cursor.fetchall()
    history = []
    for s_id, s_title, s_app, s_project in sessions_list:
        cursor.execute("SELECT role, content FROM messages WHERE session_id=? ORDER BY rowid ASC", (s_id,))
        msgs = [{"role": r, "content": c} for r, c in cursor.fetchall()]
        history.append({"id": s_id, "title": s_title, "project_id": s_project or s_app, "app_id": s_app, "messages": msgs})
    conn.close()
    return history

@app.get("/api/docs")
async def get_docs():
    file_path = os.path.join(DATA_DIR, "docs.md")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return {"content": f.read()}
    except Exception as e:
        logger.error(f"读取文档失败: {e}")
        return {"content": f"# 错误\n读取文件失败: {str(e)}"}

# 初始化 manager
code_manager = CodeManager()

async def get_app_info(app_id: str):
    apps = await get_app_list()  # 复用你已有的函数
    for app in apps:
        if app.get('id') == app_id:
            return app
    return None

@app.get("/api/admin/status/{app_id}")
async def get_app_status(app_id: str, username: str = Depends(current_user)):
    """查询该项目在宿主机/容器内的物理下载状态"""
    status = code_manager.check_status(app_id)
    return {"app_id": app_id, "status": status}


@app.post("/api/admin/task/{app_id}")
async def run_admin_task(app_id: str, payload: dict, username: str = Depends(require_admin)):
    task_type = payload.get("type")
    app_info = await get_app_info(app_id)
    
    if not app_info:
        raise HTTPException(status_code=404, detail="项目不存在")

    # --- 逻辑分发 ---
    if task_type == "download":
        if not app_info.get("repo_url"):
            return {"status": "error", "message": "该项目没有 Git 仓库地址"}
        result = code_manager.download_repo(app_info['repo_url'], app_id)
        result["repo_status"] = code_manager.check_status(app_id)
        return result
        
    elif task_type == "update":
        if app_info.get("source_type") == "apk":
            return {"status": "error", "message": "APK 导入项目不能通过 Git 更新"}
        result = code_manager.update_repo(app_id)
        result["repo_status"] = code_manager.check_status(app_id)
        return result

    return {"status": "error", "message": "未知任务类型"}
