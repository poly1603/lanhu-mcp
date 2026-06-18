# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['lanhu_mcp_all.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['lanhu_mcp_server', 'lanhu_mcp', 'lanhu_mcp.server', 'lanhu_mcp.tools', 'lanhu_mcp.tools.design_system', 'lanhu_mcp.tools.layout_spec', 'lanhu_mcp.tools.components', 'lanhu_mcp.tools.interactions', 'lanhu_mcp.tools.quality_check', 'lanhu_mcp.tools.code_gen', 'lanhu_mcp.tools.compare', 'lanhu_mcp.tools.batch_download', 'lanhu_mcp.tools.annotations', 'lanhu_mcp.tools.version_history', 'lanhu_mcp.tools.svg_extract', 'lanhu_mcp.tools.measurements', 'lanhu_mcp.tools.animation', 'lanhu_mcp.tools.export_options', 'lanhu_mcp.tools.responsive', 'lanhu_mcp.core', 'lanhu_mcp.converters', 'lanhu_mcp.utils', 'lanhu_mcp.prompts', 'fastmcp', 'fastmcp.server', 'fastmcp.utilities', 'fastmcp.utilities.types', 'httpx', 'httpcore', 'bs4', 'lxml', 'lxml.etree', 'dotenv', 'htmlmin', 'starlette', 'uvicorn', 'pydantic', 'pydantic_core', 'sse_starlette', 'mcp', 'mcp.client.sse', 'mcp.server.sse', 'authlib', 'joserfc', 'watchfiles', 'websockets', 'jsonschema', 'referencing', 'typer', 'ssl', 'certifi', 'charset_normalizer', 'idna'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter.test', 'unittest', 'pytest', 'PIL', 'matplotlib', 'numpy', 'pandas'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

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
