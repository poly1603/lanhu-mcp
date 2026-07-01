"""Project-scoped collaboration message storage for Lanhu MCP.

Extracted from the legacy monolithic ``lanhu_mcp_server.py`` so message-board
state management can be tested and evolved independently from MCP tool wiring.
"""
from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

__all__ = [
    "CHINA_TZ",
    "DATA_DIR",
    "VALID_ROLES",
    "ROLE_MAPPING_RULES",
    "normalize_role",
    "clean_message_dict",
    "MessageStore",
]

CHINA_TZ = timezone(timedelta(hours=8))
DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

VALID_ROLES = ["后端", "前端", "客户端", "开发", "运维", "产品", "项目经理"]

# 角色映射规则（按优先级排序，越具体的越靠前）
ROLE_MAPPING_RULES: list[tuple[list[str], str]] = [
    (["后端", "backend", "服务端", "server", "java", "php", "python", "go", "golang", "node", "nodejs", ".net", "c#"], "后端"),
    (["前端", "frontend", "h5", "web", "vue", "react", "angular", "javascript", "js", "ts", "typescript", "css"], "前端"),
    (["客户端", "client", "ios", "android", "安卓", "移动端", "mobile", "app", "flutter", "rn", "react native", "swift", "kotlin", "objective-c", "oc"], "客户端"),
    (["运维", "ops", "devops", "sre", "dba", "运营维护", "系统管理", "infra", "infrastructure"], "运维"),
    (["产品", "product", "pm", "产品经理", "需求"], "产品"),
    (["项目经理", "项目", "pmo", "project manager", "scrum", "敏捷"], "项目经理"),
    (["开发", "dev", "developer", "程序员", "coder", "engineer", "工程师"], "开发"),
]


def normalize_role(role: str) -> str:
    """将用户角色归一化到标准角色组。"""
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


def clean_message_dict(msg: dict[str, Any], current_user_name: Optional[str] = None) -> dict[str, Any]:
    """清理消息字典，移除未编辑消息的空更新字段并添加快捷标志。"""
    cleaned = msg.copy()
    if cleaned.get("updated_at") is None:
        cleaned.pop("updated_at", None)
        cleaned.pop("updated_by_name", None)
        cleaned.pop("updated_by_role", None)
        cleaned["is_edited"] = False
    else:
        cleaned["is_edited"] = True
    if current_user_name:
        cleaned["is_mine"] = cleaned.get("author_name") == current_user_name
    return cleaned


class MessageStore:
    """消息存储管理类 - 支持团队留言板功能。"""

    def __init__(self, project_id: Optional[str] = None) -> None:
        self.project_id = project_id
        self.storage_dir = DATA_DIR / "messages"
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        if project_id:
            self.file_path = self.storage_dir / f"{project_id}.json"
            self._data: Optional[dict[str, Any]] = self._load()
        else:
            self.file_path: Optional[Path] = None
            self._data = None

    def _load(self) -> dict[str, Any]:
        """加载项目数据。"""
        if self.file_path and self.file_path.exists():
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "project_id": self.project_id,
            "next_id": 1,
            "messages": [],
            "collaborators": [],
        }

    def _save(self) -> None:
        """保存项目数据。"""
        if self.file_path is None or self._data is None:
            return
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def _get_now(self) -> str:
        """获取当前时间字符串（东八区/北京时间）。"""
        return datetime.now(CHINA_TZ).strftime("%Y-%m-%d %H:%M:%S")

    def _check_mentions_me(self, mentions: list[str], user_role: str) -> bool:
        """检查消息是否 @ 了当前用户（支持角色归一化匹配）。"""
        if not mentions:
            return False
        if "所有人" in mentions:
            return True
        normalized_user_role = normalize_role(user_role)
        return user_role in mentions or normalized_user_role in mentions

    def record_collaborator(self, name: str, role: str) -> None:
        """记录/更新协作者。"""
        if not name or not role:
            return
        now = self._get_now()
        if self._data is None:
            return
        collaborators = self._data.get("collaborators", [])
        for collab in collaborators:
            if collab["name"] == name and collab["role"] == role:
                collab["last_seen"] = now
                self._save()
                return
        collaborators.append({
            "name": name,
            "role": role,
            "first_seen": now,
            "last_seen": now,
        })
        self._data["collaborators"] = collaborators
        self._save()

    def get_collaborators(self) -> list[dict[str, Any]]:
        """获取协作者列表。"""
        return [] if self._data is None else self._data.get("collaborators", [])

    def save_message(
        self,
        summary: str,
        content: str,
        author_name: str,
        author_role: str,
        mentions: Optional[list[str]] = None,
        message_type: str = "normal",
        project_name: Optional[str] = None,
        folder_name: Optional[str] = None,
        doc_id: Optional[str] = None,
        doc_name: Optional[str] = None,
        doc_type: Optional[str] = None,
        doc_version: Optional[str] = None,
        doc_updated_at: Optional[str] = None,
        doc_url: Optional[str] = None,
    ) -> dict[str, Any]:
        """保存新消息（包含标准元数据）。"""
        if self._data is None:
            raise RuntimeError("MessageStore.save_message requires a project_id")
        msg_id = self._data["next_id"]
        self._data["next_id"] += 1
        now = self._get_now()
        message = {
            "id": msg_id,
            "summary": summary,
            "content": content,
            "mentions": mentions or [],
            "message_type": message_type,
            "author_name": author_name,
            "author_role": author_role,
            "created_at": now,
            "updated_at": None,
            "updated_by_name": None,
            "updated_by_role": None,
            "project_id": self.project_id,
            "project_name": project_name,
            "folder_name": folder_name,
            "doc_id": doc_id,
            "doc_name": doc_name,
            "doc_type": doc_type,
            "doc_version": doc_version,
            "doc_updated_at": doc_updated_at,
            "doc_url": doc_url,
        }
        self._data["messages"].append(message)
        self._save()
        return message

    def get_messages(self, user_role: Optional[str] = None) -> list[dict[str, Any]]:
        """获取所有消息（不含 content，用于列表展示）。"""
        messages: list[dict[str, Any]] = []
        if self._data is None:
            return messages
        if self._data is None:
            return None
        if self._data is None:
            return None
        for msg in self._data.get("messages", []):
            msg_copy = {k: v for k, v in msg.items() if k != "content"}
            if user_role:
                msg_copy["mentions_me"] = self._check_mentions_me(msg.get("mentions", []), user_role)
            messages.append(msg_copy)
        messages.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return messages

    def get_message_by_id(self, msg_id: int, user_role: Optional[str] = None) -> Optional[dict[str, Any]]:
        """根据 ID 获取消息（含 content）。"""
        for msg in self._data.get("messages", []):
            if msg["id"] == msg_id:
                msg_copy = msg.copy()
                if user_role:
                    msg_copy["mentions_me"] = self._check_mentions_me(msg.get("mentions", []), user_role)
                return msg_copy
        return None

    def update_message(
        self,
        msg_id: int,
        editor_name: str,
        editor_role: str,
        summary: Optional[str] = None,
        content: Optional[str] = None,
        mentions: Optional[list[str]] = None,
    ) -> Optional[dict[str, Any]]:
        """更新消息。"""
        for msg in self._data.get("messages", []):
            if msg["id"] == msg_id:
                if summary is not None:
                    msg["summary"] = summary
                if content is not None:
                    msg["content"] = content
                if mentions is not None:
                    msg["mentions"] = mentions
                msg["updated_at"] = self._get_now()
                msg["updated_by_name"] = editor_name
                msg["updated_by_role"] = editor_role
                self._save()
                return msg
        return None

    def delete_message(self, msg_id: int) -> bool:
        """删除消息。"""
        if self._data is None:
            return False
        messages = self._data.get("messages", [])
        for i, msg in enumerate(messages):
            if msg["id"] == msg_id:
                messages.pop(i)
                self._save()
                return True
        return False

    def get_all_messages(self, user_role: Optional[str] = None) -> list[dict[str, Any]]:
        """获取所有项目的留言（全局查询）。"""
        all_messages: list[dict[str, Any]] = []
        for json_file in self.storage_dir.glob("*.json"):
            project_id = json_file.stem
            try:
                project_store = MessageStore(project_id)
                all_messages.extend(project_store.get_messages(user_role=user_role))
            except Exception:
                continue
        all_messages.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return all_messages

    def get_all_messages_grouped(
        self,
        user_role: Optional[str] = None,
        user_name: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """获取所有项目的留言（按项目 + 文档分组返回）。"""
        groups_dict = defaultdict(list)
        for msg in self.get_all_messages(user_role):
            project_id = msg.get("project_id", "unknown")
            doc_id = msg.get("doc_id", "no_doc")
            groups_dict[f"{project_id}_{doc_id}"].append(msg)

        groups = []
        meta_fields = {
            "project_id", "project_name", "folder_name", "doc_id", "doc_name",
            "doc_type", "doc_version", "doc_updated_at", "doc_url",
        }
        for messages in groups_dict.values():
            if not messages:
                continue
            first_msg = messages[0]
            groups.append({
                "project_id": first_msg.get("project_id"),
                "project_name": first_msg.get("project_name"),
                "folder_name": first_msg.get("folder_name"),
                "doc_id": first_msg.get("doc_id"),
                "doc_name": first_msg.get("doc_name"),
                "doc_type": first_msg.get("doc_type"),
                "doc_version": first_msg.get("doc_version"),
                "doc_updated_at": first_msg.get("doc_updated_at"),
                "doc_url": first_msg.get("doc_url"),
                "message_count": len(messages),
                "mentions_me_count": sum(1 for m in messages if m.get("mentions_me")),
                "messages": [
                    clean_message_dict({k: v for k, v in msg.items() if k not in meta_fields}, user_name)
                    for msg in messages
                ],
            })
        groups.sort(
            key=lambda g: max((m.get("created_at", "") for m in g["messages"]), default=""),
            reverse=True,
        )
        return groups
