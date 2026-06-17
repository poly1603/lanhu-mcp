"""设计标注/评论提取 - 获取设计图上的评论和标注信息"""
from typing import Optional, List, Dict


def extract_design_annotations(annotations_data: dict) -> dict:
    """
    从蓝湖设计图数据中提取标注和评论信息。

    Args:
        annotations_data: 蓝湖 API 返回的标注数据

    Returns:
        结构化的标注信息
    """
    if not annotations_data:
        return {'annotations': [], 'summary': {}}

    annotations = []
    resolve_status = {'open': 0, 'resolved': 0}

    for item in annotations_data if isinstance(annotations_data, list) else []:
        annotation = {
            'id': item.get('id'),
            'content': item.get('content', ''),
            'author': item.get('author_name', item.get('user_name', 'unknown')),
            'created_at': item.get('created_at', ''),
            'status': item.get('status', 'open'),
            'replies': [],
        }

        # 提取回复
        replies = item.get('replies', [])
        for reply in replies:
            annotation['replies'].append({
                'author': reply.get('author_name', reply.get('user_name', 'unknown')),
                'content': reply.get('content', ''),
                'created_at': reply.get('created_at', ''),
            })

        # 提取位置信息
        position = item.get('position', {})
        if position:
            annotation['position'] = {
                'x': position.get('x', 0),
                'y': position.get('y', 0),
                'width': position.get('width', 0),
                'height': position.get('height', 0),
            }

        # 提取标注类型
        annotation['type'] = item.get('type', 'comment')

        # 统计状态
        status = annotation['status']
        if status in resolve_status:
            resolve_status[status] += 1

        annotations.append(annotation)

    return {
        'annotations': annotations,
        'summary': {
            'total': len(annotations),
            **resolve_status,
        },
    }


def format_annotations_for_ai(annotations: list) -> str:
    """
    将标注信息格式化为AI可读的文本。

    Args:
        annotations: 标注列表

    Returns:
        格式化的文本
    """
    if not annotations:
        return "无标注信息"

    lines = ["[设计标注/评论]"]
    lines.append(f"共 {len(annotations)} 条标注\n")

    for i, ann in enumerate(annotations, 1):
        lines.append(f"--- 标注 {i} ---")
        lines.append(f"  作者: {ann.get('author', 'unknown')}")
        lines.append(f"  时间: {ann.get('created_at', 'unknown')}")
        lines.append(f"  状态: {ann.get('status', 'open')}")

        if ann.get('position'):
            pos = ann['position']
            lines.append(f"  位置: x={pos.get('x', 0)}, y={pos.get('y', 0)}")

        content = ann.get('content', '')
        if content:
            lines.append(f"  内容: {content[:500]}")

        # 显示回复
        replies = ann.get('replies', [])
        if replies:
            lines.append(f"  回复 ({len(replies)}):")
            for reply in replies[:3]:
                lines.append(f"    - {reply.get('author', 'unknown')}: {reply.get('content', '')[:200]}")

        lines.append("")

    return "\n".join(lines)
