# -*- mode: python ; coding: utf-8 -*-
"""
单文件打包配置 - 命令行版 lanhu_mcp_server
打包入口: lanhu_mcp_app.py
输出: dist\LanhuMCP-CLI.exe
"""
import sys
import os
import sysconfig
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

PYTHON_BASE = Path(sys.base_prefix)
PYTHON_DLL_DIR = PYTHON_BASE / 'DLLs'

# 收集 fastmcp 及其依赖的所有子模块和数据文件
fastmcp_hiddenimports = collect_submodules('fastmcp')
fastmcp_datas = collect_data_files('fastmcp')
mcp_hiddenimports = collect_submodules('mcp')

# 收集 pydantic 子模块
pydantic_hiddenimports = collect_submodules('pydantic')
pydantic_core_hiddenimports = collect_submodules('pydantic_core')

a = Analysis(
    ['lanhu_mcp_app.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('.env.example', '.'),
        ('lanhu_login_helper.py', '.'),
        ('lanhu_mcp_server.py', '.'),
    ] + fastmcp_datas,
    hiddenimports=[
        # === 核心入口 ===
        'lanhu_mcp_server',
        'lanhu_mcp_app',
        'lanhu_login_helper',

        # === HTTP 客户端 ===
        'httpx',
        'httpcore',
        'h11',
        'http.cookiejar',
        'http.client',

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
        'pydantic.fields',
        'pydantic.main',
        'pydantic.types',

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

        # === importlib 元数据 ===
        'importlib.metadata',
        'importlib_metadata',

        # === Playwright ===
        'playwright',
        'playwright.async_api',

        # === 其他 ===
        'anyio',
        'anyio._backends',
        'anyio._backends._asyncio',
        'sniffio',
        'typing_extensions',
        'annotated_types',
        'click',
        'rich',
        'rich.console',
        'rich.table',
    ] + fastmcp_hiddenimports + mcp_hiddenimports + pydantic_hiddenimports + pydantic_core_hiddenimports,
    hookspath=['hook_fastmcp_metadata.py'],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
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
        'notebook',
        'PIL',
        'PIL.ImageTk',
        'pystray',
        'webview',
        'pythonnet',
        'clr',
        'clr_loader',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='LanhuMCP-CLI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[
        'python312.dll',
        'vcruntime140.dll',
        '_tkinter.pyd',
    ],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
