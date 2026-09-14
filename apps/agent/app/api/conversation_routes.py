"""Conversation and Streaming API routes for YANA."""

import json
from collections.abc import AsyncGenerator
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.ai.factory import get_ai_provider
from app.ai.models import (
    Conversation,
    ConversationSummary,
    Message,
    MessageMetadata,
    MessageRole,
    StreamChunk,
)
from app.config import settings
from app.errors import YanaBaseError
from app.logger import logger
from app.memory.repository import conversation_repository

router = APIRouter(prefix="/api/conversation", tags=["conversation"])
conversations_router = APIRouter(prefix="/api/conversations", tags=["conversations"])


class CreateConversationRequest(BaseModel):
    title: str = "New Chat"


class SendMessageRequest(BaseModel):
    conversation_id: str = Field(default="default", alias="conversationId")
    content: str
    session_id: str | None = Field(default=None, alias="sessionId")
    system_prompt: str | None = Field(default=None, alias="systemPrompt")


class CancelSessionRequest(BaseModel):
    session_id: str = Field(..., alias="sessionId")


class RetryRequest(BaseModel):
    conversation_id: str = Field(..., alias="conversationId")
    session_id: str | None = Field(default=None, alias="sessionId")


# =========================================================================
# Conversation Session Management
# =========================================================================


@conversations_router.get("", response_model=list[ConversationSummary])
async def list_conversations() -> list[ConversationSummary]:
    """List all saved conversation sessions."""
    return await conversation_repository.list_conversations()


@conversations_router.post("", response_model=Conversation)
async def create_conversation(req: CreateConversationRequest) -> Conversation:
    """Create a new conversation session."""
    return await conversation_repository.create_conversation(title=req.title)


@conversations_router.get("/{conversation_id}", response_model=Conversation)
async def get_conversation(conversation_id: str) -> Conversation:
    """Fetch conversation by ID with all messages."""
    c = await conversation_repository.get_conversation(conversation_id)
    if not c:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return c


@conversations_router.delete("/{conversation_id}")
async def delete_conversation(conversation_id: str) -> dict[str, bool]:
    """Delete a conversation and all its messages."""
    await conversation_repository.delete_conversation(conversation_id)
    return {"deleted": True}


@conversations_router.delete("/{conversation_id}/messages")
async def clear_conversation(conversation_id: str) -> dict[str, bool]:
    """Clear all messages inside a conversation."""
    await conversation_repository.clear_messages(conversation_id)
    return {"cleared": True}


# =========================================================================
# Streaming and AI Generation
# =========================================================================


@router.post("/stream")
async def stream_conversation(
    request: Request,
    req: SendMessageRequest,
) -> StreamingResponse:
    """Stream AI assistant response as Server-Sent Events (SSE)."""
    session_id = req.session_id or str(uuid4())
    provider = get_ai_provider()

    # 1. Save incoming user message
    user_msg = Message(
        conversation_id=req.conversation_id,
        role=MessageRole.USER,
        content=req.content,
    )
    await conversation_repository.add_message(user_msg)

    # 2. Fetch history for context
    history = await conversation_repository.get_messages(req.conversation_id, limit=20)

    # 3. Stream generator
    async def sse_event_generator() -> AsyncGenerator[str, None]:
        accumulated_chunks: list[str] = []
        assistant_msg_id = str(uuid4())

        try:
            effective_system_prompt = req.system_prompt or settings.ai_system_prompt
            stream_gen = provider.stream_message(
                messages=history,
                system_prompt=effective_system_prompt,
                session_id=session_id,
            )

            async for token in stream_gen:
                # Check client network disconnection
                if await request.is_disconnected():
                    logger.info(f"Client disconnected; cancelling session {session_id}")
                    await provider.cancel(session_id)
                    break

                accumulated_chunks.append(token)
                chunk = StreamChunk(
                    session_id=session_id,
                    token=token,
                    is_complete=False,
                )
                yield f"data: {json.dumps(chunk.model_dump(by_alias=True))}\n\n"

            # Generation completed normally or was cancelled
            full_response = "".join(accumulated_chunks)
            assistant_msg = Message(
                id=assistant_msg_id,
                conversation_id=req.conversation_id,
                role=MessageRole.ASSISTANT,
                content=full_response,
                metadata=MessageMetadata(
                    provider=settings.ai_provider,
                    model=settings.ai_model,
                    is_streaming=False,
                ),
            )
            if full_response.strip():
                await conversation_repository.add_message(assistant_msg)

            # Send done event
            final_chunk = StreamChunk(
                session_id=session_id,
                token="",
                is_complete=True,
                message_id=assistant_msg_id,
                metadata=assistant_msg.metadata,
            )
            yield f"data: {json.dumps(final_chunk.model_dump(by_alias=True))}\n\n"

        except YanaBaseError as e:
            logger.error(f"Streaming error in session {session_id}: {e.message}")
            err_chunk = {
                "sessionId": session_id,
                "isComplete": True,
                "error": e.to_safe_payload(),
            }
            yield f"data: {json.dumps(err_chunk)}\n\n"
        except Exception as e:
            logger.error(f"Unexpected streaming exception in session {session_id}: {e}")
            err_chunk = {
                "sessionId": session_id,
                "isComplete": True,
                "error": {
                    "code": "AI_ERROR",
                    "message": "AI service encountered an issue. Please try again.",
                    "retryable": True,
                },
            }
            yield f"data: {json.dumps(err_chunk)}\n\n"

    return StreamingResponse(
        sse_event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/cancel")
async def cancel_generation(req: CancelSessionRequest) -> dict[str, Any]:
    """Cooperative cancellation of an active generation session."""
    logger.info(f"Received cancellation request for session {req.session_id}")
    provider = get_ai_provider()
    await provider.cancel(req.session_id)
    return {"sessionId": req.session_id, "cancelled": True}


@router.post("/retry")
async def retry_conversation(
    request: Request,
    req: RetryRequest,
) -> StreamingResponse:
    """Retry the last prompt in the conversation."""
    history = await conversation_repository.get_messages(req.conversation_id, limit=20)
    last_user_msg = None
    for m in reversed(history):
        if m.role == MessageRole.USER:
            last_user_msg = m
            break

    if not last_user_msg:
        raise HTTPException(status_code=400, detail="No previous user message to retry.")

    # Re-use stream_conversation logic with the last user message
    send_req = SendMessageRequest(
        conversation_id=req.conversation_id,
        content=last_user_msg.content,
        session_id=req.session_id,
    )
    return await stream_conversation(request, send_req)
