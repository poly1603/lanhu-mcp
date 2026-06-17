"""设计质量检查 - 自动检查设计一致性、可访问性等问题"""
import math
from collections import Counter
from typing import Optional


def design_quality_check(sketch_data: dict, design_scale: float = 2.0) -> dict:
    """
    对设计稿进行质量检查。

    Args:
        sketch_data: 蓝湖设计图 Sketch JSON
        design_scale: 设计稿缩放比

    Returns:
        包含 score, issues, statistics 的质量检查结果
    """
    scale = design_scale or 2.0
    issues = []

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

    def _extract_opacity(layer: dict) -> float:
        bo = layer.get('blendOptions', {})
        if 'opacity' in bo:
            op = bo['opacity']
            return op.get('value', 100) if isinstance(op, dict) else op
        return 100

    def _rgba_to_rgb(r, g, b):
        return f"rgb({r},{g},{b})"

    def _relative_luminance(r, g, b):
        """计算相对亮度 (WCAG 2.1)"""
        def linearize(c):
            c = c / 255.0
            return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
        return 0.2126 * linearize(r) + 0.7152 * linearize(g) + 0.0722 * linearize(b)

    def _contrast_ratio(c1, c2):
        """计算对比度"""
        import re
        def parse_color(c):
            m = re.match(r'rgb\((\d+),\s*(\d+),\s*(\d+)\)', c)
            if m:
                return int(m.group(1)), int(m.group(2)), int(m.group(3))
            m = re.match(r'rgba\((\d+),\s*(\d+),\s*(\d+)', c)
            if m:
                return int(m.group(1)), int(m.group(2)), int(m.group(3))
            return 0, 0, 0

        r1, g1, b1 = parse_color(c1)
        r2, g2, b2 = parse_color(c2)
        l1 = _relative_luminance(r1, g1, b1)
        l2 = _relative_luminance(r2, g2, b2)
        lighter = max(l1, l2)
        darker = min(l1, l2)
        return (lighter + 0.05) / (darker + 0.05)

    # 收集数据
    all_colors = Counter()
    text_colors = Counter()
    bg_colors = Counter()
    font_specs = Counter()
    radius_values = Counter()
    spacing_values = Counter()
    font_families = Counter()
    font_sizes = Counter()

    def _walk(obj, parent_path=""):
        if not obj or not isinstance(obj, dict):
            return

        name = obj.get('name', '')
        current_path = f"{parent_path}/{name}" if parent_path else name

        # 填充颜色
        fills = obj.get('fills', [])
        for f in fills:
            if not f.get('isEnabled', True):
                continue
            if f.get('fillType', 0) == 0:
                color = _color_str(f.get('color', {}))
                if color:
                    all_colors[color] += 1

        # 背景色（旧版）
        fill = obj.get('fill', {})
        if fill:
            color = _color_str(fill.get('color', {}))
            if color:
                all_colors[color] += 1

        # 文本样式
        text_info = obj.get('textInfo', {})
        art_text = obj.get('text', {})
        if isinstance(art_text, dict) and art_text.get('style'):
            text_info = art_text

        if text_info:
            tc = text_info.get('color', {})
            if isinstance(art_text, dict):
                tc = art_text.get('style', {}).get('color', {})
            tc_val = _color_str(tc)
            if tc_val:
                text_colors[tc_val] += 1

            font_size = text_info.get('size', 0)
            if isinstance(art_text, dict):
                font_size = art_text.get('style', {}).get('font', {}).get('size', 0)
            if font_size:
                fs = _px(font_size)
                font_sizes[f"{fs}px"] += 1

            font_name = text_info.get('fontPostScriptName', '') or text_info.get('fontName', '')
            if isinstance(art_text, dict):
                font_name = art_text.get('style', {}).get('font', {}).get('name', '')
            if font_name:
                font_families[font_name] += 1
                spec_key = f"{_px(font_size)}px|{font_name}"
                font_specs[spec_key] += 1

        # 圆角
        radius = obj.get('radius')
        if radius:
            if isinstance(radius, list):
                if len(set(radius)) == 1 and radius[0] > 0:
                    radius_values[f"{_px(radius[0])}px"] += 1
            elif radius > 0:
                radius_values[f"{_px(radius)}px"] += 1

        # 递归
        for child in obj.get('layers', []):
            _walk(child, current_path)
        for child in obj.get('children', []):
            _walk(child, current_path)

    # 遍历
    if sketch_data.get('artboard') and sketch_data['artboard'].get('layers'):
        for layer in sketch_data['artboard']['layers']:
            _walk(layer)
    elif sketch_data.get('board') and sketch_data['board'].get('layers'):
        for layer in sketch_data['board']['layers']:
            _walk(layer)

    # === 质量检查 ===

    # 1. 颜色一致性检查
    unique_colors = len(all_colors)
    if unique_colors > 20:
        issues.append({
            'severity': 'warning',
            'category': 'color',
            'message': f'色板较大：使用了{unique_colors}种颜色，建议控制在15种以内',
            'elements': [c for c, _ in all_colors.most_common(5)],
            'suggestion': '建议统一颜色为Design Tokens，减少视觉噪音',
        })

    # 2. 文字对比度检查
    for text_color, count in text_colors.items():
        for bg_color in ['#FFFFFF', 'rgb(255, 255, 255)', 'rgba(255, 255, 255, 1)']:
            try:
                ratio = _contrast_ratio(text_color, bg_color)
                if ratio < 4.5:
                    issues.append({
                        'severity': 'error',
                        'category': 'accessibility',
                        'message': f'文字对比度不足：{text_color}在白色背景上对比度仅{ratio:.1f}:1（需≥4.5:1）',
                        'elements': [text_color],
                        'suggestion': f'建议将文字颜色调整为更深的颜色以达到WCAG AA标准',
                    })
                    break
            except Exception:
                pass

    # 3. 字体一致性检查
    if len(font_families) > 3:
        issues.append({
            'severity': 'warning',
            'category': 'typography',
            'message': f'使用了{len(font_families)}种字体，建议控制在2-3种以内',
            'elements': [f for f, _ in font_families.most_common(5)],
            'suggestion': '建议统一字体为标题字体+正文字体',
        })

    # 4. 字号层级检查
    if len(font_sizes) > 6:
        issues.append({
            'severity': 'info',
            'category': 'typography',
            'message': f'使用了{len(font_sizes)}种字号，建议不超过4-5级',
            'elements': [f for f, _ in font_sizes.most_common(10)],
            'suggestion': '建议建立字号系统：如 12/14/16/20/24px',
        })

    # 5. 圆角一致性检查
    if len(radius_values) > 3:
        issues.append({
            'severity': 'info',
            'category': 'consistency',
            'message': f'使用了{len(radius_values)}种圆角值，建议统一',
            'elements': list(radius_values.keys()),
            'suggestion': '建议使用4/8/12/16px等标准圆角值',
        })

    # 计算分数
    error_count = sum(1 for i in issues if i['severity'] == 'error')
    warning_count = sum(1 for i in issues if i['severity'] == 'warning')
    info_count = sum(1 for i in issues if i['severity'] == 'info')
    score = max(0, 100 - error_count * 15 - warning_count * 5 - info_count * 2)

    return {
        'score': score,
        'issues': issues,
        'statistics': {
            'unique_colors': unique_colors,
            'text_color_count': len(text_colors),
            'font_family_count': len(font_families),
            'font_size_count': len(font_sizes),
            'radius_value_count': len(radius_values),
        },
    }
