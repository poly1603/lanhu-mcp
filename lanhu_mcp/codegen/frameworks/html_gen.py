"""
HTML 生成器 - 语义化 + BEM + 原生 CSS + 无障碍

输出：纯 HTML + 原生 CSS + 原生 JS
"""
from __future__ import annotations

import re
from typing import Optional, List, Dict, Any

from lanhu_mcp.codegen.ir import (
    DesignIR,
    ComponentIR,
    ComponentType,
    SemanticTag,
    A11ySpec,
    EventSpec,
    PropSpec,
    StyleSpec,
    CSSRule,
    InteractionSpec,
    DesignTokens,
)
from lanhu_mcp.codegen.semantic import SemanticAnalyzer
from lanhu_mcp.codegen.style_system import (
    BEMNamer,
    CSSVariableGenerator,
    ComponentStyleGenerator,
    GlobalStyleGenerator,
)
from lanhu_mcp.codegen.interaction import InteractionInference, AnimationInference


class HTMLGenerator:
    """
    HTML 代码生成器

    生成规范：
    1. 语义化 HTML5 标签
    2. BEM 命名规范
    3. CSS Variables 设计令牌
    4. ARIA 无障碍属性
    5. 键盘导航支持
    6. 响应式布局
    7. 暗色模式
    8. 减少动画偏好
    """

    def __init__(self):
        self.semantic_analyzer = SemanticAnalyzer()
        self.interaction_engine = InteractionInference(framework="html")

    def generate(self, ir: DesignIR) -> Dict[str, str]:
        """
        从 DesignIR 生成 HTML 项目

        Args:
            ir: 设计 IR

        Returns:
            {"index.html": "...", "styles.css": "...", "script.js": "..."}
        """
        # 1. 语义化分析
        ir = self.semantic_analyzer.analyze_design(ir)

        # 2. 交互推断
        ir = self.interaction_engine.analyze_design(ir)

        # 3. 生成文件
        files = {}

        # CSS
        files["styles.css"] = self._generate_css(ir)

        # HTML
        files["index.html"] = self._generate_html(ir)

        # JS
        files["script.js"] = self._generate_js(ir)

        return files

    def _generate_css(self, ir: DesignIR) -> str:
        """生成 CSS 文件"""
        parts = []

        # 文件头
        parts.append("/* =============================================")
        parts.append("   自动生成 - 请勿手动编辑")
        parts.append(f"   项目: {ir.name}")
        parts.append("   ============================================= */")
        parts.append("")

        # CSS Reset
        parts.append("/* ===== CSS Reset ===== */")
        parts.append(GlobalStyleGenerator.generate_reset())
        parts.append("")

        # 设计令牌
        parts.append("/* ===== 设计令牌 (Design Tokens) ===== */")
        parts.append(CSSVariableGenerator.generate_tokens_css(ir.tokens))
        parts.append("")

        # 组件样式
        parts.append("/* ===== 组件样式 ===== */")
        for comp in ir.components:
            css = ComponentStyleGenerator.generate_component_css(comp, ir.tokens)
            parts.append(css)
            parts.append("")

        # 工具类
        parts.append("/* ===== 工具类 ===== */")
        parts.append(GlobalStyleGenerator.generate_utilities())
        parts.append("")

        # 动画关键帧
        parts.append("/* ===== 动画 ===== */")
        self._append_keyframes(parts, ir)

        return "\n".join(parts)

    def _generate_html(self, ir: DesignIR) -> str:
        """生成 HTML 文件"""
        parts = []

        parts.append('<!DOCTYPE html>')
        parts.append('<html lang="zh-CN">')
        parts.append('<head>')
        parts.append('  <meta charset="UTF-8">')
        parts.append('  <meta name="viewport" content="width=device-width, initial-scale=1.0">')
        parts.append('  <meta name="description" content="">')
        if ir.pages:
            parts.append(f'  <title>{ir.pages[0].title or ir.name}</title>')
        else:
            parts.append(f'  <title>{ir.name}</title>')
        parts.append('  <link rel="stylesheet" href="styles.css">')
        parts.append('</head>')
        parts.append('')

        # 跳过链接（无障碍）
        parts.append('<!-- 跳过链接 - 键盘用户可直接跳到主内容 -->')
        parts.append('<a href="#main-content" class="skip-link">跳到主内容</a>')
        parts.append('')

        parts.append('<body>')

        # 生成组件树
        for comp in ir.components:
            html = self._render_component(comp, indent=2)
            parts.append(html)

        parts.append('')
        parts.append('  <script src="script.js"></script>')
        parts.append('</body>')
        parts.append('</html>')

        return "\n".join(parts)

    def _generate_js(self, ir: DesignIR) -> str:
        """生成 JavaScript 文件"""
        parts = []

        parts.append('/**')
        parts.append(f' * {ir.name} - 交互脚本')
        parts.append(' * 自动生成 - 请勿手动编辑')
        parts.append(' */')
        parts.append('')
        parts.append("'use strict';")
        parts.append("")

        # 收集所有需要交互的组件
        interactable = self._find_interactable_components(ir)

        if interactable:
            parts.append("// ============================================")
            parts.append("// 交互组件初始化")
            parts.append("// ============================================")
            parts.append("")
            parts.append("document.addEventListener('DOMContentLoaded', () => {")
            parts.append("  // 跳过链接")
            parts.append("  const skipLink = document.querySelector('.skip-link');")
            parts.append("  if (skipLink) {")
            parts.append("    skipLink.addEventListener('keydown', (e) => {")
            parts.append("      if (e.key === 'Enter') {")
            parts.append("        e.preventDefault();")
            parts.append("        document.querySelector('#main-content')?.focus();")
            parts.append("      }")
            parts.append("    });")
            parts.append("  }")
            parts.append("")

            for comp in interactable:
                js = self._generate_component_js(comp)
                if js:
                    parts.append(f"  // {comp.name}")
                    parts.append(js)
                    parts.append("")

            parts.append("});")

        return "\n".join(parts)

    def _render_component(self, comp: ComponentIR, indent: int = 0) -> str:
        """渲染单个组件为 HTML"""
        spaces = "  " * indent
        tag = comp.semantic_tag.value

        # 构建属性列表
        attrs = []

        # class (BEM)
        block = BEMNamer.block(comp.name)
        classes = [block]
        attrs.append(f'class="{" ".join(classes)}"')

        # ARIA 属性
        if comp.aria:
            if comp.aria.role:
                attrs.append(f'role="{comp.aria.role}"')
            if comp.aria.aria_label:
                attrs.append(f'aria-label="{comp.aria.aria_label}"')
            if comp.aria.aria_labelledby:
                attrs.append(f'aria-labelledby="{comp.aria.aria_labelledby}"')
            if comp.aria.aria_expanded:
                attrs.append(f'aria-expanded="{comp.aria.aria_expanded}"')
            if comp.aria.aria_haspopup:
                attrs.append(f'aria-haspopup="{comp.aria.aria_haspopup}"')
            if comp.aria.aria_controls:
                attrs.append(f'aria-controls="{comp.aria.aria_controls}"')
            if comp.aria.aria_selected:
                attrs.append(f'aria-selected="{comp.aria.aria_selected}"')
            if comp.aria.aria_checked:
                attrs.append(f'aria-checked="{comp.aria.aria_checked}"')
            if comp.aria.aria_disabled:
                attrs.append(f'aria-disabled="{comp.aria.aria_disabled}"')
            if comp.aria.aria_live:
                attrs.append(f'aria-live="{comp.aria.aria_live}"')
            if comp.aria.tabindex >= 0:
                attrs.append(f'tabindex="{comp.aria.tabindex}"')

        # 组件类型特定属性
        if comp.component_type == ComponentType.INPUT:
            attrs.append('type="text"')
            attrs.append(f'id="{block}-input"')
            # 关联 label
            label_block = BEMNamer.block(comp.name + "-label")
            attrs.append(f'aria-labelledby="{label_block}"')

        if comp.component_type == ComponentType.BUTTON:
            attrs.append('type="button"')

        if comp.component_type == ComponentType.IMAGE:
            attrs.append(f'alt="{comp.aria.aria_label if comp.aria else comp.name}"')
            attrs.append(f'loading="lazy"')

        # 构建属性字符串
        attr_str = " ".join(attrs)

        # 自闭合标签
        if tag in ("img", "input", "br", "hr"):
            return f'{spaces}<{tag} {attr_str} />'

        # 内容
        content = ""
        if comp.children:
            child_parts = []
            for child in comp.children:
                child_html = self._render_component(child, indent + 1)
                child_parts.append(child_html)
            content = "\n".join(child_parts)
        else:
            # 文本内容
            text = self._get_text_content(comp)
            if text:
                content = f'{spaces}  {text}'

        if content:
            return f'{spaces}<{tag} {attr_str}>\n{content}\n{spaces}</{tag}>'
        else:
            return f'{spaces}<{tag} {attr_str}></{tag}>'

    def _get_text_content(self, comp: ComponentIR) -> str:
        """获取组件的文本内容"""
        # 从设计样式中获取文本
        text = comp.design_styles.get("text", "")
        if text:
            return text

        # 从组件名称推断
        name = comp.name
        if comp.component_type == ComponentType.BUTTON:
            return name
        if comp.component_type == ComponentType.LABEL:
            return name

        return ""

    def _generate_component_js(self, comp: ComponentIR) -> str:
        """生成单个组件的 JS 代码"""
        block = BEMNamer.block(comp.name)
        lines = []

        # 模态框/抽屉
        if comp.component_type in (ComponentType.MODAL, ComponentType.DRAWER):
            lines.append(f"  (() => {{")
            lines.append(f"    const modal = document.querySelector('.{block}');")
            lines.append(f"    const overlay = modal?.querySelector('.{block}__overlay');")
            lines.append(f"    const closeBtn = modal?.querySelector('.{block}__close');")
            lines.append(f"    const openBtn = document.querySelector('[data-open=\"{block}\"]');")
            lines.append(f"")
            lines.append(f"    function openModal() {{")
            lines.append(f"      modal?.classList.add('is-open');")
            lines.append(f"      modal?.setAttribute('aria-hidden', 'false');")
            lines.append(f"      document.body.style.overflow = 'hidden';")
            lines.append(f"      // 焦点陷阱")
            lines.append(f"      const focusable = modal?.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex=\"-1\"])');")
            lines.append(f"      focusable?.[0]?.focus();")
            lines.append(f"    }}")
            lines.append(f"")
            lines.append(f"    function closeModal() {{")
            lines.append(f"      modal?.classList.remove('is-open');")
            lines.append(f"      modal?.setAttribute('aria-hidden', 'true');")
            lines.append(f"      document.body.style.overflow = '';")
            lines.append(f"      openBtn?.focus();")
            lines.append(f"    }}")
            lines.append(f"")
            lines.append(f"    openBtn?.addEventListener('click', openModal);")
            lines.append(f"    closeBtn?.addEventListener('click', closeModal);")
            lines.append(f"    overlay?.addEventListener('click', closeModal);")
            lines.append(f"")
            lines.append(f"    // ESC 键关闭")
            lines.append(f"    modal?.addEventListener('keydown', (e) => {{")
            lines.append(f"      if (e.key === 'Escape') closeModal();")
            lines.append(f"      // Tab 键焦点陷阱")
            lines.append(f"      if (e.key === 'Tab') {{")
            lines.append(f"        const focusable = modal?.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex=\"-1\"])');")
            lines.append(f"        if (!focusable?.length) return;")
            lines.append(f"        const first = focusable[0];")
            lines.append(f"        const last = focusable[focusable.length - 1];")
            lines.append(f"        if (e.shiftKey && document.activeElement === first) {{")
            lines.append(f"          e.preventDefault();")
            lines.append(f"          last.focus();")
            lines.append(f"        }} else if (!e.shiftKey && document.activeElement === last) {{")
            lines.append(f"          e.preventDefault();")
            lines.append(f"          first.focus();")
            lines.append(f"        }}")
            lines.append(f"      }}")
            lines.append(f"    }});")
            lines.append(f"  }})();")
            lines.append("")

        # 标签页
        elif comp.component_type == ComponentType.TABS:
            lines.append(f"  (() => {{")
            lines.append(f"    const tabs = document.querySelector('.{block}');")
            lines.append(f"    const tabList = tabs?.querySelector('[role=\"tablist\"]');")
            lines.append(f"    const tabButtons = tabs?.querySelectorAll('[role=\"tab\"]');")
            lines.append(f"    const tabPanels = tabs?.querySelectorAll('[role=\"tabpanel\"]');")
            lines.append(f"")
            lines.append(f"    function switchTab(index) {{")
            lines.append(f"      tabButtons?.forEach((btn, i) => {{")
            lines.append(f"        const isSelected = i === index;")
            lines.append(f"        btn.setAttribute('aria-selected', isSelected);")
            lines.append(f"        btn.setAttribute('tabindex', isSelected ? '0' : '-1');")
            lines.append(f"        tabPanels?.[i]?.setAttribute('hidden', !isSelected);")
            lines.append(f"      }});")
            lines.append(f"    }}")
            lines.append(f"")
            lines.append(f"    tabButtons?.forEach((btn, i) => {{")
            lines.append(f"      btn.addEventListener('click', () => switchTab(i));")
            lines.append(f"      btn.addEventListener('keydown', (e) => {{")
            lines.append(f"        let newIndex = i;")
            lines.append(f"        if (e.key === 'ArrowRight') newIndex = (i + 1) % tabButtons.length;")
            lines.append(f"        if (e.key === 'ArrowLeft') newIndex = (i - 1 + tabButtons.length) % tabButtons.length;")
            lines.append(f"        if (e.key === 'Home') newIndex = 0;")
            lines.append(f"        if (e.key === 'End') newIndex = tabButtons.length - 1;")
            lines.append(f"        if (newIndex !== i) {{")
            lines.append(f"          e.preventDefault();")
            lines.append(f"          switchTab(newIndex);")
            lines.append(f"          tabButtons[newIndex]?.focus();")
            lines.append(f"        }}")
            lines.append(f"      }});")
            lines.append(f"    }});")
            lines.append(f"  }})();")
            lines.append("")

        # 下拉菜单
        elif comp.component_type in (ComponentType.DROPDOWN, ComponentType.MENU):
            lines.append(f"  (() => {{")
            lines.append(f"    const dropdown = document.querySelector('.{block}');")
            lines.append(f"    const trigger = dropdown?.querySelector('.{block}__trigger');")
            lines.append(f"    const menu = dropdown?.querySelector('.{block}__menu');")
            lines.append(f"    const items = menu?.querySelectorAll('[role=\"menuitem\"]');")
            lines.append(f"")
            lines.append(f"    function openMenu() {{")
            lines.append(f"      menu?.removeAttribute('hidden');")
            lines.append(f"      trigger?.setAttribute('aria-expanded', 'true');")
            lines.append(f"      items?.[0]?.focus();")
            lines.append(f"    }}")
            lines.append(f"")
            lines.append(f"    function closeMenu() {{")
            lines.append(f"      menu?.setAttribute('hidden', '');")
            lines.append(f"      trigger?.setAttribute('aria-expanded', 'false');")
            lines.append(f"      trigger?.focus();")
            lines.append(f"    }}")
            lines.append(f"")
            lines.append(f"    trigger?.addEventListener('click', () => {{")
            lines.append(f"      const isOpen = trigger?.getAttribute('aria-expanded') === 'true';")
            lines.append(f"      isOpen ? closeMenu() : openMenu();")
            lines.append(f"    }});")
            lines.append(f"")
            lines.append(f"    items?.forEach((item, i) => {{")
            lines.append(f"      item.addEventListener('click', closeMenu);")
            lines.append(f"      item.addEventListener('keydown', (e) => {{")
            lines.append(f"        if (e.key === 'Escape') closeMenu();")
            lines.append(f"        if (e.key === 'ArrowDown') {{")
            lines.append(f"          e.preventDefault();")
            lines.append(f"          items[(i + 1) % items.length]?.focus();")
            lines.append(f"        }}")
            lines.append(f"        if (e.key === 'ArrowUp') {{")
            lines.append(f"          e.preventDefault();")
            lines.append(f"          items[(i - 1 + items.length) % items.length]?.focus();")
            lines.append(f"        }}")
            lines.append(f"      }});")
            lines.append(f"    }});")
            lines.append(f"  }})();")
            lines.append("")

        # 折叠面板
        elif comp.component_type == ComponentType.ACCORDION:
            lines.append(f"  (() => {{")
            lines.append(f"    const accordion = document.querySelector('.{block}');")
            lines.append(f"    const triggers = accordion?.querySelectorAll('.{block}__trigger');")
            lines.append(f"")
            lines.append(f"    triggers?.forEach((trigger) => {{")
            lines.append(f"      trigger.addEventListener('click', () => {{")
            lines.append(f"        const expanded = trigger.getAttribute('aria-expanded') === 'true';")
            lines.append(f"        trigger.setAttribute('aria-expanded', !expanded);")
            lines.append(f"        const panel = trigger.nextElementSibling;")
            lines.append(f"        panel?.toggleAttribute('hidden');")
            lines.append(f"      }});")
            lines.append(f"      trigger.addEventListener('keydown', (e) => {{")
            lines.append(f"        if (e.key === 'Enter' || e.key === 'Space') {{")
            lines.append(f"          e.preventDefault();")
            lines.append(f"          trigger.click();")
            lines.append(f"        }}")
            lines.append(f"      }});")
            lines.append(f"    }});")
            lines.append(f"  }})();")
            lines.append("")

        # 表格排序
        elif comp.component_type == ComponentType.TABLE:
            lines.append(f"  (() => {{")
            lines.append(f"    const table = document.querySelector('.{block}');")
            lines.append(f"    const sortHeaders = table?.querySelectorAll('[data-sort]');")
            lines.append(f"")
            lines.append(f"    sortHeaders?.forEach((header) => {{")
            lines.append(f"      header.addEventListener('click', () => {{")
            lines.append(f"        const key = header.dataset.sort;")
            lines.append(f"        const currentDir = header.dataset.direction || 'asc';")
            lines.append(f"        const newDir = currentDir === 'asc' ? 'desc' : 'asc';")
            lines.append(f"        header.dataset.direction = newDir;")
            lines.append(f"        header.setAttribute('aria-sort', newDir === 'asc' ? 'ascending' : 'descending');")
            lines.append(f"      }});")
            lines.append(f"    }});")
            lines.append(f"  }})();")
            lines.append("")

        # 轮播图
        elif comp.component_type == ComponentType.CAROUSEL:
            lines.append(f"  (() => {{")
            lines.append(f"    const carousel = document.querySelector('.{block}');")
            lines.append(f"    const slides = carousel?.querySelectorAll('.{block}__slide');")
            lines.append(f"    const prevBtn = carousel?.querySelector('.{block}__prev');")
            lines.append(f"    const nextBtn = carousel?.querySelector('.{block}__next');")
            lines.append(f"    let current = 0;")
            lines.append(f"")
            lines.append(f"    function goTo(index) {{")
            lines.append(f"      slides?.forEach((s, i) => {{")
            lines.append(f"        s.classList.toggle('is-active', i === index);")
            lines.append(f"        s.setAttribute('aria-hidden', i !== index);")
            lines.append(f"      }});")
            lines.append(f"      current = index;")
            lines.append(f"    }}")
            lines.append(f"")
            lines.append(f"    prevBtn?.addEventListener('click', () => {{")
            lines.append(f"      goTo((current - 1 + slides.length) % slides.length);")
            lines.append(f"    }});")
            lines.append(f"    nextBtn?.addEventListener('click', () => {{")
            lines.append(f"      goTo((current + 1) % slides.length);")
            lines.append(f"    }});")
            lines.append(f"")
            lines.append(f"    // 自动播放")
            lines.append(f"    let autoplay = setInterval(() => goTo((current + 1) % slides.length), 3000);")
            lines.append(f"    carousel?.addEventListener('mouseenter', () => clearInterval(autoplay));")
            lines.append(f"    carousel?.addEventListener('mouseleave', () => {{")
            lines.append(f"      autoplay = setInterval(() => goTo((current + 1) % slides.length), 3000);")
            lines.append(f"    }});")
            lines.append(f"  }})();")
            lines.append("")

        return "\n".join(lines)

    def _find_interactable_components(self, ir: DesignIR) -> List[ComponentIR]:
        """查找所有需要交互的组件"""
        result = []
        interactable_types = {
            ComponentType.MODAL, ComponentType.DRAWER,
            ComponentType.TABS, ComponentType.ACCORDION,
            ComponentType.DROPDOWN, ComponentType.MENU,
            ComponentType.CAROUSEL, ComponentType.TABLE,
            ComponentType.FORM, ComponentType.SELECT,
        }
        for comp in ir.components:
            if comp.component_type in interactable_types:
                result.append(comp)
            result.extend(self._find_interactable_children(comp, interactable_types))
        return result

    def _find_interactable_children(self, comp: ComponentIR, types: set) -> List[ComponentIR]:
        result = []
        for child in comp.children:
            if child.component_type in types:
                result.append(child)
            result.extend(self._find_interactable_children(child, types))
        return result

    def _append_keyframes(self, parts: List[str], ir: DesignIR):
        """追加动画关键帧"""
        seen = set()
        for comp in ir.components:
            anims = AnimationInference.DEFAULT_ANIMATIONS.get(comp.component_type, {})
            for name in anims:
                key = f"{comp.component_type.value}-{name}"
                if key not in seen:
                    seen.add(key)
                    css = AnimationInference.generate_keyframes_css(comp.component_type)
                    if css:
                        parts.append(css)
