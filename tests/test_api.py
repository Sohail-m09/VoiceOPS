from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from voiceops.api.v1.dependencies import get_current_user
from voiceops.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def authenticated_api_tests():
    """Override authentication for API validation tests."""

    test_user = SimpleNamespace(
        id="00000000-0000-0000-0000-000000000001",
        full_name="Test Operator",
        email="operator@voiceops.demo",
        role="admin",
        is_active=True,
    )

    app.dependency_overrides[get_current_user] = lambda: test_user

    yield

    app.dependency_overrides.pop(get_current_user, None)


def test_api_routes_are_registered():
    response = client.get("/openapi.json")

    assert response.status_code == 200

    paths = response.json()["paths"]

    expected_paths = [
        "/api/v1/users",
        "/api/v1/users/{user_id}",
        "/api/v1/warehouses",
        "/api/v1/warehouses/{warehouse_id}",
        "/api/v1/products",
        "/api/v1/products/{product_id}",
        "/api/v1/inventory/{warehouse_id}",
        "/api/v1/orders/{order_number}",
        "/api/v1/orders/transfer",
        "/api/v1/shipments/{shipment_number}",
    ]

    for path in expected_paths:
        assert path in paths


def test_invalid_user_uuid_returns_422():
    response = client.get("/api/v1/users/not-a-valid-uuid")

    assert response.status_code == 422


def test_transfer_order_rejects_missing_fields():
    response = client.post("/api/v1/orders/transfer", json={})

    assert response.status_code == 422


def test_transfer_order_rejects_invalid_uuid():
    response = client.post(
        "/api/v1/orders/transfer",
        json={
            "source_warehouse_id": "invalid-id",
            "destination_warehouse_id": "invalid-id",
            "items": [],
        },
    )

    assert response.status_code == 422


def test_transfer_order_rejects_non_list_items():
    response = client.post(
        "/api/v1/orders/transfer",
        json={
            "source_warehouse_id": "00000000-0000-0000-0000-000000000001",
            "destination_warehouse_id": "00000000-0000-0000-0000-000000000002",
            "items": "not-a-list",
        },
    )

    assert response.status_code == 422
