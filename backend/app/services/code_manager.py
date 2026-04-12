import os
import subprocess
import logging

logger = logging.getLogger(__name__)

class CodeManager:
    def __init__(self, repos_root: str = None):
        # 默认从环境变量读取，或者使用默认路径
        self.repos_root = repos_root or os.getenv("REPOS_PATH", "/app/repos")
        if not os.path.exists(self.repos_root):
            os.makedirs(self.repos_root, exist_ok=True)
        
        # 容器内 Git 安全配置
        subprocess.run(["git", "config", "--global", "--add", "safe.directory", "*"])

    def get_repo_path(self, app_id: str):
        return os.path.join(self.repos_root, app_id)

    def check_status(self, app_id: str):
        target_path = self.get_repo_path(app_id)
        # 检查文件夹是否存在，且里面是否有 .git 目录（证明下载完整）
        if os.path.exists(os.path.join(target_path, ".git")):
            return "ready"
        elif os.path.exists(target_path):
            return "partial" # 文件夹存在但可能不完整
        return "missing"

    def download_repo(self, repo_url: str, app_id: str):
        target_path = self.get_repo_path(app_id)
        if os.path.exists(target_path):
            return {"status": "exists", "message": "目录已存在"}
        
        try:
            subprocess.run(["git", "clone", repo_url, target_path], check=True, timeout=300)
            return {"status": "success", "message": "下载成功"}
        except Exception as e:
            logger.error(f"Download failed: {e}")
            return {"status": "error", "message": str(e)}

    def update_repo(self, app_id: str):
        target_path = self.get_repo_path(app_id)
        try:
            # 检查更新逻辑... (省略 fetch/status 逻辑)
            subprocess.run(["git", "-C", target_path, "pull"], check=True)
            return {"status": "success", "message": "更新成功"}
        except Exception as e:
            return {"status": "error", "message": str(e)}