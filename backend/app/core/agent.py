import json
import os
from openai import OpenAI
from app.core.config import config

chat_history = {}

class GuiAgent:
    def __init__(self):
        # 从环境变量读取，如果读取不到则为空
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com")
        self.model_name = os.getenv("MODEL_NAME", "deepseek-chat")

        self.client = OpenAI(api_key=api_key, base_url=base_url)

    async def chat(self, user_input: str, session_id: str, app_id: str):
        # 动态加载对应 APP 的上下文
        app_context = {}
        try:
            with open(f"data/{app_id}.json", "r", encoding="utf-8") as f:
                app_context = json.load(f)
        except:
            app_context = {"error": "Project data not found"}

        if session_id not in chat_history:
            chat_history[session_id] = [
                {"role": "system", "content": f"你是一个 Android 源码分析助手。当前分析项目: {app_id}。上下文: {json.dumps(app_context)}"}
            ]
        
        chat_history[session_id].append({"role": "user", "content": user_input})
        
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=chat_history[session_id][-10:]
        )
        
        reply = response.choices[0].message.content
        chat_history[session_id].append({"role": "assistant", "content": reply})
        return reply

        # backend/app/core/agent.py

    async def chat_stream(self, user_input: str, session_id: str, app_id: str):
        # 加载上下文 (同之前)
        with open(f"data/{app_id}.json", "r", encoding="utf-8") as f:
            app_context = json.load(f)

        if session_id not in chat_history:
            chat_history[session_id] = [
                {"role": "system", "content": f"你是一个 Android 源码分析助手。项目: {app_id}。数据: {json.dumps(app_context)}"}
            ]
        
        chat_history[session_id].append({"role": "user", "content": user_input})

        # 启用 stream=True
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=chat_history[session_id][-10:],
            stream=True 
        )
        full_reply = ""
        for chunk in response:
            content = chunk.choices[0].delta.content
            if content:
                yield content
        chat_history[session_id].append({"role": "assistant", "content": full_reply})