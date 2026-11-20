from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from voiceops.repositories.audit_logs import AuditRepository


class AuditService:
    """Create audit records for important application activities."""

    def __init__(self, session: AsyncSession) -> None:
        self.audit_repository = AuditRepository(session)

    async def record_action(
        self,
        *,
        actor_user_id: UUID | None,
        action: str,
        entity_type: str,
        entity_id: str,
        details: dict | None = None,
    ):
        """Create and flush an audit record in the current transaction."""

        return await self.audit_repository.create(
            {
                "actor_user_id": actor_user_id,
                "action": action,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "details": details or {},
            }
        )
