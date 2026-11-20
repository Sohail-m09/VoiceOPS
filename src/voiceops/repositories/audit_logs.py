from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from voiceops.database.models.audit_log import AuditLog
from voiceops.repositories.base import BaseRepository


class AuditRepository(BaseRepository[AuditLog]):
    """Database operations for audit logs."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, AuditLog)

    async def get_recent(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditLog]:
        if limit < 1 or offset < 0:
            raise ValueError("Invalid pagination values.")

        statement = (
            select(AuditLog)
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self.session.execute(statement)
        return list(result.scalars().all())
