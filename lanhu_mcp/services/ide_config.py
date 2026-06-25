"""AI IDE / MCP 客户端检测与配置写入（无 Tkinter 依赖）。

从 ``lanhu_mcp_gui.py`` 抽取的纯逻辑，仅依赖标准库。支持 JSON / Claude CLI /
YAML / TOML 四种配置格式，MCP URL 由 :func:`current_mcp_url` 按当前账号生成。
"""
from __future__ import annotations

import json
import os
import re
import shutil
import time
from pathlib import Path
from typing import Optional

from ..core.accounts import current_mcp_url

__all__ = [
    "IDE_REGISTRY",
    "IDEManager",
]


IDE_REGISTRY = {
    'Cursor': {
        'icon': 'mouse-pointer-2',
        'exe': [
            Path('D:/Apps/nodejs/cursor.cmd'),
            Path('D:/Apps/nodejs/cursor.exe'),
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Cursor' / 'Cursor.exe',
            Path(os.environ.get('LOCALAPPDATA', '')) / 'cursor' / 'Cursor.exe',
            Path('D:/Apps/cursor/Cursor.exe'),
            Path('D:/Apps/Cursor/Cursor.exe'),
            Path('D:/Apps/Cursor/resources/app/bin/cursor.cmd'),
        ],
        'config': [
            Path.home() / '.cursor' / 'mcp.json',
            Path(os.environ.get('APPDATA', '')) / 'Cursor' / 'User' / 'globalStorage' / 'saoudrizwan.claude-dev' / 'settings' / 'cline_mcp_settings.json',
            Path(os.environ.get('APPDATA', '')) / 'Cursor' / 'User' / 'globalStorage' / 'rooveterinaryinc.roo-cline' / 'settings' / 'mcp_settings.json',
        ],
        'format': 'json',
        'commands': ['cursor'],
    },
    'Windsurf': {
        'icon': 'waves',
        'exe': [
            Path('D:/Apps/nodejs/windsurf.cmd'),
            Path('D:/Apps/nodejs/windsurf.exe'),
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Windsurf' / 'Windsurf.exe',
            Path(os.environ.get('LOCALAPPDATA', '')) / 'windsurf' / 'Windsurf.exe',
            Path('D:/Apps/Windsurf/Windsurf.exe'),
            Path('D:/Apps/windsurf/Windsurf.exe'),
        ],
        'config': [
            Path.home() / '.codeium' / 'windsurf' / 'mcp_config.json',
            Path(os.environ.get('APPDATA', '')) / 'Windsurf' / 'User' / 'globalStorage' / 'saoudrizwan.claude-dev' / 'settings' / 'cline_mcp_settings.json',
            Path(os.environ.get('APPDATA', '')) / 'Windsurf' / 'User' / 'globalStorage' / 'rooveterinaryinc.roo-cline' / 'settings' / 'mcp_settings.json',
        ],
        'format': 'json',
        'commands': ['windsurf'],
    },
    'Claude Desktop': {
        'icon': 'message-circle',
        'exe': [
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Claude' / 'Claude.exe',
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Claude' / 'Claude.exe',
            Path('D:/Apps/Claude/Claude.exe'),
        ],
        'config': [
            Path(os.environ.get('APPDATA', '')) / 'Claude' / 'claude_desktop_config.json',
        ],
        'format': 'json',
    },
    'Claude Code': {
        'icon': 'terminal',
        'exe': [
            Path('D:/Apps/nodejs/claude.cmd'),
            Path('D:/Apps/nodejs/claude.exe'),
            Path(os.environ.get('APPDATA', '')) / 'npm' / 'claude.cmd',
            Path(os.environ.get('APPDATA', '')) / 'npm' / 'claude.exe',
            Path('D:/Apps/Claude/claude.cmd'),
        ],
        'config': [
            Path.home() / '.claude.json',
        ],
        'format': 'claude-cli',
        'commands': ['claude'],
    },
    'VS Code + Cline': {
        'icon': 'code-2',
        'exe': [
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Microsoft VS Code' / 'Code.exe',
            Path(os.environ.get('PROGRAMFILES', '')) / 'Microsoft VS Code' / 'Code.exe',
            Path('D:/Apps/Microsoft VS Code/Code.exe'),
            Path('D:/Apps/VS Code/Code.exe'),
        ],
        'config': [
            Path(os.environ.get('APPDATA', '')) / 'Code' / 'User' / 'globalStorage' / 'saoudrizwan.claude-dev' / 'settings' / 'cline_mcp_settings.json',
            Path(os.environ.get('APPDATA', '')) / 'Code' / 'User' / 'globalStorage' / 'rooveterinaryinc.roo-cline' / 'settings' / 'mcp_settings.json',
        ],
        'format': 'json',
        'commands': ['code'],
    },
    'Trae': {
        'icon': 'sparkles',
        'exe': [
            Path('D:/Apps/nodejs/trae.cmd'),
            Path('D:/Apps/nodejs/trae.exe'),
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Trae' / 'Trae.exe',
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Trae' / 'Trae.exe',
            Path('D:/Apps/Trae/Trae.exe'),
            Path('D:/Apps/trae/Trae.exe'),
        ],
        'config': [
            Path.home() / '.trae' / 'mcp.json',
            Path(os.environ.get('APPDATA', '')) / 'Trae' / 'User' / 'globalStorage' / 'saoudrizwan.claude-dev' / 'settings' / 'cline_mcp_settings.json',
        ],
        'format': 'json',
        'commands': ['trae'],
    },
    'Cherry Studio': {
        'icon': 'bot',
        'exe': [
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'cherry-studio' / 'Cherry Studio.exe',
            Path(os.environ.get('APPDATA', '')) / 'cherry-studio' / 'Cherry Studio.exe',
            Path('D:/Apps/CherryStudio/Cherry Studio/Cherry Studio.exe'),
            Path('D:/Apps/CherryStudio/Cherry Studio.exe'),
        ],
        'config': [
            Path(os.environ.get('APPDATA', '')) / 'cherry-studio' / 'mcp.json',
        ],
        'format': 'json',
        'commands': ['cherry-studio'],
    },
    'ChatBox': {
        'icon': 'messages-square',
        'exe': [
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'chatbox' / 'Chatbox.exe',
            Path('D:/Apps/ChatBox/Chatbox.exe'),
            Path('D:/Apps/chatbox/Chatbox.exe'),
        ],
        'config': [
            Path(os.environ.get('APPDATA', '')) / 'chatbox' / 'config.json',
        ],
        'format': 'json',
        'commands': ['chatbox'],
    },
    'Continue': {
        'icon': 'circle-fading-arrow-up',
        'exe': [
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Microsoft VS Code' / 'Code.exe',
            Path('D:/Apps/Microsoft VS Code/Code.exe'),
        ],
        'config': [
            Path.home() / '.continue' / 'config.yaml',
        ],
        'format': 'yaml',
        'commands': ['continue'],
    },
    'Cline (OpenCode)': {
        'icon': 'braces',
        'exe': [
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'opencode' / 'OpenCode.exe',
            Path('D:/Apps/OpenCode/OpenCode.exe'),
            Path('D:/Apps/opencode/OpenCode.exe'),
        ],
        'config': [
            Path(os.environ.get('APPDATA', '')) / 'opencode' / 'mcp.json',
            Path.home() / '.opencode' / 'mcp.json',
        ],
        'format': 'json',
        'commands': ['opencode'],
    },
    'CodeBuddy': {
        'icon': 'handshake',
        'exe': [
            Path('D:/Apps/CodeBuddyCN/CodeBuddy CN.exe'),
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'CodeBuddy' / 'CodeBuddy CN.exe',
        ],
        'config': [
            Path(os.environ.get('APPDATA', '')) / 'CodeBuddy' / 'mcp.json',
        ],
        'format': 'json',
        'commands': ['codebuddy'],
    },
    'MimoCode': {
        'icon': 'blocks',
        'exe': [
            Path('D:/Apps/nodejs/mimo.cmd'),
            Path('D:/Apps/nodejs/mimo.exe'),
            Path('D:/Apps/mimocode-windows-x64/mimo.exe'),
            Path('D:/Apps/MimoCode/mimo.exe'),
            Path('D:/Apps/mimocode/mimo.exe'),
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'mimocode' / 'mimo.exe',
        ],
        'config': [
            Path.cwd() / '.mimocode' / 'mcp.json',
            Path.home() / '.mimocode' / 'mcp.json',
            Path(os.environ.get('APPDATA', '')) / 'mimocode' / 'mcp.json',
        ],
        'format': 'json',
        'commands': ['mimo', 'mimocode'],
    },
    'Junie (JetBrains)': {
        'icon': 'badge-code',
        'exe': [
            Path(os.environ.get('LOCALAPPDATA', '')) / 'JetBrains' / 'Toolbox' / 'apps' / 'Junie' / 'ch-0' / 'Junie.exe',
            Path('D:/Apps/JetBrains/Toolbox/apps/Junie/ch-0/Junie.exe'),
        ],
        'config': [
            Path(os.environ.get('APPDATA', '')) / 'JetBrains' / 'Junie' / 'mcp.json',
        ],
        'format': 'json',
        'commands': ['junie'],
    },
    'Codex': {
        'icon': 'square-terminal',
        'exe': [
            Path('D:/Apps/nodejs/codex.cmd'),
            Path('D:/Apps/nodejs/codex.exe'),
            Path('D:/Apps/CodexApp/codex.bat'),
            Path(os.environ.get('APPDATA', '')) / 'npm' / 'codex.cmd',
            Path(os.environ.get('APPDATA', '')) / 'npm' / 'codex.exe',
            Path('D:/Apps/Codex/codex.cmd'),
            Path('D:/Apps/codex/codex.cmd'),
        ],
        'config': [
            Path.home() / '.codex' / 'config.toml',
        ],
        'format': 'toml',
        'commands': ['codex'],
    },
    'Gemini CLI': {
        'icon': 'gem',
        'exe': [
            Path('D:/Apps/nodejs/gemini.cmd'),
            Path('D:/Apps/nodejs/gemini.exe'),
            Path(os.environ.get('APPDATA', '')) / 'npm' / 'gemini.cmd',
            Path(os.environ.get('APPDATA', '')) / 'npm' / 'gemini.exe',
            Path('D:/Apps/Gemini/gemini.cmd'),
        ],
        'config': [
            Path.home() / '.gemini' / 'settings.json',
        ],
        'format': 'json',
        'commands': ['gemini'],
    },
    'Roo Code': {
        'icon': 'route',
        'exe': [
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Microsoft VS Code' / 'Code.exe',
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Cursor' / 'Cursor.exe',
        ],
        'config': [
            Path(os.environ.get('APPDATA', '')) / 'Code' / 'User' / 'globalStorage' / 'rooveterinaryinc.roo-cline' / 'settings' / 'mcp_settings.json',
            Path(os.environ.get('APPDATA', '')) / 'Cursor' / 'User' / 'globalStorage' / 'rooveterinaryinc.roo-cline' / 'settings' / 'mcp_settings.json',
        ],
        'format': 'json',
        'commands': ['code', 'cursor'],
    },
    'Qoder': {
        'icon': 'blocks',
        'exe': [
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Qoder' / 'Qoder.exe',
            Path('D:/Apps/Qoder/Qoder.exe'),
            Path('D:/Apps/qoder/Qoder.exe'),
        ],
        'config': [
            Path.home() / '.qoder' / 'mcp.json',
            Path(os.environ.get('APPDATA', '')) / 'Qoder' / 'mcp.json',
        ],
        'format': 'json',
        'commands': ['qoder'],
    },
    'Kiro': {
        'icon': 'sparkles',
        'exe': [
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Kiro' / 'Kiro.exe',
            Path('D:/Apps/Kiro/Kiro.exe'),
            Path('D:/Apps/kiro/Kiro.exe'),
        ],
        'config': [
            Path.home() / '.kiro' / 'mcp.json',
            Path(os.environ.get('APPDATA', '')) / 'Kiro' / 'mcp.json',
        ],
        'format': 'json',
        'commands': ['kiro'],
    },
    'Zed': {
        'icon': 'code-2',
        'exe': [
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Zed' / 'Zed.exe',
            Path('D:/Apps/Zed/Zed.exe'),
            Path('D:/Apps/zed/Zed.exe'),
        ],
        'config': [
            Path.home() / '.config' / 'zed' / 'settings.json',
            Path(os.environ.get('APPDATA', '')) / 'Zed' / 'settings.json',
        ],
        'format': 'json',
        'commands': ['zed'],
    },
}


class IDEManager:
    @staticmethod
    def _is_valid_executable_path(exe_path: Path) -> bool:
        """判断候选可执行文件是否真实可用。"""
        if not exe_path.exists() or not exe_path.is_file():
            return False
        # 命令脚本通常很小，二进制程序需要做一个基础大小判断。
        if exe_path.suffix.lower() in ('.cmd', '.bat', '.ps1'):
            return True
        return exe_path.stat().st_size > 1024 * 32

    @staticmethod
    def _resolve_command_path(command_name: str) -> Optional[Path]:
        """通过 PATH 解析 CLI 工具真实路径。"""
        resolved = shutil.which(command_name)
        return Path(resolved) if resolved else None

    @staticmethod
    def _find_executable(info: dict) -> Optional[Path]:
        """从固定路径和 PATH 中找到第一个可用程序。"""
        for exe_path in info['exe']:
            if IDEManager._is_valid_executable_path(exe_path):
                return exe_path
        for command_name in info.get('commands', []):
            resolved_path = IDEManager._resolve_command_path(str(command_name))
            if resolved_path and IDEManager._is_valid_executable_path(resolved_path):
                return resolved_path
        return None

    @staticmethod
    def _check_ide_installed(info: dict) -> bool:
        """真实检测IDE是否已安装（检查exe文件、PATH和配置目录）"""
        if IDEManager._find_executable(info):
            return True
        for config_path in info.get('config', []):
            if config_path.exists() or config_path.parent.exists():
                return True
        return False

    @staticmethod
    def _check_config_exists(info: dict) -> bool:
        """检查IDE的MCP配置目录是否存在"""
        for config_path in info['config']:
            if config_path.parent.exists():
                return True
        return False

    @staticmethod
    def detect_all() -> dict:
        results = {}
        for name, info in IDE_REGISTRY.items():
            installed = IDEManager._check_ide_installed(info)
            results[name] = installed
        return results

    @staticmethod
    def get_detection_details() -> dict:
        """获取详细的检测信息（用于调试）"""
        details = {}
        for name, info in IDE_REGISTRY.items():
            exe_found = IDEManager._find_executable(info)

            config_found = None
            for config_path in info['config']:
                if config_path.parent.exists():
                    config_found = config_path
                    break

            details[name] = {
                'installed': exe_found is not None or config_found is not None,
                'exe_path': str(exe_found) if exe_found else None,
                'config_dir': str(config_found.parent) if config_found else None,
                'config_path': str(config_found) if config_found else None,
                'icon': info.get('icon', 'plug'),
            }
        return details

    @staticmethod
    def _select_config_path(info: dict) -> Optional[Path]:
        """选择最合适的配置路径，优先使用已存在文件，其次使用已存在目录。"""
        for path in info['config']:
            if path.exists():
                return path
        for path in info['config']:
            if path.parent.exists():
                return path
        return info['config'][0] if info.get('config') else None

    @staticmethod
    def _load_json_config(config_path: Path) -> dict:
        """读取 JSON 配置文件，失败时返回空配置。"""
        if not config_path.exists():
            return {}
        try:
            content = config_path.read_text(encoding='utf-8').strip()
            return json.loads(content) if content else {}
        except json.JSONDecodeError:
            backup_path = config_path.with_suffix(config_path.suffix + f".bak-{int(time.time())}")
            try:
                shutil.copy2(config_path, backup_path)
            except OSError:
                pass
            return {}

    @staticmethod
    def _dump_json_config(config_path: Path, config: dict) -> None:
        """写入 JSON 配置文件。"""
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding='utf-8')

    @staticmethod
    def _configure_json(config_path: Path, port: int) -> None:
        """为 JSON 配置写入 lanhu MCP 服务。"""
        config = IDEManager._load_json_config(config_path)
        if not isinstance(config, dict):
            config = {}
        server_url = current_mcp_url(port)
        if 'mcpServers' not in config or not isinstance(config.get('mcpServers'), dict):
            config['mcpServers'] = {}
        config['mcpServers']['lanhu'] = {
            'url': server_url,
            'disabled': False,
        }
        IDEManager._dump_json_config(config_path, config)

    @staticmethod
    def _configure_claude_cli(config_path: Path, port: int) -> None:
        """为 Claude Code 写入用户级 HTTP MCP 配置。"""
        config = IDEManager._load_json_config(config_path)
        if not isinstance(config, dict):
            config = {}
        mcp_servers = config.get("mcpServers")
        if not isinstance(mcp_servers, dict):
            mcp_servers = {}
        mcp_servers["lanhu"] = {
            "type": "http",
            "url": current_mcp_url(port),
        }
        config["mcpServers"] = mcp_servers
        IDEManager._dump_json_config(config_path, config)

    @staticmethod
    def _configure_yaml(config_path: Path, port: int) -> None:
        """为 YAML 配置写入 lanhu MCP 服务。"""
        config = {}
        if config_path.exists():
            try:
                import yaml
                config = yaml.safe_load(config_path.read_text(encoding='utf-8')) or {}
            except Exception:
                config = {}
        if 'mcpServers' not in config or not isinstance(config.get('mcpServers'), dict):
            config['mcpServers'] = {}
        config['mcpServers']['lanhu'] = {
            'url': current_mcp_url(port),
            'disabled': False,
        }
        config_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            import yaml
            config_path.write_text(yaml.dump(config, allow_unicode=True, default_flow_style=False), encoding='utf-8')
        except Exception:
            lines = ["mcpServers:"]
            for name, server in config.get('mcpServers', {}).items():
                lines.append(f"  {name}:")
                lines.append(f"    url: {server.get('url', '')}")
                lines.append(f"    disabled: {str(server.get('disabled', False)).lower()}")
            config_path.write_text("\n".join(lines) + "\n", encoding='utf-8')

    @staticmethod
    def _configure_toml(config_path: Path, port: int) -> None:
        """为 Codex TOML 配置写入 lanhu MCP 服务。"""
        config_path.parent.mkdir(parents=True, exist_ok=True)
        content = config_path.read_text(encoding='utf-8') if config_path.exists() else ""
        server_block = (
            "[mcp_servers.lanhu]\n"
            f'url = "{current_mcp_url(port)}"\n'
        )
        pattern = r'(?ms)^\[mcp_servers\.lanhu\]\s*.*?(?=^\[|\Z)'
        if re.search(pattern, content):
            content = re.sub(pattern, server_block, content)
        else:
            if content and not content.endswith("\n"):
                content += "\n"
            if "[mcp_servers]" not in content:
                content += "\n[mcp_servers]\n"
            content += "\n" + server_block
        config_path.write_text(content, encoding='utf-8')

    @staticmethod
    def configure(ide_name: str, port: int = 8000) -> tuple[bool, str]:
        if ide_name not in IDE_REGISTRY:
            return False, "未知IDE"

        ide_info = IDE_REGISTRY[ide_name]
        config_path = IDEManager._select_config_path(ide_info)
        if not config_path:
            return False, f"{ide_name} 配置目录不存在"

        try:
            config_format = ide_info.get('format', config_path.suffix.lower().lstrip('.'))
            if config_format == 'claude-cli':
                IDEManager._configure_claude_cli(config_path, port)
            elif config_format == 'toml' or config_path.suffix.lower() == '.toml':
                IDEManager._configure_toml(config_path, port)
            elif config_format == 'yaml' or config_path.suffix.lower() in ('.yaml', '.yml'):
                IDEManager._configure_yaml(config_path, port)
            else:
                IDEManager._configure_json(config_path, port)
            return True, f"已配置 {ide_name}: {config_path}"
        except PermissionError:
            return False, f"权限不足，无法写入 {config_path}"
        except Exception as e:
            return False, f"写入失败: {e}"

    @staticmethod
    def configure_all(port: int = 8000) -> list:
        results = []
        detected = IDEManager.detect_all()
        for name, installed in detected.items():
            if installed:
                ok, msg = IDEManager.configure(name, port)
                results.append((name, ok, msg))
        return results
