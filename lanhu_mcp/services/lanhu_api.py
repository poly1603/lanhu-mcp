"""蓝湖 Web API 封装（请求头、用户资料、项目、设计 API）。

从 ``lanhu_mcp_gui.py`` 抽取的网络逻辑，仅依赖标准库 ``urllib``。归一化与去重等
纯逻辑放在 :mod:`lanhu_mcp.core.projects` / :mod:`lanhu_mcp.core.accounts`，本模块
依赖它们，保持 ``paths ← accounts ← projects ← lanhu_api`` 的单向依赖。

``load_projects_for_account`` 属于网络编排（合并 API + 登录缓存 + 本地缓存），
故置于本模块而非 ``projects``，避免 ``projects`` 反向依赖网络层造成循环导入。
"""
from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request

from ..core.accounts import parse_user_payload
from ..core.paths import DEFAULT_LANHU_LOGIN_URL
from ..core.projects import (
    cached_projects_for_account,
    merge_project_lists,
    normalize_project_item,
    projects_from_payload,
    read_projects_data,
    write_projects_data,
)

__all__ = [
    "PROJECT_ENDPOINTS",
    "USER_PROFILE_ENDPOINTS",
    "lanhu_api_headers",
    "fetch_lanhu_user_profile",
    "fetch_lanhu_projects",
    "load_projects_for_account",
]


PROJECT_ENDPOINTS = [
    "/api/project/team_projects",
]

USER_PROFILE_ENDPOINTS = [
    "/api/user/info",
    "/api/user/profile",
    "/api/user/current",
    "/api/user/getCurrentUser",
    "/api/user/get_current_user",
    "/api/users/current",
    "/api/member/info",
    "/api/member/current",
    "/api/account/info",
    "/api/account/profile",
    "/api/session",
]


def lanhu_api_headers(cookie: str) -> dict[str, str]:
    """生成访问蓝湖 Web API 的基础请求头。

    蓝湖 Web API 使用 HTTP Basic Auth 认证：
    Authorization: Basic base64(user_token + ":")
    其中 user_token 从 Cookie 中的 user_token 字段提取。
    """
    headers = {
        "Cookie": cookie,
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": DEFAULT_LANHU_LOGIN_URL,
        "real-path": "/item/project/all",
    }
    # 从 Cookie 中提取 user_token，构造 Basic Auth header
    token = ""
    for pair in cookie.split("; "):
        parts = pair.split("=", 1)
        if len(parts) == 2 and parts[0] == "user_token":
            token = parts[1]
            break
    if token:
        basic_auth = base64.b64encode(f"{token}:".encode()).decode()
        headers["Authorization"] = f"Basic {basic_auth}"
    return headers


def fetch_lanhu_user_profile(cookie: str) -> tuple[bool, str, dict]:
    """尝试用 Cookie 补全蓝湖账号邮箱、头像、用户名等资料。"""
    if not cookie:
        return False, "缺少蓝湖 Cookie，无法读取用户资料。", {}
    errors: list[str] = []
    for endpoint in USER_PROFILE_ENDPOINTS:
        url = f"https://lanhuapp.com{endpoint}"
        request = urllib.request.Request(url, headers=lanhu_api_headers(cookie))
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                body = response.read().decode('utf-8', errors='replace')
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            errors.append(f"{endpoint}: {error}")
            continue
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            errors.append(f"{endpoint}: 返回不是 JSON")
            continue
        user_info = parse_user_payload(payload)
        has_detail = any(
            user_info.get(key)
            for key in ("email", "mobile", "username", "avatar", "id", "name")
        )
        if has_detail:
            user_info["source_url"] = endpoint
            return True, f"已从 {endpoint} 补全账号资料", user_info
        errors.append(f"{endpoint}: 未发现用户资料字段")
    return False, "；".join(errors[-3:]) if errors else "未读取到用户资料", {}


def fetch_lanhu_projects(cookie: str) -> tuple[bool, str, list[dict]]:
    """尝试读取当前账号可访问项目列表。

    蓝湖 API 流程：
    1. GET /api/project/team_projects — 返回所有团队及其项目
    2. 数据结构: {"result": {"team_projects": [{"tid": "...", "team_name": "...", "projects": [...]}]}}
    """
    if not cookie:
        return False, "缺少蓝湖 Cookie，请先登录账号。", []
    errors: list[str] = []
    for endpoint in PROJECT_ENDPOINTS:
        url = f"https://lanhuapp.com{endpoint}"
        request = urllib.request.Request(url, headers=lanhu_api_headers(cookie))
        try:
            with urllib.request.urlopen(request, timeout=12) as response:
                body = response.read().decode('utf-8', errors='replace')
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            errors.append(f"{endpoint}: {error}")
            continue
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            errors.append(f"{endpoint}: 返回不是 JSON")
            continue
        # 蓝湖 team_projects API 返回 {"code": "00000", "result": {"team_projects": [...]}}
        # 手动从 team_projects 结构中提取项目（避免通用提取误识别 team 对象为项目）
        projects: list[dict] = []
        if isinstance(payload, dict):
            result = payload.get("result") or payload
            team_projects = result.get("team_projects") or []
            if isinstance(team_projects, list):
                for team_entry in team_projects:
                    if not isinstance(team_entry, dict):
                        continue
                    team_id = team_entry.get("tid") or team_entry.get("team_id") or ""
                    team_name = team_entry.get("team_name") or team_entry.get("name") or ""
                    for proj in (team_entry.get("projects") or []):
                        if not isinstance(proj, dict):
                            continue
                        proj_copy = dict(proj)
                        proj_copy.setdefault("team_id", team_id)
                        proj_copy.setdefault("tid", team_id)
                        normalized = normalize_project_item(proj_copy)
                        if not normalized.get("team_name"):
                            normalized["team_name"] = team_name
                        projects.append(normalized)
        # 回退到通用提取
        if not projects:
            projects = projects_from_payload(payload)
        if projects:
            return True, f"已从 {endpoint} 读取项目", projects
        errors.append(f"{endpoint}: 未发现项目字段")
    return False, "；".join(errors[-3:]) if errors else "未读取到项目", []


def load_projects_for_account(account: dict) -> tuple[bool, str, list[dict]]:
    """合并 API、登录缓存和本地保存的项目来源。"""
    account_id = str(account.get("id") or "")
    cached_projects = cached_projects_for_account(account_id)
    raw_projects = projects_from_payload(account.get("raw", {}), account_id)
    api_ok, api_message, api_projects = fetch_lanhu_projects(str(account.get("cookie") or ""))
    all_projects = merge_project_lists(cached_projects + raw_projects + api_projects)
    if all_projects:
        data = read_projects_data()
        persisted = merge_project_lists(data["projects"] + all_projects)
        data["projects"] = persisted
        write_projects_data(data)
        if api_ok:
            return True, f"{api_message}，共合并 {len(all_projects)} 个项目。", all_projects
        return True, f"已从本地缓存/登录记录合并 {len(all_projects)} 个项目；API 提示: {api_message}", all_projects
    return api_ok, api_message, api_projects


def _fetch_designs_api(cookie: str, project_id: str, team_id: str = "") -> dict:
    """调用蓝湖 API 获取设计图列表和分区信息。"""
    headers = lanhu_api_headers(cookie)
    # 获取设计图列表
    api_url = f"https://lanhuapp.com/api/project/images?project_id={project_id}"
    if team_id:
        api_url += f"&team_id={team_id}"
    api_url += "&dds_status=1&position=1&show_cb_src=1&comment=1"

    request = urllib.request.Request(api_url, headers=headers)
    with urllib.request.urlopen(request, timeout=20) as response:
        body = response.read().decode('utf-8', errors='replace')
    data = json.loads(body)

    if data.get('code') != '00000':
        return {'status': 'error', 'message': data.get('msg', 'Unknown error')}

    project_data = data.get('data', {})
    images = project_data.get('images', [])

    # 获取分区信息
    sectors = []
    image_sector_map = {}
    try:
        sector_url = f"https://lanhuapp.com/api/project/project_sectors?project_id={project_id}"
        sector_req = urllib.request.Request(sector_url, headers=headers)
        with urllib.request.urlopen(sector_req, timeout=15) as sector_resp:
            sector_body = sector_resp.read().decode('utf-8', errors='replace')
        sector_data = json.loads(sector_body)
        if sector_data.get('code') == '00000':
            raw_sectors = sector_data.get('data', {}).get('sectors', [])
            for sec in raw_sectors:
                sec_id = sec.get('id', '')
                sec_name = sec.get('name', '未分组')
                sectors.append({'id': sec_id, 'name': sec_name})
                for img_id in sec.get('images', []):
                    if img_id not in image_sector_map:
                        image_sector_map[img_id] = []
                    image_sector_map[img_id].append({'id': sec_id, 'name': sec_name})
    except Exception:
        pass

    # 组装设计图列表
    design_list = []
    for idx, img in enumerate(images, 1):
        img_id = img.get('id', '')
        design_sectors = image_sector_map.get(img_id, [])
        design_list.append({
            'index': idx,
            'id': img_id,
            'name': img.get('name', f'设计图{idx}'),
            'width': img.get('width', 0),
            'height': img.get('height', 0),
            'url': img.get('url', ''),
            'update_time': img.get('update_time', ''),
            'sectors': [s.get('name') for s in design_sectors if s.get('name')],
            'sector_ids': [s.get('id') for s in design_sectors if s.get('id')],
        })

    return {
        'status': 'success',
        'project_name': project_data.get('name', ''),
        'total_designs': len(design_list),
        'sectors': sectors,
        'designs': design_list,
    }


def _download_image_bytes(url: str, cookie: str = "") -> bytes:
    """下载图片字节。"""
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
    if cookie:
        headers["Cookie"] = cookie
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()
