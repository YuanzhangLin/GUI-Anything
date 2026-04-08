import sqlite3
import json
import logging
import os
import yaml
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from fastapi.responses import StreamingResponse
from app.core.agent import GuiAgent

app = FastAPI(title="GUI-Anything Multi-Project")
agent = GuiAgent()

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

@app.get("/api/apps")
async def get_app_list():
    try:
        with open("data/app_list.yml", "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
            return config.get("apps", [])
    except:
        # 回退：扫描 data 目录下的 json
        return [{"id": f.replace('.json', ''), "name": f} for f in os.listdir('data') if f.endswith('.json')]

@app.get("/api/map/{app_id}")
async def get_map(app_id: str):
    file_path = f"data/{app_id}.json"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Map file not found")
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

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
        async for chunk in agent.chat_stream(request.message, request.session_id, request.app_id):
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
        file_path = "data/docs.md"

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return {"content": f.read()}
    except Exception as e:
        logger.error(f"读取文档失败: {e}")
        return {"content": f"# 错误\n读取文件失败: {str(e)}"}