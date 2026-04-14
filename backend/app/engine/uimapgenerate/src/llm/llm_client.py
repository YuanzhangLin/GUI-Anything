import os
import yaml
from openai import OpenAI
import pathlib
ROOT_DIR = pathlib.Path(__file__).parent.parent.parent
default_secrets = ROOT_DIR / "config" / "secrets.yaml" # 或者 secrets.yaml


class LLMClient:
    def __init__(self, secrets_path=default_secrets):
        """
        初始化 LLM 客户端
        :param secrets_path: 存放 API Key 的配置文件路径
        """
        # 优先使用后端统一的环境变量（与 app/core/agent.py 保持一致）
        env_api_key = os.getenv("OPENAI_API_KEY")
        env_base_url = os.getenv("OPENAI_BASE_URL")
        env_model = os.getenv("MODEL_NAME")
        env_temp = os.getenv("TEMPERATURE")

        self.config = {}
        file_cfg = None
        try:
            if secrets_path:
                file_cfg = self._load_secrets(secrets_path)
        except Exception:
            file_cfg = None

        cfg = file_cfg or {}
        api_key = env_api_key or cfg.get("api_key")
        base_url = env_base_url or cfg.get("base_url")
        self.model = env_model or cfg.get("model", "deepseek-chat")
        self.temperature = float(env_temp) if env_temp else cfg.get("temperature", 0.2)

        if not api_key:
            raise ValueError(
                "Missing LLM api_key. Set OPENAI_API_KEY or provide engine secrets.yaml."
            )

        # 初始化 OpenAI 客户端 (兼容 OpenAI 格式的各类模型后端)
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def _load_secrets(self, path):
        """加载 secrets.yaml 配置文件"""
        if not os.path.exists(path):
            raise FileNotFoundError(f"'{path}' not found.")
        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            # 兼容你之前的结构：读取 llm 层级下的配置
            return data.get("llm", {})

    def call_chat(self, prompt, system_prompt="You are a helpful assistant.", json_mode=False):
        """
        统一调用接口
        :param prompt: 用户输入的提示词
        :param system_prompt: 系统提示词（定义 LLM 的角色和行为规范）
        :param json_mode: 是否强制要求模型返回 JSON 格式
        :return: LLM 返回的文本内容
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
        
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature
        }
        
        # 如果开启了 json_mode，且模型支持 (如 GPT-4, DeepSeek V3)
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            response = self.client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content.strip()
            print(content)
            return content
        except Exception as e:
            print(f"🔴 [LLM API Error] {e}")
            raise e

# 测试代码 (可选)
if __name__ == "__main__":
    # 如果你想单独运行这个文件测试是否通畅
    try:
        client = LLMClient("configs/secrets.yaml")
        res = client.call_chat("Hello, can you hear me?", system_prompt="Test mode.")
        print(f"Test Response: {res}")
    except Exception as e:
        print(f"Test Failed: {e}")