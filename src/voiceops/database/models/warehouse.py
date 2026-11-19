
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from voiceops.database.base import Base

if TYPE_CHECKING:
    from voiceops.database.models.inventory import Inventory
    from voiceops.database.models.inventory_movement import InventoryMovement
    from voiceops.database.models.orders import Order
    from voiceops.database.models.user_warehouse import UserWarehouse


class Warehouse(Base):
    __tablename__ = "warehouses"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    address: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(100), nullable=False)

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user_assignments: Mapped[list["UserWarehouse"]] = relationship(
        back_populates="warehouse",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="raise",
    )

    inventory_records: Mapped[list["Inventory"]] = relationship(
        back_populates="warehouse",
        passive_deletes=True,
        lazy="raise",
    )

    inventory_movements: Mapped[list["InventoryMovement"]] = relationship(
        back_populates="warehouse",
        passive_deletes=True,
        lazy="raise",
    )

    source_orders: Mapped[list["Order"]] = relationship(
        back_populates="source_warehouse",
        foreign_keys="Order.source_warehouse_id",
        lazy="raise",
    )

    destination_orders: Mapped[list["Order"]] = relationship(
        back_populates="destination_warehouse",
        foreign_keys="Order.destination_warehouse_id",
        lazy="raise",
    )
