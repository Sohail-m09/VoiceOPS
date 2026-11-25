
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from voiceops.database.models.conversation import Conversation
from voiceops.database.models.conversation_message import ConversationMessage
from voiceops.services.exceptions import BusinessRuleError, NotFoundError

MessageRole = Literal["user", "assistant"]


async def create_conversation(
    session: AsyncSession,
    user_id: UUID,
    title: str | None = None,
) -> Conversation:
    """Create a conversation owned by the supplied user."""

    if title is not None:
        title = title.strip()

        if not title:
            title = None
        elif len(title) > 200:
            raise BusinessRuleError("Conversation title cannot exceed 200 characters.")

    conversation = Conversation(
        user_id=user_id,
        title=title,
    )

    session.add(conversation)
    await session.flush()

    return conversation


async def get_user_conversation(
    session: AsyncSession,
    conversation_id: UUID,
    user_id: UUID,
) -> Conversation:
    """Retrieve a conversation only if it belongs to the supplied user."""

    statement = select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.user_id == user_id,
    )

    conversation = await session.scalar(statement)

    if conversation is None:
        raise NotFoundError("Conversation was not found.")

    return conversation


async def get_conversation_history(
    session: AsyncSession,
    conversation_id: UUID,
    user_id: UUID,
    limit: int = 20,
) -> list[ConversationMessage]:
    """Retrieve the latest messages in chronological order."""

    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise BusinessRuleError("Message history limit must be a positive integer.")

    await get_user_conversation(
        session=session,
        conversation_id=conversation_id,
        user_id=user_id,
    )

    statement = (
        select(ConversationMessage)
        .where(ConversationMessage.conversation_id == conversation_id)
        .order_by(
            ConversationMessage.created_at.desc(),
            ConversationMessage.id.desc(),
        )
        .limit(limit)
    )

    result = await session.scalars(statement)
    messages = list(result.all())

    # The query gets the newest messages first.
    # Reverse them so the agent receives oldest-to-newest history.
    messages.reverse()

    return messages


async def save_conversation_message(
    session: AsyncSession,
    conversation_id: UUID,
    user_id: UUID,
    request_id: UUID,
    role: MessageRole,
    content: str,
) -> ConversationMessage:
    """Save a message after checking conversation ownership."""

    if role not in ("user", "assistant"):
        raise BusinessRuleError("Message role must be user or assistant.")

    content = content.strip()

    if not content:
        raise BusinessRuleError("Message content cannot be empty.")

    conversation = await get_user_conversation(
        session=session,
        conversation_id=conversation_id,
        user_id=user_id,
    )

    message = ConversationMessage(
        conversation_id=conversation.id,
        request_id=request_id,
        role=role,
        content=content,
    )

    session.add(message)

    # Update the conversation's last-activity timestamp.
    conversation.updated_at = datetime.now(UTC)

    await session.flush()

    return message
