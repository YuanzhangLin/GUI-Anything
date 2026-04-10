import json
import os
from openai import OpenAI
from app.core.config import config
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

chat_history = {}

class GuiAgent:
    def __init__(self):
        # 从环境变量读取
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com")
        self.model_name = os.getenv("MODEL_NAME", "deepseek-chat")

        if not api_key:
            raise ValueError("OPENAI_API_KEY is not set in environment variables")

        self.client = OpenAI(api_key=api_key, base_url=base_url)

    # --- 关键：补上这个缺失的方法 ---
    def _load_app_context(self, app_id: str):
        """加载 APP 静态拓扑数据"""
        try:
            # 这里的路径要确保在容器内是正确的
            file_path = f"data/{app_id}.json"
            if not os.path.exists(file_path):
                return {"error": f"Data file {file_path} not found"}
                
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            return {"error": f"Failed to load context: {str(e)}"}

    async def chat(self, user_input: str, session_id: str, app_id: str):
        # 这个方法是你之前的非流式实现，保留或删除均可
        app_context = self._load_app_context(app_id)
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

    async def chat_stream(self, user_input: str, session_id: str, app_id: str):
        # 1. 构造系统角色与静态知识锚点
        app_context = self._load_app_context(app_id)
        
        system_prompt = (
            "你是一个专业的 Android 安全审计专家。请根据提供的静态分析数据回答问题。\n\n"
            "<StaticAnalysisContext>\n"
            f"目标项目 ID: {app_id}\n"
            f"应用拓扑与组件数据: {json.dumps(app_context, ensure_ascii=False)}\n"
            "</StaticAnalysisContext>\n\n"
            "注意：在分析时，请务必结合上述静态上下文。如果用户提到的组件在数据中不存在，请如实告知。"
        )

        # 2. 构造审计会话历史
        if session_id not in chat_history:
            chat_history[session_id] = []
        
        raw_history = chat_history[session_id][-8:]
        formatted_messages = [{"role": "system", "content": system_prompt}]

        for msg in raw_history:
            role_label = "以往审计指令" if msg["role"] == "user" else "之前分析结论"
            formatted_messages.append({
                "role": msg["role"],
                "content": f"<{role_label}>\n{msg['content']}\n</{role_label}>"
            })

        # 3. 构造当前审计任务
        current_query = {
            "role": "user",
            "content": f"""
# 当前指令：
请根据以下任务进行分析，仅回复本次分析的内容。
-------
<CurrentAuditTask>\n{user_input}\n</CurrentAuditTask>
-------"""
        }
        formatted_messages.append(current_query)

        # 4. 调用接口
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=formatted_messages,
            stream=True 
        )

        full_reply = ""
        for chunk in response:
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                full_reply += content
                yield content

        # 5. 持久化
        chat_history[session_id].append({"role": "user", "content": user_input})
        chat_history[session_id].append({"role": "assistant", "content": full_reply})