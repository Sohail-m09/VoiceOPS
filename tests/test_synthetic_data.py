from voiceops.database.synthetic_data import generate_dataset


def test_synthetic_dataset_is_reproducible():
    first = generate_dataset(seed=42)
    second = generate_dataset(seed=42)

    assert first == second


def test_synthetic_dataset_contains_all_tables():
    dataset = generate_dataset(seed=42)

    expected_tables = {
        "users",
        "warehouses",
        "user_warehouses",
        "products",
        "inventory",
        "inventory_movements",
        "orders",
        "order_items",
        "shipments",
        "shipment_items",
        "shipment_events",
        "audit_logs",
    }

    assert set(dataset["tables"]) == expected_tables


def test_synthetic_dataset_record_counts():
    dataset = generate_dataset(seed=42)
    tables = dataset["tables"]

    assert len(tables["users"]) == 12
    assert len(tables["warehouses"]) == 4
    assert len(tables["products"]) == 30
    assert len(tables["inventory"]) == 120
    assert len(tables["orders"]) == 35
    assert len(tables["audit_logs"]) == 30


def test_inventory_ledger_matches_inventory():
    dataset = generate_dataset(seed=42)
    tables = dataset["tables"]

    balances = {}

    for movement in tables["inventory_movements"]:
        key = (
            movement["warehouse_id"],
            movement["product_id"],
        )

        balances.setdefault(key, 0)

        if movement["movement_type"] in {
            "inbound",
            "adjustment_in",
        }:
            balances[key] += movement["quantity"]
        else:
            balances[key] -= movement["quantity"]

    for inventory in tables["inventory"]:
        key = (
            inventory["warehouse_id"],
            inventory["product_id"],
        )

        assert balances[key] == inventory["quantity_on_hand"]
