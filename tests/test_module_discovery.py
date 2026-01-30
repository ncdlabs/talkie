"""Tests for modules.discovery: discover_modules, get_module_config_paths."""

from __future__ import annotations

from pathlib import Path

import pytest

from modules.discovery import (
    DEFAULT_CONFIG_FILENAME,
    MANIFEST_FILENAME,
    discover_modules,
    get_module_config_paths,
)


@pytest.fixture
def modules_root(tmp_path: Path) -> Path:
    """Create a temporary modules-like tree."""
    (tmp_path / "speech").mkdir()
    (tmp_path / "speech" / "config.yaml").write_text("audio: {}\n")
    (tmp_path / "rag").mkdir()
    (tmp_path / "rag" / "config.yaml").write_text("rag: {}\n")
    return tmp_path


def test_discover_modules_finds_subdirs_with_config(modules_root: Path) -> None:
    found = discover_modules(modules_root)
    names = [n for n, _ in found]
    assert "speech" in names
    assert "rag" in names
    assert len(found) == 2
    for name, config_path in found:
        assert config_path.is_file()
        assert config_path.name == "config.yaml"
        assert config_path.parent.name in ("speech", "rag")


def test_discover_modules_skips_dir_without_config(modules_root: Path) -> None:
    (modules_root / "no_config").mkdir()
    found = discover_modules(modules_root)
    names = [n for n, _ in found]
    assert "no_config" not in names


def test_discover_modules_skips_disabled_by_manifest(modules_root: Path) -> None:
    manifest = "name: speech\nenabled: false\n"
    (modules_root / "speech" / MANIFEST_FILENAME).write_text(manifest)
    found = discover_modules(modules_root)
    names = [n for n, _ in found]
    assert "speech" not in names
    assert "rag" in names


def test_discover_modules_uses_custom_config_file(modules_root: Path) -> None:
    (modules_root / "custom").mkdir()
    (modules_root / "custom" / "my_config.yaml").write_text("x: 1\n")
    manifest = "name: custom\nconfig_file: my_config.yaml\n"
    (modules_root / "custom" / MANIFEST_FILENAME).write_text(manifest)
    found = discover_modules(modules_root)
    names = [n for n, _ in found]
    assert "custom" in names
    custom_path = next(p for n, p in found if n == "custom")
    assert custom_path.name == "my_config.yaml"


def test_discover_modules_respects_order(modules_root: Path) -> None:
    (modules_root / "speech" / MANIFEST_FILENAME).write_text(
        "name: speech\norder: 20\n"
    )
    (modules_root / "rag" / MANIFEST_FILENAME).write_text("name: rag\norder: 10\n")
    found = discover_modules(modules_root)
    assert found[0][0] == "rag"
    assert found[1][0] == "speech"


def test_get_module_config_paths_returns_paths_only(modules_root: Path) -> None:
    paths = get_module_config_paths(modules_root)
    assert len(paths) == 2
    assert all(isinstance(p, Path) for p in paths)
    assert all(p.is_file() for p in paths)


def test_discover_modules_skips_pycache(modules_root: Path) -> None:
    (modules_root / "__pycache__").mkdir()
    found = discover_modules(modules_root)
    names = [n for n, _ in found]
    assert "__pycache__" not in names


def test_discover_modules_nonexistent_root_returns_empty() -> None:
    assert discover_modules(Path("/nonexistent/modules/path")) == []
    assert get_module_config_paths(Path("/nonexistent/modules/path")) == []


def test_constants() -> None:
    assert MANIFEST_FILENAME == "MODULE.yaml"
    assert DEFAULT_CONFIG_FILENAME == "config.yaml"
