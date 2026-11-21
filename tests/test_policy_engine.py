
from uuid import uuid4

import pytest

from voiceops.harness.context_manager import ContextManager
from voiceops.harness.policy_engine import (
    PolicyDeniedError,
    PolicyEngine,
    ToolPolicy,
)


def create_context(role="operator", warehouse_ids=()):
    return ContextManager.create_context(
        user_id=uuid4(),
        user_role=role,
        warehouse_ids=warehouse_ids,
        request_text="Check warehouse inventory.",
    )


def test_allowed_role_is_authorized():
    engine = PolicyEngine()

    engine.register_policy(
        "get_inventory",
        ToolPolicy(
            allowed_roles=frozenset({"operator", "warehouse_manager"}),
        ),
    )

    context = create_context(role="operator")

    engine.authorize("get_inventory", context, {})


def test_disallowed_role_is_rejected():
    engine = PolicyEngine()

    engine.register_policy(
        "get_inventory",
        ToolPolicy(
            allowed_roles=frozenset({"operator"}),
        ),
    )

    context = create_context(role="analyst")

    with pytest.raises(PolicyDeniedError, match="cannot execute"):
        engine.authorize("get_inventory", context, {})


def test_user_with_warehouse_access_is_authorized():
    engine = PolicyEngine()
    warehouse_id = uuid4()

    engine.register_policy(
        "get_inventory",
        ToolPolicy(
            allowed_roles=frozenset({"operator"}),
            requires_warehouse_access=True,
        ),
    )

    context = create_context(
        role="operator",
        warehouse_ids=(warehouse_id,),
    )

    engine.authorize(
        "get_inventory",
        context,
        {"warehouse_id": warehouse_id},
    )


def test_user_without_warehouse_access_is_rejected():
    engine = PolicyEngine()
    warehouse_id = uuid4()

    engine.register_policy(
        "get_inventory",
        ToolPolicy(
            allowed_roles=frozenset({"operator"}),
            requires_warehouse_access=True,
        ),
    )

    context = create_context(role="operator")

    with pytest.raises(
        PolicyDeniedError,
        match="does not have access",
    ):
        engine.authorize(
            "get_inventory",
            context,
            {"warehouse_id": warehouse_id},
        )


def test_missing_warehouse_id_is_rejected():
    engine = PolicyEngine()

    engine.register_policy(
        "get_inventory",
        ToolPolicy(
            allowed_roles=frozenset({"operator"}),
            requires_warehouse_access=True,
        ),
    )

    context = create_context(role="operator")

    with pytest.raises(
        PolicyDeniedError,
        match="warehouse ID is required",
    ):
        engine.authorize("get_inventory", context, {})


def test_non_uuid_warehouse_id_is_rejected():
    engine = PolicyEngine()

    engine.register_policy(
        "get_inventory",
        ToolPolicy(
            allowed_roles=frozenset({"operator"}),
            requires_warehouse_access=True,
        ),
    )

    context = create_context(role="operator")

    with pytest.raises(PolicyDeniedError):
        engine.authorize(
            "get_inventory",
            context,
            {"warehouse_id": "Pune"},
        )


def test_missing_tool_policy_is_denied():
    engine = PolicyEngine()
    context = create_context()

    with pytest.raises(
        PolicyDeniedError,
        match="No access policy",
    ):
        engine.authorize("unknown_tool", context, {})


def test_empty_allowed_roles_are_rejected():
    with pytest.raises(
        ValueError,
        match="must allow at least one role",
    ):
        ToolPolicy(allowed_roles=frozenset())


def test_duplicate_policy_registration_is_rejected():
    engine = PolicyEngine()

    policy = ToolPolicy(
        allowed_roles=frozenset({"operator"}),
    )

    engine.register_policy("get_inventory", policy)

    with pytest.raises(ValueError, match="already registered"):
        engine.register_policy("get_inventory", policy)


def test_whitespace_in_policy_name_is_rejected():
    engine = PolicyEngine()

    with pytest.raises(ValueError, match="leading or trailing whitespace"):
        engine.register_policy(
            " get_inventory ",
            ToolPolicy(allowed_roles=frozenset({"operator"})),
        )
