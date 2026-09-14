"""Unit tests for Filesystem Tools (read, search, create_directory) and Safety Invariants."""

from pathlib import Path

import pytest

from app.errors import PermissionError, ValidationError
from app.tools.filesystem.safe_fs import (
    FilesystemCreateDirectoryTool,
    FilesystemReadTool,
    FilesystemSearchTool,
)
from app.tools.registry import registry


@pytest.fixture
def read_tool(tmp_path: Path) -> FilesystemReadTool:
    return FilesystemReadTool(allowed_root=tmp_path)


@pytest.fixture
def search_tool(tmp_path: Path) -> FilesystemSearchTool:
    return FilesystemSearchTool(allowed_root=tmp_path)


@pytest.fixture
def mkdir_tool(tmp_path: Path) -> FilesystemCreateDirectoryTool:
    return FilesystemCreateDirectoryTool(allowed_root=tmp_path)


# ============================================================================
# filesystem.read Tests
# ============================================================================


def test_fs_read_validation_missing_path(read_tool: FilesystemReadTool) -> None:
    with pytest.raises(ValidationError, match="Missing required argument 'path'"):
        read_tool.validate({})


def test_fs_read_path_traversal_blocked(read_tool: FilesystemReadTool) -> None:
    with pytest.raises(PermissionError, match="Path traversal blocked"):
        read_tool.validate({"path": "../../Windows/System32/config/SAM"})


def test_fs_read_sensitive_paths_blocked(read_tool: FilesystemReadTool, tmp_path: Path) -> None:
    # Create simulated sensitive file
    ssh_key = tmp_path / "id_rsa"
    ssh_key.write_text("PRIVATE KEY")

    with pytest.raises(PermissionError, match="targets a protected or sensitive location"):
        read_tool.validate({"path": str(ssh_key)})


def test_fs_read_directory_rejected(read_tool: FilesystemReadTool, tmp_path: Path) -> None:
    sub = tmp_path / "subdir"
    sub.mkdir()
    with pytest.raises(ValidationError, match="is a directory, not a file"):
        read_tool.validate({"path": str(sub)})


@pytest.mark.asyncio
async def test_fs_read_execution_and_verify(read_tool: FilesystemReadTool, tmp_path: Path) -> None:
    test_file = tmp_path / "sample.txt"
    test_file.write_text("Hello YANA Phase 04 Safe Filesystem!", encoding="utf-8")

    result = await read_tool.execute({"path": str(test_file)})

    assert result["path"] == str(test_file.resolve())
    assert result["content"] == "Hello YANA Phase 04 Safe Filesystem!"
    assert result["size_bytes"] > 0
    assert result["truncated"] is False

    # Verification
    v = await read_tool.verify({"path": str(test_file)}, result)
    assert v.verified is True


# ============================================================================
# filesystem.search Tests
# ============================================================================


def test_fs_search_validation_nonexistent(search_tool: FilesystemSearchTool) -> None:
    with pytest.raises(ValidationError, match="Path does not exist"):
        search_tool.validate({"path": "completely_invalid_dir_12345"})


@pytest.mark.asyncio
async def test_fs_search_execution(search_tool: FilesystemSearchTool, tmp_path: Path) -> None:
    # Setup test file tree
    (tmp_path / "doc1.txt").write_text("doc 1")
    (tmp_path / "doc2.log").write_text("doc 2")
    sub = tmp_path / "nested"
    sub.mkdir()
    (sub / "nested_doc.txt").write_text("nested")

    # Search for *.txt
    result = await search_tool.execute({"path": str(tmp_path), "pattern": "*.txt"})

    assert result["total_matches"] == 2
    matched_names = {r["name"] for r in result["results"]}
    assert "doc1.txt" in matched_names
    assert "nested_doc.txt" in matched_names
    assert "doc2.log" not in matched_names

    # Verification
    v = await search_tool.verify({"path": str(tmp_path)}, result)
    assert v.verified is True


# ============================================================================
# filesystem.create_directory Tests
# ============================================================================


def test_fs_mkdir_validation_root_denied(mkdir_tool: FilesystemCreateDirectoryTool) -> None:
    with pytest.raises(PermissionError):
        mkdir_tool.validate({"path": "C:\\Windows\\System32\\dangerous_dir"})


@pytest.mark.asyncio
async def test_fs_mkdir_execution(
    mkdir_tool: FilesystemCreateDirectoryTool, tmp_path: Path
) -> None:
    target_new_dir = tmp_path / "new_project" / "assets"
    assert not target_new_dir.exists()

    result = await mkdir_tool.execute({"path": str(target_new_dir)})

    assert result["status"] == "created"
    assert target_new_dir.is_dir()

    # Verification
    v = await mkdir_tool.verify({"path": str(target_new_dir)}, result)
    assert v.verified is True


# ============================================================================
# Deletion Constraint Test
# ============================================================================


def test_filesystem_deletion_tool_is_protected_high_risk() -> None:
    """Strictly verify that file deletion is protected behind HIGH risk level."""
    from app.tools import register_default_tools

    register_default_tools(registry)
    del_tool = registry.get("filesystem.delete")
    assert del_tool is not None
    assert del_tool.risk_level.value == "HIGH"
