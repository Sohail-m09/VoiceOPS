import asyncio
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from voiceops.services.exceptions import BusinessRuleError
from voiceops.services.orders import OrderService


def test_transfer_order_rejects_same_warehouse():
    session = MagicMock()
    service = OrderService(session)

    warehouse_id = uuid4()

    with pytest.raises(BusinessRuleError):
        asyncio.run(
            service.create_transfer_order(
                source_warehouse_id=warehouse_id,
                destination_warehouse_id=warehouse_id,
                items=[
                    {
                        "product_id": uuid4(),
                        "quantity_ordered": 5,
                    }
                ],
            )
        )

    session.begin.assert_not_called()


def test_transfer_order_rejects_empty_items():
    session = MagicMock()
    service = OrderService(session)

    with pytest.raises(BusinessRuleError):
        asyncio.run(
            service.create_transfer_order(
                source_warehouse_id=uuid4(),
                destination_warehouse_id=uuid4(),
                items=[],
            )
        )

    session.begin.assert_not_called()


def test_transfer_order_rejects_duplicate_products():
    session = MagicMock()
    service = OrderService(session)

    product_id = uuid4()

    items = [
        {"product_id": product_id, "quantity_ordered": 5},
        {"product_id": product_id, "quantity_ordered": 10},
    ]

    with pytest.raises(BusinessRuleError):
        asyncio.run(
            service.create_transfer_order(
                source_warehouse_id=uuid4(),
                destination_warehouse_id=uuid4(),
                items=items,
            )
        )

    session.begin.assert_not_called()


@pytest.mark.parametrize("quantity", [0, -1, True, 2.5])
def test_transfer_order_rejects_invalid_quantities(quantity):
    session = MagicMock()
    service = OrderService(session)

    with pytest.raises(BusinessRuleError):
        asyncio.run(
            service.create_transfer_order(
                source_warehouse_id=uuid4(),
                destination_warehouse_id=uuid4(),
                items=[
                    {
                        "product_id": uuid4(),
                        "quantity_ordered": quantity,
                    }
                ],
            )
        )

    session.begin.assert_not_called()
