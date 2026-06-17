"""布局规格提取 - 从设计稿中提取精确的元素位置、尺寸和布局关系"""
import math
from typing import Optional, List, Dict


def extract_layout_spec(sketch_data: dict, design_scale: float = 2.0, max_depth: int = 0) -> dict:
    """
    从 Sketch JSON 中提取详细布局规格。

    Args:
        sketch_data: 蓝湖设计图 Sketch JSON
        design_scale: 设计稿缩放比
        max_depth: 提取深度（0=全部）

    Returns:
        包含 canvas, layout_tree, measurements 的布局规格
    """
    scale = design_scale or 2.0

    def _px(val):
        if val is None:
            return 0
        return round(float(val) / scale, 1)

    def _get_frame(obj: dict) -> dict:
        """获取元素的 frame（兼容多种格式）"""
        frame = obj.get('frame') or obj.get('ddsOriginFrame') or obj.get('layerOriginFrame') or {}
        x = _px(frame.get('x', frame.get('left', obj.get('left', 0))))
        y = _px(frame.get('y', frame.get('top', obj.get('top', 0))))
        w = _px(frame.get('width', obj.get('width', 0)))
        h = _px(frame.get('height', obj.get('height', 0)))
        return {'x': x, 'y': y, 'width': w, 'height': h}

    def _detect_layout_type(children: list) -> dict:
        """检测子元素的布局类型（flex-row / flex-column / absolute）"""
        if not children or len(children) < 2:
            return {'type': 'none'}

        frames = []
        for c in children:
            f = _get_frame(c)
            if f['width'] > 0 and f['height'] > 0:
                frames.append(f)

        if len(frames) < 2:
            return {'type': 'none'}

        # 检测是否水平排列
        same_row = all(
            abs(f1['y'] - f2['y']) < 5 or
            abs(f1['y'] + f1['height']/2 - f2['y'] - f2['height']/2) < 5
            for f1 in frames for f2 in frames
        )

        # 检测是否垂直排列
        same_col = all(
            abs(f1['x'] - f2['x']) < 5 or
            abs(f1['x'] + f1['width']/2 - f2['x'] - f2['width']/2) < 5
            for f1 in frames for f2 in frames
        )

        if same_row and not same_col:
            # 水平排列，检测间距
            sorted_frames = sorted(frames, key=lambda f: f['x'])
            gaps = []
            for i in range(1, len(sorted_frames)):
                gap = sorted_frames[i]['x'] - (sorted_frames[i-1]['x'] + sorted_frames[i-1]['width'])
                if gap > 0:
                    gaps.append(round(gap, 1))
            avg_gap = round(sum(gaps) / len(gaps), 1) if gaps else 0

            return {
                'type': 'flex-row',
                'justify': 'space-between' if avg_gap > 20 else 'flex-start',
                'gap': avg_gap,
                'child_count': len(frames),
            }

        if same_col and not same_row:
            # 垂直排列
            sorted_frames = sorted(frames, key=lambda f: f['y'])
            gaps = []
            for i in range(1, len(sorted_frames)):
                gap = sorted_frames[i]['y'] - (sorted_frames[i-1]['y'] + sorted_frames[i-1]['height'])
                if gap > 0:
                    gaps.append(round(gap, 1))
            avg_gap = round(sum(gaps) / len(gaps), 1) if gaps else 0

            return {
                'type': 'flex-column',
                'justify': 'space-between' if avg_gap > 20 else 'flex-start',
                'gap': avg_gap,
                'child_count': len(frames),
            }

        return {'type': 'absolute', 'child_count': len(frames)}

    def _walk(obj: dict, depth: int = 0, parent_path: str = "") -> Optional[dict]:
        if not obj or not isinstance(obj, dict):
            return None

        name = obj.get('name', '?')
        current_path = f"{parent_path}/{name}" if parent_path else name
        frame = _get_frame(obj)

        # 跳过不可见或无尺寸的元素
        if not obj.get('isVisible', True) and obj.get('isVisible') is not None:
            return None
        if frame['width'] < 1 and frame['height'] < 1:
            return None

        node_type = 'element'
        node_props = obj.get('props', {})
        style = {**obj.get('style', {}), **node_props.get('style', {})}
        if style.get('display') == 'flex' or style.get('flexDirection'):
            node_type = 'flex-container'

        children_raw = obj.get('layers', []) or obj.get('children', [])
        children = []
        for c in children_raw:
            child = _walk(c, depth + 1, current_path)
            if child:
                children.append(child)

        # 检测子元素布局
        layout_info = _detect_layout_type(children_raw)

        node = {
            'name': name,
            'path': current_path,
            'type': node_type,
            'position': {'x': frame['x'], 'y': frame['y']},
            'size': {'width': frame['width'], 'height': frame['height']},
        }

        if layout_info['type'] != 'none':
            node['layout'] = layout_info['type']
            if 'gap' in layout_info:
                node['gap'] = layout_info['gap']
            if 'justify' in layout_info:
                node['justify'] = layout_info['justify']

        # 提取 padding/margin
        pt = style.get('paddingTop', 0) or 0
        pr = style.get('paddingRight', 0) or 0
        pb = style.get('paddingBottom', 0) or 0
        pl = style.get('paddingLeft', 0) or 0
        if pt or pr or pb or pl:
            node['padding'] = {'top': _px(pt), 'right': _px(pr), 'bottom': _px(pb), 'left': _px(pl)}

        mt = style.get('marginTop', 0) or 0
        mr = style.get('marginRight', 0) or 0
        mb = style.get('marginBottom', 0) or 0
        ml = style.get('marginLeft', 0) or 0
        if mt or mr or mb or ml:
            node['margin'] = {'top': _px(mt), 'right': _px(mr), 'bottom': _px(mb), 'left': _px(ml)}

        if children:
            node['children'] = children

        return node

    # 获取画布信息
    board_w, board_h = 375, 812
    device = sketch_data.get('device', '')

    artboard = sketch_data.get('artboard', {})
    board_frame = artboard.get('frame') or artboard.get('realFrame') or {}
    if board_frame:
        board_w = _px(board_frame.get('width', 750))
        board_h = _px(board_frame.get('height', 1334))

    board = sketch_data.get('board', {})
    if board:
        board_w = _px(board.get('width', 750))
        board_h = _px(board.get('height', 1334))

    # 构建布局树
    layout_tree = None
    raw_layers = artboard.get('layers', []) or board.get('layers', [])
    if raw_layers:
        # 合并所有顶层图层为一个根节点
        children = []
        for layer in raw_layers:
            child = _walk(layer, 0)
            if child:
                children.append(child)

        layout_tree = {
            'name': sketch_data.get('name', '设计图'),
            'type': 'root',
            'position': {'x': 0, 'y': 0},
            'size': {'width': board_w, 'height': board_h},
            'children': children,
        }

    # 提取间距测量
    measurements = []

    def _collect_measurements(node: dict, results: list):
        if not node:
            return
        children = node.get('children', [])
        for i in range(len(children)):
            for j in range(i + 1, len(children)):
                c1 = children[i]
                c2 = children[j]
                # 计算水平间距
                h_gap = c2['position']['x'] - (c1['position']['x'] + c1['size']['width'])
                # 计算垂直间距
                v_gap = c2['position']['y'] - (c1['position']['y'] + c1['size']['height'])

                if 0 < h_gap < 100:
                    results.append({
                        'from': c1['name'],
                        'to': c2['name'],
                        'gap': round(h_gap, 1),
                        'direction': 'horizontal'
                    })
                if 0 < v_gap < 100:
                    results.append({
                        'from': c1['name'],
                        'to': c2['name'],
                        'gap': round(v_gap, 1),
                        'direction': 'vertical'
                    })

            _collect_measurements(children[i], results)

    _collect_measurements(layout_tree, measurements)

    return {
        'canvas': {
            'width': board_w,
            'height': board_h,
            'device': device,
        },
        'layout_tree': layout_tree,
        'measurements': measurements[:50],
    }
