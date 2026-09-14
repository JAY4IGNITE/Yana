"""Integration tests for YANA Phase 09 memory REST API routes."""

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.memory.db import db_manager


@pytest.fixture(autouse=True)
async def init_test_db(tmp_path: Path) -> None:
    # Initialize the database manager schema before running route tests
    await db_manager.initialize()


@pytest.mark.asyncio
async def test_memory_routes_full_lifecycle() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Create a memory item (with credential leak to test auto-redaction)
        create_res = await ac.post(
            "/api/memory",
            json={
                "key": "test_api_note",
                "content": (
                    "Service config using OpenAI sk-proj-1234567890abcdef1234567890 "
                    "for test automation"
                ),
                "memoryType": "session",
                "category": "general",
                "sessionId": "sess-test-456",
                "tags": ["integration", "testing"],
                "metadata": {"token": "ghp_1234567890abcdef1234567890abcdef"},
            },
        )
        assert create_res.status_code == 201
        created = create_res.json()
        mem_id = created["id"]
        assert created["key"] == "test_api_note"
        # Secret must be redacted
        assert "sk-proj" not in created["content"]
        assert "[REDACTED_CREDENTIAL]" in created["content"]
        assert "[REDACTED_CREDENTIAL]" in created["metadata"]["token"]

        # 2. Search memories
        search_res = await ac.get("/api/memory/search", params={"q": "automation"})
        assert search_res.status_code == 200
        found = search_res.json()
        assert len(found) >= 1
        assert any(m["id"] == mem_id for m in found)

        # 3. Get single memory
        get_res = await ac.get(f"/api/memory/{mem_id}")
        assert get_res.status_code == 200
        assert get_res.json()["id"] == mem_id

        # 4. Update memory
        update_res = await ac.put(
            f"/api/memory/{mem_id}",
            json={
                "content": "Updated content without secrets",
                "tags": ["integration", "updated"],
            },
        )
        assert update_res.status_code == 200
        assert update_res.json()["content"] == "Updated content without secrets"

        # 5. Delete memory
        del_res = await ac.delete(f"/api/memory/{mem_id}")
        assert del_res.status_code == 200
        assert del_res.json()["status"] == "forgotten"

        # 6. Bulk delete
        bulk_res = await ac.delete("/api/memory", params={"sessionId": "sess-test-456"})
        assert bulk_res.status_code == 200
        assert "deletedCount" in bulk_res.json()


@pytest.mark.asyncio
async def test_project_memory_routes() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create Project memory for IntelliRepo
        create_res = await ac.post(
            "/api/memory/projects",
            json={
                "name": "IntelliRepo",
                "path": "C:\\Users\\ramuv\\IntelliRepo",
                "technology": "Python",
                "description": "Codebase analysis assistant",
                "metadata": {"version": "1.0.0"},
            },
        )
        assert create_res.status_code == 200
        proj = create_res.json()
        assert proj["name"] == "IntelliRepo"
        assert proj["path"] == "C:\\Users\\ramuv\\IntelliRepo"

        # List projects
        list_res = await ac.get("/api/memory/projects/list")
        assert list_res.status_code == 200
        projs = list_res.json()
        assert any(p["name"] == "IntelliRepo" for p in projs)

        # Search projects
        search_res = await ac.get("/api/memory/projects/search", params={"q": "IntelliRepo"})
        assert search_res.status_code == 200
        assert len(search_res.json()) >= 1

        # Delete project
        del_res = await ac.delete("/api/memory/projects/IntelliRepo")
        assert del_res.status_code == 200
        assert del_res.json()["status"] == "forgotten"


@pytest.mark.asyncio
async def test_application_and_preference_routes() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Save Application
        app_res = await ac.post(
            "/api/memory/applications",
            json={
                "name": "Terminal",
                "executablePath": "powershell.exe",
                "category": "system",
            },
        )
        assert app_res.status_code == 200
        assert app_res.json()["name"] == "Terminal"

        # List Applications
        apps_res = await ac.get("/api/memory/applications/list")
        assert apps_res.status_code == 200
        assert any(a["name"] == "Terminal" for a in apps_res.json())

        # Delete Application
        del_app_res = await ac.delete("/api/memory/applications/Terminal")
        assert del_app_res.status_code == 200

        # 2. Set Preference
        pref_res = await ac.post(
            "/api/memory/preferences",
            json={
                "key": "editor",
                "value": "code",
                "category": "dev",
            },
        )
        assert pref_res.status_code == 200
        assert pref_res.json()["key"] == "editor"

        # List Preferences
        prefs_res = await ac.get("/api/memory/preferences/list", params={"category": "dev"})
        assert prefs_res.status_code == 200
        assert len(prefs_res.json()) >= 1

        # Delete Preference
        del_pref_res = await ac.delete("/api/memory/preferences/editor")
        assert del_pref_res.status_code == 200


@pytest.mark.asyncio
async def test_workflow_routes() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        wf_res = await ac.post(
            "/api/memory/workflows",
            json={
                "name": "git_sync",
                "trigger": "manual",
                "steps": [{"step": 1, "action": "git pull"}],
                "description": "Sync active branch",
            },
        )
        assert wf_res.status_code == 200
        assert wf_res.json()["name"] == "git_sync"

        list_wf = await ac.get("/api/memory/workflows/list")
        assert list_wf.status_code == 200
        assert any(w["name"] == "git_sync" for w in list_wf.json())

        del_wf = await ac.delete("/api/memory/workflows/git_sync")
        assert del_wf.status_code == 200
