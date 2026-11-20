import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from voiceops.database.base import Base

if TYPE_CHECKING:
    from voiceops.database.models.inventory_movement import InventoryMovement
    from voiceops.database.models.order_item import OrderItem
    from voiceops.database.models.shipment import Shipment
    from voiceops.database.models.warehouse import Warehouse


class Order(Base):
    __tablename__ = "orders"

    __table_args__ = (
        CheckConstraint(
            "source_warehouse_id <> destination_warehouse_id",
            name="ck_orders_different_warehouses",
        ),
        CheckConstraint(
            "status IN ('draft', 'approved', 'processing', "
            "'partially_shipped', 'shipped', 'partially_received', "
            "'completed', 'cancelled')",
            name="ck_orders_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    order_number: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
    )

    source_warehouse_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
        nullable=False,
    )

    destination_warehouse_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="draft",
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

    source_warehouse: Mapped["Warehouse"] = relationship(
        back_populates="source_orders",
        foreign_keys=[source_warehouse_id],
        lazy="raise",
    )

    destination_warehouse: Mapped["Warehouse"] = relationship(
        back_populates="destination_orders",
        foreign_keys=[destination_warehouse_id],
        lazy="raise",
    )

    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order",
        passive_deletes="all",
        lazy="raise",
    )

    inventory_movements: Mapped[list["InventoryMovement"]] = relationship(
        back_populates="order",
        lazy="raise",
    )

    shipments: Mapped[list["Shipment"]] = relationship(
        back_populates="order",
        passive_deletes=True,
        lazy="raise",
    )
