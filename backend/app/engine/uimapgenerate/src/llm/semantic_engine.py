import json
from .prompts.transition_prompt import SYSTEM_PROMPT, format_transition_prompt

class SemanticEngine:
    def __init__(self, llm_client):
        self.llm = llm_client

    def infer_unit_interactions(self, unit_data, inventory_list):
        """
        调用 LLM 推理单个单元的跳转关系
        """
        prompt = format_transition_prompt(unit_data, inventory_list)
        
        try:
            # 开启 json_mode 以获得结构化输出
            response_text = self.llm.call_chat(
                prompt=prompt,
                system_prompt=SYSTEM_PROMPT,
                json_mode=True
            )
            
            # 解析 JSON 结果
            interactions = json.loads(response_text)
            return interactions
        except Exception as e:
            print(f"⚠️ Error inferring {unit_data['unit_id']}: {e}")
            return []