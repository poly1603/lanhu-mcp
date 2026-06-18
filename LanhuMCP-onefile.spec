# -*- mode: python ; coding: utf-8 -*-
"""
单文件打包配置 - GUI + Server 合并为一个 exe
"""
import sys
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# 收集 fastmcp 及其依赖的所有子模块和数据文件
fastmcp_hiddenimports = collect_submodules('fastmcp')
fastmcp_datas = collect_data_files('fastmcp')

mcp_hiddenimports = collect_submodules('mcp')

a = Analysis(
    ['lanhu_mcp_all.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('.env.example', '.'),
    ] + fastmcp_datas,
    hiddenimports=[
        # === 核心入口 ===
        'lanhu_mcp_server',
        'lanhu_mcp_all',

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
    ] + fastmcp_hiddenimports + mcp_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['hook_fastmcp_metadata.py'],
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
