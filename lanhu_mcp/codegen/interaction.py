"""
交互意图推断引擎 - 从设计稿推断交互逻辑、状态机、事件流和 JS 插件

核心功能：
1. 组件类型 → 状态机定义
2. 视觉状态 → 交互状态映射
3. 事件流向分析
4. JS 插件/库智能推荐
5. 动画规格推断
"""
from __future__ import annotations

from typing import Optional, List, Dict, Any, Tuple
from collections import Counter

from lanhu_mcp.codegen.ir import (
    ComponentIR,
    ComponentType,
    InteractionSpec,
    StateMachine,
    StateTransition,
    EventSpec,
    PropSpec,
    StateSpec,
    DependencySpec,
    DesignIR,
)


# ============================================================
# 组件交互模板库
# ============================================================

# 预定义的组件交互模式
COMPONENT_INTERACTION_TEMPLATES: Dict[ComponentType, Dict[str, Any]] = {
    # ---- 按钮 ----
    ComponentType.BUTTON: {
        "states": ["default", "hover", "focus", "active", "disabled", "loading"],
        "initial_state": "default",
        "transitions": [
            {"from": "default", "to": "hover", "trigger": "mouse_enter"},
            {"from": "hover", "to": "default", "trigger": "mouse_leave"},
            {"from": "default", "to": "focus", "trigger": "focus"},
            {"from": "focus", "to": "default", "trigger": "blur"},
            {"from": "hover", "to": "active", "trigger": "mouse_down"},
            {"from": "active", "to": "hover", "trigger": "mouse_up"},
            {"from": "active", "to": "default", "trigger": "mouse_leave"},
            {"from": "default", "to": "loading", "trigger": "async_start"},
            {"from": "loading", "to": "default", "trigger": "async_complete"},
            {"from": "loading", "to": "error", "trigger": "async_error"},
            {"from": "error", "to": "default", "trigger": "retry"},
        ],
        "events": [
            {"name": "click", "handler": "handleClick", "bubbles": True},
            {"name": "focus", "handler": "handleFocus"},
            {"name": "blur", "handler": "handleBlur"},
        ],
        "props": [
            {"name": "disabled", "type": "boolean", "default": False},
            {"name": "loading", "type": "boolean", "default": False},
            {"name": "variant", "type": "enum", "enum_values": ["primary", "secondary", "ghost", "danger"]},
            {"name": "size", "type": "enum", "enum_values": ["small", "medium", "large"]},
            {"name": "onClick", "type": "function"},
        ],
        "keyboard": {"Enter": "click", "Space": "click"},
        "animation": {"hover": "scale(1.02)", "active": "scale(0.98)", "duration": "150ms"},
    },

    # ---- 输入框 ----
    ComponentType.INPUT: {
        "states": ["default", "hover", "focus", "disabled", "error", "success"],
        "initial_state": "default",
        "transitions": [
            {"from": "default", "to": "hover", "trigger": "mouse_enter"},
            {"from": "hover", "to": "default", "trigger": "mouse_leave"},
            {"from": "default", "to": "focus", "trigger": "focus"},
            {"from": "focus", "to": "default", "trigger": "blur"},
            {"from": "focus", "to": "error", "trigger": "validation_fail"},
            {"from": "focus", "to": "success", "trigger": "validation_pass"},
            {"from": "error", "to": "focus", "trigger": "focus"},
            {"from": "success", "to": "focus", "trigger": "focus"},
        ],
        "events": [
            {"name": "change", "handler": "handleChange"},
            {"name": "input", "handler": "handleInput"},
            {"name": "focus", "handler": "handleFocus"},
            {"name": "blur", "handler": "handleBlur"},
            {"name": "keydown", "handler": "handleKeyDown"},
            {"name": "clear", "handler": "handleClear"},
        ],
        "props": [
            {"name": "value", "type": "string", "default": ""},
            {"name": "placeholder", "type": "string"},
            {"name": "disabled", "type": "boolean", "default": False},
            {"name": "readOnly", "type": "boolean", "default": False},
            {"name": "clearable", "type": "boolean", "default": False},
            {"name": "maxLength", "type": "number"},
            {"name": "onChange", "type": "function"},
            {"name": "onFocus", "type": "function"},
            {"name": "onBlur", "type": "function"},
        ],
        "keyboard": {"Escape": "clear", "Enter": "submit"},
        "features": ["clearable", "maxLength", "counter", "validation"],
        "debounce_ms": 300,
    },

    # ---- 文本域 ----
    ComponentType.TEXTAREA: {
        "states": ["default", "hover", "focus", "disabled", "error"],
        "initial_state": "default",
        "events": [
            {"name": "change", "handler": "handleChange"},
            {"name": "input", "handler": "handleInput"},
            {"name": "focus", "handler": "handleFocus"},
            {"name": "blur", "handler": "handleBlur"},
        ],
        "props": [
            {"name": "value", "type": "string"},
            {"name": "rows", "type": "number", "default": 4},
            {"name": "autoResize", "type": "boolean", "default": False},
            {"name": "maxLength", "type": "number"},
            {"name": "showCount", "type": "boolean", "default": False},
        ],
        "features": ["autoResize", "maxLength", "showCount"],
    },

    # ---- 选择器 ----
    ComponentType.SELECT: {
        "states": ["default", "hover", "focus", "open", "disabled"],
        "initial_state": "default",
        "transitions": [
            {"from": "default", "to": "open", "trigger": "click"},
            {"from": "open", "to": "default", "trigger": "select"},
            {"from": "open", "to": "default", "trigger": "close"},
            {"from": "open", "to": "default", "trigger": "blur"},
        ],
        "events": [
            {"name": "change", "handler": "handleChange"},
            {"name": "open", "handler": "handleOpen"},
            {"name": "close", "handler": "handleClose"},
            {"name": "search", "handler": "handleSearch"},
        ],
        "props": [
            {"name": "value", "type": "string"},
            {"name": "options", "type": "array"},
            {"name": "placeholder", "type": "string"},
            {"name": "disabled", "type": "boolean"},
            {"name": "multiple", "type": "boolean", "default": False},
            {"name": "searchable", "type": "boolean", "default": False},
            {"name": "clearable", "type": "boolean", "default": False},
        ],
        "keyboard": {"Escape": "close", "ArrowDown": "next", "ArrowUp": "prev", "Enter": "select"},
        "features": ["search", "multiple", "group", "virtual-scroll"],
    },

    # ---- 复选框 ----
    ComponentType.CHECKBOX: {
        "states": ["unchecked", "checked", "indeterminate", "disabled"],
        "initial_state": "unchecked",
        "transitions": [
            {"from": "unchecked", "to": "checked", "trigger": "click"},
            {"from": "checked", "to": "unchecked", "trigger": "click"},
            {"from": "indeterminate", "to": "checked", "trigger": "click"},
        ],
        "events": [
            {"name": "change", "handler": "handleChange"},
        ],
        "props": [
            {"name": "checked", "type": "boolean"},
            {"name": "indeterminate", "type": "boolean"},
            {"name": "disabled", "type": "boolean"},
            {"name": "onChange", "type": "function"},
        ],
        "keyboard": {"Space": "toggle"},
    },

    # ---- 单选框 ----
    ComponentType.RADIO: {
        "states": ["unchecked", "checked", "disabled"],
        "initial_state": "unchecked",
        "events": [
            {"name": "change", "handler": "handleChange"},
        ],
        "props": [
            {"name": "checked", "type": "boolean"},
            {"name": "value", "type": "string"},
            {"name": "disabled", "type": "boolean"},
            {"name": "onChange", "type": "function"},
        ],
        "keyboard": {"Space": "select", "ArrowDown": "next", "ArrowUp": "prev"},
    },

    # ---- 开关 ----
    ComponentType.SWITCH: {
        "states": ["off", "on", "disabled", "loading"],
        "initial_state": "off",
        "transitions": [
            {"from": "off", "to": "loading", "trigger": "click"},
            {"from": "loading", "to": "on", "trigger": "async_complete"},
            {"from": "loading", "to": "off", "trigger": "async_error"},
            {"from": "on", "to": "loading", "trigger": "click"},
            {"from": "loading", "to": "off", "trigger": "async_complete"},
        ],
        "events": [
            {"name": "change", "handler": "handleChange"},
        ],
        "props": [
            {"name": "checked", "type": "boolean"},
            {"name": "disabled", "type": "boolean"},
            {"name": "loading", "type": "boolean"},
            {"name": "onChange", "type": "function"},
        ],
        "keyboard": {"Space": "toggle"},
        "animation": {"toggle": "slide 200ms ease"},
    },

    # ---- 模态框 ----
    ComponentType.MODAL: {
        "states": ["closed", "opening", "open", "closing"],
        "initial_state": "closed",
        "transitions": [
            {"from": "closed", "to": "opening", "trigger": "open"},
            {"from": "opening", "to": "open", "trigger": "animation_end"},
            {"from": "open", "to": "closing", "trigger": "close"},
            {"from": "closing", "to": "closed", "trigger": "animation_end"},
        ],
        "events": [
            {"name": "open", "handler": "handleOpen"},
            {"name": "close", "handler": "handleClose"},
            {"name": "afterOpen", "handler": "handleAfterOpen"},
            {"name": "afterClose", "handler": "handleAfterClose"},
        ],
        "props": [
            {"name": "open", "type": "boolean", "default": False},
            {"name": "title", "type": "string"},
            {"name": "closable", "type": "boolean", "default": True},
            {"name": "maskClosable", "type": "boolean", "default": True},
            {"name": "onClose", "type": "function"},
            {"name": "afterClose", "type": "function"},
        ],
        "keyboard": {"Escape": "close", "Tab": "focus-trap"},
        "focus_trap": True,
        "focus_restore": True,
        "animation": {"open": "fadeIn 200ms ease", "close": "fadeOut 200ms ease"},
        "features": ["portal", "focus-trap", "scroll-lock", "stack"],
    },

    # ---- 抽屉 ----
    ComponentType.DRAWER: {
        "states": ["closed", "opening", "open", "closing"],
        "initial_state": "closed",
        "transitions": [
            {"from": "closed", "to": "opening", "trigger": "open"},
            {"from": "opening", "to": "open", "trigger": "animation_end"},
            {"from": "open", "to": "closing", "trigger": "close"},
            {"from": "closing", "to": "closed", "trigger": "animation_end"},
        ],
        "events": [
            {"name": "open", "handler": "handleOpen"},
            {"name": "close", "handler": "handleClose"},
        ],
        "props": [
            {"name": "open", "type": "boolean"},
            {"name": "placement", "type": "enum", "enum_values": ["left", "right", "top", "bottom"]},
            {"name": "closable", "type": "boolean", "default": True},
            {"name": "maskClosable", "type": "boolean", "default": True},
        ],
        "keyboard": {"Escape": "close"},
        "focus_trap": True,
        "focus_restore": True,
        "animation": {"open": "slideIn 300ms ease", "close": "slideOut 300ms ease"},
    },

    # ---- 标签页 ----
    ComponentType.TABS: {
        "states": ["default"],
        "initial_state": "default",
        "events": [
            {"name": "change", "handler": "handleChange"},
        ],
        "props": [
            {"name": "activeKey", "type": "string"},
            {"name": "defaultActiveKey", "type": "string"},
            {"name": "onChange", "type": "function"},
        ],
        "keyboard": {"ArrowLeft": "prev-tab", "ArrowRight": "next-tab", "Home": "first-tab", "End": "last-tab"},
        "aria": {"role": "tablist", "tab": "tab", "tabpanel": "tabpanel"},
        "features": ["lazy-load", "animated"],
    },

    # ---- 折叠面板 ----
    ComponentType.ACCORDION: {
        "states": ["default"],
        "initial_state": "default",
        "events": [
            {"name": "toggle", "handler": "handleToggle"},
            {"name": "change", "handler": "handleChange"},
        ],
        "props": [
            {"name": "expandMultiple", "type": "boolean", "default": False},
            {"name": "defaultActiveKeys", "type": "array"},
            {"name": "activeKeys", "type": "array"},
            {"name": "onChange", "type": "function"},
        ],
        "keyboard": {"Enter": "toggle", "Space": "toggle"},
        "features": ["animate", "nested"],
    },

    # ---- 表格 ----
    ComponentType.TABLE: {
        "states": ["default", "loading"],
        "initial_state": "default",
        "events": [
            {"name": "sort", "handler": "handleSort"},
            {"name": "filter", "handler": "handleFilter"},
            {"name": "page", "handler": "handlePage"},
            {"name": "rowSelect", "handler": "handleRowSelect"},
            {"name": "rowClick", "handler": "handleRowClick"},
        ],
        "props": [
            {"name": "columns", "type": "array"},
            {"name": "dataSource", "type": "array"},
            {"name": "loading", "type": "boolean"},
            {"name": "pagination", "type": "object"},
            {"name": "rowSelection", "type": "object"},
            {"name": "sortable", "type": "boolean"},
            {"name": "filterable", "type": "boolean"},
            {"name": "onSort", "type": "function"},
            {"name": "onFilter", "type": "function"},
            {"name": "onPageChange", "type": "function"},
        ],
        "keyboard": {"ArrowDown": "next-row", "ArrowUp": "prev-row", "ArrowRight": "next-cell", "ArrowLeft": "prev-cell"},
        "features": ["sort", "filter", "pagination", "virtual-scroll", "row-select", "column-resize", "fixed-header"],
    },

    # ---- 树形控件 ----
    ComponentType.TREE: {
        "states": ["default"],
        "initial_state": "default",
        "events": [
            {"name": "select", "handler": "handleSelect"},
            {"name": "expand", "handler": "handleExpand"},
            {"name": "check", "handler": "handleCheck"},
            {"name": "drag", "handler": "handleDrag"},
        ],
        "props": [
            {"name": "treeData", "type": "array"},
            {"name": "checkable", "type": "boolean"},
            {"name": "draggable", "type": "boolean"},
            {"name": "showLine", "type": "boolean"},
            {"name": "onSelect", "type": "function"},
            {"name": "onCheck", "type": "function"},
        ],
        "keyboard": {"ArrowDown": "next", "ArrowUp": "prev", "ArrowRight": "expand", "ArrowLeft": "collapse"},
        "features": ["async-load", "drag-drop", "checkbox", "search"],
    },

    # ---- 轮播图 ----
    ComponentType.CAROUSEL: {
        "states": ["default"],
        "initial_state": "default",
        "events": [
            {"name": "prev", "handler": "handlePrev"},
            {"name": "next", "handler": "handleNext"},
            {"name": "goto", "handler": "handleGoto"},
            {"name": "change", "handler": "handleChange"},
        ],
        "props": [
            {"name": "autoplay", "type": "boolean", "default": True},
            {"name": "autoplaySpeed", "type": "number", "default": 3000},
            {"name": "pauseOnHover", "type": "boolean", "default": True},
            {"name": "loop", "type": "boolean", "default": True},
            {"name": "showDots", "type": "boolean", "default": True},
            {"name": "showArrows", "type": "boolean", "default": True},
            {"name": "effect", "type": "enum", "enum_values": ["slide", "fade", "scroll"]},
        ],
        "keyboard": {"ArrowLeft": "prev", "ArrowRight": "next"},
        "animation": {"slide": "slide 500ms ease", "fade": "fade 500ms ease"},
        "features": ["autoplay", "pause-on-hover", "swipe", "drag"],
    },

    # ---- 分页 ----
    ComponentType.PAGINATION: {
        "states": ["default"],
        "initial_state": "default",
        "events": [
            {"name": "change", "handler": "handleChange"},
            {"name": "pageSizeChange", "handler": "handlePageSizeChange"},
        ],
        "props": [
            {"name": "current", "type": "number"},
            {"name": "pageSize", "type": "number"},
            {"name": "total", "type": "number"},
            {"name": "showSizeChanger", "type": "boolean"},
            {"name": "showQuickJumper", "type": "boolean"},
            {"name": "onChange", "type": "function"},
        ],
        "keyboard": {"ArrowLeft": "prev", "ArrowRight": "next"},
    },

    # ---- 表单 ----
    ComponentType.FORM: {
        "states": ["default", "submitting", "submitted", "error"],
        "initial_state": "default",
        "events": [
            {"name": "submit", "handler": "handleSubmit"},
            {"name": "reset", "handler": "handleReset"},
            {"name": "validate", "handler": "handleValidate"},
            {"name": "valuesChange", "handler": "handleValuesChange"},
        ],
        "props": [
            {"name": "initialValues", "type": "object"},
            {"name": "onSubmit", "type": "function"},
            {"name": "onReset", "type": "function"},
            {"name": "validateOnChange", "type": "boolean", "default": True},
            {"name": "validateOnBlur", "type": "boolean", "default": True},
        ],
        "features": ["validation", "dirty-tracking", "field-array", "dynamic-fields"],
    },

    # ---- 搜索 ----
    ComponentType.SEARCH: {
        "states": ["default", "focused", "searching"],
        "initial_state": "default",
        "events": [
            {"name": "search", "handler": "handleSearch"},
            {"name": "clear", "handler": "handleClear"},
            {"name": "change", "handler": "handleChange"},
        ],
        "props": [
            {"name": "value", "type": "string"},
            {"name": "placeholder", "type": "string"},
            {"name": "loading", "type": "boolean"},
            {"name": "onSearch", "type": "function"},
            {"name": "onChange", "type": "function"},
        ],
        "keyboard": {"Enter": "search", "Escape": "clear"},
        "debounce_ms": 300,
    },

    # ---- 工具提示 ----
    ComponentType.TOOLTIP: {
        "states": ["hidden", "showing", "visible"],
        "initial_state": "hidden",
        "transitions": [
            {"from": "hidden", "to": "showing", "trigger": "mouseenter", "delay": 300},
            {"from": "showing", "to": "visible", "trigger": "delay_complete"},
            {"from": "visible", "to": "hidden", "trigger": "mouseleave"},
            {"from": "showing", "to": "hidden", "trigger": "mouseleave", "delay": 100},
        ],
        "events": [
            {"name": "show", "handler": "handleShow"},
            {"name": "hide", "handler": "handleHide"},
        ],
        "props": [
            {"name": "content", "type": "string"},
            {"name": "placement", "type": "enum", "enum_values": ["top", "bottom", "left", "right"]},
            {"name": "delay", "type": "number", "default": 300},
        ],
        "keyboard": {"Escape": "hide"},
        "positioning": "floating",
    },

    # ---- 头像 ----
    ComponentType.AVATAR: {
        "states": ["default", "loading", "error"],
        "initial_state": "default",
        "events": [
            {"name": "error", "handler": "handleError"},
            {"name": "load", "handler": "handleLoad"},
        ],
        "props": [
            {"name": "src", "type": "string"},
            {"name": "alt", "type": "string"},
            {"name": "size", "type": "enum", "enum_values": ["small", "medium", "large"]},
            {"name": "shape", "type": "enum", "enum_values": ["circle", "square"]},
            {"name": "fallback", "type": "string"},
        ],
    },

    # ---- 徽标 ----
    ComponentType.BADGE: {
        "states": ["default"],
        "initial_state": "default",
        "props": [
            {"name": "count", "type": "number"},
            {"name": "dot", "type": "boolean"},
            {"name": "status", "type": "enum", "enum_values": ["success", "processing", "error", "default"]},
            {"name": "color", "type": "string"},
        ],
    },

    # ---- 步骤条 ----
    ComponentType.STEPS: {
        "states": ["default"],
        "initial_state": "default",
        "events": [
            {"name": "change", "handler": "handleChange"},
        ],
        "props": [
            {"name": "current", "type": "number"},
            {"name": "status", "type": "enum", "enum_values": ["wait", "process", "finish", "error"]},
            {"name": "items", "type": "array"},
            {"name": "onChange", "type": "function"},
        ],
        "keyboard": {"ArrowLeft": "prev", "ArrowRight": "next"},
    },
}


# ============================================================
# JS 插件/依赖推荐矩阵
# ============================================================

# 组件类型 → 推荐依赖
COMPONENT_DEPENDENCY_MAP: Dict[ComponentType, List[Dict[str, Any]]] = {
    ComponentType.MODAL: [
        {"name": "focus-trap-react", "version": "^6.0.0", "reason": "焦点陷阱", "category": "a11y"},
        {"name": "react-remove-scroll", "version": "^2.5.0", "reason": "滚动锁定", "category": "a11y"},
    ],
    ComponentType.DRAWER: [
        {"name": "focus-trap-react", "version": "^6.0.0", "reason": "焦点陷阱", "category": "a11y"},
        {"name": "react-remove-scroll", "version": "^2.5.0", "reason": "滚动锁定", "category": "a11y"},
    ],
    ComponentType.SELECT: [
        {"name": "downshift", "version": "^8.0.0", "reason": "可访问的下拉组件", "category": "a11y"},
    ],
    ComponentType.DATE_PICKER: [
        {"name": "dayjs", "version": "^1.11.0", "reason": "日期处理", "category": "util"},
    ],
    ComponentType.TABLE: [
        {"name": "@tanstack/react-table", "version": "^8.0.0", "reason": "表格核心逻辑", "category": "ui"},
    ],
    ComponentType.TREE: [
        {"name": "react-arborist", "version": "^3.0.0", "reason": "树形控件", "category": "ui"},
    ],
    ComponentType.CAROUSEL: [
        {"name": "swiper", "version": "^11.0.0", "reason": "轮播组件", "category": "ui"},
    ],
    ComponentType.FORM: [
        {"name": "react-hook-form", "version": "^7.50.0", "reason": "表单状态管理", "category": "form"},
        {"name": "zod", "version": "^3.22.0", "reason": "表单验证", "category": "form"},
    ],
    ComponentType.UPLOAD: [
        {"name": "react-dropzone", "version": "^14.2.0", "reason": "拖拽上传", "category": "ui"},
    ],
    ComponentType.TOOLTIP: [
        {"name": "@floating-ui/react", "version": "^0.26.0", "reason": "浮层定位", "category": "ui"},
    ],
    ComponentType.POPOVER: [
        {"name": "@floating-ui/react", "version": "^0.26.0", "reason": "浮层定位", "category": "ui"},
    ],
    ComponentType.DROPDOWN: [
        {"name": "@floating-ui/react", "version": "^0.26.0", "reason": "浮层定位", "category": "ui"},
        {"name": "downshift", "version": "^8.0.0", "reason": "可访问的下拉组件", "category": "a11y"},
    ],
    ComponentType.SLIDER: [
        {"name": "@radix-ui/react-slider", "version": "^1.1.0", "reason": "滑块组件", "category": "ui"},
    ],
}

# Vue 生态依赖
VUE_DEPENDENCY_MAP: Dict[ComponentType, List[Dict[str, Any]]] = {
    ComponentType.FORM: [
        {"name": "vee-validate", "version": "^4.11.0", "reason": "表单验证", "category": "form"},
        {"name": "zod", "version": "^3.22.0", "reason": "Schema 验证", "category": "form"},
    ],
    ComponentType.TABLE: [
        {"name": "@tanstack/vue-table", "version": "^8.0.0", "reason": "表格核心逻辑", "category": "ui"},
    ],
    ComponentType.SELECT: [
        {"name": "@vueuse/core", "version": "^10.0.0", "reason": "组合式函数", "category": "util"},
    ],
    ComponentType.DATE_PICKER: [
        {"name": "dayjs", "version": "^1.11.0", "reason": "日期处理", "category": "util"},
    ],
    ComponentType.CAROUSEL: [
        {"name": "swiper", "version": "^11.0.0", "reason": "轮播组件", "category": "ui"},
    ],
    ComponentType.TOOLTIP: [
        {"name": "@floating-ui/vue", "version": "^1.0.0", "reason": "浮层定位", "category": "ui"},
    ],
}


# ============================================================
# 交互推断引擎
# ============================================================

class InteractionInference:
    """
    交互意图推断引擎

    从设计稿推断：
    1. 组件的交互模式和状态机
    2. 事件处理逻辑
    3. 需要的 JS 插件/库
    4. 动画规格
    5. 表单验证规则
    """

    def __init__(self, framework: str = "react"):
        """
        Args:
            framework: 目标框架 (react, vue, html, flutter, svelte)
        """
        self.framework = framework

    def analyze_design(self, ir: DesignIR) -> DesignIR:
        """
        分析设计 IR，为所有组件添加交互规格。

        Args:
            ir: 设计 IR

        Returns:
            增强后的 Design IR
        """
        for comp in ir.components:
            self._analyze_component(comp)

        # 收集所有依赖
        ir.dependencies = self._collect_dependencies(ir)

        return ir

    def analyze_component(self, comp: ComponentIR) -> ComponentIR:
        """分析单个组件"""
        self._analyze_component(comp)
        return comp

    def _analyze_component(self, comp: ComponentIR):
        """分析单个组件的交互"""
        # 1. 获取交互模板
        template = COMPONENT_INTERACTION_TEMPLATES.get(comp.component_type)

        if template:
            # 应用模板
            self._apply_template(comp, template)
        else:
            # 基于名称和视觉特征推断
            self._infer_from_name(comp)

        # 2. 推断子组件交互
        for child in comp.children:
            self._analyze_component(child)

    def _apply_template(self, comp: ComponentIR, template: Dict[str, Any]):
        """应用交互模板"""
        # 状态机
        if "states" in template:
            comp.state = [
                StateSpec(name=s, type="boolean", visual_state=s)
                for s in template["states"]
            ]

        # 状态转换
        if "transitions" in template:
            transitions = []
            for t in template["transitions"]:
                transitions.append(StateTransition(
                    from_state=t["from"],
                    to_state=t["to"],
                    trigger=t["trigger"],
                    event=t.get("event", ""),
                ))
            if not comp.interaction:
                comp.interaction = InteractionSpec(
                    component_name=comp.name,
                    component_type=comp.component_type,
                )
            comp.interaction.state_machine = StateMachine(
                name=f"{comp.name}StateMachine",
                initial_state=template.get("initial_state", "default"),
                states=template["states"],
                transitions=transitions,
            )

        # 事件
        if "events" in template:
            for e in template["events"]:
                event = EventSpec(
                    name=e["name"],
                    handler_name=e.get("handler", f"handle{e['name'].capitalize()}"),
                    bubbles=e.get("bubbles", False),
                )
                comp.events.append(event)

        # Props
        if "props" in template:
            for p in template["props"]:
                prop = PropSpec(
                    name=p["name"],
                    type=p["type"],
                    default=p.get("default"),
                    required=p.get("required", False),
                    enum_values=p.get("enum_values", []),
                )
                comp.props.append(prop)

        # 键盘导航
        if "keyboard" in template:
            if not comp.aria:
                from lanhu_mcp.codegen.ir import A11ySpec
                comp.aria = A11ySpec()
            comp.aria.keyboard = template["keyboard"]

        # 焦点管理
        if template.get("focus_trap"):
            if not comp.aria:
                from lanhu_mcp.codegen.ir import A11ySpec
                comp.aria = A11ySpec()
            comp.aria.focus_trap = True

        if template.get("focus_restore"):
            if not comp.aria:
                from lanhu_mcp.codegen.ir import A11ySpec
                comp.aria = A11ySpec()
            comp.aria.focus_restore = True

        # 动画
        if "animation" in template:
            if not comp.interaction:
                comp.interaction = InteractionSpec(
                    component_name=comp.name,
                    component_type=comp.component_type,
                )
            comp.interaction.animation = template["animation"]

        # 功能列表
        if "features" in template:
            if not comp.interaction:
                comp.interaction = InteractionSpec(
                    component_name=comp.name,
                    component_type=comp.component_type,
                )
            comp.interaction.required_plugins = template["features"]

        # 防抖/节流
        if "debounce_ms" in template:
            if not comp.interaction:
                comp.interaction = InteractionSpec(
                    component_name=comp.name,
                    component_type=comp.component_type,
                )
            comp.interaction.debounce_ms = template["debounce_ms"]

        if "throttle_ms" in template:
            if not comp.interaction:
                comp.interaction = InteractionSpec(
                    component_name=comp.name,
                    component_type=comp.component_type,
                )
            comp.interaction.throttle_ms = template["throttle_ms"]

    def _infer_from_name(self, comp: ComponentIR):
        """从名称推断交互"""
        name_lower = comp.name.lower()

        # 检查是否有匹配的交互模式
        for keyword, template in COMPONENT_INTERACTION_TEMPLATES.items():
            if keyword.value in name_lower:
                self._apply_template(comp, template)
                return

        # 基础交互：所有可交互元素都有 focus 状态
        if comp.component_type in (
            ComponentType.BUTTON, ComponentType.INPUT,
            ComponentType.SELECT, ComponentType.CHECKBOX,
            ComponentType.RADIO, ComponentType.SWITCH,
        ):
            if not comp.state:
                comp.state = [
                    StateSpec(name="default", type="boolean", visual_state="default"),
                    StateSpec(name="hover", type="boolean", visual_state="hover"),
                    StateSpec(name="focus", type="boolean", visual_state="focus"),
                    StateSpec(name="disabled", type="boolean", visual_state="disabled"),
                ]

    def _collect_dependencies(self, ir: DesignIR) -> List[DependencySpec]:
        """收集所有组件需要的依赖"""
        dep_map = COMPONENT_DEPENDENCY_MAP if self.framework == "react" else VUE_DEPENDENCY_MAP
        seen = set()
        dependencies = []

        for comp in ir.components:
            deps = dep_map.get(comp.component_type, [])
            for d in deps:
                if d["name"] not in seen:
                    seen.add(d["name"])
                    dependencies.append(DependencySpec(
                        name=d["name"],
                        version=d.get("version", ""),
                        reason=d.get("reason", ""),
                        category=d.get("category", ""),
                    ))

        return dependencies


# ============================================================
# 动画规格推断器
# ============================================================

class AnimationInference:
    """
    动画规格推断器

    从设计稿推断动画参数：
    1. 过渡动画 (transition)
    2. 关键帧动画 (keyframes)
    3. 进入/退出动画 (enter/exit)
    4. 滚动触发动画 (scroll-triggered)
    """

    # 组件类型 → 默认动画
    DEFAULT_ANIMATIONS: Dict[ComponentType, Dict[str, Any]] = {
        ComponentType.BUTTON: {
            "hover": {"transform": "scale(1.02)", "duration": "150ms", "easing": "ease"},
            "active": {"transform": "scale(0.98)", "duration": "100ms", "easing": "ease"},
        },
        ComponentType.INPUT: {
            "focus": {"border-color": "var(--color-primary-500)", "box-shadow": "0 0 0 2px var(--color-primary-bg)", "duration": "150ms"},
        },
        ComponentType.MODAL: {
            "enter": {"opacity": "0", "transform": "scale(0.95)", "to": {"opacity": "1", "transform": "scale(1)"}, "duration": "200ms"},
            "exit": {"opacity": "1", "transform": "scale(1)", "to": {"opacity": "0", "transform": "scale(0.95)"}, "duration": "200ms"},
        },
        ComponentType.DRAWER: {
            "enter-left": {"transform": "translateX(-100%)", "to": {"transform": "translateX(0)"}, "duration": "300ms"},
            "enter-right": {"transform": "translateX(100%)", "to": {"transform": "translateX(0)"}, "duration": "300ms"},
            "enter-top": {"transform": "translateY(-100%)", "to": {"transform": "translateY(0)"}, "duration": "300ms"},
            "enter-bottom": {"transform": "translateY(100%)", "to": {"transform": "translateY(0)"}, "duration": "300ms"},
        },
        ComponentType.DROPDOWN: {
            "enter": {"opacity": "0", "transform": "translateY(-8px)", "to": {"opacity": "1", "transform": "translateY(0)"}, "duration": "150ms"},
            "exit": {"opacity": "1", "transform": "translateY(0)", "to": {"opacity": "0", "transform": "translateY(-8px)"}, "duration": "100ms"},
        },
        ComponentType.TOOLTIP: {
            "enter": {"opacity": "0", "transform": "translateY(4px)", "to": {"opacity": "1", "transform": "translateY(0)"}, "duration": "150ms"},
            "exit": {"opacity": "1", "transform": "translateY(0)", "to": {"opacity": "0", "transform": "translateY(4px)"}, "duration": "100ms"},
        },
        ComponentType.ACCORDION: {
            "expand": {"height": "auto", "duration": "200ms", "easing": "ease"},
            "collapse": {"height": "0", "duration": "200ms", "easing": "ease"},
        },
        ComponentType.TABS: {
            "indicator": {"transform": "translateX(var(--indicator-left))", "width": "var(--indicator-width)", "duration": "200ms", "easing": "ease"},
        },
        ComponentType.SWITCH: {
            "toggle": {"transform": "translateX(var(--toggle-offset))", "duration": "200ms", "easing": "cubic-bezier(0.34, 1.56, 0.64, 1)"},
        },
        ComponentType.CAROUSEL: {
            "slide": {"transform": "translateX(-var(--slide-offset))", "duration": "500ms", "easing": "ease"},
            "fade": {"opacity": "0", "to": {"opacity": "1"}, "duration": "500ms"},
        },
        ComponentType.SKELETON: {
            "pulse": {"opacity": "0.5", "to": {"opacity": "0.8"}, "duration": "1.5s", "easing": "ease-in-out", "iteration": "infinite"},
        },
    }

    @classmethod
    def get_animation(cls, component_type: ComponentType, animation_name: str) -> Optional[Dict[str, Any]]:
        """获取组件的动画规格"""
        anims = cls.DEFAULT_ANIMATIONS.get(component_type, {})
        return anims.get(animation_name)

    @classmethod
    def generate_keyframes_css(cls, component_type: ComponentType) -> str:
        """生成关键帧 CSS"""
        lines = []
        anims = cls.DEFAULT_ANIMATIONS.get(component_type, {})

        for name, spec in anims.items():
            if "to" in spec:
                keyframe_name = f"{component_type.value}-{name}"
                lines.append(f"@keyframes {keyframe_name} {{")
                lines.append(f"  from {{")
                for prop, value in spec.items():
                    if prop not in ("to", "duration", "easing", "iteration"):
                        lines.append(f"    {prop}: {value};")
                lines.append(f"  }}")
                lines.append(f"  to {{")
                for prop, value in spec["to"].items():
                    lines.append(f"    {prop}: {value};")
                lines.append(f"  }}")
                lines.append(f"}}")
                lines.append("")

        return "\n".join(lines)
