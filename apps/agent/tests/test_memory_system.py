"""Unit tests for YANA Phase 09 local memory system, privacy safeguards, and migrations."""

import asyncio
from pathlib import Path

import pytest

from app.errors import ValidationError
from app.memory.db import DatabaseManager
from app.memory.memory_manager import MemoryManager
from app.memory.models import MemoryCategory, MemoryType
from app.memory.privacy import (
    contains_credentials,
    redact_credentials,
    sanitize_memory_content,
    sanitize_memory_metadata,
)


@pytest.fixture
async def temp_db(tmp_path: Path) -> DatabaseManager:
    """Fixture providing an isolated SQLite database with migrations applied."""
    db_file = tmp_path / "test_memory.db"
    mgr = DatabaseManager(db_path=db_file)
    await mgr.initialize()
    return mgr


@pytest.fixture
def memory_mgr(temp_db: DatabaseManager) -> MemoryManager:
    """Fixture providing a fresh MemoryManager connected to temp_db."""
    return MemoryManager(db=temp_db)


# =============================================================================
# 1. Temporary Context (Ephemeral RAM with TTL)
# =============================================================================


@pytest.mark.asyncio
async def test_temporary_context_ttl(memory_mgr: MemoryManager) -> None:
    # Set item with short TTL
    memory_mgr.set_temp("working_file", "app/main.py", ttl_seconds=0.1)
    assert memory_mgr.get_temp("working_file") == "app/main.py"

    # Set item without TTL
    memory_mgr.set_temp("active_task", "Refactor memory")
    assert memory_mgr.get_temp("active_task") == "Refactor memory"

    # Sleep past expiration
    await asyncio.sleep(0.15)
    assert memory_mgr.get_temp("working_file") is None
    assert memory_mgr.get_temp("active_task") == "Refactor memory"

    # Clear temp
    memory_mgr.clear_temp()
    assert memory_mgr.get_temp("active_task") is None


# =============================================================================
# 2. General Memory CRUD & Search (Session vs Long-Term)
# =============================================================================


@pytest.mark.asyncio
async def test_memory_lifecycle_and_selective_persistence(memory_mgr: MemoryManager) -> None:
    # 1. Create session memory (scoped to conversation)
    sess_item = await memory_mgr.create_memory(
        key="temp_user_goal",
        content="Debug failing playwright tests in CI",
        memory_type=MemoryType.SESSION,
        category=MemoryCategory.GENERAL,
        session_id="session-123",
        tags=["ci", "tests"],
    )
    assert sess_item.id is not None
    assert sess_item.memory_type == MemoryType.SESSION
    assert sess_item.session_id == "session-123"

    # 2. Create long-term memory (persistent knowledge)
    long_item = await memory_mgr.create_memory(
        key="preferred_test_runner",
        content="Use pytest for backend and vitest for desktop",
        memory_type=MemoryType.LONG_TERM,
        category=MemoryCategory.PREFERENCE,
        tags=["testing", "preferences"],
    )
    assert long_item.memory_type == MemoryType.LONG_TERM

    # 3. Search memories by keyword
    search_results = await memory_mgr.search_memories(query="playwright")
    assert len(search_results) == 1
    assert search_results[0].id == sess_item.id

    # Filter search by memory type
    long_results = await memory_mgr.search_memories(
        query="test",
        memory_type=MemoryType.LONG_TERM,
    )
    assert len(long_results) == 1
    assert long_results[0].id == long_item.id

    # 4. Update memory
    updated = await memory_mgr.update_memory(
        memory_id=long_item.id,
        content="Use pytest with coverage for backend",
        tags=["testing", "coverage"],
    )
    assert updated is not None
    assert updated.content == "Use pytest with coverage for backend"
    assert "coverage" in updated.tags

    # 5. Selective persistence invariant: verify bulk forget removes session memory
    del_count = await memory_mgr.forget_all(session_id="session-123")
    assert del_count == 1
    assert await memory_mgr.get_memory(sess_item.id) is None
    # Long term memory is preserved
    assert await memory_mgr.get_memory(long_item.id) is not None

    # Clean up long term
    forgot = await memory_mgr.forget_memory(long_item.id)
    assert forgot is True
    assert await memory_mgr.get_memory(long_item.id) is None


# =============================================================================
# 3. Project Memory Domain (e.g. IntelliRepo)
# =============================================================================


@pytest.mark.asyncio
async def test_project_memory_domain(memory_mgr: MemoryManager) -> None:
    # Save project IntelliRepo
    proj = await memory_mgr.save_project(
        name="IntelliRepo",
        path="C:\\Projects\\IntelliRepo",
        technology="Python / FastAPI",
        description="Local intelligent repository indexing assistant",
        metadata={"gitBranch": "main", "hasDocker": True},
    )
    assert proj.id is not None
    assert proj.name == "IntelliRepo"
    assert proj.path == "C:\\Projects\\IntelliRepo"
    assert proj.technology == "Python / FastAPI"
    assert proj.metadata["hasDocker"] is True

    # Retrieve project
    retrieved = await memory_mgr.get_project("IntelliRepo")
    assert retrieved is not None
    assert retrieved.name == "IntelliRepo"
    assert retrieved.description == "Local intelligent repository indexing assistant"

    # Search projects
    searched = await memory_mgr.search_projects("indexing")
    assert len(searched) == 1
    assert searched[0].name == "IntelliRepo"

    # List projects
    projs = await memory_mgr.list_projects()
    assert len(projs) == 1

    # Forget project
    assert await memory_mgr.forget_project("IntelliRepo") is True
    assert await memory_mgr.get_project("IntelliRepo") is None


# =============================================================================
# 4. Application Memory Domain
# =============================================================================


@pytest.mark.asyncio
async def test_application_memory_domain(memory_mgr: MemoryManager) -> None:
    app_mem = await memory_mgr.save_application(
        name="Visual Studio Code",
        executable_path="C:\\Users\\ramuv\\AppData\\Local\\Programs\\Microsoft VS Code\\Code.exe",
        category="editor",
        metadata={"cli": "code"},
    )
    assert app_mem.id is not None
    assert app_mem.name == "Visual Studio Code"

    # Retrieve
    fetched = await memory_mgr.get_application("Visual Studio Code")
    assert fetched is not None
    assert fetched.category == "editor"
    assert fetched.metadata["cli"] == "code"

    # List
    apps = await memory_mgr.list_applications(category="editor")
    assert len(apps) == 1

    # Forget
    assert await memory_mgr.forget_application("Visual Studio Code") is True
    assert await memory_mgr.get_application("Visual Studio Code") is None


# =============================================================================
# 5. User Preferences Domain
# =============================================================================


@pytest.mark.asyncio
async def test_user_preferences_domain(memory_mgr: MemoryManager) -> None:
    pref = await memory_mgr.set_preference(
        key="theme",
        value={"mode": "dark", "accent": "sky"},
        category="ui",
    )
    assert pref.key == "theme"

    val = await memory_mgr.get_preference("theme")
    assert val == {"mode": "dark", "accent": "sky"}

    prefs = await memory_mgr.list_preferences(category="ui")
    assert len(prefs) == 1
    assert prefs[0].key == "theme"

    assert await memory_mgr.forget_preference("theme") is True
    assert await memory_mgr.get_preference("theme") is None


# =============================================================================
# 6. Workflow Memory Domain
# =============================================================================


@pytest.mark.asyncio
async def test_workflow_memory_domain(memory_mgr: MemoryManager) -> None:
    wf = await memory_mgr.save_workflow(
        name="daily_standup_prep",
        trigger="every weekday morning",
        steps=[
            {"step": 1, "tool": "git.status", "description": "Check git uncommitted changes"},
            {"step": 2, "tool": "terminal.execute", "command": "git log --oneline -5"},
        ],
        description="Summarize yesterday work and branch state",
    )
    assert wf.id is not None
    assert wf.name == "daily_standup_prep"
    assert len(wf.steps) == 2

    workflows = await memory_mgr.list_workflows()
    assert len(workflows) == 1
    assert workflows[0].name == "daily_standup_prep"

    assert await memory_mgr.forget_workflow("daily_standup_prep") is True
    assert len(await memory_mgr.list_workflows()) == 0


# =============================================================================
# 7. Privacy Safeguards & Credential Redaction
# =============================================================================


def test_privacy_credential_detection() -> None:
    # Test detectors
    assert contains_credentials("Here is my key: sk-proj-1234567890abcdef1234567890")
    assert contains_credentials("Anthropic key: sk-ant-api03-abcdef1234567890abcdef")
    assert contains_credentials("GitHub token: ghp_1234567890abcdef1234567890abcdef")
    assert contains_credentials("Slack: xoxb-1234567890-1234567890123-abcdefghijklmnop")
    assert contains_credentials("AWS: AKIAIOSFODNN7EXAMPLE")
    assert contains_credentials("Password assignment: password = 'SuperSecretPassword123!'")
    assert not contains_credentials("Normal safe developer note about sqlite database.")


def test_privacy_redaction_and_sanitization() -> None:
    leaked_text = (
        "Project setup: export OPENAI_API_KEY=sk-proj-1234567890abcdef1234567890 and "
        "password = 'MySecretPassword123'"
    )
    redacted = redact_credentials(leaked_text)
    assert "sk-proj" not in redacted
    assert "MySecretPassword123" not in redacted
    assert "[REDACTED_" in redacted

    # Test sanitize_memory_content non-strict
    clean = sanitize_memory_content(leaked_text, strict=False)
    assert "[REDACTED_" in clean

    # Test sanitize_memory_content strict mode raises ValidationError
    with pytest.raises(ValidationError, match="Memory contains raw credentials"):
        sanitize_memory_content(leaked_text, strict=True)

    # Test metadata sanitization
    meta = {
        "user": "developer",
        "api_token": "ghp_1234567890abcdef1234567890abcdef",
        "safe_flag": True,
    }
    clean_meta = sanitize_memory_metadata(meta, strict=False)
    assert clean_meta["user"] == "developer"
    assert clean_meta["safe_flag"] is True
    assert "[REDACTED_" in clean_meta["api_token"]


@pytest.mark.asyncio
async def test_memory_manager_redacts_credentials_on_create(
    memory_mgr: MemoryManager,
) -> None:
    # Save memory containing a secret
    item = await memory_mgr.create_memory(
        key="aws_config_note",
        content="Connecting using AWS access key AKIAIOSFODNN7EXAMPLE in us-east-1",
        tags=["aws", "config"],
        metadata={"token": "ghp_1234567890abcdef1234567890abcdef"},
    )
    # Content and metadata must be sanitized in SQLite
    assert "AKIAIOSFODNN7EXAMPLE" not in item.content
    assert "[REDACTED_CREDENTIAL]" in item.content
    assert "[REDACTED_CREDENTIAL]" in item.metadata["token"]


# =============================================================================
# 8. Database Versioned Migrations
# =============================================================================


@pytest.mark.asyncio
async def test_database_migrations_step_by_step(tmp_path: Path) -> None:
    db_file = tmp_path / "migration_test.db"
    db = DatabaseManager(db_path=db_file)

    # 1. Apply Migration 1 only
    await db.initialize(target_version=1)
    async with db.get_connection() as conn:
        cursor = await conn.execute("SELECT MAX(version) as version FROM schema_version")
        row = await cursor.fetchone()
        assert row is not None
        assert row["version"] == 1

        # Check migration 1 tables exist
        c_tasks = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='tasks'"
        )
        assert await c_tasks.fetchone() is not None

        c_conv = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='conversations'"
        )
        assert await c_conv.fetchone() is not None

        # Check migration 2 tables DO NOT exist yet
        c_mem = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='memories'"
        )
        assert await c_mem.fetchone() is None

    # 2. Apply Migration 2
    await db.initialize(target_version=2)
    async with db.get_connection() as conn:
        cursor = await conn.execute("SELECT MAX(version) as version FROM schema_version")
        row = await cursor.fetchone()
        assert row is not None
        assert row["version"] == 2

        # Check migration 2 tables now exist
        c_mem = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='memories'"
        )
        assert await c_mem.fetchone() is not None

        c_proj = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='project_memories'"
        )
        assert await c_proj.fetchone() is not None

        c_apps = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='application_memories'"
        )
        assert await c_apps.fetchone() is not None
