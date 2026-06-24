"""
Pipeline - 设计稿到生产级前端代码的完整编排器

URL → Sketch JSON → DesignIR → 语义化 + 交互推断 + 依赖检测 → 框架代码
"""
from __future__ import annotations

import json
from typing import Optional, List, Dict, Any
from pathlib import Path

from lanhu_mcp.codegen.ir import (
    DesignIR,
    Framework,
    StylingMode,
    ComponentIR,
    ComponentType,
    DesignTokens,
    ProjectSpec,
)
from lanhu_mcp.codegen.semantic import SemanticAnalyzer, DocumentOutlineAnalyzer
from lanhu_mcp.codegen.style_system import CSSVariableGenerator
from lanhu_mcp.codegen.interaction import InteractionInference
from lanhu_mcp.codegen.dependency_detector import DependencyDetector
from lanhu_mcp.codegen.frameworks.html_gen import HTMLGenerator
from lanhu_mcp.codegen.frameworks.vue_gen import VueGenerator
from lanhu_mcp.codegen.frameworks.react_gen import ReactGenerator


class Pipeline:
    """
    设计稿 → 生产级代码 完整流水线

    流程：
    1. 解析 Sketch JSON → DesignIR
    2. 语义化分析（HTML5 标签、ARIA 属性）
    3. 交互推断（状态机、事件流、插件检测）
    4. 依赖收集
    5. 框架代码生成
    6. 输出文件
    """

    def __init__(self, framework: str = "html"):
        """
        Args:
            framework: 目标框架 (html, vue, react, flutter, svelte)
        """
        self.framework = Framework(framework)
        self.semantic_analyzer = SemanticAnalyzer()
        self.outline_analyzer = DocumentOutlineAnalyzer()
        self.interaction_engine = InteractionInference(framework=framework)
        self.dep_detector = DependencyDetector(framework=self.framework)

    def generate_from_sketch(
        self,
        sketch_data: dict,
        design_name: str = "",
        design_url: str = "",
        design_scale: float = 2.0,
    ) -> Dict[str, str]:
        """
        从 Sketch JSON 生成完整的前端项目

        Args:
            sketch_data: 蓝湖 Sketch JSON
            design_name: 设计图名称
            design_url: 设计图 URL
            design_scale: 设计稿缩放比

        Returns:
            {filename: content} 文件字典
        """
        # 1. 解析 Sketch JSON → DesignIR
        ir = self._parse_sketch_to_ir(sketch_data, design_name, design_url, design_scale)

        # 2. 语义化分析
        ir = self.semantic_analyzer.analyze_design(ir)
        ir = self.outline_analyzer.analyze(ir)

        # 3. 交互推断
        ir = self.interaction_engine.analyze_design(ir)

        # 4. 依赖收集
        ir = self.dep_detector.analyze_design(ir)

        # 5. 框架代码生成
        return self._generate_code(ir)

    def generate_from_ir(self, ir: DesignIR) -> Dict[str, str]:
        """
        从已构建的 DesignIR 生成代码

        Args:
            ir: 设计 IR

        Returns:
            {filename: content} 文件字典
        """
        # 语义化分析
        ir = self.semantic_analyzer.analyze_design(ir)
        ir = self.outline_analyzer.analyze(ir)

        # 交互推断
        ir = self.interaction_engine.analyze_design(ir)

        # 依赖收集
        ir = self.dep_detector.analyze_design(ir)

        # 代码生成
        return self._generate_code(ir)

    def _parse_sketch_to_ir(
        self,
        sketch_data: dict,
        design_name: str,
        design_url: str,
        design_scale: float,
    ) -> DesignIR:
        """解析 Sketch JSON 为 DesignIR"""
        # 提取设计令牌
        tokens = self._extract_tokens(sketch_data, design_scale)

        # 提取组件
        components = self._extract_components(sketch_data, design_scale)

        # 创建 IR
        ir = DesignIR(
            name=design_name or "Design",
            framework=self.framework,
            styling=StylingMode.NATIVE_CSS,
            tokens=tokens,
            components=components,
            original_url=design_url,
            design_name=design_name,
            design_scale=design_scale,
        )

        # 创建页面
        from lanhu_mcp.codegen.ir import PageIR
        page = PageIR(
            name=design_name or "index",
            route="/",
            title=design_name,
            components=components,
        )
        ir.pages = [page]

        return ir

    def _extract_tokens(self, sketch_data: dict, design_scale: float) -> DesignTokens:
        """从 Sketch JSON 提取设计令牌"""
        from lanhu_mcp.codegen.style_system import CSSVariableGenerator

        scale = design_scale or 2.0
        tokens = DesignTokens()

        def _px(val):
            if val is None:
                return 0
            return round(float(val) / scale, 1)

        def _color_str(color: dict) -> str:
            if not color:
                return None
            if 'value' in color:
                return color['value']
            r = round(color.get('red', color.get('r', 0)))
            g = round(color.get('green', color.get('g', 0)))
            b = round(color.get('blue', color.get('b', 0)))
            return f"rgb({r},{g},{b})"

        colors = set()
        font_families = set()
        font_sizes = set()
        font_weights = set()
        radius_values = set()
        shadow_values = set()

        def _walk(obj):
            if not obj or not isinstance(obj, dict):
                return

            # 填充颜色
            fills = obj.get('fills', [])
            for f in fills:
                if f.get('isEnabled', True):
                    color = _color_str(f.get('color', {}))
                    if color:
                        colors.add(color)

            # 文本样式
            text_info = obj.get('textInfo', {})
            art_text = obj.get('text', {})
            if isinstance(art_text, dict) and art_text.get('style'):
                text_info = art_text

            if text_info:
                font_size = text_info.get('size', 0)
                if isinstance(art_text, dict):
                    font_size = art_text.get('style', {}).get('font', {}).get('size', 0)
                if font_size:
                    font_sizes.add(f"{_px(font_size)}px")

                font_name = text_info.get('fontPostScriptName', '') or text_info.get('fontName', '')
                if isinstance(art_text, dict):
                    font_name = art_text.get('style', {}).get('font', {}).get('name', '')
                if font_name:
                    font_families.add(font_name)

                bold = text_info.get('bold', False)
                if isinstance(art_text, dict):
                    bold = art_text.get('style', {}).get('font', {}).get('fontWeight', 0) >= 600
                font_weights.add('bold' if bold else 'normal')

            # 圆角
            radius = obj.get('radius')
            if radius:
                if isinstance(radius, list):
                    for r in radius:
                        if r > 0:
                            radius_values.add(f"{_px(r)}px")
                elif radius > 0:
                    radius_values.add(f"{_px(radius)}px")

            # 阴影
            shadows = obj.get('shadows', [])
            for s in shadows:
                if s.get('isEnabled', True):
                    sc = _color_str(s.get('color', {}))
                    sx = _px(s.get('x', 0))
                    sy = _px(s.get('y', 0))
                    sb = _px(s.get('blur', 0))
                    if sc:
                        shadow_values.add(f"{sx}px {sy}px {sb}px {sc}")

            # 递归
            for child in obj.get('layers', []):
                _walk(child)
            for child in obj.get('children', []):
                _walk(child)

        # 遍历
        artboard = sketch_data.get('artboard', {})
        board = sketch_data.get('board', {})
        layers = artboard.get('layers', []) or board.get('layers', [])
        for layer in layers:
            _walk(layer)

        # 构建令牌
        tokens.colors = {f"color-{i}": c for i, c in enumerate(list(colors)[:20])}
        tokens.font_families = {f"font-{i}": f for i, f in enumerate(list(font_families)[:5])}
        tokens.font_sizes = {f"size-{i}": s for i, s in enumerate(sorted(list(font_sizes), key=lambda x: float(x.replace('px', ''))))}
        tokens.font_weights = {w: w for w in font_weights}
        tokens.radii = {f"radius-{i}": r for i, r in enumerate(sorted(list(radius_values), key=lambda x: float(x.replace('px', ''))))}
        tokens.shadows = {f"shadow-{i}": s for i, s in enumerate(list(shadow_values)[:5])}

        # 默认间距
        tokens.spacing = {
            "0": "0", "1": "4px", "2": "8px", "3": "12px", "4": "16px",
            "5": "20px", "6": "24px", "8": "32px", "10": "40px", "12": "48px",
        }

        # 默认断点
        tokens.breakpoints = CSSVariableGenerator.BREAKPOINTS

        return tokens

    def _extract_components(self, sketch_data: dict, design_scale: float) -> List[ComponentIR]:
        """从 Sketch JSON 提取组件"""
        scale = design_scale or 2.0
        components = []

        def _px(val):
            if val is None:
                return 0
            return round(float(val) / scale, 1)

        def _get_frame(obj):
            frame = obj.get('frame') or obj.get('ddsOriginFrame') or obj.get('layerOriginFrame') or {}
            return {
                'x': _px(frame.get('x', obj.get('left', 0))),
                'y': _px(frame.get('y', obj.get('top', 0))),
                'width': _px(frame.get('width', obj.get('width', 0))),
                'height': _px(frame.get('height', obj.get('height', 0))),
            }

        def _infer_type(name: str, frame: dict) -> ComponentType:
            name_lower = name.lower()
            if any(k in name_lower for k in ("button", "btn", "submit")):
                return ComponentType.BUTTON
            if any(k in name_lower for k in ("input", "field", "search")):
                return ComponentType.INPUT
            if any(k in name_lower for k in ("select", "dropdown", "picker")):
                return ComponentType.SELECT
            if any(k in name_lower for k in ("textarea", "text-area")):
                return ComponentType.TEXTAREA
            if any(k in name_lower for k in ("checkbox", "check")):
                return ComponentType.CHECKBOX
            if any(k in name_lower for k in ("radio", "option")):
                return ComponentType.RADIO
            if any(k in name_lower for k in ("switch", "toggle")):
                return ComponentType.SWITCH
            if any(k in name_lower for k in ("modal", "dialog", "popup")):
                return ComponentType.MODAL
            if any(k in name_lower for k in ("drawer", "panel")):
                return ComponentType.DRAWER
            if any(k in name_lower for k in ("tooltip", "tip")):
                return ComponentType.TOOLTIP
            if any(k in name_lower for k in ("dropdown", "menu")):
                return ComponentType.DROPDOWN
            if any(k in name_lower for k in ("tabs", "tab")):
                return ComponentType.TABS
            if any(k in name_lower for k in ("accordion", "collapse")):
                return ComponentType.ACCORDION
            if any(k in name_lower for k in ("table", "grid", "list")):
                return ComponentType.TABLE
            if any(k in name_lower for k in ("carousel", "slider", "swiper")):
                return ComponentType.CAROUSEL
            if any(k in name_lower for k in ("tree", "treeview")):
                return ComponentType.TREE
            if any(k in name_lower for k in ("pagination", "pager")):
                return ComponentType.PAGINATION
            if any(k in name_lower for k in ("steps", "stepper")):
                return ComponentType.STEPS
            if any(k in name_lower for k in ("form", "formitem")):
                return ComponentType.FORM
            if any(k in name_lower for k in ("alert", "notice")):
                return ComponentType.ALERT
            if any(k in name_lower for k in ("badge", "count")):
                return ComponentType.BADGE
            if any(k in name_lower for k in ("tag", "label")):
                return ComponentType.TAG
            if any(k in name_lower for k in ("avatar", "icon", "img")):
                return ComponentType.AVATAR
            if any(k in name_lower for k in ("card", "box")):
                return ComponentType.CARD
            if any(k in name_lower for k in ("nav", "menu", "sidebar")):
                return ComponentType.NAVBAR
            if any(k in name_lower for k in ("footer", "bottom")):
                return ComponentType.FOOTER
            if any(k in name_lower for k in ("divider", "line", "separator")):
                return ComponentType.DIVIDER
            if any(k in name_lower for k in ("skeleton", "loading")):
                return ComponentType.SKELETON
            if any(k in name_lower for k in ("spinner", "loader")):
                return ComponentType.SPINNER
            if any(k in name_lower for k in ("hero", "banner")):
                return ComponentType.HERO
            if any(k in name_lower for k in ("empty", "nodata")):
                return ComponentType.EMPTY
            if any(k in name_lower for k in ("result", "status")):
                return ComponentType.RESULT
            if any(k in name_lower for k in ("breadcrumb")):
                return ComponentType.BREADCRUMB
            if any(k in name_lower for k in ("timeline")):
                return ComponentType.TIMELINE
            if any(k in name_lower for k in ("calendar")):
                return ComponentType.CALENDAR
            if any(k in name_lower for k in ("transfer")):
                return ComponentType.TRANSFER
            if any(k in name_lower for k in ("upload")):
                return ComponentType.UPLOAD
            if any(k in name_lower for k in ("date", "time")):
                return ComponentType.DATE_PICKER
            if any(k in name_lower for k in ("slider", "range")):
                return ComponentType.SLIDER
            if any(k in name_lower for k in ("text", "label", "title")):
                return ComponentType.TEXT
            return ComponentType.CONTAINER

        def _walk(obj, parent=None):
            if not obj or not isinstance(obj, dict):
                return

            name = obj.get('name', '')
            frame = _get_frame(obj)

            # 跳过不可见或太小的元素
            if not obj.get('isVisible', True) and obj.get('isVisible') is not None:
                return
            if frame['width'] < 5 and frame['height'] < 5:
                return

            # 只处理有实际内容的图层
            has_content = (
                obj.get('textInfo') or
                obj.get('text') or
                obj.get('fills') or
                obj.get('fill') or
                obj.get('images') or
                len(obj.get('layers', [])) > 0 or
                len(obj.get('children', [])) > 0
            )

            if not has_content:
                return

            # 推断组件类型
            comp_type = _infer_type(name, frame)

            # 提取样式
            design_styles = {}
            text_info = obj.get('textInfo', {})
            art_text = obj.get('text', {})
            if isinstance(art_text, dict) and art_text.get('style'):
                text_info = art_text
            if text_info:
                text = text_info.get('text', '') if isinstance(text_info, dict) else ''
                if isinstance(art_text, dict):
                    text = art_text.get('value', '')
                design_styles['text'] = text

            # 创建组件
            comp = ComponentIR(
                name=name,
                component_type=comp_type,
                design_path=name,
                design_position=frame,
                design_styles=design_styles,
            )

            # 递归子图层
            children_raw = obj.get('layers', []) or obj.get('children', [])
            for child in children_raw:
                child_comp = _walk(child, comp)
                if child_comp:
                    comp.children.append(child_comp)

            # 添加到顶层或父级
            if parent is None:
                components.append(comp)

            return comp

        # 遍历
        artboard = sketch_data.get('artboard', sketch_data)
        layers = artboard.get('layers', [])
        for layer in layers:
            _walk(layer)

        return components

    def _generate_code(self, ir: DesignIR) -> Dict[str, str]:
        """根据框架生成代码"""
        if self.framework == Framework.HTML:
            from .frameworks.html_gen import HTMLGenerator
            generator = HTMLGenerator()
            return generator.generate(ir)
        elif self.framework == Framework.VUE:
            from .frameworks.vue_gen import VueGenerator
            generator = VueGenerator()
            return generator.generate(ir)
        elif self.framework == Framework.REACT:
            from .frameworks.react_gen import ReactGenerator
            generator = ReactGenerator()
            return generator.generate(ir)
        elif self.framework == Framework.FLUTTER:
            from .frameworks.flutter_gen import FlutterGenerator
            generator = FlutterGenerator()
            return generator.generate(ir)
        elif self.framework == Framework.SVELTE:
            from .frameworks.svelte_gen import SvelteGenerator
            generator = SvelteGenerator()
            return generator.generate(ir)
        else:
            # 默认 HTML
            from .frameworks.html_gen import HTMLGenerator
            generator = HTMLGenerator()
            return generator.generate(ir)

    def generate_ir_from_sketch(
        self,
        sketch_data: dict,
        design_name: str = "",
        design_url: str = "",
        design_scale: float = 2.0,
    ) -> DesignIR:
        """仅生成 IR，不生成代码（用于调试/中间步骤）"""
        ir = self._parse_sketch_to_ir(sketch_data, design_name, design_url, design_scale)
        ir = self.semantic_analyzer.analyze_design(ir)
        ir = self.outline_analyzer.analyze(ir)
        ir = self.interaction_engine.analyze_design(ir)
        ir = self.dep_detector.analyze_design(ir)
        return ir
