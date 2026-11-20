from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from voiceops.services.audit import AuditService


@pytest.mark.asyncio
async def test_record_action_creates_audit_log():
    session = AsyncMock()
    session.add = Mock()
    actor_id = uuid4()

    service = AuditService(session)

    await service.record_action(
        actor_user_id=actor_id,
        action="login_succeeded",
        entity_type="user",
        entity_id=str(actor_id),
        details={"email": "operator@example.com"},
    )

    session.add.assert_called_once()
    session.flush.assert_awaited_once()

    audit_log = session.add.call_args.args[0]

    assert audit_log.actor_user_id == actor_id
    assert audit_log.action == "login_succeeded"
    assert audit_log.entity_type == "user"
    assert audit_log.entity_id == str(actor_id)
    assert audit_log.details == {"email": "operator@example.com"}
