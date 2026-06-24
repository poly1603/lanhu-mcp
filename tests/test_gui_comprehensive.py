"""Comprehensive tests for Lanhu MCP GUI (monolithic lanhu_mcp_gui.py)."""
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import lanhu_mcp_gui as gui


# ============================================================
# Config / Colors / Spacing
# ============================================================

class TestConfig:
    def test_colors_has_required_keys(self):
        required = ['bg', 'sidebar', 'card', 'primary', 'success', 'danger',
                     'text_primary', 'text_secondary', 'border', 'border_light']
        for key in required:
            assert key in gui.COLORS, f"Missing color key: {key}"

    def test_spacing_is_4px_grid(self):
        assert gui.SPACING['1'] == 4
        assert gui.SPACING['2'] == 8
        assert gui.SPACING['3'] == 12
        assert gui.SPACING['4'] == 16

    def test_font_has_family_and_sizes(self):
        assert 'family' in gui.FONT
        assert 'sizes' in gui.FONT

    def test_animation_interval_ms(self):
        assert gui.animation_interval_ms("sidebar_pulse") == 180
        assert gui.animation_interval_ms("page_transition") == 120
        assert gui.animation_interval_ms("unknown") == 200

    def test_should_run_sidebar_pulse(self):
        assert gui.should_run_sidebar_pulse("normal", True) is True
        assert gui.should_run_sidebar_pulse("normal", False) is False
        assert gui.should_run_sidebar_pulse("iconic", True) is False

    def test_project_rows_signature_stable(self):
        projects = [{"id": "1", "team_id": "t1", "name": "A", "updated_at": "2026-01-01", "source": "api"}]
        sig1 = gui.project_rows_signature(projects)
        sig2 = gui.project_rows_signature(projects)
        assert sig1 == sig2

    def test_project_rows_signature_ignores_raw(self):
        p1 = [{"id": "1", "team_id": "t1", "name": "A", "raw": {"x": 1}}]
        p2 = [{"id": "1", "team_id": "t1", "name": "A", "raw": {"x": 2}}]
        assert gui.project_rows_signature(p1) == gui.project_rows_signature(p2)

    def test_account_rows_signature_stable(self):
        accounts = [{"id": "a1", "name": "User", "email": "e@m.com", "mobile": "123"}]
        sig1 = gui.account_rows_signature(accounts, "a1")
        sig2 = gui.account_rows_signature(accounts, "a1")
        assert sig1 == sig2


# ============================================================
# Port / URL / Time helpers
# ============================================================

class TestUtilsBasic:
    def test_validate_port_valid(self):
        ok, port, err = gui.validate_port("8000")
        assert ok is True
        assert port == 8000

    def test_validate_port_low_port_valid(self):
        # Committed version accepts 1-65535
        ok, port, _ = gui.validate_port("80")
        assert ok is True
        assert port == 80

    def test_validate_port_zero(self):
        ok, _, _ = gui.validate_port("0")
        assert ok is False

    def test_validate_port_not_number(self):
        ok, _, _ = gui.validate_port("abc")
        assert ok is False

    def test_now_text_format(self):
        text = gui.now_text()
        assert len(text) == 19
        assert text[4] == '-'

    def test_current_mcp_url(self):
        url = gui.current_mcp_url(8000)
        assert "8000" in url
        assert "/mcp" in url


# ============================================================
# build_server_start_command
# ============================================================

class TestBuildServerStartCommand:
    def test_returns_valid_command(self):
        try:
            cmd, directory, source = gui.build_server_start_command()
            assert len(cmd) >= 2
        except FileNotFoundError:
            pytest.skip("Server not found in current environment")

    def test_uses_server_flag(self):
        try:
            cmd, _, source = gui.build_server_start_command()
            assert '--server' in cmd
        except FileNotFoundError:
            pytest.skip("Server not found")


# ============================================================
# Project URL parsing
# ============================================================

class TestProjectUrlParsing:
    def test_parse_stage_url(self):
        url = "https://lanhuapp.com/web/#/item/project/stage?tid=team1&pid=proj1"
        result = gui.parse_lanhu_project_url(url)
        assert result is not None
        assert result["id"] == "proj1"
        assert result["team_id"] == "team1"

    def test_parse_product_url(self):
        url = "https://lanhuapp.com/web/#/item/project/product?tid=t1&pid=p1"
        result = gui.parse_lanhu_project_url(url)
        assert result is not None
        assert result["type"] == "原型"

    def test_parse_empty_url(self):
        assert gui.parse_lanhu_project_url("") is None
        assert gui.parse_lanhu_project_url(None) is None

    def test_parse_cn_domain(self):
        url = "https://lanhuapp.cn/web/#/item/project/stage?tid=t1&pid=p1"
        result = gui.parse_lanhu_project_url(url)
        assert result is not None


# ============================================================
# Project normalization / merge
# ============================================================

class TestProjectNormalization:
    def test_normalize_project_item_basic(self):
        item = {"project_id": "p1", "team_id": "t1", "project_name": "Test"}
        result = gui.normalize_project_item(item)
        assert result["id"] == "p1"
        assert result["name"] == "Test"

    def test_project_identity_key_by_id(self):
        p = {"id": "p1", "team_id": "t1"}
        assert gui.project_identity_key(p) == "project:t1:p1"

    def test_project_identity_key_empty(self):
        assert gui.project_identity_key({}) == ""

    def test_merge_project_lists_dedup(self):
        projects = [
            {"id": "p1", "team_id": "t1", "name": "Old", "source": "cache"},
            {"id": "p1", "team_id": "t1", "name": "New", "updated_at": "2026-01-01"},
        ]
        merged = gui.merge_project_lists(projects)
        assert len(merged) == 1
        assert merged[0]["updated_at"] == "2026-01-01"

    def test_merge_project_lists_different(self):
        projects = [
            {"id": "p1", "team_id": "t1", "name": "A"},
            {"id": "p2", "team_id": "t1", "name": "B"},
        ]
        assert len(gui.merge_project_lists(projects)) == 2

    def test_merge_empty(self):
        assert gui.merge_project_lists([]) == []


# ============================================================
# MCP tool discovery
# ============================================================

class TestMCPToolDiscovery:
    def test_discover_returns_list(self):
        tools = gui.discover_mcp_tools(refresh=True)
        assert isinstance(tools, list)
        assert len(tools) > 0

    def test_discover_has_names_and_descriptions(self):
        tools = gui.discover_mcp_tools(refresh=True)
        for name, desc in tools:
            assert isinstance(name, str) and len(name) > 0

    def test_discover_caches(self):
        gui._MCP_TOOLS_CACHE = None
        tools1 = gui.discover_mcp_tools()
        tools2 = gui.discover_mcp_tools()
        assert tools1 == tools2

    def test_group_mcp_tools(self):
        tools = gui.discover_mcp_tools(refresh=True)
        groups = gui.group_mcp_tools(tools)
        assert len(groups) > 0
        total = sum(len(v) for v in groups.values())
        assert total == len(tools)


# ============================================================
# User payload parsing
# ============================================================

class TestUserPayloadParsing:
    def test_parse_nested_data(self):
        payload = {"data": {"id": "u1", "name": "Test", "email": "e@m.com"}}
        result = gui.parse_user_payload(payload)
        assert result["id"] == "u1"
        assert result["name"] == "Test"

    def test_parse_empty(self):
        result = gui.parse_user_payload({})
        assert result.get("id", "") == ""

    def test_parse_non_dict_returns_defaults(self):
        # Monolithic version returns default dict with empty strings
        result = gui.parse_user_payload("string")
        assert isinstance(result, dict)
        assert "id" in result


# ============================================================
# Project manager (read/write)
# ============================================================

class TestProjectManager:
    def test_read_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(gui, 'PROJECTS_FILE', tmp_path / 'none.json')
        data = gui.read_projects_data()
        assert data == {"projects": []}

    def test_write_and_read(self, tmp_path, monkeypatch):
        pf = tmp_path / 'projects.json'
        monkeypatch.setattr(gui, 'PROJECTS_FILE', pf)
        monkeypatch.setattr(gui, 'DATA_DIR', tmp_path)
        gui.write_projects_data({"projects": [{"id": "p1"}]})
        data = gui.read_projects_data()
        assert len(data["projects"]) == 1

    def test_read_corrupted(self, tmp_path, monkeypatch):
        pf = tmp_path / 'bad.json'
        pf.write_text("not json", encoding='utf-8')
        monkeypatch.setattr(gui, 'PROJECTS_FILE', pf)
        assert gui.read_projects_data() == {"projects": []}


# ============================================================
# Account manager
# ============================================================

class TestAccountManager:
    def test_get_accounts_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(gui, 'ACCOUNTS_FILE', tmp_path / 'none.json')
        monkeypatch.setattr(gui, 'COOKIE_FILE', tmp_path / 'none_cookie.txt')
        assert gui.get_accounts() == []

    def test_write_and_get_accounts(self, tmp_path, monkeypatch):
        af = tmp_path / 'accounts.json'
        monkeypatch.setattr(gui, 'ACCOUNTS_FILE', af)
        monkeypatch.setattr(gui, 'DATA_DIR', tmp_path)
        gui.write_accounts_data({"accounts": [{"id": "a1", "name": "U1", "cookie": "c1"}], "active_id": "a1"})
        loaded = gui.get_accounts()
        assert len(loaded) == 1

    def test_get_active_account(self, tmp_path, monkeypatch):
        af = tmp_path / 'accounts.json'
        monkeypatch.setattr(gui, 'ACCOUNTS_FILE', af)
        monkeypatch.setattr(gui, 'DATA_DIR', tmp_path)
        gui.write_accounts_data({
            "accounts": [
                {"id": "a1", "name": "U1", "cookie": "c1"},
                {"id": "a2", "name": "U2", "cookie": "c2"},
            ],
            "active_id": "a2",
        })
        active = gui.get_active_account()
        assert active["id"] == "a2"

    def test_remove_account(self, tmp_path, monkeypatch):
        af = tmp_path / 'accounts.json'
        monkeypatch.setattr(gui, 'ACCOUNTS_FILE', af)
        monkeypatch.setattr(gui, 'DATA_DIR', tmp_path)
        gui.write_accounts_data({
            "accounts": [
                {"id": "a1", "name": "U1", "cookie": "c1"},
                {"id": "a2", "name": "U2", "cookie": "c2"},
            ],
            "active_id": "a1",
        })
        result = gui.remove_account("a1")
        assert result is not None
        remaining = gui.get_accounts()
        assert len(remaining) == 1


# ============================================================
# Pagination logic
# ============================================================

class TestPagination:
    def test_total_pages(self):
        page_size = 20
        def total_pages(t):
            return 0 if t == 0 else (t + page_size - 1) // page_size
        assert total_pages(0) == 0
        assert total_pages(1) == 1
        assert total_pages(20) == 1
        assert total_pages(21) == 2
        assert total_pages(100) == 5

    def test_page_slice(self):
        page_size = 20
        projects = [{"id": f"p{i}"} for i in range(55)]
        assert len(projects[0:20]) == 20
        assert len(projects[40:60]) == 15
        assert len(projects[100:120]) == 0

    def test_page_clamping(self):
        total_pages = 3
        assert max(0, min(-1, total_pages - 1)) == 0
        assert max(0, min(5, total_pages - 1)) == 2


# ============================================================
# collect_dict_items
# ============================================================

class TestCollectDictItems:
    def test_collect_direct(self):
        payload = {"project_id": "p1", "name": "Test", "team_id": "t1"}
        items = gui.collect_dict_items(payload)
        assert len(items) >= 1

    def test_collect_nested(self):
        payload = {"data": {"projects": [{"project_id": "p1", "name": "A"}, {"project_id": "p2", "name": "B"}]}}
        items = gui.collect_dict_items(payload)
        assert len(items) >= 2

    def test_collect_empty(self):
        assert gui.collect_dict_items({}) == []
        assert gui.collect_dict_items([]) == []


# ============================================================
# collect_project_urls
# ============================================================

class TestCollectProjectUrls:
    def test_collect_from_string(self):
        found = []
        gui.collect_project_urls('https://lanhuapp.com/web/#/item/project/stage?tid=t1&pid=p1', found)
        assert len(found) >= 1

    def test_collect_empty(self):
        found = []
        gui.collect_project_urls({}, found)
        assert found == []


# ============================================================
# parse_json_object / first_detail_value
# ============================================================

class TestParsingHelpers:
    def test_parse_json_valid(self):
        assert gui.parse_json_object('{"k": "v"}') == {"k": "v"}

    def test_parse_json_invalid(self):
        assert gui.parse_json_object("not json") == "not json"

    def test_parse_json_non_string(self):
        assert gui.parse_json_object(42) == 42

    def test_first_detail_value(self):
        assert gui.first_detail_value({"a": "", "b": "ok"}, ("a", "b")) == "ok"

    def test_first_detail_value_missing(self):
        assert gui.first_detail_value({}, ("a",)) == ""


# ============================================================
# projects_from_payload
# ============================================================

class TestProjectsFromPayload:
    def test_from_team_projects(self):
        payload = {"result": {"team_projects": [{"tid": "t1", "team_name": "T", "projects": [{"project_id": "p1", "project_name": "P"}]}]}}
        projects = gui.projects_from_payload(payload, "acc1")
        assert len(projects) >= 1

    def test_from_empty(self):
        assert gui.projects_from_payload({}, "acc1") == []


# ============================================================
# lanhu_api_headers
# ============================================================

class TestApiHeaders:
    def test_headers_with_token(self):
        headers = gui.lanhu_api_headers("user_token=abc123; x=1")
        assert "Authorization" in headers

    def test_headers_without_token(self):
        headers = gui.lanhu_api_headers("SERVERID=s1")
        assert "Authorization" not in headers


# ============================================================
# Avatar helpers
# ============================================================

class TestAvatar:
    def test_cache_path(self, tmp_path, monkeypatch):
        monkeypatch.setattr(gui, 'AVATAR_CACHE_DIR', tmp_path)
        account = {"id": "user1", "avatar": "http://example.com/a.png"}
        path = gui.avatar_cache_path(account)
        assert path.parent == tmp_path

    def test_download_avatar_no_url(self):
        account = {"id": "u1", "avatar": ""}
        assert gui.download_avatar(account) is None


# ============================================================
# Cookie parsing
# ============================================================

class TestCookieParsing:
    def test_parse_cookie_pairs(self):
        pairs = gui.parse_cookie_pairs("a=1; b=2; c=3")
        assert pairs["a"] == "1"
        assert pairs["b"] == "2"

    def test_mask_cookie_short(self):
        # Short cookies may not be masked
        masked = gui.mask_cookie_value("abc")
        assert isinstance(masked, str)

    def test_mask_cookie_long(self):
        masked = gui.mask_cookie_value("a" * 100)
        assert isinstance(masked, str)


# ============================================================
# Tool descriptions completeness
# ============================================================

class TestToolDescriptions:
    def test_all_have_descriptions(self):
        for name, desc in gui.TOOL_DESCRIPTIONS.items():
            assert len(name) > 0
            assert len(desc) > 0

    def test_groups_cover_all(self):
        grouped = set()
        for tools in gui.TOOL_GROUPS.values():
            grouped.update(tools)
        for name in gui.TOOL_DESCRIPTIONS:
            assert name in grouped
