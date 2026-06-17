"""精确测量 - 元素间精确距离和尺寸计算"""
from typing import Optional, List, Dict
import math


def calculate_distance(element_a: dict, element_b: dict, design_scale: float = 2.0) -> dict:
    """
    计算两个元素之间的精确距离。

    Args:
        element_a: 元素A的位置信息 {x, y, width, height}
        element_b: 元素B的位置信息 {x, y, width, height}
        design_scale: 设计稿缩放比

    Returns:
        距离信息
    """
    scale = design_scale or 2.0

    def _px(val):
        if val is None:
            return 0
        return round(float(val) / scale, 1)

    ax = _px(element_a.get('x', 0))
    ay = _px(element_a.get('y', 0))
    aw = _px(element_a.get('width', 0))
    ah = _px(element_a.get('height', 0))

    bx = _px(element_b.get('x', 0))
    by = _px(element_b.get('y', 0))
    bw = _px(element_b.get('width', 0))
    bh = _px(element_b.get('height', 0))

    # 计算中心点
    acx, acy = ax + aw / 2, ay + ah / 2
    bcx, bcy = bx + bw / 2, by + bh / 2

    # 欧几里得距离（中心到中心）
    euclidean = round(math.sqrt((acx - bcx) ** 2 + (acy - bcy) ** 2), 1)

    # 水平距离
    h_distance = round(abs(acx - bcx), 1)

    # 垂直距离
    v_distance = round(abs(acy - bcy), 1)

    # 边缘间距（最近边之间的距离）
    # 水平边缘间距
    if ax + aw <= bx:
        h_gap = round(bx - (ax + aw), 1)
    elif bx + bw <= ax:
        h_gap = round(ax - (bx + bw), 1)
    else:
        h_gap = 0  # 重叠

    # 垂直边缘间距
    if ay + ah <= by:
        v_gap = round(by - (ay + ah), 1)
    elif by + bh <= ay:
        v_gap = round(ay - (by + bh), 1)
    else:
        v_gap = 0  # 重叠

    # 对齐检测
    alignment = []
    if abs(ax - bx) < 2:
        alignment.append('left-aligned')
    if abs(ax + aw - bx - bw) < 2:
        alignment.append('right-aligned')
    if abs(ay - by) < 2:
        alignment.append('top-aligned')
    if abs(ay + ah - by - bh) < 2:
        alignment.append('bottom-aligned')
    if abs(acx - bcx) < 2:
        alignment.append('center-x-aligned')
    if abs(acy - bcy) < 2:
        alignment.append('center-y-aligned')

    return {
        'euclidean_distance': euclidean,
        'horizontal_distance': h_distance,
        'vertical_distance': v_distance,
        'horizontal_gap': h_gap,
        'vertical_gap': v_gap,
        'alignment': alignment,
        'element_a': {'x': ax, 'y': ay, 'width': aw, 'height': ah},
        'element_b': {'x': bx, 'y': by, 'width': bw, 'height': bh},
    }


def measure_all_elements(sketch_data: dict, design_scale: float = 2.0) -> dict:
    """
    测量设计稿中所有元素的尺寸和位置。

    Args:
        sketch_data: 蓝湖设计图 Sketch JSON
        design_scale: 设计稿缩放比

    Returns:
        所有元素的测量信息
    """
    scale = design_scale or 2.0

    def _px(val):
        if val is None:
            return 0
        return round(float(val) / scale, 1)

    elements = []

    def _walk(obj, parent_path=""):
        if not obj or not isinstance(obj, dict):
            return

        name = obj.get('name', '')
        current_path = f"{parent_path}/{name}" if parent_path else name

        frame = obj.get('frame') or obj.get('ddsOriginFrame') or {}
        x = _px(frame.get('x', obj.get('left', 0)))
        y = _px(frame.get('y', obj.get('top', 0)))
        w = _px(frame.get('width', obj.get('width', 0)))
        h = _px(frame.get('height', obj.get('height', 0)))

        if w > 0 and h > 0:
            elements.append({
                'name': name,
                'path': current_path,
                'x': x,
                'y': y,
                'width': w,
                'height': h,
                'area': round(w * h, 1),
            })

        for child in obj.get('layers', []):
            _walk(child, current_path)
        for child in obj.get('children', []):
            _walk(child, current_path)

    artboard = sketch_data.get('artboard', {})
    board = sketch_data.get('board', {})
    layers = artboard.get('layers', []) or board.get('layers', [])

    for layer in layers:
        _walk(layer)

    return {
        'total_elements': len(elements),
        'elements': elements,
    }


def format_measurements_for_ai(measurements: dict) -> str:
    """
    将测量信息格式化为AI可读的文本。

    Args:
        measurements: 测量数据

    Returns:
        格式化的文本
    """
    elements = measurements.get('elements', [])
    if not elements:
        return "无测量数据"

    lines = ["[元素测量数据]"]
    lines.append(f"共 {measurements.get('total_elements', 0)} 个元素\n")

    for i, el in enumerate(elements[:30], 1):
        lines.append(f"  {i}. \"{el['name']}\"")
        lines.append(f"     位置: x={el['x']}, y={el['y']}")
        lines.append(f"     尺寸: {el['width']} x {el['height']}")
        lines.append(f"     面积: {el['area']}px²")

    return "\n".join(lines)
