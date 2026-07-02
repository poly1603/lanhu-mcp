"""项目数据类型定义。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Project:
    """界面层使用的项目数据对象。"""
    id: str = ""
    team_id: str = ""
    name: str = "未命名项目"
    type: str = "项目"
    updated_at: str = ""
    team_name: str = ""
    owner_name: str = ""
    url: str = ""
    source: str = ""
    color: str = ""
    raw: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> Project:
        return cls(
            id=str(data.get("id") or ""),
            team_id=str(data.get("team_id") or ""),
            name=str(data.get("name") or "未命名项目"),
            type=str(data.get("type") or "项目"),
            updated_at=str(data.get("updated_at") or ""),
            team_name=str(data.get("team_name") or ""),
            owner_name=str(data.get("owner_name") or ""),
            url=str(data.get("url") or ""),
            source=str(data.get("source") or ""),
            color=str(data.get("color") or ""),
            raw=data.get("raw") or {},
        )

    @property
    def project_id(self) -> str:
        return self.id


__all__ = ["Project"]
