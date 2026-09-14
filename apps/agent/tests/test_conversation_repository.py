"""Unit tests for conversation database repository."""

from pathlib import Path

import pytest

from app.ai.models import Message, MessageRole
from app.memory.db import DatabaseManager
from app.memory.repository import ConversationRepository


@pytest.fixture
async def temp_repo(tmp_path: Path) -> ConversationRepository:
    db_file = tmp_path / "test_convo.db"
    mgr = DatabaseManager(db_path=db_file)
    await mgr.initialize()
    return ConversationRepository(db=mgr)


@pytest.mark.asyncio
async def test_conversation_lifecycle(temp_repo: ConversationRepository) -> None:
    # 1. Create conversation
    convo = await temp_repo.create_conversation(title="Chat Session 1")
    assert convo.id is not None
    assert convo.title == "Chat Session 1"
    assert len(convo.messages) == 0

    # 2. Add message
    msg = Message(
        conversation_id=convo.id,
        role=MessageRole.USER,
        content="Hello YANA",
    )
    await temp_repo.add_message(msg)

    # 3. Retrieve messages
    messages = await temp_repo.get_messages(convo.id)
    assert len(messages) == 1
    assert messages[0].content == "Hello YANA"
    assert messages[0].role == MessageRole.USER

    # 4. List conversations
    summaries = await temp_repo.list_conversations()
    assert len(summaries) == 1
    assert summaries[0].id == convo.id
    assert summaries[0].message_count == 1

    # 5. Clear messages
    await temp_repo.clear_messages(convo.id)
    cleared = await temp_repo.get_messages(convo.id)
    assert len(cleared) == 0

    # 6. Delete conversation
    await temp_repo.delete_conversation(convo.id)
    retrieved = await temp_repo.get_conversation(convo.id)
    assert retrieved is None
