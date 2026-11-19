
from typing import Any, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from voiceops.database.base import Base


ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Reusable database operations for ORM models."""

    def __init__(
        self,
        session: AsyncSession,
        model: type[ModelT],
    ) -> None:
        self.session = session
        self.model = model

    async def get_by_id(self, identity: Any) -> ModelT | None:
        """Retrieve a record using its primary key."""

        return await self.session.get(self.model, identity)

    async def get_all(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ModelT]:
        """Retrieve records with pagination."""

        if limit < 1:
            raise ValueError("Limit must be greater than zero.")

        if offset < 0:
            raise ValueError("Offset cannot be negative.")

        statement = (
            select(self.model)
            .limit(limit)
            .offset(offset)
        )

        result = await self.session.execute(statement)

        return list(result.scalars().all())

    async def create(self, data: dict[str, Any]) -> ModelT:
        """Create a record and flush it to the current transaction."""

        record = self.model(**data)

        self.session.add(record)

        await self.session.flush()

        return record

    async def update(
        self,
        identity: Any,
        data: dict[str, Any],
    ) -> ModelT | None:
        """Update an existing record without changing its primary key."""

        record = await self.get_by_id(identity)

        if record is None:
            return None

        allowed_fields = {
            attribute.key
            for attribute in self.model.__mapper__.column_attrs
        }

        primary_key_fields = {
            column.key
            for column in self.model.__mapper__.primary_key
        }

        for field, value in data.items():
            if field not in allowed_fields:
                raise ValueError(
                    f"Invalid field '{field}' for {self.model.__name__}."
                )

            if field in primary_key_fields:
                raise ValueError(
                    f"Cannot update primary key field '{field}'."
                )

            setattr(record, field, value)

        await self.session.flush()

        return record
