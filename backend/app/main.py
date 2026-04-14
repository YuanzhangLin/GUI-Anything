import sqlite3
import json
import logging
import os
import yaml
import uuid
import asyncio
import random
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from fastapi.responses import StreamingResponse
from app.core.agent import GuiAgent
from app.paths import DATA_DIR
from app.services.code_manager import CodeManager
from app.services.issue_service import IssueService
app = FastAPI(title="GUI-Anything Multi-Project")
agent = GuiAgent()
from app.services.issue_solver import IssueSolver

issue_solver = IssueSolver()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = 'gui_anything.db'

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT)')
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

@app.get("/api/apps")
async def get_app_list():
    try:
        with open(os.path.join(DATA_DIR, "app_list.yml"), "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
            return config.get("apps", [])
    except:
        # 回退：扫描 data 目录下的 json
        if not os.path.isdir(DATA_DIR):
            return []
        return [
            {"id": f.replace(".json", ""), "name": f}
            for f in os.listdir(DATA_DIR)
            if f.endswith(".json")
        ]

@app.get("/api/issues/{app_id}")
async def list_cached_issues(app_id: str):
    """返回管理台「同步 Issue」后写入本地的缓存列表，供对话区附加引用。"""
    cache_path = os.path.join(DATA_DIR, f"issues_{app_id}.json")
    if not os.path.exists(cache_path):
        return []
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error("读取 Issue 缓存失败: %s", e)
        return []


@app.get("/api/map/{app_id}")
async def get_map(app_id: str):
    file_path = os.path.join(DATA_DIR, f"{app_id}.json")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Map file not found")
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/api/map_status/{app_id}")
async def get_map_status(app_id: str):
    """轻量查询：是否已生成 UI Map（不返回大 JSON）。"""
    file_path = os.path.join(DATA_DIR, f"{app_id}.json")
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
    mode: Optional[str] = "mock"


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


def _mock_generate_map(app_id: str) -> dict:
    # 输出结构必须兼容 frontend/src/utils/parser.ts 的 parseAndroidJson
    unit_types = ["Activity", "Fragment", "Dialog", "Other"]
    n = random.randint(6, 12)
    unit_ids = [f"{app_id}.Unit{i}" for i in range(1, n + 1)]

    units = []
    for i, uid in enumerate(unit_ids):
        t = random.choice(unit_types)
        is_entry = i == 0
        # 每个 unit 0-2 个跳转按钮
        ui_elements = []
        for j in range(random.randint(0, 2)):
            target = random.choice(unit_ids)
            if target == uid:
                continue
            ui_elements.append({
                "id": f"{uid}.btn{j+1}",
                "text": f"Go {target.split('.')[-1]}",
                "interaction": {
                    "type": "NAVIGATE_TO",
                    "target_unit": target
                }
            })

        units.append({
            "unit_id": uid,
            "unit_type": t,
            "is_entry_point": is_entry,
            "ui_elements": ui_elements
        })

    return {"app_id": app_id, "generated_at": datetime.now(timezone.utc).isoformat(), "units": units}


async def _run_map_task(task_id: str, app_id: str, mode: str):
    try:
        for p in (5, 15, 30, 55, 75, 90):
            _db_execute(
                "UPDATE map_tasks SET status=?, progress=?, message=? WHERE id=?",
                ("running", p, "Generating UI Map...", task_id)
            )
            await asyncio.sleep(0.6)

        result = None
        if (mode or "mock") != "mock":
            # 真实引擎（如果已集成）优先
            try:
                from app.engine.uimapgenerate.service import generate_uimap  # type: ignore

                result = generate_uimap(app_id=app_id)
            except Exception as e:
                logger.warning("Real UI map engine unavailable, fallback to mock: %s", e)
                result = None

        if result is None:
            result = _mock_generate_map(app_id)
        os.makedirs(DATA_DIR, exist_ok=True)
        result_path = os.path.join(DATA_DIR, f"{app_id}.json")
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
async def generate_map(app_id: str, payload: MapGenerateRequest):
    task_id = uuid.uuid4().hex
    _db_execute(
        "INSERT INTO map_tasks (id, app_id, status, progress, message, result_path, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (task_id, app_id, "queued", 0, "Queued.", "", datetime.now(timezone.utc).isoformat())
    )
    asyncio.create_task(_run_map_task(task_id, app_id, payload.mode or "mock"))
    return {"task_id": task_id, "status": "queued"}


@app.get("/api/map/tasks/{task_id}")
async def get_map_task(task_id: str):
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
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO users VALUES (?, ?)", (req.username, req.password))
        conn.commit()
        return {"message": "success"}
    except:
        raise HTTPException(status_code=400, detail="User exists")
    finally: conn.close()

@app.post("/api/login")
async def login(req: AuthRequest):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM users WHERE username=? AND password=?", (req.username, req.password))
    user = cursor.fetchone()
    conn.close()
    if user: return {"username": user[0]}
    raise HTTPException(status_code=401)

@app.post("/api/chat")
async def chat(request: ChatRequest):
    # 1. 依然先记录用户消息到数据库
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO sessions (id, title, username, app_id) VALUES (?, ?, ?, ?)", 
                   (request.session_id, request.message[:15], request.username, request.app_id))
    cursor.execute("INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)", 
                   (request.session_id, 'user', request.message))
    conn.commit()
    conn.close()

    # 2. 返回一个生成器对象
    async def event_generator():
        full_reply = ""
        # 调用 agent 的流式方法
        async for chunk in agent.chat_stream(
            request.message,
            request.session_id,
            request.app_id,
            tool_rounds=request.tool_rounds or 6,
            force_no_tools=bool(request.force_no_tools),
        ):
            if chunk:
                full_reply += chunk
                yield chunk
        
        # 3. 迭代结束后，将完整的 AI 回复存入数据库
        conn_inner = sqlite3.connect(DB_PATH)
        cursor_inner = conn_inner.cursor()
        cursor_inner.execute("INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)", 
                             (request.session_id, 'assistant', full_reply))
        conn_inner.commit()
        conn_inner.close()

    return StreamingResponse(event_generator(), media_type="text/plain")

@app.get("/api/history/{username}")
async def get_history(username: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, app_id FROM sessions WHERE username=?", (username,))
    sessions_list = cursor.fetchall()
    history = []
    for s_id, s_title, s_app in sessions_list:
        cursor.execute("SELECT role, content FROM messages WHERE session_id=? ORDER BY timestamp ASC", (s_id,))
        msgs = [{"role": r, "content": c} for r, c in cursor.fetchall()]
        history.append({"id": s_id, "title": s_title, "app_id": s_app, "messages": msgs})
    conn.close()
    return history

@app.get("/api/docs")
async def get_docs():
    # 使用绝对路径定位，假设你的程序运行在 /app 下
    file_path = "/app/data/docs.md" 
    
    # 如果不是在 Docker 运行，可以保留原来的 data/docs.md
    if not os.path.exists(file_path):
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
async def get_app_status(app_id: str):
    """查询该项目在宿主机/容器内的物理下载状态"""
    status = code_manager.check_status(app_id)
    return {"app_id": app_id, "status": status}


issue_service = IssueService()

@app.post("/api/admin/task/{app_id}")
async def run_admin_task(app_id: str, payload: dict):
    task_type = payload.get("type")
    app_info = await get_app_info(app_id)
    
    if not app_info:
        raise HTTPException(status_code=404, detail="项目不存在")

    # --- 逻辑分发 ---
    if task_type == "download":
        result = code_manager.download_repo(app_info['repo_url'], app_id)
        result["repo_status"] = code_manager.check_status(app_id)
        return result
        
    elif task_type == "update":
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
async def analyze_issue(payload: dict):
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