import asyncio
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from voiceops.services.conversations import (
    create_conversation,
    get_conversation_history,
    get_user_conversation,
    save_conversation_message,
)
from voiceops.services.exceptions import BusinessRuleError, NotFoundError
from voiceops.services.orders import OrderService


def test_transfer_order_rejects_same_warehouse():
    session = MagicMock()
    service = OrderService(session)

    warehouse_id = uuid4()

    with pytest.raises(BusinessRuleError):
        asyncio.run(
            service.create_transfer_order(
                source_warehouse_id=warehouse_id,
                destination_warehouse_id=warehouse_id,
                items=[
                    {
                        "product_id": uuid4(),
                        "quantity_ordered": 5,
                    }
                ],
            )
        )

    session.begin.assert_not_called()


def test_transfer_order_rejects_empty_items():
    session = MagicMock()
    service = OrderService(session)

    with pytest.raises(BusinessRuleError):
        asyncio.run(
            service.create_transfer_order(
                source_warehouse_id=uuid4(),
                destination_warehouse_id=uuid4(),
                items=[],
            )
        )

    session.begin.assert_not_called()


def test_transfer_order_rejects_duplicate_products():
    session = MagicMock()
    service = OrderService(session)

    product_id = uuid4()

    items = [
        {"product_id": product_id, "quantity_ordered": 5},
        {"product_id": product_id, "quantity_ordered": 10},
    ]

    with pytest.raises(BusinessRuleError):
        asyncio.run(
            service.create_transfer_order(
                source_warehouse_id=uuid4(),
                destination_warehouse_id=uuid4(),
                items=items,
            )
        )

    session.begin.assert_not_called()


@pytest.mark.parametrize("quantity", [0, -1, True, 2.5])
def test_transfer_order_rejects_invalid_quantities(quantity):
    session = MagicMock()
    service = OrderService(session)

    with pytest.raises(BusinessRuleError):
        asyncio.run(
            service.create_transfer_order(
                source_warehouse_id=uuid4(),
                destination_warehouse_id=uuid4(),
                items=[
                    {
                        "product_id": uuid4(),
                        "quantity_ordered": quantity,
                    }
                ],
            )
        )

    session.begin.assert_not_called()


def test_create_conversation_success():
    session = MagicMock()
    session.flush = AsyncMock()

    user_id = uuid4()

    conversation = asyncio.run(
        create_conversation(
            session=session,
            user_id=user_id,
            title="  Warehouse Chat  ",
        )
    )

    assert conversation.user_id == user_id
    assert conversation.title == "Warehouse Chat"
    session.add.assert_called_once_with(conversation)
    session.flush.assert_awaited_once()


def test_create_conversation_without_title():
    session = MagicMock()
    session.flush = AsyncMock()

    conversation = asyncio.run(
        create_conversation(
            session=session,
            user_id=uuid4(),
        )
    )

    assert conversation.title is None
    session.flush.assert_awaited_once()


def test_create_conversation_blank_title_becomes_none():
    session = MagicMock()
    session.flush = AsyncMock()

    conversation = asyncio.run(
        create_conversation(
            session=session,
            user_id=uuid4(),
            title="   ",
        )
    )

    assert conversation.title is None


def test_create_conversation_rejects_long_title():
    session = MagicMock()
    session.flush = AsyncMock()

    with pytest.raises(BusinessRuleError):
        asyncio.run(
            create_conversation(
                session=session,
                user_id=uuid4(),
                title="A" * 201,
            )
        )

    session.add.assert_not_called()
    session.flush.assert_not_awaited()


def test_get_user_conversation_success():
    session = MagicMock()
    conversation = MagicMock()
    session.scalar = AsyncMock(return_value=conversation)

    result = asyncio.run(
        get_user_conversation(
            session=session,
            conversation_id=uuid4(),
            user_id=uuid4(),
        )
    )

    assert result is conversation
    session.scalar.assert_awaited_once()


def test_get_user_conversation_rejects_missing_or_unauthorized():
    session = MagicMock()
    session.scalar = AsyncMock(return_value=None)

    with pytest.raises(NotFoundError):
        asyncio.run(
            get_user_conversation(
                session=session,
                conversation_id=uuid4(),
                user_id=uuid4(),
            )
        )


def test_get_conversation_history_returns_chronological_messages():
    session = MagicMock()

    conversation = MagicMock()
    session.scalar = AsyncMock(return_value=conversation)

    oldest_message = MagicMock()
    newest_message = MagicMock()

    scalar_result = MagicMock()
    scalar_result.all.return_value = [
        newest_message,
        oldest_message,
    ]

    session.scalars = AsyncMock(return_value=scalar_result)

    result = asyncio.run(
        get_conversation_history(
            session=session,
            conversation_id=uuid4(),
            user_id=uuid4(),
            limit=20,
        )
    )

    assert result == [oldest_message, newest_message]
    session.scalar.assert_awaited_once()
    session.scalars.assert_awaited_once()
    scalar_result.all.assert_called_once()


@pytest.mark.parametrize("limit", [0, -1, True, 2.5])
def test_get_conversation_history_rejects_invalid_limit(limit):
    session = MagicMock()

    with pytest.raises(BusinessRuleError):
        asyncio.run(
            get_conversation_history(
                session=session,
                conversation_id=uuid4(),
                user_id=uuid4(),
                limit=limit,
            )
        )

    session.scalar.assert_not_called()
    session.scalars.assert_not_called()


def test_save_conversation_message_success():
    session = MagicMock()
    session.scalar = AsyncMock()
    session.flush = AsyncMock()

    conversation = MagicMock()
    conversation.id = uuid4()
    conversation.updated_at = None

    session.scalar.return_value = conversation

    conversation_id = conversation.id
    user_id = uuid4()
    request_id = uuid4()

    message = asyncio.run(
        save_conversation_message(
            session=session,
            conversation_id=conversation_id,
            user_id=user_id,
            request_id=request_id,
            role="user",
            content="  Where is my shipment?  ",
        )
    )

    assert message.conversation_id == conversation_id
    assert message.request_id == request_id
    assert message.role == "user"
    assert message.content == "Where is my shipment?"
    assert conversation.updated_at is not None

    session.add.assert_called_once_with(message)
    session.flush.assert_awaited_once()


@pytest.mark.parametrize("role", ["admin", "operator", "system", "tool"])
def test_save_conversation_message_rejects_invalid_role(role):
    session = MagicMock()

    with pytest.raises(BusinessRuleError):
        asyncio.run(
            save_conversation_message(
                session=session,
                conversation_id=uuid4(),
                user_id=uuid4(),
                request_id=uuid4(),
                role=role,
                content="Test message",
            )
        )

    session.scalar.assert_not_called()
    session.add.assert_not_called()


def test_save_conversation_message_rejects_empty_content():
    session = MagicMock()

    with pytest.raises(BusinessRuleError):
        asyncio.run(
            save_conversation_message(
                session=session,
                conversation_id=uuid4(),
                user_id=uuid4(),
                request_id=uuid4(),
                role="user",
                content="   ",
            )
        )

    session.scalar.assert_not_called()
    session.add.assert_not_called()
