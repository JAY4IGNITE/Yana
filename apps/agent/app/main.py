"""Main Application Entrypoint for YANA Agent."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.agent_routes import router as agent_router
from app.api.conversation_routes import (
    conversations_router,
)
from app.api.conversation_routes import (
    router as conversation_router,
)
from app.api.memory_routes import router as memory_router
from app.api.routes import router
from app.api.voice_routes import router as voice_router
from app.config import settings
from app.errors import ErrorCode, YanaBaseError
from app.logger import logger
from app.memory.db import db_manager
from app.tools import register_default_tools


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager: sets up database and default tools."""
    import time

    from app.core.performance import performance_monitor

    start_time = time.perf_counter()
    logger.info("Initializing YANA Agent services...")
    # Initialize SQLite database schema
    await db_manager.initialize()
    # Register default baseline tools
    register_default_tools()
    duration = time.perf_counter() - start_time
    performance_monitor.record_startup_time(duration)
    logger.info(f"YANA Agent startup complete in {duration:.4f}s.")
    yield
    logger.info("Shutting down YANA Agent services...")


app = FastAPI(
    title="YANA Agent",
    version="0.1.0",
    description="Backend AI Agent Core for YANA Desktop Companion",
    lifespan=lifespan,
)


def get_cors_origins(env: str | None = None) -> list[str]:
    """Determine allowed CORS origins based on application environment."""
    target_env = env or settings.env
    if target_env == "production":
        return ["tauri://localhost", "http://tauri.localhost", "https://tauri.localhost"]
    return ["*"]


allowed_origins = get_cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(YanaBaseError)
async def yana_exception_handler(request: Request, exc: YanaBaseError) -> JSONResponse:
    """Ensure all YANA errors are safely returned to clients without exposing raw stack traces."""
    logger.error(f"YANA error occurred: {exc.code} - {exc.message}", exc_info=settings.debug)
    return JSONResponse(
        status_code=400,
        content={"error": exc.to_safe_payload()},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Fallback handler for unhandled server exceptions."""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": ErrorCode.SYSTEM_ERROR.value,
                "message": "An internal system error occurred.",
                "retryable": False,
            }
        },
    )


# Mount API routes
app.include_router(router)
app.include_router(conversation_router)
app.include_router(conversations_router)
app.include_router(agent_router)
app.include_router(voice_router)
app.include_router(memory_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.agent_host,
        port=settings.agent_port,
        log_level=settings.agent_log_level.lower(),
        reload=settings.debug,
    )
