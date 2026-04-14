# src/llm/prompts/element_semantic_prompt.py

SYSTEM_PROMPT = """你是一个安卓源码语义分析专家。你的任务是分析 UI 元素与代码逻辑的对应关系。

### 核心任务：
1. **精准对齐**：为提供的 UI ID 补充其在源码中实现的业务功能。
2. **符号提取（极其重要）**：如果点击某个 ID 触发了一个函数调用（例如 `R.id.add_xx -> addXX()`），你必须将函数名 `addXX()` 填写在 `target_unit` 字段中。
3. **发现新 ID**：若代码操作了 UI 列表中不存在的 ID（如菜单项），请将其作为新元素加入，并推测其类型和文本。

### 位置(location)判定逻辑：
- **menu**：ID 出现在 `setOnMenuItemClickListener`、`when(menuItem.itemId)` 或 `inflateMenu` 块中。
- **layout**：ID 出现在普通的 `setOnClickListener` 或 `binding.xxx` 块中。

必须以规范的 JSON 数组返回，严禁输出解释性文字。"""

USER_PROMPT_TEMPLATE = """
### 待分析组件: {unit_id}
### 现有静态 UI 列表: 
{ui_elements_json}

### 交互代码切片: 
{code_snippets}

---
### 提取要求：
1. 请检查 `when(menuItem.itemId)` 或点击事件中的每一个分支。
2. **必须提取代码符号**：如果逻辑是 `R.id.xx -> launchxxx()`，则 `target_unit` 应填写 `"launchxxx()"`。
3. 如果是页面跳转，`target_unit` 填写目标 Activity 类名（如 `"XXActivity"`）。
4. 生成的结果必须要有依据，如果没有依据，请不要生成结果。
请返回如下 JSON 数组:
[
  {{
    "id": "元素ID",
    "location": "layout / menu",
    "inferred_type": "MenuItem / Button / ImageButton",
    "display_text": "推测显示的文本",
    "business_logic": "该元素实现的具体业务功能描述",
    "interaction": {{
        "type": "NAVIGATE_TO / SHOW_DIALOG / INTERNAL_FUNCTION",
        "target_unit": "此处填：具体的函数名() 或 目标Activity类名"
    }},
    "source":"直接给出依据的代码片段"
  }}
]
"""

def build_element_semantic_prompt(unit_data, inventory_list):
    # 提取现有的元素简表
    existing_elements = []
    for e in unit_data.get('ui_elements', []):
        existing_elements.append({
            "id": e['id'], 
            "type": e.get('type', 'Unknown'), 
            "text": e.get('text', '')
        })

    import json
    # 格式化代码切片
    code_desc = ""
    for idx, inter in enumerate(unit_data.get('interactions', [])):
        code_desc += f"\n[Snippet {idx}]:\n```kotlin\n{inter.get('code_snippet', '')}\n```\n"

    return USER_PROMPT_TEMPLATE.format(
        unit_id=unit_data['unit_id'],
        ui_elements_json=json.dumps(existing_elements, ensure_ascii=False, indent=2),
        code_snippets=code_desc
    )