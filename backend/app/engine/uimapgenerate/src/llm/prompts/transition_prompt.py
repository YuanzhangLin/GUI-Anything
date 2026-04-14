# src/llm/prompts/transition_prompt.py

SYSTEM_PROMPT = """你是一个安卓源码分析专家。
你的任务是推断组件间的跳转关系。请特别注意：
1. 菜单项：识别是直接可见的图标还是隐藏在 'More Options' (三个点) 菜单中。
2. 对话框按钮：识别是 '确定' (Positive)、'取消' (Negative) 还是 '中立' (Neutral) 按钮。
3. 文本语义：如果 ID 关联了字符串，请根据字符串含义推断业务逻辑。
"""

USER_PROMPT_TEMPLATE = """
### 1. 全局清单 (目标组件池):
{inventory}

### 2. 当前分析组件: {unit_id} ({unit_type})
关联布局: {layout}

#### UI 元素及文本:
{ui_elements}

#### 交互逻辑代码切片:
{code_snippets}

---
请分析跳转关系，必须返回 JSON 数组。
对于每个跳转，请额外补充 'trigger_type' 和 'interaction_detail'：

[
  {{
    "trigger_id": "元素 ID (如 btn_save 或 menu_settings)",
    "trigger_type": "UI_ELEMENT / MENU_ITEM / DIALOG_BUTTON",
    "target_unit": "目标类名",
    "interaction_type": "NAVIGATE_TO / HOST_FRAGMENT / SHOW_DIALOG",
    "interaction_detail": {{
        "is_overflow_menu": true/false (如果是菜单项),
        "dialog_role": "POSITIVE / NEGATIVE / NEUTRAL" (如果是对话框按钮),
        "display_text": "按钮或菜单显示的文本内容"
    }},
    "logic": "业务逻辑描述"
  }}
]
"""

def build_transition_prompt(unit_data, inventory_list):
    # 增强 UI 描述，加入 text 内容
    ui_elements_info = []
    for e in unit_data.get('ui_elements', []):
        text_part = f" (Text: '{e['text']}')" if e.get('text') else ""
        ui_elements_info.append(f"- {e['id']} [{e['type']}]{text_part}")
    
    ui_desc = "\n".join(ui_elements_info)
    
    # 交互代码
    code_desc = ""
    for idx, inter in enumerate(unit_data.get('interactions', [])):
        code_desc += f"\nSnippet {idx}:\n```kotlin\n{inter.get('code_snippet', '')}\n```"

    return USER_PROMPT_TEMPLATE.format(
        inventory="\n".join([f"- {name}" for name in inventory_list]),
        unit_id=unit_data['unit_id'],
        unit_type=unit_data['unit_type'],
        layout=unit_data.get('layout', 'None'),
        ui_elements=ui_desc,
        code_snippets=code_desc
    )