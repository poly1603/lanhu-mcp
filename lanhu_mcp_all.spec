# -*- mode: python ; coding: utf-8 -*-
"""
单文件打包配置 - GUI + Server 合并
"""

a = Analysis(
    ['lanhu_mcp_all.py'],
    pathex=['.'],
    binaries=[],
    datas=[],
    hiddenimports=[
        # 核心MCP服务
        'lanhu_mcp_server',
        'lanhu_mcp',
        'lanhu_mcp.server',
        'lanhu_mcp.tools',
        'lanhu_mcp.core',
        'lanhu_mcp.converters',
        'lanhu_mcp.utils',
        'lanhu_mcp.prompts',
        # FastMCP及其依赖
        'fastmcp',
        'fastmcp.server',
        'fastmcp.utilities',
        'fastmcp.utilities.types',
        'fastmcp.server.dependencies',
        'fastmcp_slim',
        'fastmcp_slim.server',
        # HTTP客户端
        'httpx',
        'httpcore',
        'h11',
        # HTML解析
        'bs4',
        'bs4.builder',
        'lxml',
        'lxml.etree',
        'lxml._elementpath',
        # 环境变量
        'dotenv',
        # HTML压缩
        'htmlmin',
        # JSON Schema
        'jsonschema',
        'jsonschema_specifications',
        'referencing',
        # Starlette (FastMCP依赖)
        'starlette',
        'starlette.responses',
        'starlette.routing',
        'starlette.middleware',
        'starlette.websockets',
        # Uvicorn
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
        # Pydantic
        'pydantic',
        'pydantic_core',
        'pydantic_settings',
        # SSE
        'sse_starlette',
        # MCP协议
        'mcp',
        'mcp.client',
        'mcp.client.sse',
        'mcp.server',
        'mcp.server.sse',
        # Auth
        'authlib',
        'joserfc',
        # Watchfiles
        'watchfiles',
        # Websockets
        'websockets',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter.test',
        'unittest',
        'pytest',
        'PIL',
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
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
