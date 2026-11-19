
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from voiceops.database.base import Base

if TYPE_CHECKING:
    from voiceops.database.models.product import Product
    from voiceops.database.models.warehouse import Warehouse


class Inventory(Base):
    __tablename__ = "inventory"

    __table_args__ = (
        CheckConstraint(
            "quantity_on_hand >= 0",
            name="ck_inventory_quantity_on_hand_nonnegative",
        ),
        CheckConstraint(
            "quantity_reserved >= 0 "
            "AND quantity_reserved <= quantity_on_hand",
            name="ck_inventory_quantity_reserved_valid",
        ),
    )

    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
        primary_key=True,
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("products.id", ondelete="RESTRICT"),
        primary_key=True,
    )

    quantity_on_hand: Mapped[int] = mapped_column(
        Integer,
        server_default=text("0"),
        nullable=False,
    )

    quantity_reserved: Mapped[int] = mapped_column(
        Integer,
        server_default=text("0"),
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

    warehouse: Mapped["Warehouse"] = relationship(
        back_populates="inventory_records",
        lazy="raise",
    )

    product: Mapped["Product"] = relationship(
        back_populates="inventory_records",
        lazy="raise",
    )
