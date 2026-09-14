"""FastAPI REST routes for YANA local memory, projects, preferences, and workflows."""

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.errors import ValidationError, YanaBaseError
from app.memory import (
    MemoryCategory,
    MemoryType,
    memory_manager,
)

router = APIRouter(prefix="/api/memory", tags=["Memory"])


class CreateMemoryRequest(BaseModel):
    key: str
    content: str
    memory_type: MemoryType = Field(default=MemoryType.LONG_TERM, alias="memoryType")
    category: MemoryCategory = Field(default=MemoryCategory.GENERAL)
    session_id: str | None = Field(default=None, alias="sessionId")
    metadata: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)


class UpdateMemoryRequest(BaseModel):
    content: str | None = None
    metadata: dict[str, Any] | None = None
    tags: list[str] | None = None


class SaveProjectRequest(BaseModel):
    name: str
    path: str
    technology: str = "unknown"
    description: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class SaveApplicationRequest(BaseModel):
    name: str
    executable_path: str = Field(..., alias="executablePath")
    category: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SetPreferenceRequest(BaseModel):
    key: str
    value: Any
    category: str = "general"


class SaveWorkflowRequest(BaseModel):
    name: str
    trigger: str
    steps: list[dict[str, Any]]
    description: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# General Memory Endpoints
# =============================================================================


@router.post("", status_code=201)
async def create_memory(req: CreateMemoryRequest) -> dict[str, Any]:
    """Create and persist a new memory item."""
    try:
        item = await memory_manager.create_memory(
            key=req.key,
            content=req.content,
            memory_type=req.memory_type,
            category=req.category,
            session_id=req.session_id,
            metadata=req.metadata,
            tags=req.tags,
        )
        return item.model_dump(by_alias=True)
    except ValidationError as ex:
        raise HTTPException(status_code=400, detail=ex.to_safe_payload()) from ex
    except YanaBaseError as ex:
        raise HTTPException(status_code=400, detail=ex.to_safe_payload()) from ex


@router.get("/search")
async def search_memories(
    q: str = Query(..., description="Keyword search query"),
    category: MemoryCategory | None = None,
    memory_type: MemoryType | None = Query(default=None, alias="memoryType"),
    session_id: str | None = Query(default=None, alias="sessionId"),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[dict[str, Any]]:
    """Search stored memories by keyword query across content, keys, and tags."""
    items = await memory_manager.search_memories(
        query=q,
        category=category,
        memory_type=memory_type,
        session_id=session_id,
        limit=limit,
    )
    return [i.model_dump(by_alias=True) for i in items]


@router.get("/{memory_id}")
async def get_memory(memory_id: str) -> dict[str, Any]:
    """Retrieve a specific memory item by ID."""
    item = await memory_manager.get_memory(memory_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Memory item '{memory_id}' not found.")
    return item.model_dump(by_alias=True)


@router.put("/{memory_id}")
async def update_memory(memory_id: str, req: UpdateMemoryRequest) -> dict[str, Any]:
    """Update content, metadata, or tags of an existing memory item."""
    item = await memory_manager.update_memory(
        memory_id=memory_id,
        content=req.content,
        metadata=req.metadata,
        tags=req.tags,
    )
    if not item:
        raise HTTPException(status_code=404, detail=f"Memory item '{memory_id}' not found.")
    return item.model_dump(by_alias=True)


@router.delete("/{memory_id}")
async def forget_memory(memory_id: str) -> dict[str, Any]:
    """Delete a specific memory item by ID."""
    deleted = await memory_manager.forget_memory(memory_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Memory item '{memory_id}' not found.")
    return {"status": "forgotten", "id": memory_id}


@router.delete("")
async def bulk_forget_memories(
    category: MemoryCategory | None = None,
    memory_type: MemoryType | None = Query(default=None, alias="memoryType"),
    session_id: str | None = Query(default=None, alias="sessionId"),
) -> dict[str, Any]:
    """Bulk forget memories matching criteria (user privacy control)."""
    count = await memory_manager.forget_all(
        category=category,
        memory_type=memory_type,
        session_id=session_id,
    )
    return {"status": "ok", "deletedCount": count}


# =============================================================================
# Project Memory Endpoints
# =============================================================================


@router.get("/projects/list")
async def list_projects() -> list[dict[str, Any]]:
    """List all registered projects."""
    projects = await memory_manager.list_projects()
    return [p.model_dump(by_alias=True) for p in projects]


@router.post("/projects")
async def save_project(req: SaveProjectRequest) -> dict[str, Any]:
    """Save or update developer project memory."""
    proj = await memory_manager.save_project(
        name=req.name,
        path=req.path,
        technology=req.technology,
        description=req.description,
        metadata=req.metadata,
    )
    return proj.model_dump(by_alias=True)


@router.get("/projects/search")
async def search_projects(q: str = Query(...)) -> list[dict[str, Any]]:
    """Search projects by name, technology, or description."""
    projects = await memory_manager.search_projects(q)
    return [p.model_dump(by_alias=True) for p in projects]


@router.delete("/projects/{name_or_id}")
async def forget_project(name_or_id: str) -> dict[str, Any]:
    """Remove a project from memory."""
    deleted = await memory_manager.forget_project(name_or_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Project '{name_or_id}' not found.")
    return {"status": "forgotten", "project": name_or_id}


# =============================================================================
# Preferences Endpoints
# =============================================================================


@router.get("/preferences/list")
async def list_preferences(category: str | None = None) -> list[dict[str, Any]]:
    """List all user preferences."""
    prefs = await memory_manager.list_preferences(category=category)
    return [p.model_dump(by_alias=True) for p in prefs]


@router.post("/preferences")
async def set_preference(req: SetPreferenceRequest) -> dict[str, Any]:
    """Save a user preference key-value."""
    pref = await memory_manager.set_preference(
        key=req.key,
        value=req.value,
        category=req.category,
    )
    return pref.model_dump(by_alias=True)


@router.delete("/preferences/{key}")
async def forget_preference(key: str) -> dict[str, Any]:
    """Delete a user preference."""
    deleted = await memory_manager.forget_preference(key)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Preference '{key}' not found.")
    return {"status": "forgotten", "key": key}


# =============================================================================
# Applications Endpoints
# =============================================================================


@router.get("/applications/list")
async def list_applications(category: str | None = None) -> list[dict[str, Any]]:
    """List all registered applications."""
    apps = await memory_manager.list_applications(category=category)
    return [a.model_dump(by_alias=True) for a in apps]


@router.post("/applications")
async def save_application(req: SaveApplicationRequest) -> dict[str, Any]:
    """Save or update known application memory."""
    app_mem = await memory_manager.save_application(
        name=req.name,
        executable_path=req.executable_path,
        category=req.category,
        metadata=req.metadata,
    )
    return app_mem.model_dump(by_alias=True)


@router.delete("/applications/{name_or_id}")
async def forget_application(name_or_id: str) -> dict[str, Any]:
    """Delete an application from memory."""
    deleted = await memory_manager.forget_application(name_or_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Application '{name_or_id}' not found.")
    return {"status": "forgotten", "application": name_or_id}


# =============================================================================
# Workflows Endpoints
# =============================================================================


@router.get("/workflows/list")
async def list_workflows() -> list[dict[str, Any]]:
    """List all saved workflow recipes."""
    wfs = await memory_manager.list_workflows()
    return [w.model_dump(by_alias=True) for w in wfs]


@router.post("/workflows")
async def save_workflow(req: SaveWorkflowRequest) -> dict[str, Any]:
    """Save an automated workflow recipe."""
    wf = await memory_manager.save_workflow(
        name=req.name,
        trigger=req.trigger,
        steps=req.steps,
        description=req.description,
        metadata=req.metadata,
    )
    return wf.model_dump(by_alias=True)


@router.delete("/workflows/{name_or_id}")
async def forget_workflow(name_or_id: str) -> dict[str, Any]:
    """Delete a workflow recipe from memory."""
    deleted = await memory_manager.forget_workflow(name_or_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Workflow '{name_or_id}' not found.")
    return {"status": "forgotten", "workflow": name_or_id}
