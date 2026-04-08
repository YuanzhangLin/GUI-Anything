import yaml
from pydantic import BaseModel
from typing import Dict

class LLMConfig(BaseModel):
    name: str
    api_key: str
    base_url: str
    model_name: str
    temperature: float

class AppConfig:
    def __init__(self, config_path="config.yml"):
        with open(config_path, "r", encoding="utf-8") as f:
            self._raw = yaml.safe_load(f)
        
        self.active_model = self._raw.get("active_model")
        self.providers: Dict[str, LLMConfig] = {
            k: LLMConfig(**v) for k, v in self._raw.get("llm_providers", {}).items()
        }
        self.map_json_path = self._raw.get("data_paths", {}).get("map_json")

    def get_active_provider(self) -> LLMConfig:
        return self.providers[self.active_model]

config = AppConfig()