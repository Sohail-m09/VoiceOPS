from datetime import datetime
from uuid import UUID

from voiceops.database.seed import prepare_seed_records
from voiceops.database.synthetic_data import generate_dataset


def test_seed_records_convert_uuid_and_datetime_values():
    dataset = generate_dataset(seed=42)

    records = prepare_seed_records(
        dataset,
        password_hash="test-argon2-hash",
    )

    user = records["users"][0]
    warehouse = records["warehouses"][0]
    inventory = records["inventory"][0]

    assert isinstance(user["id"], UUID)
    assert isinstance(warehouse["id"], UUID)
    assert isinstance(inventory["warehouse_id"], UUID)
    assert isinstance(user["created_at"], datetime)


def test_seed_records_replace_password_placeholders():
    dataset = generate_dataset(seed=42)

    records = prepare_seed_records(
        dataset,
        password_hash="test-argon2-hash",
    )

    for user in records["users"]:
        assert user["password_hash"] == "test-argon2-hash"
        assert "PLACEHOLDER" not in user["password_hash"]


def test_seed_records_contain_all_database_tables():
    dataset = generate_dataset(seed=42)

    records = prepare_seed_records(
        dataset,
        password_hash="test-argon2-hash",
    )

    assert set(records) == set(dataset["tables"])

    for table_name, rows in records.items():
        assert len(rows) == len(dataset["tables"][table_name])
