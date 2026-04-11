import json
import os
import yaml
from openai import OpenAI
from dotenv import load_dotenv
# 导入你的执行工具
from app.skills.github_tool import get_github_issues, get_github_issue_details

load_dotenv()
chat_history = {}

class GuiAgent:
    def __init__(self):
        self.client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"), 
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com")
        )
        self.model_name = os.getenv("MODEL_NAME", "deepseek-chat")
        
        # --- 重点：从外部 YAML 加载工具描述 ---
        self.skills_file = "app/skills/skills_schema.yaml"
        self.tools = self._load_tools_schema()

    def _load_tools_schema(self):
        """动态加载 YAML 中的工具定义"""
        try:
            with open(self.skills_file, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"警告：加载 skills_schema.yaml 失败: {e}")
            return []

    def _load_app_context(self, app_id: str):
        try:
            with open(f"data/{app_id}.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {"error": "未找到项目的静态分析拓扑数据"}

    async def chat_stream(self, user_input: str, session_id: str, app_id: str):
        # 1. 组装初始上下文
        app_context = self._load_app_context(app_id)
        system_prompt = (
            f"你是一个 Android 专家。当前分析项目 ID: {app_id}。\n"
            f"你可以分析代码拓扑，也可以利用提供的工具查看 GitHub Issue。\n"
            f"静态数据: {json.dumps(app_context, ensure_ascii=False)}"
        )
        
        messages = [{"role": "system", "content": system_prompt}]
        if session_id in chat_history:
            messages.extend(chat_history[session_id][-6:])
        messages.append({"role": "user", "content": user_input})

        # 2. 第一轮请求：意图判定
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            tools=self.tools,  # 这里直接使用从 YAML 加载的内容
            tool_choice="auto" 
        )

        msg_obj = response.choices[0].message
        
        # 3. 核心 ReAct 逻辑：处理工具调用
        if msg_obj.tool_calls:
            messages.append(msg_obj) 
            
            for tool_call in msg_obj.tool_calls:
                func_name = tool_call.function.name
                args = json.loads(tool_call.function.arguments)
                
                # 动态映射执行函数
                # 这里如果工具多了，可以用 dict 来映射，现在只有两个，直接用 if 也很清晰
                if func_name == "get_github_issues":
                    result = get_github_issues(**args)
                elif func_name == "get_github_issue_details":
                    result = get_github_issue_details(**args)
                else:
                    result = "未知工具调用"
                
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result, ensure_ascii=False)
                })
            
            # 4. 第二轮请求：基于工具返回结果生成最终流式回答
            final_stream = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                stream=True
            )
        else:
            # 没有工具调用意图，直接生成普通流式回答
            final_stream = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                stream=True
            )

        # 5. 处理流式输出并持久化历史
        full_reply = ""
        for chunk in final_stream:
            if chunk.choices[0].delta.content:
                c = chunk.choices[0].delta.content
                full_reply += c
                yield c

        if session_id not in chat_history: chat_history[session_id] = []
        chat_history[session_id].append({"role": "user", "content": user_input})
        chat_history[session_id].append({"role": "assistant", "content": full_reply})