"""MCP 工具发现与分组（无 Tkinter 依赖）。

通过 AST 扫描服务端源码里的 ``@mcp.tool`` 装饰器，避免界面方法清单过期。仅依赖
标准库。``tool_source_candidates`` 仅使用 :data:`APP_DIR` / :data:`FROZEN_TEMP_DIR`
覆盖源码与打包两种运行模式（原 GUI 中基于 ``__file__`` 的候选与 ``APP_DIR``
等价，已移除以避免指向 ``lanhu_mcp/services`` 目录）。
"""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Optional

from ..core.paths import APP_DIR, FROZEN_TEMP_DIR

__all__ = [
    "TOOL_DESCRIPTIONS",
    "TOOL_GROUPS",
    "tool_source_candidates",
    "extract_doc_summary",
    "scan_mcp_tools_from_file",
    "discover_mcp_tools",
    "tool_sort_key",
    "group_mcp_tools",
    "MCP_TOOL_NAMES",
]


TOOL_DESCRIPTIONS = {
    "lanhu_resolve_invite_link": "解析蓝湖邀请链接",
    "lanhu_list_product_documents": "列出项目 PRD/原型文档",
    "lanhu_get_pages": "获取 PRD/原型页面列表",
    "lanhu_get_ai_analyze_page_result": "分析 PRD/原型页面并生成开发/测试视角结果",
    "lanhu_get_designs": "获取 UI 设计图列表",
    "lanhu_get_ai_analyze_design_result": "分析 UI 设计图并输出视觉与代码规格",
    "lanhu_get_design_slices": "获取设计切图、图标和素材",
    "lanhu_say": "给项目留言/通知团队",
    "lanhu_say_list": "查看留言列表",
    "lanhu_say_detail": "查看留言详情",
    "lanhu_say_edit": "编辑留言",
    "lanhu_say_delete": "删除留言",
    "lanhu_get_members": "查看项目协作者",
    "lanhu_extract_design_system": "提取颜色、字体、间距等设计系统",
    "lanhu_get_layout_spec": "提取布局结构、尺寸和间距规格",
    "lanhu_extract_component_patterns": "识别可复用组件、按钮、卡片和表单模式",
    "lanhu_design_qa": "检查设计一致性、对比度和质量问题",
    "lanhu_compare_designs": "对比设计版本和变更点",
    "lanhu_generate_framework_code": "按 React/Vue/Flutter 等框架生成还原代码",
    "lanhu_batch_download_assets": "批量下载设计资源和切图",
    "lanhu_extract_interactions": "提取交互、点击区域和表单规则",
    "lanhu_get_design_annotations": "读取设计评论和标注",
    "lanhu_get_version_history": "查看设计版本历史",
    "lanhu_extract_svg": "提取 SVG/矢量图形",
    "lanhu_measure_elements": "测量元素尺寸、距离和位置",
    "lanhu_extract_animation_specs": "提取动效、过渡和微交互规格",
    "lanhu_get_export_options": "读取导出格式和切图配置",
    "lanhu_get_responsive_variants": "分析响应式、多设备和断点适配",
}

TOOL_GROUPS = {
    "需求与原型": (
        "lanhu_resolve_invite_link",
        "lanhu_list_product_documents",
        "lanhu_get_pages",
        "lanhu_get_ai_analyze_page_result",
        "lanhu_extract_interactions",
    ),
    "UI 设计": (
        "lanhu_get_designs",
        "lanhu_get_ai_analyze_design_result",
        "lanhu_get_design_slices",
        "lanhu_get_design_annotations",
        "lanhu_get_version_history",
    ),
    "高还原开发": (
        "lanhu_extract_design_system",
        "lanhu_get_layout_spec",
        "lanhu_extract_component_patterns",
        "lanhu_design_qa",
        "lanhu_compare_designs",
        "lanhu_generate_framework_code",
        "lanhu_batch_download_assets",
        "lanhu_extract_svg",
        "lanhu_measure_elements",
        "lanhu_extract_animation_specs",
        "lanhu_get_export_options",
        "lanhu_get_responsive_variants",
    ),
    "协作": (
        "lanhu_say",
        "lanhu_say_list",
        "lanhu_say_detail",
        "lanhu_say_edit",
        "lanhu_say_delete",
        "lanhu_get_members",
    ),
}

_MCP_TOOLS_CACHE: Optional[list[tuple[str, str]]] = None


def tool_source_candidates() -> list[Path]:
    """返回可能包含 MCP 工具定义的源码文件。"""
    return [
        APP_DIR / 'lanhu_mcp_server.py',
        APP_DIR / 'lanhu_mcp' / 'server.py',
        FROZEN_TEMP_DIR / 'lanhu_mcp_server.py',
        FROZEN_TEMP_DIR / 'lanhu_mcp' / 'server.py',
    ]


def extract_doc_summary(docstring: str) -> str:
    """从工具 docstring 提取第一句可读摘要。"""
    for line in (docstring or "").splitlines():
        text = line.strip().strip("[]")
        if text and not text.startswith("USE THIS WHEN"):
            return text[:80]
    return ""


def scan_mcp_tools_from_file(source_path: Path) -> list[tuple[str, str]]:
    """用 AST 扫描源码中的 @mcp.tool 工具，避免界面方法数量过期。"""
    if not source_path.exists():
        return []
    try:
        tree = ast.parse(source_path.read_text(encoding='utf-8'))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return []
    tools: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            target = decorator.func if isinstance(decorator, ast.Call) else decorator
            if isinstance(target, ast.Attribute) and target.attr == 'tool':
                summary = TOOL_DESCRIPTIONS.get(node.name) or extract_doc_summary(ast.get_docstring(node) or "")
                tools.append((node.name, summary or "MCP 工具方法"))
                break
    return tools


def discover_mcp_tools(refresh: bool = False) -> list[tuple[str, str]]:
    """发现当前服务支持的全部 MCP 工具。"""
    global _MCP_TOOLS_CACHE
    if _MCP_TOOLS_CACHE is not None and not refresh:
        return list(_MCP_TOOLS_CACHE)
    discovered: dict[str, str] = {}
    for source_path in tool_source_candidates():
        for tool_name, description in scan_mcp_tools_from_file(source_path):
            discovered.setdefault(tool_name, description)
    if not discovered:
        discovered = TOOL_DESCRIPTIONS.copy()
    _MCP_TOOLS_CACHE = sorted(discovered.items(), key=lambda item: tool_sort_key(item[0]))
    return list(_MCP_TOOLS_CACHE)


def tool_sort_key(tool_name: str) -> tuple[int, str]:
    """按业务分组顺序排序工具名。"""
    for index, group_tools in enumerate(TOOL_GROUPS.values()):
        if tool_name in group_tools:
            return index, f"{group_tools.index(tool_name):03d}"
    return len(TOOL_GROUPS), tool_name


def group_mcp_tools(tools: list[tuple[str, str]]) -> dict[str, list[tuple[str, str]]]:
    """把 MCP 工具按使用场景分组。"""
    grouped = {group_name: [] for group_name in TOOL_GROUPS}
    grouped["其他"] = []
    for tool_name, description in tools:
        target_group = "其他"
        for group_name, group_tools in TOOL_GROUPS.items():
            if tool_name in group_tools:
                target_group = group_name
                break
        grouped[target_group].append((tool_name, description))
    return {name: items for name, items in grouped.items() if items}


def __getattr__(name: str):
    """惰性计算 ``MCP_TOOL_NAMES``（PEP 562）。

    旧实现在模块导入时立即 ``discover_mcp_tools()``，会对 ``lanhu_mcp_server.py``
    等大文件做 AST 扫描；Flet 页面仅需 ``discover_mcp_tools`` 函数，故把这一开销
    推迟到首次真正访问 ``MCP_TOOL_NAMES`` 时（多为后台线程内），缩短冷启动。
    结果仍由 ``_MCP_TOOLS_CACHE`` 缓存，重复访问不再扫描。
    """
    if name == "MCP_TOOL_NAMES":
        return discover_mcp_tools()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
