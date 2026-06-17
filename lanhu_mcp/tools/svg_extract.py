"""SVG提取 - 从设计稿中提取矢量图形代码"""
import re
from typing import Optional


def extract_svg_from_layer(layer_data: dict, design_scale: float = 2.0) -> Optional[str]:
    """
    从图层数据中提取或生成 SVG 代码。

    Args:
        layer_data: 图层数据
        design_scale: 设计稿缩放比

    Returns:
        SVG 代码字符串，如果无法生成则返回 None
    """
    scale = design_scale or 2.0

    def _px(val):
        if val is None:
            return 0
        return round(float(val) / scale, 1)

    def _color_str(color: dict) -> str:
        if not color:
            return '#000000'
        if 'value' in color:
            return color['value']
        r = round(color.get('red', color.get('r', 0)))
        g = round(color.get('green', color.get('g', 0)))
        b = round(color.get('blue', color.get('b', 0)))
        return f"rgb({r},{g},{b})"

    # 获取图层基本信息
    name = layer_data.get('name', 'unnamed')
    frame = layer_data.get('frame') or layer_data.get('ddsOriginFrame') or {}
    x = _px(frame.get('x', layer_data.get('left', 0)))
    y = _px(frame.get('y', layer_data.get('top', 0)))
    w = _px(frame.get('width', layer_data.get('width', 0)))
    h = _px(frame.get('height', layer_data.get('height', 0)))

    if w <= 0 or h <= 0:
        return None

    # 检查是否有SVG URL
    image = layer_data.get('image', {})
    if image and image.get('svgUrl'):
        return f'<!-- SVG from URL: {image["svgUrl"]} -->'

    # 提取填充颜色
    fills = layer_data.get('fills', [])
    fill_color = None
    fill_opacity = 1.0
    for f in fills:
        if f.get('isEnabled', True) and f.get('fillType', 0) == 0:
            fill_color = _color_str(f.get('color', {}))
            alpha = f.get('color', {}).get('alpha', 1)
            if alpha < 1:
                fill_opacity = alpha
            break

    # 提取边框
    borders = layer_data.get('borders', [])
    stroke_color = None
    stroke_width = 0
    for b in borders:
        if b.get('isEnabled', True):
            stroke_color = _color_str(b.get('color', {}))
            stroke_width = b.get('thickness', 1)
            break

    # 提取圆角
    radius = layer_data.get('radius')
    rx = ry = 0
    if radius:
        if isinstance(radius, list) and len(radius) >= 4:
            rx = _px(radius[0])
            ry = _px(radius[1])
        elif isinstance(radius, (int, float)):
            rx = ry = _px(radius)

    # 构建 SVG
    fill_attr = f' fill="{fill_color}"' if fill_color else ' fill="none"'
    if fill_opacity < 1:
        fill_attr += f' fill-opacity="{fill_opacity}"'

    stroke_attr = ''
    if stroke_color and stroke_width > 0:
        stroke_attr = f' stroke="{stroke_color}" stroke-width="{stroke_width}"'

    rx_attr = f' rx="{rx}" ry="{ry}"' if rx > 0 else ''

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
  <rect x="0" y="0" width="{w}" height="{h}"{fill_attr}{stroke_attr}{rx_attr} />
</svg>'''

    return svg


def extract_all_svgs(sketch_data: dict, design_scale: float = 2.0) -> list:
    """
    从设计稿中提取所有可用的 SVG。

    Args:
        sketch_data: 蓝湖设计图 Sketch JSON
        design_scale: 设计稿缩放比

    Returns:
        SVG 列表
    """
    svgs = []

    def _walk(obj, parent_path=""):
        if not obj or not isinstance(obj, dict):
            return

        name = obj.get('name', '')
        current_path = f"{parent_path}/{name}" if parent_path else name

        # 检查是否有 SVG URL
        image = obj.get('image', {})
        if image and image.get('svgUrl'):
            svgs.append({
                'name': name,
                'path': current_path,
                'svg_url': image['svgUrl'],
                'type': 'url',
            })

        # 尝试从图层生成 SVG
        svg_code = extract_svg_from_layer(obj, design_scale)
        if svg_code:
            svgs.append({
                'name': name,
                'path': current_path,
                'svg_code': svg_code,
                'type': 'generated',
            })

        # 递归
        for child in obj.get('layers', []):
            _walk(child, current_path)
        for child in obj.get('children', []):
            _walk(child, current_path)

    # 遍历所有图层
    artboard = sketch_data.get('artboard', {})
    board = sketch_data.get('board', {})
    layers = artboard.get('layers', []) or board.get('layers', [])

    for layer in layers:
        _walk(layer)

    return svgs


def format_svgs_for_ai(svgs: list) -> str:
    """
    将 SVG 列表格式化为AI可读的文本。

    Args:
        svgs: SVG 列表

    Returns:
        格式化的文本
    """
    if not svgs:
        return "无可提取的 SVG"

    lines = ["[SVG 矢量图形]"]
    lines.append(f"共 {len(svgs)} 个 SVG\n")

    for i, svg in enumerate(svgs[:20], 1):
        lines.append(f"--- SVG {i}: {svg['name']} ---")
        lines.append(f"  路径: {svg['path']}")
        lines.append(f"  类型: {svg['type']}")

        if svg.get('svg_url'):
            lines.append(f"  URL: {svg['svg_url']}")
        if svg.get('svg_code'):
            lines.append(f"  代码:\n```svg\n{svg['svg_code']}\n```")
        lines.append("")

    return "\n".join(lines)
