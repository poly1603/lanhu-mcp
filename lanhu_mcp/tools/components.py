"""组件模式识别 - 自动识别设计稿中的可复用组件"""
from collections import Counter, defaultdict
from typing import Optional


def extract_component_patterns(sketch_data: dict, design_scale: float = 2.0) -> dict:
    """
    从 Sketch JSON 中识别可复用的组件模式。

    Args:
        sketch_data: 蓝湖设计图 Sketch JSON
        design_scale: 设计稿缩放比

    Returns:
        识别出的组件模式列表
    """
    scale = design_scale or 2.0

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

    def _get_frame(obj: dict) -> dict:
        frame = obj.get('frame') or obj.get('ddsOriginFrame') or obj.get('layerOriginFrame') or {}
        return {
            'x': _px(frame.get('x', obj.get('left', 0))),
            'y': _px(frame.get('y', obj.get('top', 0))),
            'width': _px(frame.get('width', obj.get('width', 0))),
            'height': _px(frame.get('height', obj.get('height', 0))),
        }

    def _extract_fills(obj: dict) -> list:
        fills = obj.get('fills', [])
        result = []
        for f in fills:
            if not f.get('isEnabled', True):
                continue
            fill_type = f.get('fillType', 0)
            if fill_type == 0:
                color = _color_str(f.get('color', {}))
                if color:
                    result.append({'type': 'solid', 'color': color})
            elif fill_type == 1:
                gradient = f.get('gradient', {})
                stops = gradient.get('colorStops', [])
                colors = [_color_str(s.get('color', {})) for s in stops]
                result.append({'type': 'gradient', 'colors': [c for c in colors if c]})
        return result

    def _extract_border(obj: dict) -> Optional[dict]:
        borders = obj.get('borders', [])
        for b in borders:
            if not b.get('isEnabled', True):
                continue
            return {
                'width': b.get('thickness', 1),
                'color': _color_str(b.get('color', {})),
            }
        return None

    def _extract_radius(obj: dict) -> Optional[float]:
        radius = obj.get('radius')
        if radius:
            if isinstance(radius, list):
                if len(set(radius)) == 1:
                    return _px(radius[0])
                return _px(radius[0])
            return _px(radius)
        return None

    def _extract_text_style(obj: dict) -> Optional[dict]:
        text_info = obj.get('textInfo', {})
        art_text = obj.get('text', {})
        if isinstance(art_text, dict) and art_text.get('style'):
            text_info = art_text

        if not text_info:
            return None

        font_size = text_info.get('size', 0)
        if isinstance(art_text, dict):
            font_size = art_text.get('style', {}).get('font', {}).get('size', 0)

        color = text_info.get('color', {})
        if isinstance(art_text, dict):
            color = art_text.get('style', {}).get('color', {})

        bold = text_info.get('bold', False)
        if isinstance(art_text, dict):
            fw = art_text.get('style', {}).get('font', {}).get('fontWeight', 0)
            bold = fw >= 600

        return {
            'font_size': _px(font_size),
            'color': _color_str(color),
            'font_weight': 'bold' if bold else 'normal',
        }

    # 组件候选列表
    candidates = []

    def _walk(obj: dict, parent_name: str = "", parent_path: str = ""):
        if not obj or not isinstance(obj, dict):
            return

        name = obj.get('name', '')
        current_path = f"{parent_path}/{name}" if parent_path else name
        frame = _get_frame(obj)

        # 分析元素特征
        fills = _extract_fills(obj)
        border = _extract_border(obj)
        radius = _extract_radius(obj)
        text_style = _extract_text_style(obj)

        # 识别按钮模式：有背景色+圆角+文字
        is_button = False
        button_features = []
        if fills and radius and radius > 2:
            button_features.append('filled+rounded')
        if border and border.get('width', 0) > 0 and radius and radius > 2:
            button_features.append('bordered+rounded')
        if text_style:
            button_features.append('has-text')
            if frame['height'] >= 28 and frame['height'] <= 60:
                button_features.append('button-height')

        if len(button_features) >= 2:
            is_button = True

        # 识别卡片模式：有背景/边框+圆角+较大尺寸
        is_card = False
        if frame['width'] > 100 and frame['height'] > 80:
            if fills or border:
                if radius and radius > 4:
                    is_card = True

        # 识别输入框模式：有边框+固定高度
        is_input = False
        if border and 28 <= frame['height'] <= 50 and frame['width'] > 80:
            is_input = True

        # 识别头像模式：正方形+圆角或圆形
        is_avatar = False
        if abs(frame['width'] - frame['height']) < 5 and frame['width'] > 10:
            if radius and radius >= frame['width'] / 2:
                is_avatar = True

        # 识别标签/徽章模式：小尺寸+圆角
        is_badge = False
        if frame['width'] < 120 and frame['height'] < 30 and radius and radius > 2:
            is_badge = True

        # 识别图标模式：小正方形
        is_icon = False
        if 8 <= frame['width'] <= 64 and abs(frame['width'] - frame['height']) < 5:
            if not text_style:
                is_icon = True

        # 收集组件特征
        component_type = None
        features = {}

        if is_button:
            component_type = 'button'
            features = {
                'size': {'width': frame['width'], 'height': frame['height']},
                'border_radius': radius,
                'fills': fills[:2],
                'border': border,
                'text_style': text_style,
            }
        elif is_card:
            component_type = 'card'
            features = {
                'size': {'width': frame['width'], 'height': frame['height']},
                'border_radius': radius,
                'fills': fills[:2],
                'border': border,
            }
        elif is_input:
            component_type = 'input'
            features = {
                'size': {'width': frame['width'], 'height': frame['height']},
                'border_radius': radius,
                'border': border,
            }
        elif is_avatar:
            component_type = 'avatar'
            features = {
                'size': {'width': frame['width'], 'height': frame['height']},
                'border_radius': radius,
                'fills': fills[:1],
            }
        elif is_badge:
            component_type = 'badge'
            features = {
                'size': {'width': frame['width'], 'height': frame['height']},
                'border_radius': radius,
                'fills': fills[:1],
                'text_style': text_style,
            }
        elif is_icon:
            component_type = 'icon'
            features = {
                'size': {'width': frame['width'], 'height': frame['height']},
                'fills': fills[:1],
            }

        if component_type:
            candidates.append({
                'type': component_type,
                'name': name,
                'path': current_path,
                'features': features,
            })

        # 递归子图层
        for child in obj.get('layers', []):
            _walk(child, name, current_path)
        for child in obj.get('children', []):
            _walk(child, name, current_path)

    # 遍历所有图层
    if sketch_data.get('artboard') and sketch_data['artboard'].get('layers'):
        for layer in sketch_data['artboard']['layers']:
            _walk(layer)
    elif sketch_data.get('board') and sketch_data['board'].get('layers'):
        for layer in sketch_data['board']['layers']:
            _walk(layer)
    elif sketch_data.get('info'):
        for item in sketch_data['info']:
            _walk(item)

    # 聚类相似组件
    patterns = defaultdict(list)
    for c in candidates:
        patterns[c['type']].append(c)

    # 构建输出
    result_patterns = []
    for comp_type, instances in patterns.items():
        # 按尺寸分组
        size_groups = defaultdict(list)
        for inst in instances:
            size = inst['features'].get('size', {})
            size_key = f"{size.get('width', 0)}x{size.get('height', 0)}"
            size_groups[size_key].append(inst)

        variants = []
        for size_key, group in size_groups.items():
            representative = group[0]['features']
            variants.append({
                'name': f"{comp_type}_{size_key}",
                'instance_count': len(group),
                'spec': representative,
            })

        result_patterns.append({
            'type': comp_type,
            'name': f"{'主要' if comp_type == 'button' else ''}{comp_type}",
            'total_instances': len(instances),
            'variants': variants,
        })

    total_instances = sum(p['total_instances'] for p in result_patterns)

    return {
        'patterns': result_patterns,
        'summary': {
            'total_patterns': len(result_patterns),
            'total_instances': total_instances,
            'types': [p['type'] for p in result_patterns],
        },
    }
