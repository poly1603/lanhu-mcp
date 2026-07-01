from __future__ import annotations

import importlib

import lanhu_mcp.codegen.mcp_tools as codegen_tools


def test_codegen_registration_passes_required_context(monkeypatch) -> None:
    """扩展工具注册时必须传入提取器类和基础地址。"""
    called: dict[str, object] = {}

    def fake_register(mcp: object, lanhu_extractor: object, base_url: str) -> None:
        called["mcp"] = mcp
        called["lanhu_extractor"] = lanhu_extractor
        called["base_url"] = base_url

    monkeypatch.setattr(codegen_tools, "register_codegen_tools", fake_register)

    server_module = importlib.import_module("lanhu_mcp.server")
    importlib.reload(server_module)

    assert called["lanhu_extractor"] is server_module.LanhuExtractor
    assert called["base_url"] == server_module.BASE_URL
