import os
import requests
import json
import logging

logger = logging.getLogger(__name__)

class IssueService:
    def __init__(self):
        self.token = os.getenv("GITHUB_TOKEN")

    def fetch_and_save_issues(self, repo_url: str, app_id: str):
        """
        从 GitHub 抓取全量 Issue 并返回列表
        """
        try:
            # 1. 构造 API 地址
            parts = repo_url.rstrip('/').split('/')
            owner, repo = parts[-2], parts[-1]
            api_url = f"https://api.github.com/repos/{owner}/{repo}/issues"
            
            headers = {
                "Accept": "application/vnd.github.v3+json"
            }
            if self.token:
                headers["Authorization"] = f"token {self.token}"

            # 2. 发起请求
            # 默认抓取最近 30 条 open 状态的 Issue
            params = {"state": "open", "per_page": 30}
            response = requests.get(api_url, headers=headers, params=params, timeout=15)
            
            if response.status_code != 200:
                return {"status": "error", "message": f"GitHub API 返回错误: {response.status_code}"}

            raw_issues = response.json()
            
            # 3. 数据清洗：只提取前端需要的字段，并过滤掉 Pull Requests
            formatted_issues = []
            for item in raw_issues:
                if "pull_request" not in item:
                    formatted_issues.append({
                        "id": item["id"],
                        "number": item["number"],
                        "title": item["title"],
                        "state": item["state"],
                        "html_url": item["html_url"],
                        "body": item["body"]
                    })

            # 4. (可选) 持久化到本地，方便 AI 后续检索
            cache_path = f"data/issues_{app_id}.json"
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(formatted_issues, f, ensure_ascii=False, indent=2)

            return {
                "status": "success", 
                "message": f"成功同步 {len(formatted_issues)} 条 Issue", 
                "issues": formatted_issues
            }

        except Exception as e:
            logger.error(f"Sync issues failed: {str(e)}")
            return {"status": "error", "message": str(e)}