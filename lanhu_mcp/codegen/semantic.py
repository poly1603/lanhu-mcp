"""
语义化分析器 - 从设计稿推断 HTML5 语义标签、ARIA 属性和无障碍结构

核心规则引擎：
1. 视觉层级 → HTML5 语义标签
2. 内容特征 → ARIA 角色/属性
3. 交互模式 → 键盘导航/焦点管理
4. 文档结构 → 标题层级/大纲
"""
from __future__ import annotations

import re
from typing import Optional, List, Dict, Tuple, Set
from collections import Counter

from lanhu_mcp.codegen.ir import (
    ComponentIR,
    ComponentType,
    SemanticTag,
    A11ySpec,
    EventSpec,
    PropSpec,
    SlotSpec,
    DesignIR,
    PageIR,
)


# ============================================================
# 语义标签推断规则
# ============================================================

# 名称关键词 → 语义标签映射
_NAME_TO_TAG: Dict[str, List[Tuple[SemanticTag, float]]] = {
    # 导航类
    "nav": [(SemanticTag.NAV, 0.95)],
    "navigation": [(SemanticTag.NAV, 0.95)],
    "navbar": [(SemanticTag.NAV, 0.9)],
    "header": [(SemanticTag.HEADER, 0.9)],
    "topbar": [(SemanticTag.HEADER, 0.85)],
    "footer": [(SemanticTag.FOOTER, 0.95)],
    "sidebar": [(SemanticTag.ASIDE, 0.9)],
    "aside": [(SemanticTag.ASIDE, 0.95)],
    "menu": [(SemanticTag.NAV, 0.8)],
    # 主体内容
    "main": [(SemanticTag.MAIN, 0.95)],
    "content": [(SemanticTag.MAIN, 0.7)],
    "body": [(SemanticTag.MAIN, 0.6)],
    "container": [(SemanticTag.DIV, 0.8)],
    "wrapper": [(SemanticTag.DIV, 0.8)],
    # 区块
    "section": [(SemanticTag.SECTION, 0.9)],
    "article": [(SemanticTag.ARTICLE, 0.9)],
    "post": [(SemanticTag.ARTICLE, 0.85)],
    "blog": [(SemanticTag.ARTICLE, 0.8)],
    "card": [(SemanticTag.ARTICLE, 0.7)],
    # 文本
    "title": [(SemanticTag.H1, 0.8), (SemanticTag.H2, 0.6)],
    "heading": [(SemanticTag.H1, 0.7)],
    "subtitle": [(SemanticTag.H2, 0.8)],
    "paragraph": [(SemanticTag.P, 0.9)],
    "text": [(SemanticTag.P, 0.6)],
    "label": [(SemanticTag.LABEL, 0.8)],
    "caption": [(SemanticTag.FIGCAPTION, 0.9)],
    "description": [(SemanticTag.P, 0.7)],
    # 列表
    "list": [(SemanticTag.UL, 0.8)],
    "item": [(SemanticTag.LI, 0.9)],
    "menu-item": [(SemanticTag.LI, 0.9)],
    # 表格
    "table": [(SemanticTag.TABLE, 0.95)],
    "thead": [(SemanticTag.THEAD, 0.95)],
    "tbody": [(SemanticTag.TBODY, 0.95)],
    "row": [(SemanticTag.TR, 0.9)],
    "cell": [(SemanticTag.TD, 0.9)],
    "header-cell": [(SemanticTag.TH, 0.9)],
    # 表单
    "form": [(SemanticTag.FORM, 0.95)],
    "input": [(SemanticTag.INPUT, 0.9)],
    "textarea": [(SemanticTag.TEXTAREA, 0.95)],
    "select": [(SemanticTag.SELECT, 0.95)],
    "checkbox": [(SemanticTag.INPUT, 0.9)],
    "radio": [(SemanticTag.INPUT, 0.9)],
    "switch": [(SemanticTag.INPUT, 0.85)],
    "button": [(SemanticTag.BUTTON, 0.9)],
    "submit": [(SemanticTag.BUTTON, 0.9)],
    "search": [(SemanticTag.INPUT, 0.8)],
    # 媒体
    "image": [(SemanticTag.IMG, 0.9)],
    "img": [(SemanticTag.IMG, 0.95)],
    "avatar": [(SemanticTag.IMG, 0.8)],
    "icon": [(SemanticTag.SVG, 0.7)],
    "logo": [(SemanticTag.IMG, 0.8)],
    "banner": [(SemanticTag.IMG, 0.7)],
    "video": [(SemanticTag.VIDEO, 0.95)],
    # 其他
    "divider": [(SemanticTag.HR, 0.9)],
    "separator": [(SemanticTag.HR, 0.85)],
    "code": [(SemanticTag.CODE, 0.9)],
    "pre": [(SemanticTag.PRE, 0.9)],
    "quote": [(SemanticTag.BLOCKQUOTE, 0.9)],
    "dialog": [(SemanticTag.DIALOG, 0.95)],
    "modal": [(SemanticTag.DIALOG, 0.9)],
    "drawer": [(SemanticTag.DIALOG, 0.85)],
    "tooltip": [(SemanticTag.SPAN, 0.8)],
    "badge": [(SemanticTag.SPAN, 0.7)],
    "tag": [(SemanticTag.SPAN, 0.7)],
    "alert": [(SemanticTag.DIV, 0.7)],
    "toast": [(SemanticTag.DIV, 0.7)],
    "breadcrumb": [(SemanticTag.NAV, 0.8)],
    "pagination": [(SemanticTag.NAV, 0.8)],
    "steps": [(SemanticTag.OL, 0.7)],
    "timeline": [(SemanticTag.OL, 0.7)],
    "result": [(SemanticTag.SECTION, 0.7)],
    "empty": [(SemanticTag.SECTION, 0.6)],
    "skeleton": [(SemanticTag.DIV, 0.8)],
    "spinner": [(SemanticTag.DIV, 0.8)],
    "hero": [(SemanticTag.SECTION, 0.8)],
    "footer-nav": [(SemanticTag.FOOTER, 0.8)],
}

# 组件类型 → 默认语义标签
_TYPE_TO_TAG: Dict[ComponentType, SemanticTag] = {
    ComponentType.BUTTON: SemanticTag.BUTTON,
    ComponentType.INPUT: SemanticTag.INPUT,
    ComponentType.TEXTAREA: SemanticTag.TEXTAREA,
    ComponentType.SELECT: SemanticTag.SELECT,
    ComponentType.CHECKBOX: SemanticTag.INPUT,
    ComponentType.RADIO: SemanticTag.INPUT,
    ComponentType.SWITCH: SemanticTag.INPUT,
    ComponentType.FORM: SemanticTag.FORM,
    ComponentType.NAVBAR: SemanticTag.NAV,
    ComponentType.SIDEBAR: SemanticTag.ASIDE,
    ComponentType.FOOTER: SemanticTag.FOOTER,
    ComponentType.TABLE: SemanticTag.TABLE,
    ComponentType.MODAL: SemanticTag.DIALOG,
    ComponentType.DRAWER: SemanticTag.DIALOG,
    ComponentType.ACCORDION: SemanticTag.DETAILS,
    ComponentType.IMAGE: SemanticTag.IMG,
    ComponentType.TEXT: SemanticTag.P,
    ComponentType.DIVIDER: SemanticTag.HR,
    ComponentType.BREADCRUMB: SemanticTag.NAV,
    ComponentType.PAGINATION: SemanticTag.NAV,
    ComponentType.STEPS: SemanticTag.OL,
    ComponentType.TIMELINE: SemanticTag.OL,
    ComponentType.CARD: SemanticTag.ARTICLE,
    ComponentType.HERO: SemanticTag.SECTION,
}


# ============================================================
# ARIA 角色推断规则
# ============================================================

# 组件类型 → ARIA 角色
_TYPE_TO_ARIA_ROLE: Dict[ComponentType, str] = {
    ComponentType.BUTTON: "button",
    ComponentType.INPUT: "textbox",
    ComponentType.TEXTAREA: "textbox",
    ComponentType.SELECT: "listbox",
    ComponentType.CHECKBOX: "checkbox",
    ComponentType.RADIO: "radiogroup",
    ComponentType.SWITCH: "switch",
    ComponentType.SLIDER: "slider",
    ComponentType.NAVBAR: "navigation",
    ComponentType.BREADCRUMB: "navigation",
    ComponentType.PAGINATION: "navigation",
    ComponentType.TABS: "tablist",
    ComponentType.ACCORDION: "region",
    ComponentType.TABLE: "table",
    ComponentType.MODAL: "dialog",
    ComponentType.DRAWER: "dialog",
    ComponentType.DROPDOWN: "menu",
    ComponentType.MENU: "menu",
    ComponentType.TREE: "tree",
    ComponentType.PROGRESS: "progressbar",
    ComponentType.SPINNER: "status",
    ComponentType.ALERT: "alert",
    ComponentType.TOAST: "status",
    ComponentType.SEARCH: "search",
    ComponentType.LIST: "list",
    ComponentType.STEPS: "list",
    ComponentType.TIMELINE: "list",
    ComponentType.SKELETON: "presentation",
    ComponentType.IMAGE: "img",
    ComponentType.AVATAR: "img",
    ComponentType.DIVIDER: "separator",
    ComponentType.BADGE: "status",
    ComponentType.TOOLTIP: "tooltip",
    ComponentType.POPOVER: "dialog",
}

# 标签名 → ARIA 角色
_TAG_TO_ARIA_ROLE: Dict[SemanticTag, str] = {
    SemanticTag.NAV: "navigation",
    SemanticTag.MAIN: "main",
    SemanticTag.ASIDE: "complementary",
    SemanticTag.HEADER: "banner",
    SemanticTag.FOOTER: "contentinfo",
    SemanticTag.FORM: "form",
    SemanticTag.TABLE: "table",
    SemanticTag.DIALOG: "dialog",
    SemanticTag.SECTION: "region",
    SemanticTag.ARTICLE: "article",
    SemanticTag.OL: "list",
    SemanticTag.UL: "list",
    SemanticTag.H1: "heading",
    SemanticTag.H2: "heading",
    SemanticTag.H3: "heading",
    SemanticTag.H4: "heading",
    SemanticTag.H5: "heading",
    SemanticTag.H6: "heading",
}


# ============================================================
# 交互类型检测规则
# ============================================================

# 名称关键词 → 交互模式
_NAME_TO_INTERACTION: Dict[str, Dict[str, Any]] = {
    "modal": {
        "type": "modal",
        "events": ["open", "close"],
        "keyboard": {"Escape": "close", "Tab": "focus-trap"},
        "focus_trap": True,
        "focus_restore": True,
        "overlay_click": "close",
    },
    "dialog": {
        "type": "modal",
        "events": ["open", "close"],
        "keyboard": {"Escape": "close", "Tab": "focus-trap"},
        "focus_trap": True,
        "focus_restore": True,
    },
    "drawer": {
        "type": "drawer",
        "events": ["open", "close"],
        "keyboard": {"Escape": "close"},
        "focus_trap": True,
        "focus_restore": True,
        "overlay_click": "close",
        "animation": "slide",
    },
    "dropdown": {
        "type": "dropdown",
        "events": ["open", "close", "select"],
        "keyboard": {"Escape": "close", "ArrowDown": "next", "ArrowUp": "prev", "Enter": "select"},
        "positioning": "floating",
    },
    "menu": {
        "type": "menu",
        "events": ["open", "close", "select"],
        "keyboard": {"Escape": "close", "ArrowDown": "next", "ArrowUp": "prev", "Enter": "select", "Home": "first", "End": "last"},
    },
    "tabs": {
        "type": "tabs",
        "events": ["change"],
        "keyboard": {"ArrowLeft": "prev-tab", "ArrowRight": "next-tab", "Home": "first-tab", "End": "last-tab"},
        "aria": {"role": "tablist", "tab": "tab", "tabpanel": "tabpanel"},
    },
    "accordion": {
        "type": "accordion",
        "events": ["toggle"],
        "keyboard": {"Enter": "toggle", "Space": "toggle"},
        "aria": {"expanded": "aria-expanded"},
    },
    "carousel": {
        "type": "carousel",
        "events": ["prev", "next", "goto"],
        "keyboard": {"ArrowLeft": "prev", "ArrowRight": "next"},
        "autoplay": True,
        "pause_on_hover": True,
    },
    "tooltip": {
        "type": "tooltip",
        "events": ["show", "hide"],
        "keyboard": {"Escape": "hide"},
        "positioning": "floating",
        "delay_show": 300,
        "delay_hide": 100,
    },
    "popover": {
        "type": "popover",
        "events": ["open", "close"],
        "keyboard": {"Escape": "close"},
        "positioning": "floating",
    },
    "tree": {
        "type": "tree",
        "events": ["select", "expand", "collapse"],
        "keyboard": {"ArrowDown": "next", "ArrowUp": "prev", "ArrowRight": "expand", "ArrowLeft": "collapse", "Home": "first", "End": "last"},
    },
    "table": {
        "type": "table",
        "events": ["sort", "filter", "page", "select"],
        "keyboard": {"ArrowDown": "next-row", "ArrowUp": "prev-row", "ArrowRight": "next-cell", "ArrowLeft": "prev-cell"},
        "features": ["sort", "filter", "pagination", "virtual-scroll", "row-select"],
    },
    "select": {
        "type": "select",
        "events": ["change", "open", "close"],
        "keyboard": {"Escape": "close", "ArrowDown": "next", "ArrowUp": "prev", "Enter": "select"},
        "features": ["search", "multi", "group"],
    },
    "upload": {
        "type": "upload",
        "events": ["upload", "remove", "preview"],
        "keyboard": {"Enter": "upload"},
        "features": ["drag-drop", "preview", "progress"],
    },
    "carousel": {
        "type": "carousel",
        "events": ["prev", "next", "goto"],
        "autoplay": True,
        "pause_on_hover": True,
    },
    "stepper": {
        "type": "stepper",
        "events": ["next", "prev", "submit"],
    },
    "form": {
        "type": "form",
        "events": ["submit", "reset", "validate"],
        "features": ["validation", "dirty-tracking", "field-array"],
    },
}


# ============================================================
# 语义化分析器
# ============================================================

class SemanticAnalyzer:
    """
    语义化分析器 - 从设计稿推断 HTML5 语义标签和 ARIA 属性

    输入：设计稿 Sketch JSON 或 ComponentIR
    输出：增强后的 ComponentIR（带有语义标签和 ARIA 属性）
    """

    def __init__(self):
        self._heading_counter = 0
        self._id_counter = 0

    def analyze_design(self, ir: DesignIR) -> DesignIR:
        """
        分析整个设计 IR，增强所有组件的语义信息。

        Args:
            ir: 设计 IR

        Returns:
            增强后的 Design IR
        """
        self._heading_counter = 0
        self._id_counter = 0

        # 分析所有页面
        for page in ir.pages:
            self._analyze_page(page)

        # 分析所有组件
        for comp in ir.components:
            self._analyze_component(comp, parent_tag=SemanticTag.DIV)

        # 分析组件树中的子组件
        for comp in ir.components:
            self._analyze_children(comp)

        return ir

    def analyze_component(self, comp: ComponentIR, context: Dict[str, Any] = None) -> ComponentIR:
        """
        分析单个组件，推断语义标签和 ARIA 属性。

        Args:
            comp: 组件 IR
            context: 上下文信息

        Returns:
            增强后的组件 IR
        """
        self._analyze_component(comp, parent_tag=SemanticTag.DIV)
        return comp

    def _analyze_page(self, page: PageIR):
        """分析页面级语义"""
        # 设置页面语义标签
        if page.name.lower() in ("home", "index", "首页"):
            page.semantic_tag = SemanticTag.MAIN
        elif page.name.lower() in ("about", "关于"):
            page.semantic_tag = SemanticTag.ARTICLE
        elif page.name.lower() in ("blog", "news", "博客", "新闻"):
            page.semantic_tag = SemanticTag.ARTICLE
        elif page.name.lower() in ("help", "faq", "帮助"):
            page.semantic_tag = SemanticTag.ARTICLE
        elif page.name.lower() in ("settings", "profile", "设置", "个人"):
            page.semantic_tag = SemanticTag.SECTION
        else:
            page.semantic_tag = SemanticTag.MAIN

    def _analyze_component(self, comp: ComponentIR, parent_tag: SemanticTag):
        """分析单个组件的语义"""
        # 1. 推断语义标签
        tag = self._infer_semantic_tag(comp)
        comp.semantic_tag = tag

        # 2. 推断 ARIA 属性
        if comp.aria is None:
            comp.aria = A11ySpec()
        self._infer_aria(comp)

        # 3. 推断交互模式
        self._infer_interaction(comp)

        # 4. 生成唯一 ID
        comp.aria.aria_labelledby = comp.aria.aria_labelledby or self._generate_id(comp.name)

    def _analyze_children(self, comp: ComponentIR):
        """递归分析子组件"""
        for child in comp.children:
            self._analyze_component(child, parent_tag=comp.semantic_tag)
            self._analyze_children(child)

    def _infer_semantic_tag(self, comp: ComponentIR) -> SemanticTag:
        """推断语义标签"""
        # 优先级 1：组件类型直接映射
        if comp.component_type in _TYPE_TO_TAG:
            return _TYPE_TO_TAG[comp.component_type]

        # 优先级 2：名称关键词匹配
        name_lower = comp.name.lower()
        # 尝试完整名称
        if name_lower in _NAME_TO_TAG:
            candidates = _NAME_TO_TAG[name_lower]
            return candidates[0][0]

        # 尝试部分匹配
        best_tag = None
        best_score = 0
        for keyword, candidates in _NAME_TO_TAG.items():
            if keyword in name_lower:
                for tag, score in candidates:
                    if score > best_score:
                        best_score = score
                        best_tag = tag

        if best_tag and best_score >= 0.7:
            return best_tag

        # 优先级 3：视觉特征推断
        return self._infer_tag_from_visual(comp)

    def _infer_tag_from_visual(self, comp: ComponentIR) -> SemanticTag:
        """从视觉特征推断标签"""
        pos = comp.design_position
        styles = comp.design_styles

        w = pos.get("width", 0)
        h = pos.get("height", 0)

        # 宽度接近页面宽度 → 可能是 section/header/footer
        if w > 600:
            if h < 100:
                return SemanticTag.HEADER
            elif h > 400:
                return SemanticTag.SECTION

        # 固定高度的小元素 → 按钮/标签
        if 30 <= h <= 60 and w < 300:
            return SemanticTag.BUTTON

        # 包含多个子元素 → 容器
        if len(comp.children) > 3:
            return SemanticTag.SECTION

        return SemanticTag.DIV

    def _infer_aria(self, comp: ComponentIR):
        """推断 ARIA 属性"""
        # 设置 role
        if comp.component_type in _TYPE_TO_ARIA_ROLE:
            comp.aria.role = _TYPE_TO_ARIA_ROLE[comp.component_type]
        elif comp.semantic_tag in _TAG_TO_ARIA_ROLE:
            comp.aria.role = _TAG_TO_ARIA_ROLE[comp.semantic_tag]

        # 设置 aria-label
        if not comp.aria.aria_label:
            label = self._infer_aria_label(comp)
            if label:
                comp.aria.aria_label = label

        # 设置 tabindex
        if comp.component_type in (
            ComponentType.BUTTON, ComponentType.INPUT,
            ComponentType.SELECT, ComponentType.CHECKBOX,
            ComponentType.RADIO, ComponentType.TEXTAREA,
            ComponentType.LINK, ComponentType.TAB,
        ):
            comp.aria.tabindex = 0

        # 设置 aria-disabled
        if "disabled" in [s.name for s in comp.state]:
            comp.aria.aria_disabled = "false"  # 动态值

        # 设置 aria-expanded
        if comp.component_type in (ComponentType.ACCORDION, ComponentType.DROPDOWN, ComponentType.MENU):
            comp.aria.aria_expanded = "false"  # 动态值

        # 设置 aria-haspopup
        if comp.component_type in (ComponentType.DROPDOWN, ComponentType.MENU):
            comp.aria.aria_haspopup = "true"

        # 设置 aria-live
        if comp.component_type in (ComponentType.ALERT, ComponentType.TOAST, ComponentType.STATUS):
            comp.aria.aria_live = "polite"

    def _infer_aria_label(self, comp: ComponentIR) -> str:
        """推断 aria-label"""
        name = comp.name

        # 按钮类
        if comp.component_type == ComponentType.BUTTON:
            if "close" in name.lower() or "dismiss" in name.lower():
                return "关闭"
            if "submit" in name.lower():
                return "提交"
            if "cancel" in name.lower():
                return "取消"
            if "confirm" in name.lower():
                return "确认"
            if "delete" in name.lower() or "remove" in name.lower():
                return "删除"
            if "edit" in name.lower():
                return "编辑"
            if "save" in name.lower():
                return "保存"
            if "search" in name.lower():
                return "搜索"
            if "menu" in name.lower():
                return "菜单"
            if "more" in name.lower():
                return "更多选项"
            # 使用名称本身
            return name

        # 输入类
        if comp.component_type in (ComponentType.INPUT, ComponentType.TEXTAREA, ComponentType.SELECT):
            # 尝试关联的 label
            return f"请输入{name}" if name else ""

        # 图标类
        if comp.component_type == ComponentType.ICON:
            icon_meaning = self._guess_icon_meaning(name)
            if icon_meaning:
                return icon_meaning

        return ""

    def _guess_icon_meaning(self, name: str) -> str:
        """猜测图标含义"""
        name_lower = name.lower()
        icon_map = {
            "close": "关闭",
            "search": "搜索",
            "menu": "菜单",
            "setting": "设置",
            "add": "添加",
            "delete": "删除",
            "edit": "编辑",
            "save": "保存",
            "back": "返回",
            "forward": "前进",
            "refresh": "刷新",
            "home": "首页",
            "user": "用户",
            "heart": "收藏",
            "like": "点赞",
            "share": "分享",
            "download": "下载",
            "upload": "上传",
            "filter": "筛选",
            "sort": "排序",
            "calendar": "日历",
            "clock": "时间",
            "notification": "通知",
            "bell": "通知",
            "mail": "邮件",
            "phone": "电话",
            "location": "位置",
            "map": "地图",
            "camera": "相机",
            "image": "图片",
            "file": "文件",
            "folder": "文件夹",
            "lock": "锁定",
            "unlock": "解锁",
            "eye": "查看",
            "eye-off": "隐藏",
            "info": "信息",
            "warning": "警告",
            "error": "错误",
            "success": "成功",
            "check": "确认",
            "arrow": "箭头",
            "chevron": "箭头",
            "left": "向左",
            "right": "向右",
            "up": "向上",
            "down": "向下",
            "plus": "添加",
            "minus": "减少",
            "copy": "复制",
            "paste": "粘贴",
            "cut": "剪切",
            "undo": "撤销",
            "redo": "重做",
            "logout": "退出登录",
            "login": "登录",
            "more": "更多",
        }
        for keyword, meaning in icon_map.items():
            if keyword in name_lower:
                return meaning
        return ""

    def _infer_interaction(self, comp: ComponentIR):
        """推断交互模式"""
        name_lower = comp.name.lower()

        # 匹配交互模式
        for keyword, interaction_def in _NAME_TO_INTERACTION.items():
            if keyword in name_lower:
                # 设置键盘导航
                if "keyboard" in interaction_def:
                    comp.aria.keyboard = interaction_def["keyboard"]

                # 设置焦点陷阱
                if interaction_def.get("focus_trap"):
                    comp.aria.focus_trap = True

                # 设置焦点恢复
                if interaction_def.get("focus_restore"):
                    comp.aria.focus_restore = True

                # 添加事件
                for event_name in interaction_def.get("events", []):
                    event = EventSpec(
                        name=event_name,
                        handler_name=f"handle{event_name.capitalize()}",
                    )
                    comp.events.append(event)

                break

        # 表单组件特殊处理
        if comp.component_type in (
            ComponentType.INPUT, ComponentType.TEXTAREA,
            ComponentType.SELECT, ComponentType.CHECKBOX,
            ComponentType.RADIO, ComponentType.SWITCH,
        ):
            # 添加 change 事件
            if not any(e.name == "change" for e in comp.events):
                comp.events.append(EventSpec(
                    name="change",
                    handler_name="handleChange",
                ))

        # 按钮特殊处理
        if comp.component_type == ComponentType.BUTTON:
            if not any(e.name == "click" for e in comp.events):
                comp.events.append(EventSpec(
                    name="click",
                    handler_name="handleClick",
                ))

    def _generate_id(self, name: str) -> str:
        """生成唯一 ID"""
        self._id_counter += 1
        # 将名称转换为 kebab-case
        kebab = re.sub(r'([A-Z])', r'-\1', name).lower().strip('-')
        return f"{kebab}-{self._id_counter}"


# ============================================================
# 文档大纲分析
# ============================================================

class DocumentOutlineAnalyzer:
    """
    文档大纲分析器 - 确保标题层级正确

    规则：
    1. 每个页面只有一个 h1
    2. 标题层级不能跳级 (h1 → h3 不允许)
    3. 标题层级反映内容结构
    """

    def analyze(self, ir: DesignIR) -> DesignIR:
        """分析并修正标题层级"""
        for page in ir.pages:
            self._fix_heading_hierarchy(page.components)
        return ir

    def _fix_heading_hierarchy(self, components: List[ComponentIR], current_level: int = 1):
        """修正标题层级"""
        for comp in components:
            if comp.semantic_tag in (SemanticTag.H1, SemanticTag.H2, SemanticTag.H3,
                                      SemanticTag.H4, SemanticTag.H5, SemanticTag.H6):
                # 计算正确的标题级别
                tag_name = comp.semantic_tag.value
                current_num = int(tag_name[1])

                # 如果跳级了，修正
                if current_num > current_level + 1:
                    correct_tag = f"h{current_level + 1}"
                    comp.semantic_tag = SemanticTag(correct_tag)

                # 递归处理子组件
                self._fix_heading_hierarchy(comp.children, int(comp.semantic_tag.value[1]))
            else:
                self._fix_heading_hierarchy(comp.children, current_level)


# ============================================================
# 无障碍树构建器
# ============================================================

class A11yTreeBuilder:
    """
    无障碍树构建器 - 生成完整的无障碍信息

    输出：屏幕阅读器可理解的组件层级
    """

    def build_tree(self, ir: DesignIR) -> Dict[str, Any]:
        """构建无障碍树"""
        tree = {
            "role": "WebApplication",
            "name": ir.name,
            "children": [],
        }

        for page in ir.pages:
            page_node = {
                "role": page.semantic_tag.value,
                "name": page.name,
                "children": self._build_components_tree(page.components),
            }
            tree["children"].append(page_node)

        return tree

    def _build_components_tree(self, components: List[ComponentIR]) -> List[Dict[str, Any]]:
        """构建组件无障碍树"""
        nodes = []
        for comp in components:
            node = {
                "role": comp.aria.role if comp.aria and comp.aria.role else comp.semantic_tag.value,
                "name": comp.aria.aria_label if comp.aria and comp.aria.aria_label else comp.name,
            }
            if comp.children:
                node["children"] = self._build_components_tree(comp.children)
            nodes.append(node)
        return nodes
