"""
PyInstaller runtime hook:
1. patch importlib.metadata.version so fastmcp can import even when .dist-info is missing
2. patch logging.config.dictConfig so uvicorn's formatter resolution works in frozen env
"""
import importlib.metadata
import logging
import logging.config

# --- 1. Patch importlib.metadata.version ---
_original_version = importlib.metadata.version

def _patched_version(name):
    try:
        return _original_version(name)
    except importlib.metadata.PackageNotFoundError:
        return "0.0.0"

importlib.metadata.version = _patched_version


# --- 2. Patch logging.config.dictConfig ---
# In frozen env, uvicorn's dictConfig uses "()" factory syntax which fails
# because the class reference can't be resolved. Patch to handle gracefully.
_original_dictConfig = logging.config.dictConfig

def _safe_dictConfig(config):
    """dictConfig that replaces factory-style formatters with plain Formatters."""
    if isinstance(config, dict) and 'formatters' in config:
        for name, fmt_cfg in config['formatters'].items():
            if '()' in fmt_cfg:
                # Replace factory-based formatter with basic formatter
                fmt_str = fmt_cfg.get('fmt', '%(message)s')
                fmt_cfg.clear()
                fmt_cfg['format'] = fmt_str
    try:
        return _original_dictConfig(config)
    except (ValueError, KeyError, TypeError):
        pass

logging.config.dictConfig = _safe_dictConfig
