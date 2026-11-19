
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
    from voiceops.database.models.orders import Order
    from voiceops.database.models.shipment_event import ShipmentEvent
    from voiceops.database.models.shipment_item import ShipmentItem


class Shipment(Base):
    __tablename__ = "shipments"

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'packed', 'dispatched', "
            "'in_transit', 'delivered', 'partially_received', "
            "'received', 'cancelled')",
            name="ck_shipments_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    shipment_number: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
    )

    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="pending",
        nullable=False,
    )

    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    received_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
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

    order: Mapped["Order"] = relationship(
        back_populates="shipments",
        lazy="raise",
    )

    items: Mapped[list["ShipmentItem"]] = relationship(
        back_populates="shipment",
        passive_deletes=True,
        lazy="raise",
    )

    events: Mapped[list["ShipmentEvent"]] = relationship(
        back_populates="shipment",
        passive_deletes=True,
        lazy="raise",
    )
