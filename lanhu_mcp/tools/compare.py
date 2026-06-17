"""设计对比/变更追踪 - 对比两个设计版本的差异"""
from typing import Optional, List, Dict


def compare_design_versions(
    sketch_data_a: dict,
    sketch_data_b: dict,
    design_scale: float = 2.0,
) -> dict:
    """
    对比两个设计版本的差异。

    Args:
        sketch_data_a: 版本A的 Sketch JSON
        sketch_data_b: 版本B的 Sketch JSON
        design_scale: 设计稿缩放比

    Returns:
        包含 summary 和 changes 的对比结果
    """
    scale = design_scale or 2.0

    def _px(val):
        if val is None:
            return 0
        return round(float(val) / scale, 1)

    def _get_frame(obj: dict) -> dict:
        frame = obj.get('frame') or obj.get('ddsOriginFrame') or {}
        return {
            'x': _px(frame.get('x', obj.get('left', 0))),
            'y': _px(frame.get('y', obj.get('top', 0))),
            'width': _px(frame.get('width', obj.get('width', 0))),
            'height': _px(frame.get('height', obj.get('height', 0))),
        }

    def _color_str(color: dict) -> str:
        if not color:
            return None
        if 'value' in color:
            return color['value']
        r = round(color.get('red', color.get('r', 0)))
        g = round(color.get('green', color.get('g', 0)))
        b = round(color.get('blue', color.get('b', 0)))
        return f"rgb({r},{g},{b})"

    def _build_layer_index(sketch_data: dict) -> Dict[str, dict]:
        """构建图层索引：path → layer_info"""
        index = {}

        def _walk(obj, parent_path=""):
            if not obj or not isinstance(obj, dict):
                return
            name = obj.get('name', '')
            if not name:
                return
            current_path = f"{parent_path}/{name}" if parent_path else name

            frame = _get_frame(obj)
            text = ''
            text_info = obj.get('textInfo', {})
            if text_info:
                text = text_info.get('text', '')

            fills = obj.get('fills', [])
            fill_color = None
            for f in fills:
                if f.get('isEnabled', True) and f.get('fillType', 0) == 0:
                    fill_color = _color_str(f.get('color', {}))
                    break

            text_color = None
            if text_info:
                tc = text_info.get('color', {})
                text_color = _color_str(tc)

            font_size = text_info.get('size', 0)

            index[current_path] = {
                'name': name,
                'path': current_path,
                'frame': frame,
                'text': text,
                'text_color': text_color,
                'font_size': _px(font_size) if font_size else None,
                'fill_color': fill_color,
            }

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

        return index

    # 构建两个版本的图层索引
    index_a = _build_layer_index(sketch_data_a)
    index_b = _build_layer_index(sketch_data_b)

    paths_a = set(index_a.keys())
    paths_b = set(index_b.keys())

    added_paths = paths_b - paths_a
    removed_paths = paths_a - paths_b
    common_paths = paths_a & paths_b

    changes = []

    # 新增的元素
    for path in sorted(added_paths):
        info = index_b[path]
        changes.append({
            'type': 'added',
            'element': info['name'],
            'path': path,
            'position': info['frame'],
        })

    # 删除的元素
    for path in sorted(removed_paths):
        info = index_a[path]
        changes.append({
            'type': 'removed',
            'element': info['name'],
            'path': path,
            'position': info['frame'],
        })

    # 修改的元素
    for path in sorted(common_paths):
        a = index_a[path]
        b = index_b[path]
        diffs = []

        # 检查位置变化
        if a['frame'] != b['frame']:
            pos_before = a['frame']
            pos_after = b['frame']
            if pos_before['x'] != pos_after['x'] or pos_before['y'] != pos_after['y']:
                diffs.append({
                    'field': 'position',
                    'before': {'x': pos_before['x'], 'y': pos_before['y']},
                    'after': {'x': pos_after['x'], 'y': pos_after['y']},
                })
            if pos_before['width'] != pos_after['width'] or pos_before['height'] != pos_after['height']:
                diffs.append({
                    'field': 'size',
                    'before': {'width': pos_before['width'], 'height': pos_before['height']},
                    'after': {'width': pos_after['width'], 'height': pos_after['height']},
                })

        # 检查文字内容变化
        if a.get('text') != b.get('text') and (a.get('text') or b.get('text')):
            diffs.append({
                'field': 'text',
                'before': a.get('text', ''),
                'after': b.get('text', ''),
            })

        # 检查文字颜色变化
        if a.get('text_color') != b.get('text_color'):
            diffs.append({
                'field': 'text_color',
                'before': a.get('text_color'),
                'after': b.get('text_color'),
            })

        # 检查字号变化
        if a.get('font_size') != b.get('font_size'):
            diffs.append({
                'field': 'font_size',
                'before': a.get('font_size'),
                'after': b.get('font_size'),
            })

        # 检查填充色变化
        if a.get('fill_color') != b.get('fill_color'):
            diffs.append({
                'field': 'fill_color',
                'before': a.get('fill_color'),
                'after': b.get('fill_color'),
            })

        if diffs:
            changes.append({
                'type': 'modified',
                'element': a['name'],
                'path': path,
                'diffs': diffs,
            })

    # 统计
    added = sum(1 for c in changes if c['type'] == 'added')
    removed = sum(1 for c in changes if c['type'] == 'removed')
    modified = sum(1 for c in changes if c['type'] == 'modified')

    return {
        'summary': {
            'total_changes': len(changes),
            'added': added,
            'removed': removed,
            'modified': modified,
        },
        'changes': changes,
    }
