"""设计系统提取 - 从设计稿中提取完整设计规范"""
import re
import math
from collections import Counter, defaultdict
from typing import Optional


def extract_design_system(sketch_data: dict, design_scale: float = 2.0) -> dict:
    """
    从 Sketch JSON 中提取完整设计系统规范。

    Args:
        sketch_data: 蓝湖设计图 Sketch JSON
        design_scale: 设计稿缩放比

    Returns:
        包含 colors, typography, spacing, borders, shadows, components 的设计系统
    """
    scale = design_scale or 2.0

    colors_counter = Counter()
    text_colors_counter = Counter()
    bg_colors_counter = Counter()
    border_colors_counter = Counter()
    border_styles_counter = Counter()
    gradient_list = []
    font_families_counter = Counter()
    font_specs_counter = Counter()
    font_sizes_counter = Counter()
    font_weights_counter = Counter()
    margin_values = Counter()
    padding_values = Counter()
    gap_values = Counter()
    radius_values = Counter()
    border_styles = Counter()
    shadow_list = []

    def _px(val):
        if val is None:
            return 0
        return round(float(val) / scale, 1)

    def _color_str(color: dict, opacity: float = 100) -> str:
        if not color:
            return None
        if 'value' in color:
            return color['value']
        r = round(color.get('red', color.get('r', 0)))
        g = round(color.get('green', color.get('g', 0)))
        b = round(color.get('blue', color.get('b', 0)))
        a = round(opacity / 100, 2) if opacity < 100 else 1
        if a < 1:
            return f"rgba({r},{g},{b},{a})"
        return f"rgb({r},{g},{b})"

    def _extract_opacity(layer: dict) -> float:
        bo = layer.get('blendOptions', {})
        if 'opacity' in bo:
            op = bo['opacity']
            return op.get('value', 100) if isinstance(op, dict) else op
        return 100

    def _walk(obj, parent_path=""):
        if not obj or not isinstance(obj, dict):
            return

        name = obj.get('name', '')
        current_path = f"{parent_path}/{name}" if parent_path else name

        # 提取填充颜色
        fills = obj.get('fills', [])
        for f in fills:
            if not f.get('isEnabled', True):
                continue
            fill_type = f.get('fillType', f.get('type', 0))
            if fill_type == 0 or fill_type == 'color':
                color = f.get('color', {})
                color_val = _color_str(color, _extract_opacity(obj))
                if color_val:
                    colors_counter[color_val] += 1
            elif fill_type == 1 or fill_type == 'gradient':
                gradient = f.get('gradient', {})
                stops = gradient.get('colorStops', [])
                parts = []
                for s in stops:
                    c = _color_str(s.get('color', {}))
                    p = s.get('position', 0)
                    if c:
                        parts.append(f"{c} {round(p * 100)}%")
                if parts:
                    grad_str = f"linear-gradient({', '.join(parts)})"
                    gradient_list.append(grad_str)

        # 旧版填充
        fill = obj.get('fill', {})
        if fill:
            fill_color = _color_str(fill.get('color', {}), _extract_opacity(obj))
            if fill_color:
                colors_counter[fill_color] += 1

        # 提取文本样式
        text_info = obj.get('textInfo', {})
        art_text = obj.get('text', {})
        if isinstance(art_text, dict) and art_text.get('style'):
            text_info = art_text

        if text_info:
            # 文本颜色
            tc = text_info.get('color', {})
            if isinstance(art_text, dict):
                tc = art_text.get('style', {}).get('color', {})
            tc_val = _color_str(tc, _extract_opacity(obj))
            if tc_val:
                text_colors_counter[tc_val] += 1
                colors_counter[tc_val] += 1

            # 字体信息
            font_size = text_info.get('size', 0)
            if isinstance(art_text, dict):
                font_size = art_text.get('style', {}).get('font', {}).get('size', 0)
            if font_size:
                fs = _px(font_size)
                font_sizes_counter[f"{fs}px"] += 1

            font_name = text_info.get('fontPostScriptName', '') or text_info.get('fontName', '')
            if isinstance(art_text, dict):
                font_name = art_text.get('style', {}).get('font', {}).get('name', '') or art_text.get('style', {}).get('font', {}).get('postScriptName', '')
            if font_name:
                font_families_counter[font_name] += 1

            bold = text_info.get('bold', False)
            if isinstance(art_text, dict):
                bold = art_text.get('style', {}).get('font', {}).get('fontWeight', 0) >= 600
            fw = 'bold' if bold else 'normal'
            font_weights_counter[fw] += 1

            if font_size and font_name:
                spec_key = f"{_px(font_size)}px|{fw}|{font_name}"
                font_specs_counter[spec_key] += 1

        # 提取边框/圆角/阴影
        borders = obj.get('borders', [])
        for b in borders:
            if b.get('isEnabled', True):
                bc = _color_str(b.get('color', {}))
                thickness = b.get('thickness', 1)
                if bc:
                    border_styles_counter[f"{thickness}px solid {bc}"] += 1
                    border_colors_counter[bc] += 1

        radius = obj.get('radius')
        if radius:
            if isinstance(radius, list):
                for r in radius:
                    if r > 0:
                        radius_values[f"{_px(r)}px"] += 1
            elif radius > 0:
                radius_values[f"{_px(radius)}px"] += 1

        shadows = obj.get('shadows', [])
        for s in shadows:
            if s.get('isEnabled', True):
                sc = _color_str(s.get('color', {}))
                sx = _px(s.get('x', 0))
                sy = _px(s.get('y', 0))
                sb = _px(s.get('blur', 0))
                ss = _px(s.get('spread', 0))
                if sc:
                    shadow_str = f"{sx}px {sy}px {sb}px {ss}px {sc}"
                    if shadow_str not in shadow_list:
                        shadow_list.append(shadow_str)

        # 递归子图层
        for child in obj.get('layers', []):
            _walk(child, current_path)
        for child in obj.get('children', []):
            _walk(child, current_path)

    # 开始遍历
    if sketch_data.get('artboard') and sketch_data['artboard'].get('layers'):
        for layer in sketch_data['artboard']['layers']:
            _walk(layer)
    elif sketch_data.get('board') and sketch_data['board'].get('layers'):
        for layer in sketch_data['board']['layers']:
            _walk(layer)
    elif sketch_data.get('info'):
        for item in sketch_data['info']:
            _walk(item)

    # 构建色板
    palette = sorted(colors_counter.keys(), key=lambda c: colors_counter[c], reverse=True)

    # 间距模式分析
    all_spacing = list(margin_values.keys()) + list(padding_values.keys())
    spacing_counter = Counter()
    for s in all_spacing:
        try:
            val = float(s.replace('px', ''))
            spacing_counter[val] += 1
        except ValueError:
            pass

    # 识别间距系统
    spacing_system = {}
    for val in sorted(spacing_counter.keys()):
        if val in [4, 8, 12, 16, 20, 24, 32, 40, 48, 64]:
            spacing_system[f"{val}px"] = spacing_counter[val]

    # 生成 CSS Variables
    css_vars = [":root {"]
    for i, color in enumerate(palette[:20]):
        var_name = f"--color-{i+1}"
        css_vars.append(f"  {var_name}: {color};")
    css_vars.append("}")
    css_vars_str = "\n".join(css_vars)

    return {
        "colors": {
            "palette": palette[:30],
            "text": text_colors_counter.most_common(15),
            "background": bg_colors_counter.most_common(10),
            "border": border_colors_counter.most_common(10),
            "gradient": list(set(gradient_list))[:10],
        },
        "typography": {
            "font_families": [f for f, _ in font_families_counter.most_common(10)],
            "font_sizes": [f for f, _ in font_sizes_counter.most_common(15)],
            "font_weights": dict(font_weights_counter),
            "font_specs": [(k, v) for k, v in font_specs_counter.most_common(20)],
        },
        "spacing": {
            "margin_values": [k for k, _ in margin_values.most_common(20)],
            "padding_values": [k for k, _ in padding_values.most_common(20)],
            "patterns": spacing_system,
        },
        "borders": {
            "radius_values": sorted(radius_values.keys(), key=lambda r: radius_values[r], reverse=True)[:10],
            "border_styles": [k for k, _ in border_styles.most_common(10)],
        },
        "shadows": shadow_list[:10],
        "design_tokens_css": css_vars_str,
    }
