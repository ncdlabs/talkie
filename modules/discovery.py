"""
Re-export module discovery from the SDK.
Provides backward-compatible default for modules_root (this package's parent directory).
"""

from __future__ import annotations

from pathlib import Path

from sdk.discovery import (
    DEFAULT_CONFIG_FILENAME,
    MANIFEST_FILENAME,
    discover_modules as _discover_modules,
    get_module_config_paths as _get_module_config_paths,
)


def discover_modules(modules_root: Path | None = None) -> list[tuple[str, Path]]:
    """Discover modules; if modules_root is None, use the modules/ directory next to this file."""
    if modules_root is None:
        modules_root = Path(__file__).resolve().parent
    return _discover_modules(modules_root)


def get_module_config_paths(modules_root: Path | None = None) -> list[Path]:
    """Return ordered config paths; if modules_root is None, use the modules/ directory next to this file."""
    if modules_root is None:
        modules_root = Path(__file__).resolve().parent
    return _get_module_config_paths(modules_root)


__all__ = [
    "DEFAULT_CONFIG_FILENAME",
    "MANIFEST_FILENAME",
    "discover_modules",
    "get_module_config_paths",
]
