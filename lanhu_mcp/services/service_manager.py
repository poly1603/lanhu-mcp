"""MCP 服务子进程管理与服务脚本定位（无 Tkinter 依赖）。

从 ``lanhu_mcp_gui.py`` 抽取。源码模式下统一通过 ``python <gui> --server`` 拉起
服务，确保扩展 MCP 工具被加载；打包后复用当前 exe 的 ``--server`` 分支。

注意：原 GUI 用 ``Path(__file__)`` 推断 GUI 脚本路径，迁移到本模块后改用
``APP_DIR / 'lanhu_mcp_gui.py'``（源码模式下 ``APP_DIR`` 即仓库根目录），避免
``__file__`` 指向 ``lanhu_mcp/services`` 目录。
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from typing import Optional

from ..core.accounts import get_active_account
from ..core.paths import (
    APP_DIR,
    ENV_FILE,
    find_server_exe,
    first_existing_path,
    flog,
    is_port_in_use,
    validate_port,
)

__all__ = [
    "find_server_script",
    "build_server_start_command",
    "ServiceManager",
]


def find_server_script() -> Optional[Path]:
    """查找源码模式下可直接运行的 MCP 服务脚本。"""
    candidates = [
        APP_DIR / 'lanhu_mcp_server.py',
    ]
    return first_existing_path(candidates)


def build_server_start_command() -> tuple[list[str], "Path", str]:
    """构造服务启动命令，打包后优先复用当前 exe 的内置服务分支。"""
    if getattr(sys, 'frozen', False):
        # 单文件打包后没有独立服务 exe，直接拉起自身的 --server 分支。
        return [sys.executable, '--server'], APP_DIR, '内置服务'

    gui_script = APP_DIR / 'lanhu_mcp_gui.py'
    if gui_script.exists():
        # 源码开发时也走同一个 --server 分支，确保扩展 MCP 工具被加载。
        return [sys.executable, str(gui_script), '--server'], gui_script.parent, '源码内置服务'

    server_script = find_server_script()
    if server_script:
        # 源码开发时直接运行服务脚本，方便当前代码改动立即生效。
        return [sys.executable, str(server_script)], server_script.parent, '源码服务'

    server_exe = find_server_exe()
    if server_exe:
        # 兼容旧版独立服务端 exe 的部署方式。
        return [str(server_exe)], server_exe.parent, '独立服务端'

    raise FileNotFoundError(
        "未找到可启动的 MCP 服务。\n"
        "已检查: 内置服务分支、lanhu_mcp_server.py、lanhu_mcp.exe、lanhu_mcp_server.exe。"
    )


class ServiceManager:
    _process = None
    _running = False
    _port = 8000
    _stop_event = threading.Event()
    _lock = threading.RLock()

    @staticmethod
    def is_running() -> bool:
        with ServiceManager._lock:
            if ServiceManager._process is None:
                return False
            if ServiceManager._process.poll() is not None:
                ServiceManager._running = False
                return False
            return ServiceManager._running

    @staticmethod
    def start(port: int = 8000, on_output=None, on_error=None) -> tuple[bool, str]:
        with ServiceManager._lock:
            if ServiceManager.is_running():
                return False, "服务已在运行"

            valid, p, err = validate_port(str(port))
            if not valid:
                return False, err
            if is_port_in_use(p):
                return False, f"端口 {port} 已被占用，请更换端口或关闭占用程序"

        try:
            server_command, server_dir, server_source = build_server_start_command()
        except FileNotFoundError as error:
            return False, str(error)

        # 准备环境变量
        env = os.environ.copy()
        if ENV_FILE.exists():
            try:
                with open(ENV_FILE, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            k, v = line.split('=', 1)
                            env[k.strip()] = v.strip().strip('"').strip("'")
            except Exception as e:
                if on_error:
                    on_error(f"读取环境变量失败: {e}")

        active_account = get_active_account()
        if active_account:
            env['LANHU_COOKIE'] = active_account.get("cookie", "")
            env['LANHU_USER_NAME'] = active_account.get("name", "蓝湖用户")
            env['LANHU_USER_ROLE'] = active_account.get("role", "Developer")

        env['SERVER_PORT'] = str(port)
        env['MCP_TRANSPORT'] = 'http'

        ServiceManager._stop_event.clear()

        try:
            creation_flags = 0
            if sys.platform == 'win32':
                creation_flags = subprocess.CREATE_NO_WINDOW

            flog(f"启动 MCP 服务({server_source}): {' '.join(server_command)}")
            ServiceManager._process = subprocess.Popen(
                server_command,
                cwd=str(server_dir),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                creationflags=creation_flags,
            )
            ServiceManager._running = True
            ServiceManager._port = port

            # 读取输出线程
            def read_output() -> None:
                try:
                    for line in iter(ServiceManager._process.stdout.readline, b''):
                        if ServiceManager._stop_event.is_set():
                            break
                        if on_output:
                            decoded = line.decode('utf-8', errors='replace').rstrip('\n\r')
                            on_output(decoded)
                except Exception:
                    pass

            threading.Thread(target=read_output, daemon=True).start()

            # 等待启动（最多15秒）
            for i in range(30):
                time.sleep(0.5)
                if ServiceManager._stop_event.is_set():
                    return False, "已取消启动"
                if is_port_in_use(port):
                    return True, "服务已启动"

            # 检查进程是否退出
            if ServiceManager._process.poll() is not None:
                ServiceManager._running = False
                rc = ServiceManager._process.returncode
                return False, f"服务启动失败（进程退出码: {rc}，请检查日志）"

            return True, "服务启动中..."

        except OSError as e:
            ServiceManager._running = False
            return False, f"启动失败(权限/路径): {e}"
        except Exception as e:
            ServiceManager._running = False
            return False, f"启动失败: {type(e).__name__}: {e}"

    @staticmethod
    def stop() -> tuple[bool, str]:
        if ServiceManager._process is None:
            return False, "服务未运行"

        ServiceManager._stop_event.set()
        ServiceManager._running = False

        try:
            ServiceManager._process.terminate()
            try:
                ServiceManager._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                ServiceManager._process.kill()
                ServiceManager._process.wait(timeout=3)
        except Exception:
            try:
                ServiceManager._process.kill()
            except Exception:
                pass

        ServiceManager._process = None
        return True, "服务已停止"
