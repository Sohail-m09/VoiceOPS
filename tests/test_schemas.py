from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from voiceops.schemas import (
    OrderResponse,
    TransferOrderCreate,
    UserResponse,
)

SOURCE_ID = UUID("00000000-0000-0000-0000-000000000001")
DESTINATION_ID = UUID("00000000-0000-0000-0000-000000000002")
PRODUCT_ID = UUID("00000000-0000-0000-0000-000000000003")


def valid_transfer_payload() -> dict:
    return {
        "source_warehouse_id": SOURCE_ID,
        "destination_warehouse_id": DESTINATION_ID,
        "items": [
            {
                "product_id": PRODUCT_ID,
                "quantity_ordered": 10,
            }
        ],
    }


def test_valid_transfer_order_request():
    payload = TransferOrderCreate.model_validate(valid_transfer_payload())

    assert payload.source_warehouse_id == SOURCE_ID
    assert payload.destination_warehouse_id == DESTINATION_ID
    assert len(payload.items) == 1
    assert payload.items[0].quantity_ordered == 10


def test_transfer_order_rejects_same_warehouse():
    payload = valid_transfer_payload()
    payload["destination_warehouse_id"] = SOURCE_ID

    with pytest.raises(ValidationError):
        TransferOrderCreate.model_validate(payload)


def test_transfer_order_rejects_empty_items():
    payload = valid_transfer_payload()
    payload["items"] = []

    with pytest.raises(ValidationError):
        TransferOrderCreate.model_validate(payload)


def test_transfer_order_rejects_zero_quantity():
    payload = valid_transfer_payload()
    payload["items"][0]["quantity_ordered"] = 0

    with pytest.raises(ValidationError):
        TransferOrderCreate.model_validate(payload)


def test_transfer_order_rejects_negative_quantity():
    payload = valid_transfer_payload()
    payload["items"][0]["quantity_ordered"] = -5

    with pytest.raises(ValidationError):
        TransferOrderCreate.model_validate(payload)


def test_transfer_order_rejects_string_quantity():
    payload = valid_transfer_payload()
    payload["items"][0]["quantity_ordered"] = "10"

    with pytest.raises(ValidationError):
        TransferOrderCreate.model_validate(payload)


def test_transfer_order_rejects_boolean_quantity():
    payload = valid_transfer_payload()
    payload["items"][0]["quantity_ordered"] = True

    with pytest.raises(ValidationError):
        TransferOrderCreate.model_validate(payload)


def test_transfer_order_rejects_duplicate_products():
    payload = valid_transfer_payload()
    payload["items"].append(
        {
            "product_id": PRODUCT_ID,
            "quantity_ordered": 5,
        }
    )

    with pytest.raises(ValidationError):
        TransferOrderCreate.model_validate(payload)


def test_transfer_order_rejects_invalid_uuid():
    payload = valid_transfer_payload()
    payload["source_warehouse_id"] = "not-a-uuid"

    with pytest.raises(ValidationError):
        TransferOrderCreate.model_validate(payload)


def test_transfer_order_rejects_unexpected_fields():
    payload = valid_transfer_payload()
    payload["unexpected_field"] = "not allowed"

    with pytest.raises(ValidationError):
        TransferOrderCreate.model_validate(payload)


def test_user_response_does_not_expose_password_hash():
    assert "password_hash" not in UserResponse.model_fields


def test_order_response_matches_service_structure():
    now = datetime.now(UTC)

    order_data = {
        "id": SOURCE_ID,
        "order_number": "ORD-TEST-001",
        "source_warehouse_id": SOURCE_ID,
        "destination_warehouse_id": DESTINATION_ID,
        "status": "draft",
        "created_at": now,
        "items": [
            {
                "id": 1,
                "product_id": PRODUCT_ID,
                "quantity_ordered": 10,
            }
        ],
    }

    order = OrderResponse.model_validate(order_data)

    assert order.order_number == "ORD-TEST-001"
    assert order.status == "draft"
    assert order.items[0].quantity_ordered == 10
