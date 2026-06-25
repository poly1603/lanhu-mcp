"""项目数据处理（无 Tkinter / 无网络依赖）。

从 ``lanhu_mcp_gui.py`` 抽取的纯逻辑：项目缓存读写、蓝湖项目 URL 解析、字段
归一化、去重合并、登录缓存项目链接提取。网络拉取（``fetch_lanhu_projects`` /
``load_projects_for_account``）放在 :mod:`lanhu_mcp.services.lanhu_api`，以保持
``paths ← accounts ← projects`` 的单向依赖、避免循环导入。
"""
from __future__ import annotations

import json
import re
from typing import Optional
from urllib.parse import urlencode, urlparse

from .accounts import first_detail_value, merge_identity_info, parse_json_object
from .paths import DATA_DIR, PROJECTS_FILE, now_text

__all__ = [
    "PROJECT_CONTAINER_KEYS",
    "PROJECT_URL_PATTERN",
    "read_projects_data",
    "write_projects_data",
    "parse_lanhu_project_url",
    "save_manual_project",
    "cached_projects_for_account",
    "collect_dict_items",
    "collect_project_urls",
    "normalize_project_item",
    "projects_from_payload",
    "project_identity_key",
    "merge_project_lists",
]


PROJECT_CONTAINER_KEYS = (
    "project",
    "projectInfo",
    "project_info",
    "currentProject",
    "current_project",
    "projects",
    "projectList",
    "project_list",
    "items",
    "list",
    "records",
    "data",
    "result",
    "teams",
    "team",
    "workspace",
)

PROJECT_URL_PATTERN = re.compile(
    r"https?://lanhuapp\.(?:com|cn)/web/#/item/project/"
    r"(?:stage|product|detailDetach)[^\s\"'<>，。；、]*"
)


def read_projects_data() -> dict:
    """读取本地项目缓存，文件损坏时返回空结构。"""
    if not PROJECTS_FILE.exists():
        return {"projects": []}
    try:
        data = json.loads(PROJECTS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"projects": []}
    projects = data.get("projects", [])
    return {"projects": [item for item in projects if isinstance(item, dict)]}


def write_projects_data(data: dict) -> None:
    """保存本地项目缓存。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    projects = data.get("projects", [])
    PROJECTS_FILE.write_text(
        json.dumps({"projects": projects}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def parse_lanhu_project_url(project_url: str) -> Optional[dict]:
    """从蓝湖项目链接中解析 tid、pid、docId 等关键信息。"""
    text = (project_url or "").strip()
    if not text:
        return None
    matched = PROJECT_URL_PATTERN.search(text)
    normalized_url = matched.group(0) if matched else text
    if "lanhuapp." not in normalized_url or "pid=" not in normalized_url:
        return None
    parsed_url = urlparse(normalized_url)
    query_text = parsed_url.query
    if parsed_url.fragment and "?" in parsed_url.fragment:
        query_text = parsed_url.fragment.split("?", 1)[1]
    params = {}
    for part in query_text.split("&"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        params[key] = value
    project_id = params.get("pid") or params.get("project_id")
    if not project_id:
        return None
    team_id = params.get("tid") or params.get("team_id") or ""
    doc_id = params.get("docId") or params.get("doc_id") or params.get("image_id") or ""
    if "/product" in normalized_url:
        project_type = "原型"
    elif "/detailDetach" in normalized_url:
        project_type = "详情"
    else:
        project_type = "设计"
    name = f"蓝湖项目 {project_id}"
    return {
        "id": project_id,
        "team_id": team_id,
        "doc_id": doc_id,
        "name": name,
        "type": project_type,
        "updated_at": now_text(),
        "team_name": "",
        "owner_name": "",
        "url": normalized_url,
        "source": "手动链接",
    }


def save_manual_project(project_url: str, account_id: str = "") -> tuple[bool, str, Optional[dict]]:
    """保存用户手动粘贴的蓝湖项目链接。"""
    project = parse_lanhu_project_url(project_url)
    if not project:
        return False, "请输入包含 tid/pid 的蓝湖项目链接。", None
    project["account_id"] = account_id
    data = read_projects_data()
    projects = data["projects"]
    key = project.get("url") or f"{project.get('team_id')}:{project.get('id')}"
    existing = next(
        (
            item for item in projects
            if (item.get("url") or f"{item.get('team_id')}:{item.get('id')}") == key
        ),
        None,
    )
    if existing:
        existing.update(project)
    else:
        projects.append(project)
    write_projects_data(data)
    return True, "项目链接已保存到本地列表。", project


def cached_projects_for_account(account_id: str = "") -> list[dict]:
    """读取当前账号可见的本地项目缓存。"""
    projects = read_projects_data()["projects"]
    if not account_id:
        return projects
    return [
        project for project in projects
        if not project.get("account_id") or project.get("account_id") == account_id
    ]


def collect_dict_items(value: object) -> list[dict]:
    """递归收集响应中可能代表项目的字典项。"""
    items: list[dict] = []
    if isinstance(value, dict):
        has_project_marker = any(
            key in value
            for key in ("project_id", "projectId", "projectID", "pid", "id", "project")
        ) and any(
            key in value
            for key in ("name", "project_name", "projectName", "projName", "title", "displayName")
        )
        if has_project_marker:
            items.append(value)
        for key in PROJECT_CONTAINER_KEYS:
            if key in value:
                items.extend(collect_dict_items(value.get(key)))
        for nested_value in value.values():
            if isinstance(nested_value, (dict, list)):
                items.extend(collect_dict_items(nested_value))
    elif isinstance(value, list):
        for nested_value in value:
            items.extend(collect_dict_items(nested_value))
    return items


def collect_project_urls(value: object, found_urls: list[str], depth: int = 0) -> None:
    """从登录缓存或接口响应中递归提取蓝湖项目链接。"""
    if depth > 8:
        return
    parsed = parse_json_object(value)
    if isinstance(parsed, str):
        for matched in PROJECT_URL_PATTERN.findall(parsed):
            found_urls.append(matched)
        return
    if isinstance(parsed, dict):
        for item_value in parsed.values():
            collect_project_urls(item_value, found_urls, depth + 1)
        return
    if isinstance(parsed, list):
        for item_value in parsed[:100]:
            collect_project_urls(item_value, found_urls, depth + 1)


def normalize_project_item(item: dict) -> dict:
    """把蓝湖不同接口返回的项目字段统一为界面可用结构。"""
    team_payload = parse_json_object(item.get("team") or item.get("workspace") or {})
    owner_payload = parse_json_object(item.get("owner") or item.get("creator") or item.get("user") or {})
    project_id = (
        item.get("project_id")
        or item.get("projectId")
        or item.get("pid")
        or item.get("projectID")
        or item.get("project")
        or item.get("id")
        or ""
    )
    team_id = (
        item.get("team_id")
        or item.get("teamId")
        or item.get("tid")
        or (team_payload.get("id") if isinstance(team_payload, dict) else "")
        or ""
    )
    name = (
        item.get("project_name")
        or item.get("projectName")
        or item.get("projName")
        or item.get("name")
        or item.get("displayName")
        or item.get("title")
        or item.get("folder_name")
        or item.get("save_path")
        or "未命名项目"
    )
    project_type = item.get("type") or item.get("project_type") or item.get("projectType") or item.get("category") or ""
    updated_at = (
        item.get("updated_at")
        or item.get("updatedAt")
        or item.get("updatedTime")
        or item.get("modify_time")
        or item.get("modifyTime")
        or item.get("gmtModified")
        or item.get("lastUpdateTime")
        or ""
    )
    team_name = ""
    owner_name = ""
    if isinstance(team_payload, dict):
        team_name = first_detail_value(team_payload, ("name", "teamName", "title"))
    if isinstance(owner_payload, dict):
        owner_name = first_detail_value(owner_payload, ("name", "nickname", "userName", "realName"))
    url = ""
    if project_id:
        base_url = "https://lanhuapp.com/web/#/item/project/stage"
        query = {"pid": project_id}
        if team_id:
            query["tid"] = team_id
        url = f"{base_url}?{urlencode(query)}"
    return {
        "id": str(project_id),
        "team_id": str(team_id),
        "name": str(name),
        "type": str(project_type) if project_type else "项目",
        "updated_at": str(updated_at) if updated_at else "",
        "team_name": team_name,
        "owner_name": owner_name,
        "url": url,
        "source": str(item.get("source") or "蓝湖接口"),
        "raw": item,
    }


def projects_from_payload(payload: object, account_id: str = "") -> list[dict]:
    """从登录缓存或接口响应里提取项目对象和项目链接。"""
    projects = [
        normalize_project_item(item)
        for item in collect_dict_items(payload)
    ]
    found_urls: list[str] = []
    collect_project_urls(payload, found_urls)
    for project_url in found_urls:
        parsed_project = parse_lanhu_project_url(project_url)
        if parsed_project:
            parsed_project["source"] = "登录缓存"
            projects.append(parsed_project)
    normalized_projects = merge_project_lists(projects)
    for project in normalized_projects:
        if account_id and not project.get("account_id"):
            project["account_id"] = account_id
    return normalized_projects


def project_identity_key(project: dict) -> str:
    """生成项目稳定身份键，优先按团队和项目 ID 去重。"""
    project_id = str(project.get("id") or project.get("project_id") or "").strip()
    team_id = str(project.get("team_id") or project.get("tid") or "").strip()
    if project_id:
        return f"project:{team_id}:{project_id}"
    project_url = str(project.get("url") or "").strip()
    if project_url:
        parsed_project = parse_lanhu_project_url(project_url)
        if parsed_project and parsed_project.get("id"):
            return f"project:{parsed_project.get('team_id') or ''}:{parsed_project.get('id')}"
        return f"url:{project_url}"
    project_name = str(project.get("name") or "").strip()
    if project_name:
        return f"name:{team_id}:{project_name}"
    return ""


def merge_project_lists(projects: list[dict]) -> list[dict]:
    """按项目链接或 pid/tid 合并项目列表。"""
    unique_projects: dict[str, dict] = {}
    for project in projects:
        if not project:
            continue
        key = project_identity_key(project)
        if not key:
            continue
        if key in unique_projects:
            unique_projects[key] = merge_identity_info(project, unique_projects[key])
        else:
            unique_projects[key] = dict(project)
    return list(unique_projects.values())
