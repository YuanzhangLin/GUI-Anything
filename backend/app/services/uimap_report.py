"""Human-readable UI Map report (text) from units JSON."""

from __future__ import annotations

from typing import Any, Dict, List, TextIO


def print_banner(text: str, out: TextIO) -> None:
    msg = f"\n{'=' * 60}\n {text}\n{'=' * 60}\n"
    out.write(msg)


def print_human_report(enriched_units: List[Dict[str, Any]], out: TextIO) -> None:
    """
    分层打印报告：增加全局概览和跳转路径统计。
    与引擎侧 print_human_report 逻辑一致，输出到 TextIO。
    """
    print_banner("📁 AIST 应用组件清单 (App Inventory)", out)

    stats = {"Activity": 0, "Fragment": 0, "Dialog": 0, "Other": 0}
    inventory_lines: List[str] = []

    for unit in enriched_units:
        u_type = unit.get("unit_type", "Other")
        stats[u_type if u_type in stats else "Other"] += 1
        inventory_lines.append(f"  - [{u_type:8}] {unit['unit_id']}")

    out.write("📊 统计概览: " + ", ".join([f"{k}: {v}" for k, v in stats.items()]) + "\n")
    out.write("\n".join(sorted(inventory_lines)) + "\n")

    print_banner("📱 AIST 元素级交互语义与跳转地图", out)

    for unit in enriched_units:
        is_entry = unit.get("is_entry_point", False)
        entry_tag = " 🌟 [APP 入口点]" if is_entry else ""

        out.write(f"\n【组件】: {unit['unit_id']} ({unit.get('unit_type', 'Activity')}){entry_tag}\n")
        elements = unit.get("ui_elements", [])
        if not elements and unit.get("unit_type") != "Activity":
            continue

        destinations = set()
        for el in elements:
            target = (el.get("interaction") or {}).get("target_unit")
            if target:
                destinations.add(target)

        out.write(f"\n【组件】: {unit['unit_id']} ({unit.get('unit_type', 'Activity')})\n")
        if unit.get("layout"):
            out.write(f"   XML 布局: {unit['layout']}\n")

        if destinations:
            out.write(f"   🚩 可迁移/跳转至: {' ➔ '.join(sorted(destinations))}\n")
        else:
            out.write("   📍 终点页 (无出站跳转)\n")

        layout_els = [e for e in elements if e.get("location") == "layout"]
        menu_els = [e for e in elements if e.get("location") == "menu"]
        other_els = [e for e in elements if e.get("location") not in ["layout", "menu"]]

        def _draw_section(title: str, el_list: List[Dict[str, Any]]) -> None:
            if not el_list:
                return
            out.write(f"\n  --- {title} ---\n")
            for el in el_list:
                logic = el.get("business_logic")
                inter = el.get("interaction") or {}
                target = inter.get("target_unit")

                if not logic and not target:
                    symbol = "⚪"
                elif target:
                    symbol = "🔗"
                else:
                    symbol = "⚡"

                source = el.get("source", "")
                tag = " [!]新发现" if source == "code_discovery" else ""
                inherit = f" (来自 {source.split('_')[-1]})" if str(source).startswith("inherited_from") else ""

                out.write(f"  {symbol} [{el['id']}]{tag}{inherit}\n")
                if el.get("text"):
                    out.write(f"     文本: \"{el['text']}\"\n")
                if logic:
                    out.write(f"     功能: {logic}\n")
                if target:
                    out.write(f"     动作: 跳转至 {target}\n")

        _draw_section("页面布局 (Layout)", layout_els)
        _draw_section("系统菜单 (Menu)", menu_els)
        _draw_section("动态/代码元素", other_els)

        out.write("\n" + "-" * 40 + "\n")

    out.write(f"\n{'=' * 60}\n全量语义分析报告生成完成。\n")


def build_report_from_map_json(data: Dict[str, Any]) -> str:
    """从 get_map 返回的 dict 中提取 units 并生成报告文本。"""
    content = data.get("units") or data.get("topology")
    if not isinstance(content, list):
        raise ValueError("JSON 中缺少 units 列表或格式无法识别")
    from io import StringIO

    buf = StringIO()
    print_human_report(content, buf)
    return buf.getvalue()
