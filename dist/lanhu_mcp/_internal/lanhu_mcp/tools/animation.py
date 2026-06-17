"""动效规格提取 - 从设计稿中提取过渡/动画时间参数"""
from typing import Optional, List, Dict


def extract_animation_specs(sketch_data: dict, design_scale: float = 2.0) -> dict:
    """
    从设计数据中提取动效/过渡规格。

    Args:
        sketch_data: 蓝湖设计图 Sketch JSON
        design_scale: 设计稿缩放比

    Returns:
        动效规格信息
    """
    animations = []
    transitions = []

    # 提取动画信息
    def _walk(obj, parent_path=""):
        if not obj or not isinstance(obj, dict):
            return

        name = obj.get('name', '')
        current_path = f"{parent_path}/{name}" if parent_path else name

        # 检查动画属性
        animation = obj.get('animation', {})
        if animation:
            animations.append({
                'name': name,
                'path': current_path,
                'type': animation.get('type', 'unknown'),
                'duration': animation.get('duration', 0),
                'delay': animation.get('delay', 0),
                'easing': animation.get('easing', 'ease'),
            })

        # 检查过渡属性
        transition = obj.get('transition', {})
        if transition:
            transitions.append({
                'name': name,
                'path': current_path,
                'property': transition.get('property', 'all'),
                'duration': transition.get('duration', 0),
                'delay': transition.get('delay', 0),
                'easing': transition.get('easing', 'ease'),
            })

        # 递归
        for child in obj.get('layers', []):
            _walk(child, current_path)
        for child in obj.get('children', []):
            _walk(child, current_path)

    # 遍历
    artboard = sketch_data.get('artboard', {})
    board = sketch_data.get('board', {})
    layers = artboard.get('layers', []) or board.get('layers', [])

    for layer in layers:
        _walk(layer)

    return {
        'animations': animations,
        'transitions': transitions,
        'summary': {
            'total_animations': len(animations),
            'total_transitions': len(transitions),
        },
    }


def format_animation_specs_for_ai(specs: dict) -> str:
    """
    将动效规格格式化为AI可读的文本。

    Args:
        specs: 动效规格数据

    Returns:
        格式化的文本
    """
    animations = specs.get('animations', [])
    transitions = specs.get('transitions', [])

    if not animations and not transitions:
        return "无动效规格数据"

    lines = ["[动效/过渡规格]"]
    summary = specs.get('summary', {})
    lines.append(f"动画: {summary.get('total_animations', 0)} 个")
    lines.append(f"过渡: {summary.get('total_transitions', 0)} 个\n")

    if animations:
        lines.append("--- 动画 ---")
        for a in animations[:10]:
            lines.append(f"  {a['name']}:")
            lines.append(f"    类型: {a['type']}")
            lines.append(f"    时长: {a['duration']}ms")
            if a['delay'] > 0:
                lines.append(f"    延迟: {a['delay']}ms")
            lines.append(f"    缓动: {a['easing']}")

    if transitions:
        lines.append("\n--- 过渡 ---")
        for t in transitions[:10]:
            lines.append(f"  {t['name']}:")
            lines.append(f"    属性: {t['property']}")
            lines.append(f"    时长: {t['duration']}ms")
            if t['delay'] > 0:
                lines.append(f"    延迟: {t['delay']}ms")
            lines.append(f"    缓动: {t['easing']}")

    return "\n".join(lines)
