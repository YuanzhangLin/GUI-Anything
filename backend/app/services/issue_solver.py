import os
import json
import logging

logger = logging.getLogger(__name__)

class IssueSolver:
    def __init__(self, repos_root="/app/repos", data_root="/app/data"):
        self.repos_root = repos_root
        self.data_root = data_root
        if not os.path.exists(self.data_root):
            os.makedirs(self.data_root, exist_ok=True)

    def _get_cache_path(self, app_id: str):
        """每个项目生成一个独立的分析缓存文件"""
        return os.path.join(self.data_root, f"analysis_{app_id}.json")

    def get_cached_solution(self, app_id: str, issue_number: str):
        """检查并读取已有的诊断记录"""
        cache_path = self._get_cache_path(app_id)
        if os.path.exists(cache_path):
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    # 返回该 issue 编号对应的缓存，没有则返回 None
                    return cache_data.get(str(issue_number))
            except Exception as e:
                logger.error(f"读取分析缓存失败: {e}")
        return None

    def _save_solution_to_cache(self, app_id: str, issue_number: str, solution: str):
        """将生成的方案持久化到本地"""
        cache_path = self._get_cache_path(app_id)
        cache_data = {}
        
        # 先读取旧数据
        if os.path.exists(cache_path):
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
            except: pass
        
        # 更新并写入
        cache_data[str(issue_number)] = solution
        try:
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"持久化分析建议失败: {e}")

    async def solve(self, agent, app_id, title, body, issue_number):
        """
        核心求解方法：结合缓存、Issue 和源码生成解决方案
        """
        # 1. 优先尝试从本地缓存获取
        cached_res = self.get_cached_solution(app_id, issue_number)
        if cached_res:
            logger.info(f"Issue #{issue_number} 命中本地缓存")
            return cached_res

        # 2. 如果没有缓存，则构造 Prompt 调用 AI
        solver_prompt = f"""
        你现在是 GUI-Anything 项目的【高级修复专家】。
        任务：针对项目 {app_id} 中报告的 Issue，给出精准的定位和修复代码。

        【问题报告】
        编号: #{issue_number}
        标题: {title}
        详情: {body}

        【执行指令】
        1. 识别该 Issue 涉及的 UI 组件或后台逻辑（如 Activity, Fragment, Service）。
        2. 如果涉及崩溃，请分析堆栈信息定位潜在代码行。
        3. 给出可以直接参考的修复方案（XML 配置或 Java/Kotlin 代码片段）。
        
        请以 Markdown 格式输出。
        """
        
        full_response = ""
        try:
            # 沿用流式传输并聚合结果
            async for chunk in agent.chat_stream(solver_prompt, f"solve_{app_id}_{issue_number}", app_id):
                if chunk:
                    full_response += chunk
            
            # 3. 生成成功后，存入本地缓存
            if full_response:
                self._save_solution_to_cache(app_id, issue_number, full_response)
                
            return full_response
            
        except Exception as e:
            logger.error(f"AI Solver 运行出错: {e}")
            return f"### ❌ AI 诊断失败\n服务暂时不可用: {str(e)}"