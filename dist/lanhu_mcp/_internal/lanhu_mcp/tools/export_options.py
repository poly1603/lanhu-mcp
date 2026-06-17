"""导出选项 - 设计图导出格式和配置"""
from typing import Optional, List, Dict


def get_export_options(slices_data: dict) -> dict:
    """
    获取设计图的导出选项和配置。

    Args:
        slices_data: 切图数据

    Returns:
        导出选项信息
    """
    slices = slices_data.get('slices', [])

    # 分析可用的导出格式
    formats = set()
    for s in slices:
        fmt = s.get('format', 'png')
        formats.add(fmt)

    # 分析可用的倍率
    scales = set()
    for s in slices:
        scale_urls = s.get('scale_urls', {})
        scales.update(scale_urls.keys())

    # 分析尺寸范围
    sizes = []
    for s in slices:
        size_str = s.get('size', '0x0')
        parts = size_str.split('x')
        if len(parts) == 2:
            try:
                w, h = int(parts[0]), int(parts[1])
                sizes.append({'width': w, 'height': h, 'name': s.get('name', '')})
            except ValueError:
                pass

    size_range = {}
    if sizes:
        widths = [s['width'] for s in sizes]
        heights = [s['height'] for s in sizes]
        size_range = {
            'min_width': min(widths),
            'max_width': max(widths),
            'min_height': min(heights),
            'max_height': max(heights),
        }

    return {
        'available_formats': list(formats),
        'available_scales': sorted(scales),
        'total_slices': len(slices),
        'size_range': size_range,
        'export_recommendations': {
            'web': '2x (Retina)',
            'ios': '3x',
            'android': 'xxhdpi',
        },
    }


def format_export_options_for_ai(options: dict) -> str:
    """
    将导出选项格式化为AI可读的文本。

    Args:
        options: 导出选项数据

    Returns:
        格式化的文本
    """
    lines = ["[导出选项]"]
    lines.append(f"切图总数: {options.get('total_slices', 0)}")
    lines.append(f"可用格式: {', '.join(options.get('available_formats', []))}")
    lines.append(f"可用倍率: {', '.join(options.get('available_scales', []))}")

    size_range = options.get('size_range', {})
    if size_range:
        lines.append(f"尺寸范围: {size_range.get('min_width', 0)}x{size_range.get('min_height', 0)} ~ {size_range.get('max_width', 0)}x{size_range.get('max_height', 0)}")

    recs = options.get('export_recommendations', {})
    if recs:
        lines.append("\n推荐导出配置:")
        for platform, scale in recs.items():
            lines.append(f"  {platform}: {scale}")

    return "\n".join(lines)
