from sqlalchemy import CheckConstraint, Index

from voiceops.database.base import Base
from voiceops.database.models import Conversation, ConversationMessage


def test_conversation_models_are_registered_in_metadata():
    assert "conversations" in Base.metadata.tables
    assert "conversation_messages" in Base.metadata.tables


def test_conversation_has_expected_columns():
    expected_columns = {
        "id",
        "user_id",
        "title",
        "created_at",
        "updated_at",
    }

    actual_columns = set(Conversation.__table__.columns.keys())

    assert expected_columns.issubset(actual_columns)


def test_conversation_message_has_expected_columns():
    expected_columns = {
        "id",
        "conversation_id",
        "request_id",
        "role",
        "content",
        "created_at",
    }

    actual_columns = set(ConversationMessage.__table__.columns.keys())

    assert expected_columns.issubset(actual_columns)


def test_conversation_user_foreign_key_uses_restrict():
    foreign_keys = [
        foreign_key
        for foreign_key in Conversation.__table__.foreign_keys
        if foreign_key.parent.name == "user_id"
    ]

    assert len(foreign_keys) == 1
    assert foreign_keys[0].target_fullname == "users.id"
    assert foreign_keys[0].ondelete == "RESTRICT"


def test_message_conversation_foreign_key_uses_cascade():
    foreign_keys = [
        foreign_key
        for foreign_key in ConversationMessage.__table__.foreign_keys
        if foreign_key.parent.name == "conversation_id"
    ]

    assert len(foreign_keys) == 1
    assert foreign_keys[0].target_fullname == "conversations.id"
    assert foreign_keys[0].ondelete == "CASCADE"


def test_conversation_message_role_constraint_exists():
    constraints = [
        constraint.name
        for constraint in ConversationMessage.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    ]

    assert "ck_conversation_messages_role" in constraints


def test_conversation_has_user_updated_at_index():
    indexes = [
        index
        for index in Conversation.__table__.indexes
        if isinstance(index, Index)
    ]

    assert any(
        index.name == "ix_conversations_user_updated_at"
        and tuple(column.name for column in index.columns)
        == ("user_id", "updated_at")
        for index in indexes
    )


def test_conversation_message_has_chronological_index():
    indexes = [
        index
        for index in ConversationMessage.__table__.indexes
        if isinstance(index, Index)
    ]

    assert any(
        index.name == "ix_conversation_messages_conversation_created"
        and tuple(column.name for column in index.columns)
        == ("conversation_id", "created_at", "id")
        for index in indexes
    )


def test_conversation_message_request_id_is_not_a_foreign_key():
    foreign_keys = ConversationMessage.__table__.foreign_keys

    assert all(
        foreign_key.parent.name != "request_id"
        for foreign_key in foreign_keys
    )


def test_conversation_messages_relationship_is_configured():
    relationship = Conversation.messages.property

    assert relationship.back_populates == "conversation"
    assert relationship.lazy == "raise"
    assert "delete-orphan" in relationship.cascade


def test_message_conversation_relationship_is_configured():
    relationship = ConversationMessage.conversation.property

    assert relationship.back_populates == "messages"
    assert relationship.lazy == "raise"
