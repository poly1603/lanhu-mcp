# -*- mode: python ; coding: utf-8 -*-

import sys
import sysconfig
from pathlib import Path


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

a = Analysis(
    ['lanhu_mcp_gui.py'],
    pathex=[],
    binaries=tcl_tk_binaries,
    datas=[('lanhu_login_helper.py', '.')] + tcl_tk_datas,
    hiddenimports=['lanhu_mcp_server', 'lanhu_mcp_gui', 'lanhu_mcp_all', 'lanhu_mcp', 'lanhu_mcp.server', 'lanhu_mcp.tools', 'lanhu_mcp.tools.design_system', 'lanhu_mcp.tools.layout_spec', 'lanhu_mcp.tools.components', 'lanhu_mcp.tools.interactions', 'lanhu_mcp.tools.quality_check', 'lanhu_mcp.tools.code_gen', 'lanhu_mcp.tools.compare', 'lanhu_mcp.tools.batch_download', 'lanhu_mcp.tools.annotations', 'lanhu_mcp.tools.version_history', 'lanhu_mcp.tools.svg_extract', 'lanhu_mcp.tools.measurements', 'lanhu_mcp.tools.animation', 'lanhu_mcp.tools.export_options', 'lanhu_mcp.tools.responsive', 'lanhu_mcp.core', 'lanhu_mcp.converters', 'lanhu_mcp.utils', 'lanhu_mcp.prompts', 'fastmcp', 'fastmcp.server', 'fastmcp.utilities', 'fastmcp.utilities.types', 'httpx', 'httpcore', 'bs4', 'lxml', 'lxml.etree', 'dotenv', 'htmlmin', 'starlette', 'uvicorn', 'pydantic', 'pydantic_core', 'sse_starlette', 'mcp', 'mcp.client.sse', 'authlib', 'joserfc', 'watchfiles', 'websockets', 'jsonschema', 'referencing', 'typer', 'ssl', 'certifi', 'charset_normalizer', 'idna', 'webview', 'webview.platforms.winforms', 'webview.platforms.edgechromium', 'webview.platforms.mshtml', 'pythonnet', 'clr', 'clr_loader', 'clr_loader.netfx', 'clr_loader.hostfxr', 'clr_loader.ffi', 'tkinter', 'tkinter.ttk', 'tkinter.messagebox'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['hook_tcl_find_executable.py'],
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
