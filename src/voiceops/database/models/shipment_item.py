import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Integer,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from voiceops.database.base import Base

if TYPE_CHECKING:
    from voiceops.database.models.order_item import OrderItem
    from voiceops.database.models.shipment import Shipment


class ShipmentItem(Base):
    __tablename__ = "shipment_items"

    __table_args__ = (
        UniqueConstraint(
            "shipment_id",
            "order_item_id",
            name="uq_shipment_items_shipment_order_item",
        ),
        CheckConstraint(
            "quantity_shipped > 0",
            name="ck_shipment_items_quantity_shipped_positive",
        ),
        CheckConstraint(
            "quantity_received >= 0 AND quantity_received <= quantity_shipped",
            name="ck_shipment_items_quantity_received_valid",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    shipment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("shipments.id", ondelete="RESTRICT"),
        nullable=False,
    )

    order_item_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("order_items.id", ondelete="RESTRICT"),
        nullable=False,
    )

    quantity_shipped: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    quantity_received: Mapped[int] = mapped_column(
        Integer,
        server_default=text("0"),
        nullable=False,
    )

    shipment: Mapped["Shipment"] = relationship(
        back_populates="items",
        lazy="raise",
    )

    order_item: Mapped["OrderItem"] = relationship(
        back_populates="shipment_items",
        lazy="raise",
    )
