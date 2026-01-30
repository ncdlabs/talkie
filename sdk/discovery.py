"""
Module discovery: find all modules under a modules root and their config paths.
A module is a subdirectory that contains config.yaml (or the file named in MODULE.yaml).
Optional MODULE.yaml manifest: name, description, enabled, order, config_file.
Callers must pass modules_root (e.g. project_root / "modules"); no default to avoid wrong paths.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

MANIFEST_FILENAME = "MODULE.yaml"
DEFAULT_CONFIG_FILENAME = "config.yaml"


def _load_manifest(module_dir: Path) -> dict[str, Any]:
    """Load MODULE.yaml from module_dir. Returns {} if missing or invalid."""
    from config import load_yaml_file

    path = module_dir / MANIFEST_FILENAME
    data = load_yaml_file(path)
    if not data and path.exists():
        logger.debug("Could not load %s (invalid or empty)", path)
    return data


def discover_modules(modules_root: Path) -> list[tuple[str, Path]]:
    """
    Discover modules under modules_root. A module is a subdirectory that contains
    config.yaml (or the config_file from MODULE.yaml) and is not disabled.

    Args:
        modules_root: Path to the modules directory (e.g. project_root / "modules").

    Returns:
        List of (module_name, config_path) sorted by manifest order then directory name.
    """
    if not modules_root.is_dir():
        return []

    result: list[
        tuple[str, str, int, Path]
    ] = []  # (name, sort_key, order, config_path)

    for candidate in sorted(modules_root.iterdir()):
        if not candidate.is_dir():
            continue
        if candidate.name.startswith(".") or candidate.name == "__pycache__":
            continue
        manifest = _load_manifest(candidate)
        if manifest.get("enabled") is False:
            continue
        config_file = manifest.get("config_file") or DEFAULT_CONFIG_FILENAME
        config_path = candidate / config_file
        if not config_path.is_file():
            continue
        name = manifest.get("name") or candidate.name
        order = (
            int(manifest.get("order", 0))
            if isinstance(manifest.get("order"), (int, float))
            else 0
        )
        result.append((name, candidate.name, order, config_path))

    result.sort(key=lambda x: (x[2], x[1]))
    return [(name, config_path) for name, _sk, _order, config_path in result]


def get_module_config_paths(modules_root: Path) -> list[Path]:
    """
    Return ordered list of config file paths for discovered modules (for config merge).

    Args:
        modules_root: Path to the modules directory.
    """
    return [path for _name, path in discover_modules(modules_root)]
