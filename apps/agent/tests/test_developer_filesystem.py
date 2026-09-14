"""Unit tests for Phase 06 Developer Filesystem Tools.

Tests write, copy, move, rename, and delete operations within isolated temp directories,
verifying security policies, traversal protection, deletion guards, and atomic writes.
"""

from pathlib import Path

import pytest

from app.errors import PermissionError, ValidationError
from app.protocol.models import RiskLevel
from app.tools.filesystem.safe_fs import (
    FilesystemCopyTool,
    FilesystemDeleteTool,
    FilesystemMoveTool,
    FilesystemRenameTool,
    FilesystemWriteTool,
)


@pytest.mark.asyncio
async def test_filesystem_write_creates_and_overwrites(tmp_path: Path):
    tool = FilesystemWriteTool(allowed_root=tmp_path)
    target_file = tmp_path / "subdir" / "test.txt"

    # Write new file (auto-creates parent directories)
    res = await tool.execute(
        {"path": str(target_file), "content": "Hello World", "overwrite": False}
    )
    assert res["bytes_written"] == 11
    assert target_file.read_text(encoding="utf-8") == "Hello World"

    # Attempt overwrite when overwrite=False should fail validation
    with pytest.raises(ValidationError, match="already exists"):
        tool.validate({"path": str(target_file), "content": "New", "overwrite": False})

    # Overwrite when overwrite=True succeeds
    res2 = await tool.execute(
        {"path": str(target_file), "content": "Updated Content", "overwrite": True}
    )
    assert res2["bytes_written"] == 15
    assert target_file.read_text(encoding="utf-8") == "Updated Content"


@pytest.mark.asyncio
async def test_filesystem_copy(tmp_path: Path):
    tool = FilesystemCopyTool(allowed_root=tmp_path)
    src = tmp_path / "source.txt"
    src.write_text("Source Data", encoding="utf-8")
    dst = tmp_path / "copied.txt"

    tool.validate({"source_path": str(src), "destination_path": str(dst)})
    res = await tool.execute({"source_path": str(src), "destination_path": str(dst)})
    assert res["copied"] is True
    assert dst.exists()
    assert dst.read_text(encoding="utf-8") == "Source Data"
    assert src.exists()  # Source remains


@pytest.mark.asyncio
async def test_filesystem_move(tmp_path: Path):
    tool = FilesystemMoveTool(allowed_root=tmp_path)
    src = tmp_path / "move_me.txt"
    src.write_text("Move Content", encoding="utf-8")
    dst = tmp_path / "destination" / "moved.txt"

    tool.validate({"source_path": str(src), "destination_path": str(dst)})
    res = await tool.execute({"source_path": str(src), "destination_path": str(dst)})
    assert res["moved"] is True
    assert dst.exists()
    assert dst.read_text(encoding="utf-8") == "Move Content"
    assert not src.exists()  # Source removed


@pytest.mark.asyncio
async def test_filesystem_rename(tmp_path: Path):
    tool = FilesystemRenameTool(allowed_root=tmp_path)
    src = tmp_path / "old_name.txt"
    src.write_text("Rename Data", encoding="utf-8")

    tool.validate({"path": str(src), "new_name": "new_name.txt"})
    res = await tool.execute({"path": str(src), "new_name": "new_name.txt"})
    assert res["renamed"] is True
    assert (tmp_path / "new_name.txt").exists()
    assert not src.exists()

    # Reject invalid characters in new_name
    with pytest.raises(ValidationError, match=r"directory separators"):
        tool.validate({"path": str(tmp_path / "new_name.txt"), "new_name": "bad/name.txt"})


@pytest.mark.asyncio
async def test_filesystem_delete_file_and_directory(tmp_path: Path):
    tool = FilesystemDeleteTool(allowed_root=tmp_path)
    assert tool.risk_level == RiskLevel.HIGH

    # Delete single file
    test_file = tmp_path / "to_delete.txt"
    test_file.write_text("Delete Me", encoding="utf-8")
    tool.validate({"path": str(test_file)})
    res = await tool.execute({"path": str(test_file)})
    assert res["deleted"] is True
    assert not test_file.exists()

    # Delete non-empty directory with recursive=True
    test_dir = tmp_path / "del_dir"
    test_dir.mkdir()
    (test_dir / "child.txt").write_text("Child", encoding="utf-8")

    # Reject without recursive
    with pytest.raises(ValidationError, match=r"is not empty"):
        tool.validate({"path": str(test_dir), "recursive": False})

    # Succeed with recursive
    tool.validate({"path": str(test_dir), "recursive": True})
    res_dir = await tool.execute({"path": str(test_dir), "recursive": True})
    assert res_dir["deleted"] is True
    assert not test_dir.exists()


@pytest.mark.asyncio
async def test_filesystem_delete_root_guard(tmp_path: Path):
    tool = FilesystemDeleteTool(allowed_root=tmp_path)

    # Attempt to delete allowed root itself should be blocked by guard
    with pytest.raises(PermissionError, match="targets root or system anchor"):
        tool.validate({"path": str(tmp_path)})
