from voiceops.database.models import AuditLog, Order


def test_order_status_created_at_index_exists():
    indexes = {
        index.name: tuple(column.name for column in index.columns)
        for index in Order.__table__.indexes
    }

    assert indexes["ix_orders_status_created_at"] == (
        "status",
        "created_at",
    )


def test_audit_log_created_at_id_index_exists():
    indexes = {
        index.name: tuple(column.name for column in index.columns)
        for index in AuditLog.__table__.indexes
    }

    assert indexes["ix_audit_logs_created_at_id"] == (
        "created_at",
        "id",
    )
