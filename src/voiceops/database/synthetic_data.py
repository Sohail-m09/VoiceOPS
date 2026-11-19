from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from faker import Faker

AS_OF = datetime(2026, 11, 20, tzinfo=UTC)

WAREHOUSE_DATA = [
    ("Mumbai Central Warehouse", "WH-MUM-01", "Mumbai", "Maharashtra"),
    ("Pune Distribution Center", "WH-PUN-01", "Pune", "Maharashtra"),
    ("Nagpur Logistics Hub", "WH-NAG-01", "Nagpur", "Maharashtra"),
    ("Bengaluru Warehouse", "WH-BLR-01", "Bengaluru", "Karnataka"),
]

PRODUCT_NAMES = [
    "Laptop",
    "Wireless Mouse",
    "Keyboard",
    "Monitor",
    "USB Cable",
    "Headphones",
    "Power Adapter",
    "Webcam",
    "Router",
    "SSD Drive",
    "RAM Module",
    "Printer",
    "Scanner",
    "HDMI Cable",
    "Power Bank",
    "Smartphone",
    "Tablet",
    "Bluetooth Speaker",
    "Microphone",
    "UPS",
    "Ethernet Cable",
    "Graphics Card",
    "CPU Cooler",
    "External Hard Drive",
    "Laptop Stand",
    "Docking Station",
    "Projector",
    "Surge Protector",
    "Network Switch",
    "Smart Watch",
]

ORDER_STATUSES = [
    "draft",
    "approved",
    "processing",
    "partially_shipped",
    "shipped",
    "partially_received",
    "completed",
    "cancelled",
]


def make_uuid(seed: int, entity: str, index: int) -> str:
    """Generate a deterministic UUID for a record."""

    return str(uuid5(NAMESPACE_URL, f"voiceops:{seed}:{entity}:{index}"))


def timestamp(rng: random.Random, max_days: int = 90) -> datetime:
    """Generate a deterministic timestamp before AS_OF."""

    return AS_OF - timedelta(
        days=rng.randint(0, max_days),
        hours=rng.randint(0, 23),
        minutes=rng.randint(0, 59),
    )


def iso(value: datetime) -> str:
    """Convert a datetime into an ISO-8601 string."""

    return value.isoformat()


def validate_dataset(tables: dict) -> None:
    """Validate relationships and important database constraints."""

    users = {row["id"] for row in tables["users"]}
    warehouses = {row["id"] for row in tables["warehouses"]}
    products = {row["id"] for row in tables["products"]}
    orders = {row["id"]: row for row in tables["orders"]}
    order_items = {row["id"]: row for row in tables["order_items"]}
    shipments = {row["id"]: row for row in tables["shipments"]}

    for row in tables["user_warehouses"]:
        assert row["user_id"] in users
        assert row["warehouse_id"] in warehouses

    inventory_keys = set()

    for row in tables["inventory"]:
        assert row["warehouse_id"] in warehouses
        assert row["product_id"] in products
        assert row["quantity_on_hand"] >= 0
        assert 0 <= row["quantity_reserved"] <= row["quantity_on_hand"]

        key = (row["warehouse_id"], row["product_id"])
        assert key not in inventory_keys
        inventory_keys.add(key)

    for row in tables["inventory_movements"]:
        assert row["warehouse_id"] in warehouses
        assert row["product_id"] in products
        assert row["quantity"] > 0

        if row["order_id"] is not None:
            assert row["order_id"] in orders

    order_item_pairs = set()

    for row in tables["order_items"]:
        assert row["order_id"] in orders
        assert row["product_id"] in products
        assert row["quantity_ordered"] > 0

        pair = (row["order_id"], row["product_id"])
        assert pair not in order_item_pairs
        order_item_pairs.add(pair)

    for row in tables["orders"]:
        assert row["source_warehouse_id"] in warehouses
        assert row["destination_warehouse_id"] in warehouses
        assert row["source_warehouse_id"] != row["destination_warehouse_id"]

    shipped_quantities = defaultdict(int)

    for row in tables["shipment_items"]:
        assert row["shipment_id"] in shipments
        assert row["order_item_id"] in order_items
        assert row["quantity_shipped"] > 0
        assert 0 <= row["quantity_received"] <= row["quantity_shipped"]

        shipment = shipments[row["shipment_id"]]
        order_item = order_items[row["order_item_id"]]

        assert shipment["order_id"] == order_item["order_id"]

        shipped_quantities[row["order_item_id"]] += row["quantity_shipped"]

    for item_id, shipped in shipped_quantities.items():
        assert shipped <= order_items[item_id]["quantity_ordered"]

    for row in tables["shipment_events"]:
        assert row["shipment_id"] in shipments

    for row in tables["audit_logs"]:
        if row["actor_user_id"] is not None:
            assert row["actor_user_id"] in users

    # Verify that the inventory movement ledger matches stock balances.
    ledger = defaultdict(int)

    for row in tables["inventory_movements"]:
        key = (row["warehouse_id"], row["product_id"])

        if row["movement_type"] in ("inbound", "adjustment_in"):
            ledger[key] += row["quantity"]
        elif row["movement_type"] in ("outbound", "adjustment_out"):
            ledger[key] -= row["quantity"]

    for row in tables["inventory"]:
        key = (row["warehouse_id"], row["product_id"])
        assert ledger[key] == row["quantity_on_hand"]


def generate_dataset(seed: int = 42) -> dict:
    """Generate a complete synthetic warehouse dataset."""

    rng = random.Random(seed)

    fake = Faker("en_IN")
    fake.seed_instance(seed)

    tables = {
        "users": [],
        "warehouses": [],
        "user_warehouses": [],
        "products": [],
        "inventory": [],
        "inventory_movements": [],
        "orders": [],
        "order_items": [],
        "shipments": [],
        "shipment_items": [],
        "shipment_events": [],
        "audit_logs": [],
    }

    # ---------------------------------------------------------
    # 1. Warehouses
    # ---------------------------------------------------------

    for index, (name, code, city, state) in enumerate(WAREHOUSE_DATA, 1):
        tables["warehouses"].append(
            {
                "id": make_uuid(seed, "warehouse", index),
                "name": name,
                "code": code,
                "address": fake.street_address(),
                "city": city,
                "state": state,
                "is_active": True,
                "created_at": iso(timestamp(rng, 180)),
                "updated_at": iso(AS_OF),
            }
        )

    warehouse_ids = [row["id"] for row in tables["warehouses"]]

    # ---------------------------------------------------------
    # 2. Users
    # ---------------------------------------------------------

    roles = ["admin", "warehouse_manager", "operator", "analyst"]

    for index in range(1, 13):
        tables["users"].append(
            {
                "id": make_uuid(seed, "user", index),
                "full_name": fake.name(),
                "email": f"user{index:02d}@voiceops.demo",
                "password_hash": "SYNTHETIC_PASSWORD_HASH_PLACEHOLDER",
                "role": "admin" if index == 1 else roles[(index - 2) % 3 + 1],
                "is_active": True,
                "created_at": iso(timestamp(rng, 180)),
                "updated_at": iso(AS_OF),
            }
        )

    user_ids = [row["id"] for row in tables["users"]]

    # ---------------------------------------------------------
    # 3. User-Warehouse Assignments
    # ---------------------------------------------------------

    for index, user_id in enumerate(user_ids):
        assigned = warehouse_ids if index == 0 else rng.sample(warehouse_ids, rng.randint(1, 2))

        for warehouse_id in assigned:
            tables["user_warehouses"].append(
                {
                    "user_id": user_id,
                    "warehouse_id": warehouse_id,
                    "assigned_at": iso(timestamp(rng, 90)),
                }
            )

    # ---------------------------------------------------------
    # 4. Products
    # ---------------------------------------------------------

    for index, name in enumerate(PRODUCT_NAMES, 1):
        tables["products"].append(
            {
                "id": make_uuid(seed, "product", index),
                "sku": f"SKU-{index:04d}",
                "name": name,
                "description": fake.sentence(),
                "unit_of_measure": rng.choice(["pieces", "boxes", "kg", "litres"]),
                "is_active": True,
                "created_at": iso(timestamp(rng, 180)),
                "updated_at": iso(AS_OF),
            }
        )

    product_ids = [row["id"] for row in tables["products"]]

    # ---------------------------------------------------------
    # 5. Inventory and Inventory Movements
    # ---------------------------------------------------------

    movement_id = 1

    for warehouse_id in warehouse_ids:
        for product_id in product_ids:
            opening_quantity = rng.randint(100, 500)
            current_quantity = opening_quantity

            opened_at = timestamp(rng, 180)
            latest_update = opened_at

            tables["inventory_movements"].append(
                {
                    "id": movement_id,
                    "warehouse_id": warehouse_id,
                    "product_id": product_id,
                    "order_id": None,
                    "movement_type": "inbound",
                    "quantity": opening_quantity,
                    "notes": "Opening stock balance",
                    "created_at": iso(opened_at),
                }
            )

            movement_id += 1

            if rng.random() < 0.55:
                adjustment = rng.randint(1, 20)

                if rng.choice([True, False]):
                    movement_type = "adjustment_in"
                    current_quantity += adjustment
                    notes = "Stock adjustment increase"
                else:
                    movement_type = "adjustment_out"
                    current_quantity -= adjustment
                    notes = "Stock adjustment decrease"

                days_available = max(0, (AS_OF - opened_at).days)

                adjustment_at = opened_at + timedelta(days=rng.randint(0, days_available))

                latest_update = max(latest_update, adjustment_at)

                tables["inventory_movements"].append(
                    {
                        "id": movement_id,
                        "warehouse_id": warehouse_id,
                        "product_id": product_id,
                        "order_id": None,
                        "movement_type": movement_type,
                        "quantity": adjustment,
                        "notes": notes,
                        "created_at": iso(adjustment_at),
                    }
                )

                movement_id += 1

            tables["inventory"].append(
                {
                    "warehouse_id": warehouse_id,
                    "product_id": product_id,
                    "quantity_on_hand": current_quantity,
                    "quantity_reserved": rng.randint(0, min(50, current_quantity)),
                    "created_at": iso(opened_at),
                    "updated_at": iso(latest_update),
                }
            )

    # ---------------------------------------------------------
    # 6. Orders and Order Items
    # ---------------------------------------------------------

    order_item_id = 1

    for index in range(1, 36):
        order_id = make_uuid(seed, "order", index)

        source, destination = rng.sample(warehouse_ids, 2)

        status = rng.choices(
            ORDER_STATUSES,
            weights=[5, 5, 7, 5, 7, 5, 5, 3],
        )[0]

        order_created = timestamp(rng, 60)
        order_updated = min(
            AS_OF,
            order_created + timedelta(hours=rng.randint(1, 72)),
        )

        tables["orders"].append(
            {
                "id": order_id,
                "order_number": f"ORD-{1000 + index}",
                "source_warehouse_id": source,
                "destination_warehouse_id": destination,
                "status": status,
                "created_at": iso(order_created),
                "updated_at": iso(order_updated),
            }
        )

        selected_products = rng.sample(product_ids, rng.randint(2, 4))

        for product_id in selected_products:
            tables["order_items"].append(
                {
                    "id": order_item_id,
                    "order_id": order_id,
                    "product_id": product_id,
                    "quantity_ordered": rng.randint(5, 30),
                }
            )

            order_item_id += 1

    order_items_by_order = defaultdict(list)

    for item in tables["order_items"]:
        order_items_by_order[item["order_id"]].append(item)

    # ---------------------------------------------------------
    # 7. Shipments, Shipment Items and Shipment Events
    # ---------------------------------------------------------

    shipment_item_id = 1
    event_id = 1

    for order_index, order in enumerate(tables["orders"], 1):
        order_status = order["status"]

        if order_status not in {
            "partially_shipped",
            "shipped",
            "partially_received",
            "completed",
        }:
            continue

        shipment_id = make_uuid(seed, "shipment", order_index)

        if order_status == "partially_shipped":
            shipment_status = "dispatched"
        elif order_status == "shipped":
            shipment_status = rng.choice(["in_transit", "delivered"])
        elif order_status == "partially_received":
            shipment_status = "partially_received"
        else:
            shipment_status = "received"

        order_created = datetime.fromisoformat(order["created_at"])

        shipment_created = min(
            AS_OF,
            order_created + timedelta(hours=2),
        )

        event_types = ["created", "packed", "dispatched"]

        if shipment_status in {
            "in_transit",
            "delivered",
            "partially_received",
            "received",
        }:
            event_types.append("in_transit")

        if shipment_status in {
            "delivered",
            "partially_received",
            "received",
        }:
            event_types.append("delivered")

        if shipment_status == "partially_received":
            event_types.append("partially_received")
        elif shipment_status == "received":
            event_types.append("received")

        event_times = []

        for event_index, event_type in enumerate(event_types):
            event_time = min(
                AS_OF,
                shipment_created + timedelta(hours=event_index * 8),
            )

            event_times.append(event_time)

            tables["shipment_events"].append(
                {
                    "id": event_id,
                    "shipment_id": shipment_id,
                    "event_type": event_type,
                    "description": f"Shipment event: {event_type}",
                    "location": rng.choice(["Mumbai", "Pune", "Nagpur", "Bengaluru"]),
                    "event_time": iso(event_time),
                    "created_at": iso(event_time),
                }
            )

            event_id += 1

        delivered_at = (
            iso(event_times[event_types.index("delivered")]) if "delivered" in event_types else None
        )

        received_event = (
            "partially_received" if shipment_status == "partially_received" else "received"
        )

        received_at = (
            iso(event_times[event_types.index(received_event)])
            if received_event in event_types
            else None
        )

        tables["shipments"].append(
            {
                "id": shipment_id,
                "shipment_number": f"SHP-{2000 + order_index}",
                "order_id": order["id"],
                "status": shipment_status,
                "delivered_at": delivered_at,
                "received_at": received_at,
                "created_at": iso(shipment_created),
                "updated_at": iso(event_times[-1]),
            }
        )

        for item in order_items_by_order[order["id"]]:
            ordered = item["quantity_ordered"]

            if order_status == "partially_shipped":
                shipped = rng.randint(1, ordered - 1)
            else:
                shipped = ordered

            if shipment_status == "received":
                received = shipped
            elif shipment_status == "partially_received":
                received = rng.randint(1, shipped - 1)
            else:
                received = 0

            tables["shipment_items"].append(
                {
                    "id": shipment_item_id,
                    "shipment_id": shipment_id,
                    "order_item_id": item["id"],
                    "quantity_shipped": shipped,
                    "quantity_received": received,
                }
            )

            shipment_item_id += 1

    # ---------------------------------------------------------
    # 8. Audit Logs
    # ---------------------------------------------------------

    for index in range(1, 31):
        warehouse = rng.choice(tables["warehouses"])
        product = rng.choice(tables["products"])

        tables["audit_logs"].append(
            {
                "id": index,
                "actor_user_id": rng.choice(user_ids),
                "action": "inventory.opening_balance.created",
                "entity_type": "inventory",
                "entity_id": (f"{warehouse['id']}:{product['id']}"),
                "details": {
                    "source": "synthetic_dataset",
                    "warehouse_code": warehouse["code"],
                    "product_sku": product["sku"],
                },
                "created_at": iso(timestamp(rng, 60)),
            }
        )

    # ---------------------------------------------------------
    # 9. Validate and Return Dataset
    # ---------------------------------------------------------

    validate_dataset(tables)

    counts = {table: len(records) for table, records in tables.items()}

    return {
        "metadata": {
            "schema_version": 1,
            "seed": seed,
            "generated_at": iso(AS_OF),
            "password_hash_note": (
                "Synthetic password placeholders are not valid "
                "login credentials. The seeder must hash a demo "
                "password before inserting users."
            ),
            "counts": counts,
        },
        "tables": tables,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic VoiceOps warehouse data.")

    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducible generation.",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/generated/warehouse_seed.json"),
        help="Output JSON file path.",
    )

    args = parser.parse_args()

    dataset = generate_dataset(args.seed)

    args.output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with args.output.open("w", encoding="utf-8") as file:
        json.dump(
            dataset,
            file,
            indent=2,
            ensure_ascii=False,
        )

        file.write("\n")

    print("\nSynthetic dataset generated successfully.")
    print(f"Output: {args.output.resolve()}")
    print(f"Seed: {args.seed}")
    print("\nRecord counts:")

    for table, count in dataset["metadata"]["counts"].items():
        print(f"  {table}: {count}")


if __name__ == "__main__":
    main()
