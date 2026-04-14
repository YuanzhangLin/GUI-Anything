import os
import json
import yaml
import time
import sys
from app.engine.uimapgenerate.src.analyzer.project_analyzer import ProjectAnalyzer
from app.engine.uimapgenerate.src.llm.llm_client import LLMClient
from app.engine.uimapgenerate.src.analyzer.topology_builder import TopologyBuilder

# ==========================================
# 辅助工具：日志记录与界面美化
# ==========================================
class Logger:
    """支持同时输出到控制台和文件的类"""
    def __init__(self, filename=None):
        self.terminal = sys.stdout
        self.log = open(filename, "w", encoding="utf-8") if filename else None

    def write(self, message):
        self.terminal.write(message)
        if self.log:
            self.log.write(message)

    def flush(self):
        self.terminal.flush()
        if self.log:
            self.log.flush()

def print_banner(text, logger=None):
    msg = f"\n{'='*60}\n {text}\n{'='*60}\n"
    if logger:
        logger.write(msg)
    else:
        print(msg)

def print_human_report(enriched_units, logger):
    """
    分层打印报告：增加全局概览和跳转路径统计
    """
    # --- A. 应用全局概览 ---
    print_banner("📁 AIST 应用组件清单 (App Inventory)", logger)
    
    stats = {"Activity": 0, "Fragment": 0, "Dialog": 0, "Other": 0}
    inventory_lines = []
    
    for unit in enriched_units:
        u_type = unit.get('unit_type', 'Other')
        stats[u_type if u_type in stats else "Other"] += 1
        inventory_lines.append(f"  - [{u_type:8}] {unit['unit_id']}")
    
    logger.write(f"📊 统计概览: " + ", ".join([f"{k}: {v}" for k, v in stats.items()]) + "\n")
    logger.write("\n".join(sorted(inventory_lines)) + "\n")

    # --- B. 详细语义报告 ---
    print_banner("📱 AIST 元素级交互语义与跳转地图", logger)
    
    for unit in enriched_units:
        # 1. 检查是否是入口点
        is_entry = unit.get('is_entry_point', False)
        # 如果是入口点，就加一个星星图标，否则为空字符串
        entry_tag = " 🌟 [APP 入口点]" if is_entry else ""
        
        # 2. 将 entry_tag 拼接到组件名后面打印
        logger.write(f"\n【组件】: {unit['unit_id']} ({unit.get('unit_type', 'Activity')}){entry_tag}\n")
        elements = unit.get('ui_elements', [])
        # 即使没有元素，如果它是一个重要的 Activity，我们也展示它的存在
        if not elements and unit.get('unit_type') != 'Activity':
            continue

        # 1. 提取该组件所有可能的跳转目标 (去重)
        destinations = set()
        for el in elements:
            target = (el.get('interaction') or {}).get('target_unit')
            if target:
                destinations.add(target)

        # 2. 打印组件头部
        logger.write(f"\n【组件】: {unit['unit_id']} ({unit.get('unit_type', 'Activity')})\n")
        if unit.get('layout'):
            logger.write(f"   XML 布局: {unit['layout']}\n")
        
        # 3. 打印跳转图谱 (核心新增！)
        if destinations:
            logger.write(f"   🚩 可迁移/跳转至: {' ➔ '.join(sorted(destinations))}\n")
        else:
            logger.write(f"   📍 终点页 (无出站跳转)\n")

        # 4. 打印元素详情 (按位置分组)
        layout_els = [e for e in elements if e.get('location') == 'layout']
        menu_els = [e for e in elements if e.get('location') == 'menu']
        other_els = [e for e in elements if e.get('location') not in ['layout', 'menu']]

        def _draw_section(title, el_list):
            if not el_list: return
            logger.write(f"\n  --- {title} ---\n")
            for el in el_list:
                logic = el.get('business_logic')
                inter = el.get('interaction') or {}
                target = inter.get('target_unit')
                
                if not logic and not target: symbol = "⚪"
                elif target: symbol = "🔗"
                else: symbol = "⚡"

                source = el.get('source', '')
                tag = " [!]新发现" if source == "code_discovery" else ""
                inherit = f" (来自 {source.split('_')[-1]})" if source.startswith("inherited_from") else ""
                
                logger.write(f"  {symbol} [{el['id']}]{tag}{inherit}\n")
                if el.get('text'): logger.write(f"     文本: \"{el['text']}\"\n")
                if logic: logger.write(f"     功能: {logic}\n")
                if target: logger.write(f"     动作: 跳转至 {target}\n")

        _draw_section("页面布局 (Layout)", layout_els)
        _draw_section("系统菜单 (Menu)", menu_els)
        _draw_section("动态/代码元素", other_els)

        logger.write("\n" + "-"*40 + "\n")

    logger.write(f"\n{'='*60}\n全量语义分析报告生成完成。\n")


def process_single_project(project_config, secrets_path):
    """
    封装原有的 main 逻辑，用于处理单个项目
    """
    project_name = project_config.get("name", "unknown_project")
    overall_start = time.time()
    
    # 动态生成该项目的输出路径
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    master_map_path = os.path.join(output_dir, f"{project_name}_master_map.json")
    log_path = os.path.join(output_dir, f"{project_name}_report.log")
    
    logger = Logger(log_path)
    print_banner(f"🚀 开始批量分析项目: {project_name}", logger)

    # --- 1. 静态分析 ---
    print('# --- 1. 静态分析 ---')
    # 修改：直接把 project_config 传给 analyzer
    analyzer = ProjectAnalyzer(project_config=project_config) 
    analyzer.analyze()
    all_units = analyzer.results

    # --- 2. 排序 ---
    print('# --- 2. 组件排序 (基于继承关系) ---')
    def get_inheritance_depth(unit_id):
        depth = 0
        curr = unit_id
        while curr in analyzer.class_index:
            parent = analyzer.class_index[curr].get('super_class')
            if not parent or parent not in analyzer.class_index: break
            depth += 1
            curr = parent
        return depth

    sorted_unit_ids = sorted([u['unit_id'] for u in all_units], key=get_inheritance_depth)

    # --- 3. 并行语义注入 ---
    print('# --- 3. 并行语义注入 ---')
    llm_client = LLMClient(secrets_path)
    builder = TopologyBuilder(all_units, llm_client)
    builder.build_parallel(sorted_unit_ids, max_workers=8)

    # --- 4. 保存结果 ---
    print('# --- 4. 保存结果 ---')
    master_output = {
        "project_name": project_name,
        "units": all_units 
    }
    with open(master_map_path, "w", encoding="utf-8") as f:
        json.dump(master_output, f, indent=2, ensure_ascii=False)
    
    # --- 5. 打印报告 ---
    print('# --- 5. 打印报告 ---')
    # 注意：这里的 print_human_report 也会根据不同的 logger 存入不同的 log 文件
    from main import print_human_report 
    print_human_report(all_units, logger)

    print(f"✅ {project_name} 分析完成！耗时: {time.time() - overall_start:.2f}s")

def main():
    config_path = "config/project.yaml"
    secrets_path = "config/secrets.yaml"
    
    with open(config_path, "r", encoding="utf-8") as f:
        config_data = yaml.safe_load(f)
    
    project_list = config_data.get("projects", [])
    
    if not project_list:
        print("❌ 配置文件中没有找到项目列表。")
        return

    print(f"🔍 发现 {len(project_list)} 个待分析项目...")
    
    for p_config in project_list:
        try:
            process_single_project(p_config, secrets_path)
        except Exception as e:
            print(f"❌ 项目 {p_config.get('name')} 分析失败: {e}")
            continue

if __name__ == "__main__":
    main()