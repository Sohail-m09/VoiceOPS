
from uuid import uuid4

import pytest
from pydantic import ValidationError

from voiceops.harness.context_manager import (
    ContextManager,
    ExecutionContext,
)


def test_create_execution_context():
    user_id = uuid4()
    warehouse_id = uuid4()

    context = ContextManager.create_context(
        user_id=user_id,
        user_role="operator",
        warehouse_ids=(warehouse_id,),
        request_text="Why is order ORD-1052 delayed?",
    )

    assert isinstance(context, ExecutionContext)
    assert context.user_id == user_id
    assert context.user_role == "operator"
    assert context.warehouse_ids == (warehouse_id,)
    assert context.request_text == "Why is order ORD-1052 delayed?"
    assert context.request_id is not None
    assert context.created_at.tzinfo is not None


def test_each_context_gets_a_unique_request_id():
    user_id = uuid4()

    first = ContextManager.create_context(
        user_id=user_id,
        user_role="operator",
        request_text="Check inventory.",
    )

    second = ContextManager.create_context(
        user_id=user_id,
        user_role="operator",
        request_text="Check shipments.",
    )

    assert first.request_id != second.request_id


def test_invalid_user_role_is_rejected():
    with pytest.raises(ValidationError):
        ContextManager.create_context(
            user_id=uuid4(),
            user_role="superuser",
            request_text="Check inventory.",
        )


def test_empty_request_text_is_rejected():
    with pytest.raises(ValidationError):
        ContextManager.create_context(
            user_id=uuid4(),
            user_role="operator",
            request_text="   ",
        )


def test_duplicate_warehouse_ids_are_rejected():
    warehouse_id = uuid4()

    with pytest.raises(ValidationError):
        ContextManager.create_context(
            user_id=uuid4(),
            user_role="operator",
            warehouse_ids=(warehouse_id, warehouse_id),
            request_text="Check inventory.",
        )


def test_extra_fields_are_rejected():
    with pytest.raises(ValidationError):
        ExecutionContext(
            user_id=uuid4(),
            user_role="operator",
            request_text="Check inventory.",
            password="should-not-be-accepted",
        )
