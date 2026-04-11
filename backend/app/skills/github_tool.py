import requests
import os

def get_github_issues(repo_url: str, limit: int = 5):
    """
    获取 GitHub 仓库的最近 Issue 列表。
    """
    try:
        token = os.getenv("GITHUB_TOKEN")
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"} if token else {}
        
        # 解析 owner 和 repo
        parts = repo_url.rstrip('/').split('/')
        owner, repo = parts[-2], parts[-1]
        
        api_url = f"https://api.github.com/repos/{owner}/{repo}/issues"
        params = {"state": "all", "per_page": limit}
        
        response = requests.get(api_url, params=params, headers=headers, timeout=10)
        if response.status_code == 200:
            issues = response.json()
            # 过滤掉 PR，只保留真正的 Issue，且只返回 LLM 关心的核心信息
            return [
                {"number": i['number'], "title": i['title'], "state": i['state']}
                for i in issues if 'pull_request' not in i
            ]
        return f"GitHub API 错误: {response.status_code}"
    except Exception as e:
        return f"执行 get_github_issues 出错: {str(e)}"

def get_github_issue_details(repo_url: str, issue_number: int):
    """
    获取指定 Issue 编号的详细正文和评论，用于深度分析报错原因。
    """
    try:
        token = os.getenv("GITHUB_TOKEN")
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"} if token else {}
        
        parts = repo_url.rstrip('/').split('/')
        owner, repo = parts[-2], parts[-1]
        
        api_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}"
        
        response = requests.get(api_url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return {
                "number": data.get("number"),
                "title": data.get("title"),
                "body": data.get("body", "无正文描述"),
                "state": data.get("state"),
                "created_at": data.get("created_at")
            }
        return f"无法获取 Issue 详情，状态码: {response.status_code}"
    except Exception as e:
        return f"执行 get_github_issue_details 出错: {str(e)}"