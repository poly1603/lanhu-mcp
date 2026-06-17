"""版本历史 - 获取设计图的版本演进"""
from typing import Optional, List, Dict


def extract_version_history(versions_data: list) -> dict:
    """
    从蓝湖 API 返回的版本数据中提取版本历史。

    Args:
        versions_data: 版本列表

    Returns:
        版本历史信息
    """
    if not versions_data:
        return {'versions': [], 'summary': {}}

    versions = []
    for v in versions_data:
        version = {
            'id': v.get('id'),
            'version_info': v.get('version_info', ''),
            'created_at': v.get('created_at', ''),
            'updated_at': v.get('updated_at', ''),
            'author': v.get('author_name', v.get('user_name', 'unknown')),
            'description': v.get('description', ''),
            'json_url': v.get('json_url', ''),
            'has_changes': v.get('has_changes', False),
        }
        versions.append(version)

    return {
        'versions': versions,
        'summary': {
            'total_versions': len(versions),
            'latest_version': versions[0]['version_info'] if versions else 'unknown',
            'oldest_version': versions[-1]['version_info'] if versions else 'unknown',
        },
    }


def format_version_history_for_ai(history: dict) -> str:
    """
    将版本历史格式化为AI可读的文本。

    Args:
        history: 版本历史数据

    Returns:
        格式化的文本
    """
    versions = history.get('versions', [])
    if not versions:
        return "无版本历史"

    lines = ["[设计版本历史]"]
    summary = history.get('summary', {})
    lines.append(f"总版本数: {summary.get('total_versions', 0)}")
    lines.append(f"最新版本: {summary.get('latest_version', 'unknown')}")
    lines.append(f"最早版本: {summary.get('oldest_version', 'unknown')}")
    lines.append("")

    for i, v in enumerate(versions[:10], 1):
        lines.append(f"--- 版本 {i} ---")
        lines.append(f"  版本号: {v.get('version_info', 'unknown')}")
        lines.append(f"  作者: {v.get('author', 'unknown')}")
        lines.append(f"  更新时间: {v.get('updated_at', v.get('created_at', 'unknown'))}")
        if v.get('description'):
            lines.append(f"  描述: {v['description']}")
        lines.append("")

    return "\n".join(lines)
