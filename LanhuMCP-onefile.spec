# -*- mode: python ; coding: utf-8 -*-
"""
单文件打包配置 - GUI + Server 合并为一个 exe
"""
import sys
import os
import sysconfig
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules


def collect_runtime_tree(source: Path, target: str) -> list[tuple[str, str]]:
    """把目录递归转换为 PyInstaller datas。"""
    root = Path(source)
    if not root.exists():
        return []
    return [(str(path), str(Path(target) / path.relative_to(root).parent)) for path in root.rglob('*') if path.is_file()]


PYTHON_BASE = Path(sys.base_prefix)
PYTHON_DLL_DIR = PYTHON_BASE / 'DLLs'
TCL_ROOT = PYTHON_BASE / 'tcl'
TKINTER_ROOT = Path(sysconfig.get_path('stdlib')) / 'tkinter'

tcl_tk_datas = (
    collect_runtime_tree(TCL_ROOT / 'tcl8.6', '_tcl_data')
    + collect_runtime_tree(TCL_ROOT / 'tk8.6', '_tk_data')
    + collect_runtime_tree(TCL_ROOT / 'tcl8', 'tcl8')
    + collect_runtime_tree(TKINTER_ROOT, 'tkinter')
)
tcl_tk_binaries = [
    (str(path), '.') for path in [
        PYTHON_DLL_DIR / '_tkinter.pyd',
        PYTHON_DLL_DIR / 'tcl86t.dll',
        PYTHON_DLL_DIR / 'tk86t.dll',
    ] if path.exists()
]

# 收集 fastmcp 及其依赖的所有子模块和数据文件
fastmcp_hiddenimports = collect_submodules('fastmcp')
fastmcp_datas = collect_data_files('fastmcp')

mcp_hiddenimports = collect_submodules('mcp')

# 收集 flet（新的 Flet GUI 依赖）。flet 未安装时不阻断 server/CLI 打包。
try:
    flet_hiddenimports = collect_submodules('flet')
    flet_datas = collect_data_files('flet')
except Exception:
    flet_hiddenimports = []
    flet_datas = []

a = Analysis(
    ['lanhu_mcp_gui.py'],
    pathex=['.'],
    binaries=tcl_tk_binaries,
    datas=[
        ('.env.example', '.'),
        ('lanhu_login_helper.py', '.'),
    ] + fastmcp_datas + tcl_tk_datas + flet_datas,
    hiddenimports=[
        # === 核心入口 ===
        'lanhu_mcp_server',
        'lanhu_login_helper',
        'lanhu_mcp_gui',

        # === pywebview ===
        'webview',
        'webview.platforms.winforms',
        'webview.platforms.edgechromium',
        'webview.platforms.mshtml',
        'pythonnet',
        'clr',
        'clr_loader',
        'clr_loader.netfx',
        'clr_loader.hostfxr',
        'clr_loader.ffi',

        # === Tkinter GUI ===
        'tkinter',
        'tkinter.ttk',
        'tkinter.messagebox',
        'PIL',
        'PIL.Image',
        'PIL.ImageTk',

        # === lanhu_mcp 子包 ===
        'lanhu_mcp',
        'lanhu_mcp.server',
        'lanhu_mcp.tools',
        'lanhu_mcp.tools.design_system',
        'lanhu_mcp.tools.layout_spec',
        'lanhu_mcp.tools.components',
        'lanhu_mcp.tools.interactions',
        'lanhu_mcp.tools.quality_check',
        'lanhu_mcp.tools.code_gen',
        'lanhu_mcp.tools.compare',
        'lanhu_mcp.tools.batch_download',
        'lanhu_mcp.tools.annotations',
        'lanhu_mcp.tools.version_history',
        'lanhu_mcp.tools.svg_extract',
        'lanhu_mcp.tools.measurements',
        'lanhu_mcp.tools.animation',
        'lanhu_mcp.tools.export_options',
        'lanhu_mcp.tools.responsive',
        'lanhu_mcp.core',
        'lanhu_mcp.core.paths',
        'lanhu_mcp.core.accounts',
        'lanhu_mcp.core.projects',
        'lanhu_mcp.core.avatar',
        'lanhu_mcp.services',
        'lanhu_mcp.services.tools_registry',
        'lanhu_mcp.services.lanhu_api',
        'lanhu_mcp.services.ide_config',
        'lanhu_mcp.services.service_manager',

        # === lanhu_mcp.gui（Flet 界面）===
        'lanhu_mcp.gui',
        'lanhu_mcp.gui.theme',
        'lanhu_mcp.gui.state',
        'lanhu_mcp.gui.app',
        'lanhu_mcp.gui.components',
        'lanhu_mcp.gui.components.widgets',
        'lanhu_mcp.gui.pages',
        'lanhu_mcp.gui.pages.overview',
        'lanhu_mcp.gui.pages.service',
        'lanhu_mcp.gui.pages.accounts',
        'lanhu_mcp.gui.pages.projects',
        'lanhu_mcp.gui.pages.ide_tools',
        'lanhu_mcp.gui.pages.logs',

        'lanhu_mcp.converters',
        'lanhu_mcp.utils',
        'lanhu_mcp.prompts',

        # === HTTP 客户端 ===
        'httpx',
        'httpcore',
        'h11',

        # === HTML 解析 ===
        'bs4',
        'bs4.builder',
        'lxml',
        'lxml.etree',
        'lxml._elementpath',

        # === 环境变量 ===
        'dotenv',

        # === HTML 压缩 ===
        'htmlmin',

        # === JSON Schema ===
        'jsonschema',
        'jsonschema_specifications',
        'referencing',

        # === Starlette ===
        'starlette',
        'starlette.responses',
        'starlette.routing',
        'starlette.middleware',
        'starlette.websockets',

        # === Uvicorn ===
        'uvicorn',
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',

        # === Pydantic ===
        'pydantic',
        'pydantic_core',
        'pydantic_settings',

        # === SSE ===
        'sse_starlette',

        # === Auth ===
        'authlib',
        'joserfc',

        # === Watchfiles ===
        'watchfiles',

        # === Websockets ===
        'websockets',

        # === 网络相关 ===
        'ssl',
        'certifi',
        'charset_normalizer',
        'idna',

        # === importlib 元数据（关键！fastmcp 需要） ===
        'importlib.metadata',
        'importlib_metadata',
    ] + fastmcp_hiddenimports + mcp_hiddenimports + flet_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['hook_tcl_find_executable.py', 'hook_fastmcp_metadata.py'],
    excludes=[
        'tkinter.test',
        'unittest',
        'pytest',
        '_pytest',
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'IPython',
        'jupyter',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='LanhuMCP',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
