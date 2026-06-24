"""
样式系统 - BEM 命名 + CSS Variables + 原生 CSS 规范化

核心功能：
1. 设计令牌 → CSS Variables（语义化命名）
2. BEM 命名生成器
3. 响应式断点系统
4. 暗色模式支持
5. 无障碍焦点样式
"""
from __future__ import annotations

import re
from typing import Optional, List, Dict, Tuple
from collections import Counter

from lanhu_mcp.codegen.ir import (
    DesignTokens,
    StyleSpec,
    CSSRule,
    ComponentIR,
    ComponentType,
    DesignIR,
)


# ============================================================
# BEM 命名工具
# ============================================================

class BEMNamer:
    """
    BEM 命名生成器

    规范：
    - Block: .block (组件名，kebab-case)
    - Element: .block__element (双下划线)
    - Modifier: .block--modifier (双连字符)
    - State: .is-active, .has-icon (is-/has- 前缀)
    """

    # 常用缩写
    ABBREVIATIONS = {
        "button": "btn",
        "navigation": "nav",
        "container": "container",
        "wrapper": "wrap",
        "header": "hd",
        "footer": "ft",
        "sidebar": "side",
        "content": "cnt",
        "title": "tit",
        "description": "desc",
        "avatar": "avt",
        "checkbox": "chk",
        "radio": "rdo",
        "textarea": "txtarea",
        "input": "inp",
        "select": "sel",
        "dropdown": "drop",
        "modal": "mdl",
        "dialog": "dlg",
        "tooltip": "tip",
        "popover": "pop",
        "accordion": "acc",
        "carousel": "csl",
        "breadcrumb": "brd",
        "pagination": "pgn",
        "table": "tbl",
        "form": "frm",
        "alert": "alrt",
        "badge": "bdg",
        "divider": "dvdr",
    }

    @staticmethod
    def to_kebab(name: str) -> str:
        """转换为 kebab-case"""
        # 处理 camelCase
        s = re.sub(r'([A-Z])', r'-\1', name)
        # 处理特殊字符
        s = re.sub(r'[^a-zA-Z0-9\-_]', '-', s)
        # 合并多个连字符
        s = re.sub(r'-+', '-', s)
        # 去除首尾连字符
        s = s.strip('-').lower()
        return s

    @classmethod
    def block(cls, component_name: str) -> str:
        """生成 BEM block 名称"""
        kebab = cls.to_kebab(component_name)
        # 使用缩写
        parts = kebab.split('-')
        abbreviated = []
        for part in parts:
            if part in cls.ABBREVIATIONS:
                abbreviated.append(cls.ABBREVIATIONS[part])
            else:
                abbreviated.append(part)
        return '-'.join(abbreviated)

    @staticmethod
    def element(block: str, element: str) -> str:
        """生成 BEM element 名称"""
        kebab_element = BEMNamer.to_kebab(element)
        return f"{block}__{kebab_element}"

    @staticmethod
    def modifier(block_or_element: str, modifier: str) -> str:
        """生成 BEM modifier 名称"""
        kebab_modifier = BEMNamer.to_kebab(modifier)
        return f"{block_or_element}--{kebab_modifier}"

    @staticmethod
    def state(block_or_element: str, state: str) -> str:
        """生成 BEM state 类名"""
        kebab_state = BEMNamer.to_kebab(state)
        if kebab_state.startswith("is-") or kebab_state.startswith("has-"):
            return f"{block_or_element} {kebab_state}"
        return f"{block_or_element} is-{kebab_state}"


# ============================================================
# CSS Variables 生成器
# ============================================================

class CSSVariableGenerator:
    """
    CSS Variables 生成器

    将设计令牌转换为语义化的 CSS Custom Properties

    命名规范：
    - --color-primary-500
    - --color-text-primary
    - --color-bg-page
    - --color-border-default
    - --spacing-4 (4px)
    - --radius-md
    - --shadow-lg
    - --font-size-sm
    - --font-weight-semibold
    - --line-height-snug
    - --z-index-modal
    """

    # 语义化颜色名称映射
    SEMANTIC_COLOR_MAP = {
        "primary": "primary",
        "secondary": "secondary",
        "accent": "accent",
        "success": "success",
        "warning": "warning",
        "error": "error",
        "danger": "danger",
        "info": "info",
        "neutral": "neutral",
        "gray": "neutral",
        "grey": "neutral",
    }

    # 间距尺度
    SPACING_SCALE = {
        0: "0",
        2: "2px",
        4: "4px",
        6: "6px",
        8: "8px",
        10: "10px",
        12: "12px",
        14: "14px",
        16: "16px",
        20: "20px",
        24: "24px",
        28: "28px",
        32: "32px",
        36: "36px",
        40: "40px",
        48: "48px",
        56: "56px",
        64: "64px",
        80: "80px",
        96: "96px",
        128: "128px",
    }

    # 圆角尺度
    RADIUS_SCALE = {
        "none": "0",
        "sm": "2px",
        "md": "4px",
        "lg": "8px",
        "xl": "12px",
        "2xl": "16px",
        "3xl": "24px",
        "full": "9999px",
    }

    # 阴影尺度
    SHADOW_SCALE = {
        "xs": "0 1px 2px 0 rgba(0, 0, 0, 0.05)",
        "sm": "0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px -1px rgba(0, 0, 0, 0.1)",
        "md": "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1)",
        "lg": "0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.1)",
        "xl": "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1)",
        "2xl": "0 25px 50px -12px rgba(0, 0, 0, 0.25)",
        "inner": "inset 0 2px 4px 0 rgba(0, 0, 0, 0.05)",
    }

    # 断点
    BREAKPOINTS = {
        "sm": "640px",
        "md": "768px",
        "lg": "1024px",
        "xl": "1280px",
        "2xl": "1536px",
    }

    # z-index 层级
    Z_INDEX_SCALE = {
        "base": "0",
        "dropdown": "1000",
        "sticky": "1100",
        "fixed": "1200",
        "modal-backdrop": "1300",
        "modal": "1400",
        "popover": "1500",
        "tooltip": "1600",
        "toast": "1700",
    }

    # 字体尺度
    FONT_SIZE_SCALE = {
        "xs": "12px",
        "sm": "14px",
        "base": "16px",
        "lg": "18px",
        "xl": "20px",
        "2xl": "24px",
        "3xl": "30px",
        "4xl": "36px",
        "5xl": "48px",
    }

    # 行高尺度
    LINE_HEIGHT_SCALE = {
        "none": "1",
        "tight": "1.25",
        "snug": "1.375",
        "normal": "1.5",
        "relaxed": "1.625",
        "loose": "2",
    }

    @classmethod
    def generate_tokens_css(cls, tokens: DesignTokens) -> str:
        """
        从设计令牌生成 CSS Variables

        Args:
            tokens: 设计令牌

        Returns:
            CSS 变量定义字符串
        """
        lines = []
        lines.append("/* 自动生成 - 请勿手动编辑 */")
        lines.append(":root {")
        lines.append("  /* ===== 色彩 ===== */")

        # 基础色彩
        if tokens.colors:
            for name, value in tokens.colors.items():
                var_name = cls._to_css_var_name("color", name)
                lines.append(f"  {var_name}: {value};")
            lines.append("")

        # 语义化色彩
        if tokens.semantic_colors:
            lines.append("  /* 语义化色彩 */")
            for category, colors in tokens.semantic_colors.items():
                for name, value in colors.items():
                    var_name = f"--color-{category}-{name}"
                    lines.append(f"  {var_name}: {value};")
            lines.append("")

        # 字体
        lines.append("  /* ===== 字体 ===== */")
        if tokens.font_families:
            for name, value in tokens.font_families.items():
                var_name = cls._to_css_var_name("font-family", name)
                lines.append(f"  {var_name}: {value};")
            lines.append("")

        if tokens.font_sizes:
            for name, value in tokens.font_sizes.items():
                var_name = cls._to_css_var_name("font-size", name)
                lines.append(f"  {var_name}: {value};")
            lines.append("")

        if tokens.font_weights:
            for name, value in tokens.font_weights.items():
                var_name = cls._to_css_var_name("font-weight", name)
                lines.append(f"  {var_name}: {value};")
            lines.append("")

        if tokens.line_heights:
            for name, value in tokens.line_heights.items():
                var_name = cls._to_css_var_name("line-height", name)
                lines.append(f"  {var_name}: {value};")
            lines.append("")

        if tokens.letter_spacings:
            for name, value in tokens.letter_spacings.items():
                var_name = cls._to_css_var_name("letter-spacing", name)
                lines.append(f"  {var_name}: {value};")
            lines.append("")

        # 间距
        lines.append("  /* ===== 间距 ===== */")
        if tokens.spacing:
            for name, value in tokens.spacing.items():
                var_name = cls._to_css_var_name("spacing", name)
                lines.append(f"  {var_name}: {value};")
            lines.append("")

        # 圆角
        lines.append("  /* ===== 圆角 ===== */")
        if tokens.radii:
            for name, value in tokens.radii.items():
                var_name = cls._to_css_var_name("radius", name)
                lines.append(f"  {var_name}: {value};")
            lines.append("")

        # 阴影
        lines.append("  /* ===== 阴影 ===== */")
        if tokens.shadows:
            for name, value in tokens.shadows.items():
                var_name = cls._to_css_var_name("shadow", name)
                lines.append(f"  {var_name}: {value};")
            lines.append("")

        # 边框
        lines.append("  /* ===== 边框 ===== */")
        if tokens.borders:
            for name, value in tokens.borders.items():
                var_name = cls._to_css_var_name("border", name)
                lines.append(f"  {var_name}: {value};")
            lines.append("")

        # 断点
        lines.append("  /* ===== 断点 ===== */")
        for name, value in cls.BREAKPOINTS.items():
            var_name = f"--breakpoint-{name}"
            lines.append(f"  {var_name}: {value};")
        lines.append("")

        # z-index
        lines.append("  /* ===== Z-Index ===== */")
        if tokens.z_index:
            for name, value in tokens.z_index.items():
                var_name = f"--z-index-{name}"
                lines.append(f"  {var_name}: {value};")
        else:
            for name, value in cls.Z_INDEX_SCALE.items():
                var_name = f"--z-index-{name}"
                lines.append(f"  {var_name}: {value};")
        lines.append("")

        # 过渡
        lines.append("  /* ===== 过渡 ===== */")
        if tokens.transitions:
            for name, value in tokens.transitions.items():
                var_name = cls._to_css_var_name("transition", name)
                lines.append(f"  {var_name}: {value};")
        else:
            lines.append("  --transition-fast: 150ms ease;")
            lines.append("  --transition-normal: 200ms ease;")
            lines.append("  --transition-slow: 300ms ease;")
            lines.append("  --transition-spring: 500ms cubic-bezier(0.34, 1.56, 0.64, 1);")
        lines.append("}")

        # 暗色模式
        lines.append("")
        lines.append("/* 暗色模式 */")
        lines.append("@media (prefers-color-scheme: dark) {")
        lines.append("  :root {")
        lines.append("    /* TODO: 添加暗色模式色彩 */")
        lines.append("  }")
        lines.append("}")

        return "\n".join(lines)

    @classmethod
    def _to_css_var_name(cls, prefix: str, name: str) -> str:
        """转换为 CSS 变量名"""
        # 去除已有前缀
        if name.startswith(f"{prefix}-"):
            name = name[len(prefix)+1:]
        # kebab-case
        kebab = re.sub(r'([A-Z])', r'-\1', name).lower()
        kebab = re.sub(r'[^a-z0-9\-]', '-', kebab)
        kebab = re.sub(r'-+', '-', kebab).strip('-')
        return f"--{prefix}-{kebab}"


# ============================================================
# 组件样式生成器
# ============================================================

class ComponentStyleGenerator:
    """
    组件样式生成器

    生成规范化的组件 CSS：
    1. BEM 命名
    2. CSS Variables 引用
    3. 状态类 (is-*, has-*)
    4. 无障碍焦点样式
    5. 响应式样式
    6. 暗色模式
    """

    @classmethod
    def generate_component_css(cls, comp: ComponentIR, tokens: DesignTokens) -> str:
        """
        生成单个组件的 CSS

        Args:
            comp: 组件 IR
            tokens: 设计令牌

        Returns:
            CSS 字符串
        """
        block = BEMNamer.block(comp.name)
        lines = []

        # 组件基础样式
        lines.append(f"/* {comp.name} 组件样式 */")
        lines.append(f".{block} {{")
        lines.append("  /* 布局 */")
        lines.append("  display: flex;")
        lines.append("  flex-direction: column;")
        lines.append("  box-sizing: border-box;")
        lines.append("")

        # 根据组件类型添加默认样式
        if comp.component_type == ComponentType.BUTTON:
            lines.extend(cls._button_defaults(block, tokens))
        elif comp.component_type == ComponentType.INPUT:
            lines.extend(cls._input_defaults(block, tokens))
        elif comp.component_type == ComponentType.CARD:
            lines.extend(cls._card_defaults(block, tokens))
        elif comp.component_type == ComponentType.MODAL:
            lines.extend(cls._modal_defaults(block, tokens))
        else:
            lines.extend(cls._container_defaults(block, tokens))

        lines.append("}")
        lines.append("")

        # 子元素样式
        for child in comp.children:
            child_block = BEMNamer.block(child.name)
            element_name = child_block.split('-')[-1]  # 取最后一部分作为 element 名
            lines.append(f".{block}__{element_name} {{")
            lines.append("  box-sizing: border-box;")
            lines.append("}")
            lines.append("")

        # 状态样式
        lines.extend(cls._generate_state_styles(block, comp, tokens))

        # 变体样式
        lines.extend(cls._generate_variant_styles(block, comp, tokens))

        # 无障碍焦点样式
        lines.extend(cls._generate_focus_styles(block, comp))

        # 响应式样式
        lines.extend(cls._generate_responsive_styles(block, comp, tokens))

        return "\n".join(lines)

    @classmethod
    def _button_defaults(cls, block: str, tokens: DesignTokens) -> List[str]:
        """按钮默认样式"""
        return [
            "  /* 按钮基础 */",
            "  display: inline-flex;",
            "  align-items: center;",
            "  justify-content: center;",
            "  gap: 8px;",
            "  padding: 8px 16px;",
            "  border: 1px solid transparent;",
            "  border-radius: var(--radius-md, 4px);",
            "  background-color: var(--color-primary-500, #1677ff);",
            "  color: #ffffff;",
            "  font-family: var(--font-family-base, inherit);",
            "  font-size: var(--font-size-base, 14px);",
            "  font-weight: 500;",
            "  line-height: 1.5;",
            "  text-decoration: none;",
            "  cursor: pointer;",
            "  user-select: none;",
            "  transition: all var(--transition-fast, 150ms ease);",
            "  outline: none;",
            "",
            "  /* 禁用态 */",
            "  &.is-disabled,",
            "  &:disabled {",
            "    opacity: 0.5;",
            "    cursor: not-allowed;",
            "    pointer-events: none;",
            "  }",
        ]

    @classmethod
    def _input_defaults(cls, block: str, tokens: DesignTokens) -> List[str]:
        """输入框默认样式"""
        return [
            "  /* 输入框基础 */",
            "  display: flex;",
            "  flex-direction: column;",
            "  gap: 4px;",
            "",
            f"  &__control {{",
            "    padding: 8px 12px;",
            "    border: 1px solid var(--color-border-default, #d9d9d9);",
            "    border-radius: var(--radius-md, 4px);",
            "    background-color: var(--color-bg-page, #ffffff);",
            "    color: var(--color-text-primary, #262626);",
            "    font-family: var(--font-family-base, inherit);",
            "    font-size: var(--font-size-base, 14px);",
            "    line-height: 1.5;",
            "    outline: none;",
            "    transition: border-color var(--transition-fast, 150ms ease);",
            "",
            "    &::placeholder {",
            "      color: var(--color-text-tertiary, #bfbfbf);",
            "    }",
            "",
            "    &:hover {",
            "      border-color: var(--color-primary-400, #4096ff);",
            "    }",
            "",
            "    &:focus {",
            "      border-color: var(--color-primary-500, #1677ff);",
            "      box-shadow: 0 0 0 2px var(--color-primary-bg, #e6f4ff);",
            "    }",
            "",
            "    &.is-error {",
            "      border-color: var(--color-error-500, #ff4d4f);",
            "    }",
            "",
            "    &.is-success {",
            "      border-color: var(--color-success-500, #52c41a);",
            "    }",
            "",
            "    &:disabled {",
            "      background-color: var(--color-bg-disabled, #f5f5f5);",
            "      cursor: not-allowed;",
            "    }",
            "  }",
        ]

    @classmethod
    def _card_defaults(cls, block: str, tokens: DesignTokens) -> List[str]:
        """卡片默认样式"""
        return [
            "  /* 卡片基础 */",
            "  background-color: var(--color-bg-page, #ffffff);",
            "  border: 1px solid var(--color-border-default, #f0f0f0);",
            "  border-radius: var(--radius-lg, 8px);",
            "  box-shadow: var(--shadow-sm, 0 1px 2px 0 rgba(0, 0, 0, 0.03));",
            "  overflow: hidden;",
            "  transition: box-shadow var(--transition-normal, 200ms ease);",
            "",
            "  &:hover {",
            "    box-shadow: var(--shadow-md, 0 4px 6px -1px rgba(0, 0, 0, 0.1));",
            "  }",
        ]

    @classmethod
    def _modal_defaults(cls, block: str, tokens: DesignTokens) -> List[str]:
        """模态框默认样式"""
        return [
            "  /* 模态框基础 */",
            "  position: fixed;",
            "  top: 0;",
            "  left: 0;",
            "  right: 0;",
            "  bottom: 0;",
            "  display: flex;",
            "  align-items: center;",
            "  justify-content: center;",
            "  z-index: var(--z-index-modal, 1400);",
            "  opacity: 0;",
            "  visibility: hidden;",
            "  transition: opacity var(--transition-normal, 200ms ease),",
            "              visibility var(--transition-normal, 200ms ease);",
            "",
            "  &.is-open {",
            "    opacity: 1;",
            "    visibility: visible;",
            "  }",
            "",
            "  &__overlay {",
            "    position: absolute;",
            "    top: 0;",
            "    left: 0;",
            "    right: 0;",
            "    bottom: 0;",
            "    background-color: rgba(0, 0, 0, 0.45);",
            "  }",
            "",
            "  &__content {",
            "    position: relative;",
            "    width: 520px;",
            "    max-width: calc(100vw - 32px);",
            "    max-height: calc(100vh - 32px);",
            "    padding: 24px;",
            "    background-color: var(--color-bg-page, #ffffff);",
            "    border-radius: var(--radius-lg, 8px);",
            "    box-shadow: var(--shadow-xl, 0 20px 25px -5px rgba(0, 0, 0, 0.1));",
            "    overflow: auto;",
            "  }",
            "",
            "  &__close {",
            "    position: absolute;",
            "    top: 16px;",
            "    right: 16px;",
            "    width: 24px;",
            "    height: 24px;",
            "    padding: 0;",
            "    border: none;",
            "    background: transparent;",
            "    cursor: pointer;",
            "    color: var(--color-text-tertiary, #8c8c8c);",
            "    font-size: 16px;",
            "    line-height: 1;",
            "  }",
        ]

    @classmethod
    def _container_defaults(cls, block: str, tokens: DesignTokens) -> List[str]:
        """通用容器默认样式"""
        return [
            "  /* 容器基础 */",
            "  box-sizing: border-box;",
            "  width: 100%;",
        ]

    @classmethod
    def _generate_state_styles(cls, block: str, comp: ComponentIR, tokens: DesignTokens) -> List[str]:
        """生成状态样式"""
        lines = []
        states = ["active", "hover", "focus", "disabled", "loading", "success", "error", "selected", "checked", "expanded", "collapsed"]

        for state in states:
            has_state = any(s.name == state or s.visual_state == state for s in comp.state)
            if has_state:
                class_name = f".{block}.is-{state}"
                lines.append(f"{class_name} {{")
                # 根据状态添加样式
                if state == "hover":
                    lines.append("  /* hover 状态 */")
                elif state == "active":
                    lines.append("  /* active 状态 */")
                elif state == "focus":
                    lines.append("  /* focus 状态 */")
                elif state == "disabled":
                    lines.append("  opacity: 0.5;")
                    lines.append("  cursor: not-allowed;")
                    lines.append("  pointer-events: none;")
                elif state == "loading":
                    lines.append("  opacity: 0.7;")
                    lines.append("  cursor: wait;")
                elif state == "success":
                    lines.append(f"  border-color: var(--color-success-500, #52c41a);")
                elif state == "error":
                    lines.append(f"  border-color: var(--color-error-500, #ff4d4f);")
                lines.append("}")
                lines.append("")

        return lines

    @classmethod
    def _generate_variant_styles(cls, block: str, comp: ComponentIR, tokens: DesignTokens) -> List[str]:
        """生成变体样式"""
        lines = []

        # 根据组件类型推断变体
        if comp.component_type == ComponentType.BUTTON:
            variants = {
                "primary": {
                    "background-color": "var(--color-primary-500, #1677ff)",
                    "color": "#ffffff",
                },
                "secondary": {
                    "background-color": "var(--color-bg-page, #ffffff)",
                    "border-color": "var(--color-border-default, #d9d9d9)",
                    "color": "var(--color-text-primary, #262626)",
                },
                "ghost": {
                    "background-color": "transparent",
                    "color": "var(--color-primary-500, #1677ff)",
                },
                "danger": {
                    "background-color": "var(--color-error-500, #ff4d4f)",
                    "color": "#ffffff",
                },
            }
            sizes = {
                "small": {"padding": "4px 8px", "font-size": "12px"},
                "medium": {"padding": "8px 16px", "font-size": "14px"},
                "large": {"padding": "12px 24px", "font-size": "16px"},
            }
            for variant_name, styles in variants.items():
                lines.append(f".{block}--{variant_name} {{")
                for prop, value in styles.items():
                    lines.append(f"  {prop}: {value};")
                lines.append("}")
                lines.append("")
            for size_name, styles in sizes.items():
                lines.append(f".{block}--{size_name} {{")
                for prop, value in styles.items():
                    lines.append(f"  {prop}: {value};")
                lines.append("}")
                lines.append("")

        elif comp.component_type == ComponentType.ALERT:
            variants = {
                "info": {"background-color": "var(--color-info-bg, #e6f4ff)", "border-color": "var(--color-info-500, #1677ff)"},
                "success": {"background-color": "var(--color-success-bg, #f6ffed)", "border-color": "var(--color-success-500, #52c41a)"},
                "warning": {"background-color": "var(--color-warning-bg, #fffbe6)", "border-color": "var(--color-warning-500, #faad14)"},
                "error": {"background-color": "var(--color-error-bg, #fff2f0)", "border-color": "var(--color-error-500, #ff4d4f)"},
            }
            for variant_name, styles in variants.items():
                lines.append(f".{block}--{variant_name} {{")
                for prop, value in styles.items():
                    lines.append(f"  {prop}: {value};")
                lines.append("}")
                lines.append("")

        return lines

    @classmethod
    def _generate_focus_styles(cls, block: str, comp: ComponentIR) -> List[str]:
        """生成无障碍焦点样式"""
        lines = []
        lines.append(f"/* 无障碍焦点样式 */")
        lines.append(f".{block}:focus-visible {{")
        lines.append("  outline: 2px solid var(--color-primary-500, #1677ff);")
        lines.append("  outline-offset: 2px;")
        lines.append("}")
        lines.append("")
        return lines

    @classmethod
    def _generate_responsive_styles(cls, block: str, comp: ComponentIR, tokens: DesignTokens) -> List[str]:
        """生成响应式样式"""
        lines = []
        # 基础响应式：小屏幕下全宽
        lines.append(f"/* 响应式 */")
        lines.append(f"@media (max-width: 640px) {{")
        lines.append(f"  .{block} {{")
        lines.append("    width: 100%;")
        lines.append("  }")
        lines.append("}")
        lines.append("")
        return lines


# ============================================================
# 全局样式生成器
# ============================================================

class GlobalStyleGenerator:
    """
    全局样式生成器

    生成 CSS Reset、全局样式、工具类
    """

    @classmethod
    def generate_reset(cls) -> str:
        """CSS Reset"""
        return """/* CSS Reset - 现代化重置 */
*, *::before, *::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

html {
  -webkit-text-size-adjust: 100%;
  -moz-text-size-adjust: 100%;
  text-size-adjust: 100%;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

body {
  min-height: 100vh;
  font-family: var(--font-family-base, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, 'Noto Sans', sans-serif);
  font-size: var(--font-size-base, 14px);
  line-height: var(--line-height-normal, 1.5);
  color: var(--color-text-primary, #262626);
  background-color: var(--color-bg-page, #ffffff);
}

img, svg, video, canvas {
  display: block;
  max-width: 100%;
}

img {
  height: auto;
}

input, button, textarea, select {
  font: inherit;
}

button {
  cursor: pointer;
  border: none;
  background: none;
}

a {
  color: inherit;
  text-decoration: none;
}

ul, ol {
  list-style: none;
}

table {
  border-collapse: collapse;
  border-spacing: 0;
}

/* 无障碍：跳过链接 */
.skip-link {
  position: absolute;
  top: -40px;
  left: 0;
  padding: 8px 16px;
  background: var(--color-primary-500, #1677ff);
  color: #ffffff;
  z-index: var(--z-index-toast, 1700);
  transition: top 0.2s ease;
}

.skip-link:focus {
  top: 0;
}

/* 屏幕阅读器专用 */
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border-width: 0;
}

/* 焦点可见性 */
:focus-visible {
  outline: 2px solid var(--color-primary-500, #1677ff);
  outline-offset: 2px;
}

/* 减少动画 */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
"""

    @classmethod
    def generate_utilities(cls) -> str:
        """工具类"""
        return """/* 工具类 */

/* 布局 */
.flex { display: flex; }
.flex-col { flex-direction: column; }
.flex-row { flex-direction: row; }
.flex-wrap { flex-wrap: wrap; }
.items-center { align-items: center; }
.items-start { align-items: flex-start; }
.items-end { align-items: flex-end; }
.justify-center { justify-content: center; }
.justify-between { justify-content: space-between; }
.justify-end { justify-content: flex-end; }
.gap-1 { gap: 4px; }
.gap-2 { gap: 8px; }
.gap-3 { gap: 12px; }
.gap-4 { gap: 16px; }
.gap-6 { gap: 24px; }
.gap-8 { gap: 32px; }

/* 间距 */
.p-0 { padding: 0; }
.p-1 { padding: 4px; }
.p-2 { padding: 8px; }
.p-3 { padding: 12px; }
.p-4 { padding: 16px; }
.p-6 { padding: 24px; }
.p-8 { padding: 32px; }

.m-0 { margin: 0; }
.m-1 { margin: 4px; }
.m-2 { margin: 8px; }
.m-3 { margin: 12px; }
.m-4 { margin: 16px; }

.mx-auto { margin-left: auto; margin-right: auto; }

/* 宽高 */
.w-full { width: 100%; }
.h-full { height: 100%; }
.min-h-screen { min-height: 100vh; }

/* 文本 */
.text-center { text-align: center; }
.text-left { text-align: left; }
.text-right { text-align: right; }
.font-bold { font-weight: 700; }
.font-medium { font-weight: 500; }
.font-normal { font-weight: 400; }
.text-xs { font-size: var(--font-size-xs, 12px); }
.text-sm { font-size: var(--font-size-sm, 14px); }
.text-base { font-size: var(--font-size-base, 16px); }
.text-lg { font-size: var(--font-size-lg, 18px); }
.text-xl { font-size: var(--font-size-xl, 20px); }
.text-2xl { font-size: var(--font-size-2xl, 24px); }

/* 颜色 */
.text-primary { color: var(--color-primary-500, #1677ff); }
.text-success { color: var(--color-success-500, #52c41a); }
.text-warning { color: var(--color-warning-500, #faad14); }
.text-error { color: var(--color-error-500, #ff4d4f); }
.text-muted { color: var(--color-text-tertiary, #8c8c8c); }

/* 溢出 */
.overflow-hidden { overflow: hidden; }
.overflow-auto { overflow: auto; }
.truncate { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* 定位 */
.relative { position: relative; }
.absolute { position: absolute; }
.fixed { position: fixed; }
.sticky { position: sticky; top: 0; }

/* 圆角 */
.rounded-sm { border-radius: var(--radius-sm, 2px); }
.rounded { border-radius: var(--radius-md, 4px); }
.rounded-lg { border-radius: var(--radius-lg, 8px); }
.rounded-full { border-radius: var(--radius-full, 9999px); }

/* 阴影 */
.shadow-sm { box-shadow: var(--shadow-sm); }
.shadow { box-shadow: var(--shadow-md); }
.shadow-lg { box-shadow: var(--shadow-lg); }

/* 隐藏/显示 */
.hidden { display: none; }
.block { display: block; }
.inline-block { display: inline-block; }
.inline { display: inline; }

/* 可访问性 */
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border-width: 0; }
.not-sr-only { position: static; width: auto; height: auto; padding: 0; margin: 0; overflow: visible; clip: auto; white-space: normal; }
"""
