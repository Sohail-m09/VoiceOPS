from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import selectors
from datetime import datetime
from pathlib import Path
from uuid import UUID

from pwdlib import PasswordHash
from sqlalchemy import DateTime, Uuid, func, insert, select

from voiceops.database.models import (
    AuditLog,
    Inventory,
    InventoryMovement,
    Order,
    OrderItem,
    Product,
    Shipment,
    ShipmentEvent,
    ShipmentItem,
    User,
    UserWarehouse,
    Warehouse,
)

# Insert order follows the database foreign-key dependencies.
TABLE_MODELS = [
    ("warehouses", Warehouse),
    ("users", User),
    ("user_warehouses", UserWarehouse),
    ("products", Product),
    ("inventory", Inventory),
    ("orders", Order),
    ("order_items", OrderItem),
    ("inventory_movements", InventoryMovement),
    ("shipments", Shipment),
    ("shipment_items", ShipmentItem),
    ("shipment_events", ShipmentEvent),
    ("audit_logs", AuditLog),
]


def prepare_seed_records(
    dataset: dict,
    password_hash: str,
) -> dict[str, list[dict]]:
    """Convert generated JSON records into database-ready values."""

    tables = dataset["tables"]
    prepared = {}

    for table_name, model in TABLE_MODELS:
        records = []

        for original in tables[table_name]:
            record = dict(original)

            if table_name == "users":
                record["password_hash"] = password_hash

            for column in model.__table__.columns:
                column_name = column.name
                value = record.get(column_name)

                if value is None:
                    continue

                if isinstance(column.type, Uuid):
                    record[column_name] = UUID(str(value))

                elif isinstance(column.type, DateTime):
                    if isinstance(value, str):
                        record[column_name] = datetime.fromisoformat(value)

            records.append(record)

        prepared[table_name] = records

    return prepared


async def seed_database(records: dict[str, list[dict]]) -> None:
    """Insert all synthetic records in a single transaction."""

    from voiceops.database.connection import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        async with session.begin():
            # Refuse to seed if any application table already has data.
            for table_name, model in TABLE_MODELS:
                count = await session.scalar(select(func.count()).select_from(model))

                if count:
                    raise RuntimeError(
                        f"Table '{table_name}' already contains {count} records. Seeding cancelled."
                    )

            # Insert records in foreign-key dependency order.
            for table_name, model in TABLE_MODELS:
                table_records = records[table_name]

                if table_records:
                    await session.execute(
                        insert(model),
                        table_records,
                    )

                print(f"Inserted {len(table_records):>4} records into {table_name}")


def load_dataset(input_path: Path) -> dict:
    """Load the generated JSON dataset."""

    if not input_path.is_file():
        raise FileNotFoundError(f"Synthetic dataset not found: {input_path}")

    with input_path.open("r", encoding="utf-8") as file:
        dataset = json.load(file)

    if "tables" not in dataset:
        raise ValueError("Invalid dataset: missing 'tables' section.")

    expected_tables = {name for name, _ in TABLE_MODELS}

    if set(dataset["tables"]) != expected_tables:
        raise ValueError("Dataset tables do not match the expected database schema.")

    return dataset


def get_demo_password() -> str:
    """Prompt for a demo password without displaying it."""

    password = getpass.getpass("Enter demo password for all seed users: ")
    confirmation = getpass.getpass("Confirm demo password: ")

    if password != confirmation:
        raise ValueError("Passwords do not match.")

    if len(password) < 12:
        raise ValueError("Use a demo password containing at least 12 characters.")

    return password


async def run_seed(input_path: Path, password: str) -> None:
    dataset = load_dataset(input_path)

    password_hasher = PasswordHash.recommended()
    hashed_password = password_hasher.hash(password)

    records = prepare_seed_records(
        dataset=dataset,
        password_hash=hashed_password,
    )

    print("\nStarting database seeding...\n")

    await seed_database(records)

    print("\nDatabase seeding completed successfully.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the VoiceOps PostgreSQL database.")

    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/generated/warehouse_seed.json"),
        help="Path to the generated synthetic dataset.",
    )

    args = parser.parse_args()

    try:
        password = get_demo_password()

        asyncio.run(
            run_seed(args.input, password),
            loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()),
        )

    except (FileNotFoundError, ValueError, RuntimeError) as error:
        raise SystemExit(f"\nSeeding failed: {error}") from error


if __name__ == "__main__":
    main()
