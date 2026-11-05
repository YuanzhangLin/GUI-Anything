import sqlite3
import json
import logging
import os
import yaml
import uuid
import asyncio
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Depends, Header, UploadFile, File, Form
from pydantic import BaseModel
from typing import List, Optional, Literal
from fastapi.responses import StreamingResponse
from app.core.agent import GuiAgent
from app.core.opencode_agent import ask as ask_opencode, available as opencode_available
from app.core.external_agent import ask as ask_external, available as external_available
from app.core.auth import current_user, hash_password, verify_password, issue_token, revoke_token, require_admin, is_admin
from app.paths import BACKEND_ROOT, DATA_DIR, validate_app_id
from app.services.code_manager import CodeManager
from app.services.issue_service import IssueService
from app.services.uimap_report import build_report_from_map_json
from app.services.apk_import import import_apk_file, MAX_APK_BYTES
app = FastAPI(title="GUI-Anything Multi-Project")
from app.workbench.api import router as workbench_router
app.include_router(workbench_router)
agent = GuiAgent()
from app.services.issue_solver import IssueSolver

issue_solver = IssueSolver()
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
    # 增加 app_id 字段
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY, 
            title TEXT, 
            username TEXT,
            app_id TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            session_id TEXT, 
            role TEXT, 
            content TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

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

class ChatRequest(BaseModel):
    message: str
    session_id: str
    username: str
    app_id: str # 新增：告知后端当前是哪个APP
    tool_rounds: Optional[int] = 6
    force_no_tools: Optional[bool] = False
    provider: Literal["opencode", "builtin", "external"] = "opencode"


@app.get("/api/agents")
async def get_agents(username: str = Depends(current_user)):
    return {"default": "opencode", "agents": [
        {"id": "opencode", "name": "OpenCode", "available": opencode_available()},
        {"id": "builtin", "name": "内置 Agent", "available": bool(os.getenv("OPENAI_API_KEY"))},
        {"id": "external", "name": "自定义 Agent", "available": external_available()},
    ]}

@app.get("/api/apps")
async def get_app_list():
    apps = []
    try:
        with open(os.path.join(DATA_DIR, "app_list.yml"), "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
            apps = (config or {}).get("apps", []) or []
    except (OSError, yaml.YAMLError):
        pass
    imported = os.path.join(DATA_DIR, "imported_apps.json")
    if os.path.isfile(imported):
        with open(imported, "r", encoding="utf-8") as f:
            apps.extend(json.load(f))
    return apps


@app.post("/api/import/apk")
async def import_apk(app_id: str = Form(), file: UploadFile = File(), username: str = Depends(require_admin)):
    try:
        validate_app_id(app_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid app ID")
    if not file.filename or not file.filename.lower().endswith(".apk"):
        raise HTTPException(status_code=400, detail="Select an APK file")
    if any(app.get("id") == app_id for app in await get_app_list()):
        raise HTTPException(status_code=409, detail="Project ID already exists")
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
    entries.append({"id": app_id, "name": file.filename[:-4], "source_type": "apk", "description": "Imported APK"})
    imported_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"app_id": app_id, "status": "ready"}


@app.get("/api/demo/map")
async def get_demo_map():
    with open(os.path.join(DATA_DIR, "demo.json"), "r", encoding="utf-8") as f:
        return json.load(f)

@app.get("/api/issues/{app_id}")
async def list_cached_issues(app_id: str, username: str = Depends(current_user)):
    """返回管理台「同步 Issue」后写入本地的缓存列表，供对话区附加引用。"""
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
        return {
            "app_id": app_id,
            "exists": True,
            "bytes": stat.st_size,
            "updated_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        }
    except Exception:
        return {"app_id": app_id, "exists": True}


class MapGenerateRequest(BaseModel):
    mode: Literal["fast", "deep"] = "fast"


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


async def _run_map_task(task_id: str, app_id: str, mode: str):
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
            result = await asyncio.to_thread(generate_uimap, app_id=app_id)
            result.update(build_graph(result["units"], mode="deep", source="android_repository"))
        os.makedirs(DATA_DIR, exist_ok=True)
        result_path = os.path.join(DATA_DIR, f"{validate_app_id(app_id)}.json")
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        _db_execute(
            "UPDATE map_tasks SET status=?, progress=?, message=?, result_path=? WHERE id=?",
            ("success", 100, "UI Map generated.", result_path, task_id)
        )
    except Exception as e:
        logger.exception("map task failed: %s", e)
        _db_execute(
            "UPDATE map_tasks SET status=?, message=? WHERE id=?",
            ("error", str(e), task_id)
        )


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
    task_id = uuid.uuid4().hex
    _db_execute(
        "INSERT INTO map_tasks (id, app_id, status, progress, message, result_path, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (task_id, app_id, "queued", 0, "Queued.", "", datetime.now(timezone.utc).isoformat())
    )
    asyncio.create_task(_run_map_task(task_id, app_id, payload.mode))
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
    cursor.execute("INSERT OR IGNORE INTO sessions (id, title, username, app_id) VALUES (?, ?, ?, ?)", 
                   (request.session_id, request.message[:15], request.username, request.app_id))
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

@app.get("/api/history/{username}")
async def get_history(username: str, authenticated_user: str = Depends(current_user)):
    if username != authenticated_user:
        raise HTTPException(status_code=403, detail="Cannot read another user's history")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, app_id FROM sessions WHERE username=?", (username,))
    sessions_list = cursor.fetchall()
    history = []
    for s_id, s_title, s_app in sessions_list:
        cursor.execute("SELECT role, content FROM messages WHERE session_id=? ORDER BY rowid ASC", (s_id,))
        msgs = [{"role": r, "content": c} for r, c in cursor.fetchall()]
        history.append({"id": s_id, "title": s_title, "app_id": s_app, "messages": msgs})
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


issue_service = IssueService()

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

    # 新增：处理 Issue 同步任务
    elif task_type == "sync_issues":
        repo_url = app_info.get("repo_url")
        if not repo_url:
            return {"status": "error", "message": "该项目未配置仓库地址"}
        return issue_service.fetch_and_save_issues(repo_url, app_id)

    return {"status": "error", "message": "未知任务类型"}

@app.post("/api/admin/analyze_issue")
async def analyze_issue(payload: dict, username: str = Depends(require_admin)):
    """
    召唤 AI 专家：针对特定的 Issue 调用 IssueSolver 进行诊断
    """
    app_id = payload.get("app_id")
    title = payload.get("title")
    body = payload.get("body")
    issue_number = payload.get("issue_number") 
    if not app_id or not body:
        raise HTTPException(status_code=400, detail="缺少必要参数 (app_id 或内容)")

    try:
        solution = await issue_solver.solve(
        agent=agent, 
        app_id=app_id, 
        title=payload.get("title"), 
        body=payload.get("body"),
        issue_number=issue_number 
        )
        
        return {"analysis": solution}
    except Exception as e:
        logger.error(f"AI 诊断失败: {e}")
        return {"analysis": f"### ❌ 诊断服务异常\n原因: {str(e)}"}
