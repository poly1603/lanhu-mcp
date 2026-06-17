"""响应式变体 - 获取多设备尺寸的设计变体"""
from typing import Optional, List, Dict


def extract_responsive_variants(sketch_data: dict, design_scale: float = 2.0) -> dict:
    """
    从设计数据中提取响应式/多设备变体信息。

    Args:
        sketch_data: 蓝湖设计图 Sketch JSON
        design_scale: 设计稿缩放比

    Returns:
        响应式变体信息
    """
    scale = design_scale or 2.0

    def _px(val):
        if val is None:
            return 0
        return round(float(val) / scale, 1)

    # 获取画布尺寸
    artboard = sketch_data.get('artboard', {})
    board = sketch_data.get('board', {})
    board_frame = artboard.get('frame') or board or {}
    board_w = _px(board_frame.get('width', 750))
    board_h = _px(board_frame.get('height', 1334))

    device = sketch_data.get('device', '')
    name = sketch_data.get('name', '')

    # 检测设备类型
    device_type = 'unknown'
    if board_w <= 375:
        device_type = 'mobile'
    elif board_w <= 768:
        device_type = 'tablet'
    elif board_w <= 1440:
        device_type = 'desktop'
    else:
        device_type = 'wide-desktop'

    # 分析布局适配
    layout_hints = []
    layers = artboard.get('layers', []) or board.get('layers', [])

    def _analyze_layout(obj, depth=0):
        if not obj or not isinstance(obj, dict):
            return

        name = obj.get('name', '')
        frame = obj.get('frame') or obj.get('ddsOriginFrame') or {}
        w = _px(frame.get('width', obj.get('width', 0)))

        # 检测全宽元素
        if w >= board_w * 0.95:
            layout_hints.append({
                'element': name,
                'type': 'full-width',
                'width': w,
            })

        # 检测固定宽度元素
        if 200 <= w <= 400 and w < board_w * 0.8:
            layout_hints.append({
                'element': name,
                'type': 'fixed-width',
                'width': w,
            })

        for child in obj.get('layers', []):
            _analyze_layout(child, depth + 1)
        for child in obj.get('children', []):
            _analyze_layout(child, depth + 1)

    for layer in layers:
        _analyze_layout(layer)

    return {
        'device_type': device_type,
        'device_name': device,
        'canvas': {
            'width': board_w,
            'height': board_h,
            'aspect_ratio': round(board_w / board_h, 2) if board_h > 0 else 0,
        },
        'layout_hints': layout_hints[:20],
        'responsive_suggestions': _generate_responsive_suggestions(device_type, board_w, board_h),
    }


def _generate_responsive_suggestions(device_type: str, width: float, height: float) -> list:
    """生成响应式适配建议"""
    suggestions = []

    if device_type == 'mobile':
        suggestions.append('移动端设计，建议添加 tablet 和 desktop 断点')
        suggestions.append(f'建议断点: 768px (tablet), 1024px (desktop)')
    elif device_type == 'tablet':
        suggestions.append('平板设计，建议添加 mobile 和 desktop 断点')
        suggestions.append(f'建议断点: 375px (mobile), 1024px (desktop)')
    elif device_type == 'desktop':
        suggestions.append('桌面端设计，建议添加 mobile 和 tablet 断点')
        suggestions.append(f'建议断点: 375px (mobile), 768px (tablet)')

    if width >= 1440:
        suggestions.append('宽屏设计，注意内容区域不要过宽（建议 max-width: 1200px）')

    return suggestions


def format_responsive_for_ai(variants: dict) -> str:
    """
    将响应式变体格式化为AI可读的文本。

    Args:
        variants: 响应式变体数据

    Returns:
        格式化的文本
    """
    lines = ["[响应式/多设备变体]"]
    lines.append(f"设备类型: {variants.get('device_type', 'unknown')}")
    lines.append(f"设备名称: {variants.get('device_name', 'unknown')}")

    canvas = variants.get('canvas', {})
    lines.append(f"画布尺寸: {canvas.get('width', 0)} x {canvas.get('height', 0)}")
    lines.append(f"宽高比: {canvas.get('aspect_ratio', 0)}")

    hints = variants.get('layout_hints', [])
    if hints:
        lines.append(f"\n布局提示 ({len(hints)} 个):")
        for h in hints[:10]:
            lines.append(f"  - {h['element']}: {h['type']} ({h['width']}px)")

    suggestions = variants.get('responsive_suggestions', [])
    if suggestions:
        lines.append("\n响应式建议:")
        for s in suggestions:
            lines.append(f"  - {s}")

    return "\n".join(lines)
