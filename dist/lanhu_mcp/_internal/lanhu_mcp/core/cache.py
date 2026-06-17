"""缓存管理 - 基于版本号的元数据缓存"""
from typing import Optional

from .config import _metadata_cache


def _get_metadata_cache_key(project_id: str, doc_id: str = None) -> str:
    """生成元数据缓存键"""
    if doc_id:
        return f"{project_id}_{doc_id}"
    return project_id


def _get_cached_metadata(cache_key: str, version_id: str = None) -> Optional[dict]:
    """获取缓存的元数据"""
    if cache_key in _metadata_cache:
        cache_entry = _metadata_cache[cache_key]
        if version_id:
            if cache_entry.get('version_id') == version_id:
                return cache_entry['data']
            else:
                del _metadata_cache[cache_key]
                return None
        return cache_entry['data']
    return None


def _set_cached_metadata(cache_key: str, metadata: dict, version_id: str = None):
    """设置缓存（基于版本号的永久缓存）"""
    _metadata_cache[cache_key] = {
        'data': metadata.copy(),
        'version_id': version_id
    }
