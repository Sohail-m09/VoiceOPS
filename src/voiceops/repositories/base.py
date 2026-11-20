from typing import Any

from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from voiceops.database.base import Base


class BaseRepository[ModelT: Base]:
    """Reusable database operations for ORM models."""

    def __init__(
        self,
        session: AsyncSession,
        model: type[ModelT],
    ) -> None:
        self.session = session
        self.model = model

    async def get_by_id(self, record_id: Any) -> ModelT | None:
        return await self.session.get(self.model, record_id)

    async def get_all(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ModelT]:
        if limit < 1 or offset < 0:
            raise ValueError("Invalid pagination values.")

        statement = select(self.model).limit(limit).offset(offset)
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def create(self, data: dict[str, Any]) -> ModelT:
        record = self.model(**data)
        self.session.add(record)
        await self.session.flush()
        return record

    async def update(
        self,
        record_id: Any,
        data: dict[str, Any],
    ) -> ModelT:
        primary_key_columns = inspect(self.model).primary_key
        primary_key_names = {column.key for column in primary_key_columns}

        if primary_key_names.intersection(data):
            raise ValueError("Updating primary key fields is not allowed.")

        record = await self.get_by_id(record_id)

        if record is None:
            raise ValueError("Record not found.")

        for key, value in data.items():
            if not hasattr(record, key):
                raise ValueError(f"Invalid field: {key}")
            setattr(record, key, value)

        await self.session.flush()
        return record
