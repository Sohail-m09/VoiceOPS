
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from voiceops.database.base import Base

if TYPE_CHECKING:
    from voiceops.database.models.orders import Order
    from voiceops.database.models.product import Product
    from voiceops.database.models.warehouse import Warehouse


class InventoryMovement(Base):
    __tablename__ = "inventory_movements"

    __table_args__ = (
        CheckConstraint(
            "quantity > 0",
            name="ck_inventory_movements_quantity_positive",
        ),
        CheckConstraint(
            "movement_type IN ('inbound', 'outbound', "
            "'adjustment_in', 'adjustment_out', "
            "'transfer_in', 'transfer_out')",
            name="ck_inventory_movements_type",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
        nullable=False,
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
    )

    order_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=True,
    )

    movement_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    warehouse: Mapped["Warehouse"] = relationship(
        back_populates="inventory_movements",
        lazy="raise",
    )

    product: Mapped["Product"] = relationship(
        back_populates="inventory_movements",
        lazy="raise",
    )

    order: Mapped["Order | None"] = relationship(
        back_populates="inventory_movements",
        lazy="raise",
    )
