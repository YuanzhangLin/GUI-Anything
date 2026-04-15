import json
import os
import yaml
import re
import logging

from openai import OpenAI
from dotenv import load_dotenv
# 导入你的执行工具
from app.skills.github_tool import get_github_issues, get_github_issue_details
from app.skills.repo_tool import repo_list_files, repo_search, repo_read_file

load_dotenv()
chat_history = {}
logger = logging.getLogger(__name__)

TOOL_LOOP_LIMIT_MARKER = "\n\n[[TOOL_LOOP_LIMIT_REACHED]]\n\n"


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

    async def chat_stream(
        self,
        user_input: str,
        session_id: str,
        app_id: str,
        tool_rounds: int = 6,
        force_no_tools: bool = False,
    ):
        # 1. 组装初始上下文（不再默认加载 UI Map/拓扑数据）
        tool_names = []
        try:
            tool_names = [
                (t.get("function") or {}).get("name")
                for t in (self.tools or [])
                if isinstance(t, dict)
            ]
            tool_names = [n for n in tool_names if n]
        except Exception:
            tool_names = []

        system_prompt = (
            f"你是一个 Android 专家。当前分析项目 ID: {app_id}。\n"
            f"用户消息中可能包含「### 附件：GitHub Issue」开头的区块（含标题与正文），"
            f"那是用户从本系统附加的 Issue 全文，请结合其内容作答；"
            f"用户消息中也可能包含「### 附件：UI Map 摘要」开头的区块，那是用户显式附加的 UI 图谱文本摘要，请结合其内容作答；"
            f"必要时也可调用工具补充 GitHub 信息。\n"
            f"注意：你只能调用系统提供的工具（tools 列表中出现的函数）。如果某个能力没有工具支持，请不要虚构函数名，改用自然语言说明需要用户补充什么信息。\n"
            + (f"可用工具列表：{', '.join(tool_names)}\n" if tool_names else "")
        )
        
        messages = [{"role": "system", "content": system_prompt}]
        if session_id in chat_history:
            messages.extend(chat_history[session_id][-6:])
        messages.append({"role": "user", "content": user_input})

        def _run_tool(func_name: str, args: dict):
            # repo_* 工具参数容错：模型经常会给 repo_url，我们统一改为 app_id
            if func_name.startswith("repo_"):
                if "repo_url" in args and "app_id" not in args:
                    args = {k: v for k, v in args.items() if k != "repo_url"}
                    args["app_id"] = app_id
                elif "app_id" not in args:
                    args = dict(args)
                    args["app_id"] = app_id

            logger.info("[tool] call %s args=%s", func_name, list(args.keys()))
            if func_name == "get_github_issues":
                return get_github_issues(**args)
            if func_name == "get_github_issue_details":
                return get_github_issue_details(**args)
            if func_name == "repo_list_files":
                return repo_list_files(**args)
            if func_name == "repo_search":
                res = repo_search(**args)
                try:
                    logger.info("[tool] repo_search hits=%s", len(res) if isinstance(res, list) else "n/a")
                except Exception:
                    pass
                return res
            if func_name == "repo_read_file":
                res = repo_read_file(**args)
                try:
                    logger.info("[tool] repo_read_file truncated=%s", res.get("truncated"))
                except Exception:
                    pass
                return res
            return {
                "error": "UNKNOWN_TOOL",
                "message": f"Tool '{func_name}' is not available in this system.",
                "available_tools": tool_names,
                "hint": "Please call one of the available tools, or answer without tool calls."
            }

        def _extract_dsml_invokes(text: str):
            """
            Best-effort parser for DeepSeek-style DSML tool call markup that may appear
            in message content even when `tool_calls` is not populated.
            """
            if not text:
                return []
            # Example:
            # <｜DSML｜invoke name="repo_search">
            # <｜DSML｜parameter name="app_id" string="true">activitydiary</｜DSML｜parameter>
            # ...
            invokes = []
            for m in re.finditer(r'<\｜DSML\｜invoke name="([^"]+)"\>([\s\S]*?)<\｜DSML\｜\/invoke\>', text):
                name = m.group(1).strip()
                body = m.group(2)
                params = {}
                for pm in re.finditer(r'<\｜DSML\｜parameter name="([^"]+)"[^>]*\>([\s\S]*?)<\｜DSML\｜\/parameter\>', body):
                    k = pm.group(1).strip()
                    v = pm.group(2).strip()
                    # naive type casting
                    if v.isdigit():
                        params[k] = int(v)
                    else:
                        params[k] = v
                invokes.append((name, params))
            return invokes

        # 强制输出：不允许调用工具，直接根据现有上下文生成回答
        if force_no_tools:
            final_stream = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                stream=True,
                tool_choice="none",
            )
        else:
            # 2~4. 多轮工具调用（ReAct loop），直到模型不再请求工具
            max_tool_rounds = max(1, min(int(tool_rounds or 6), 24))
            msg_obj = None
            tool_loop_limit_reached = True
            for _round in range(max_tool_rounds):
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    tools=self.tools,
                    tool_choice="auto",
                )
                msg_obj = response.choices[0].message

                dsml_invokes = []
                try:
                    dsml_invokes = _extract_dsml_invokes(getattr(msg_obj, "content", "") or "")
                except Exception:
                    dsml_invokes = []

                if not msg_obj.tool_calls and not dsml_invokes:
                    tool_loop_limit_reached = False
                    break

                if dsml_invokes and not msg_obj.tool_calls:
                    logger.info("[tool] DSML invokes detected: %s", [n for (n, _a) in dsml_invokes])

                messages.append(msg_obj)

                if msg_obj.tool_calls:
                    for tool_call in msg_obj.tool_calls:
                        func_name = tool_call.function.name
                        args = json.loads(tool_call.function.arguments)
                        result = _run_tool(func_name, args)
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": json.dumps(result, ensure_ascii=False),
                            }
                        )
                else:
                    for (func_name, args) in dsml_invokes[:3]:
                        result = _run_tool(func_name, args)
                        messages.append(
                            {
                                "role": "tool",
                                "content": json.dumps(result, ensure_ascii=False),
                            }
                        )

            # 如果仍然想调用工具，直接返回 marker，让前端显示“继续/强制输出”
            if tool_loop_limit_reached:
                yield TOOL_LOOP_LIMIT_MARKER
                return

            final_stream = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                stream=True,
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