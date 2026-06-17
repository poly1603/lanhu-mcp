"""用户信息管理 - 角色归一化、用户识别"""
import os
from typing import Tuple

from .config import VALID_ROLES, ROLE_MAPPING_RULES


def normalize_role(role: str) -> str:
    """将用户角色归一化到标准角色组"""
    if not role:
        return "未知"

    role_lower = role.lower()

    if role in VALID_ROLES:
        return role

    for keywords, standard_role in ROLE_MAPPING_RULES:
        for keyword in keywords:
            if keyword.lower() in role_lower:
                return standard_role

    return role


def get_user_info(ctx) -> Tuple[str, str]:
    """
    从URL query参数获取用户信息

    MCP连接URL格式：http://xxx:port/mcp?role=后端&name=张三
    stdio模式可通过 LANHU_USER_NAME 和 LANHU_USER_ROLE 环境变量获取
    """
    try:
        from fastmcp.server.dependencies import get_http_request
        req = get_http_request()
        name = req.query_params.get('name', '匿名')
        role = req.query_params.get('role', '未知')
        return name, role
    except Exception:
        pass
    return os.getenv('LANHU_USER_NAME', '匿名'), os.getenv('LANHU_USER_ROLE', '未知')


def get_project_id_from_url(url: str) -> str:
    """从URL中提取project_id"""
    if not url or url.lower() == 'all':
        return None
    from .extractor import LanhuExtractor
    extractor = LanhuExtractor()
    try:
        params = extractor.parse_url(url)
        return params.get('project_id', '')
    finally:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    pool.submit(lambda: asyncio.run(extractor.close()))
            else:
                loop.run_until_complete(extractor.close())
        except Exception:
            pass
