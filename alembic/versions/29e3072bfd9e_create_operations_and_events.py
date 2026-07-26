"""create operations and events

Revision ID: 29e3072bfd9e
Revises: 
Create Date: 2026-07-26 21:23:14.619810

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '29e3072bfd9e'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


operation_status = postgresql.ENUM(
    "CREATED",
    "PROCESSING",
    "COMPLETED",
    "REJECTED",
    name="operation_status",
    create_type=False,
)

event_type = postgresql.ENUM(
    "CREATED",
    "PROCESSING",
    "COMPLETED",
    "REJECTED",
    "RECEIPT_IGNORED",
    name="event_type",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()

    operation_status.create(bind, checkfirst=True)
    event_type.create(bind, checkfirst=True)

    op.create_table(
        "operations",
        sa.Column(
            "operation_id",
            sa.String(),
            nullable=False,
        ),
        sa.Column(
            "amount",
            sa.Numeric(precision=20, scale=2),
            nullable=False,
        ),
        sa.Column(
            "currency",
            sa.String(length=3),
            nullable=False,
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "status",
            operation_status,
            server_default="CREATED",
            nullable=False,
        ),
        sa.Column(
            "provider_payment_id",
            sa.String(),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "amount > 0",
            name="ck_operations_amount_positive",
        ),
        sa.CheckConstraint(
            "currency = 'RUB'",
            name="ck_operations_currency_rub",
        ),
        sa.PrimaryKeyConstraint("operation_id"),
        sa.UniqueConstraint(
            "provider_payment_id",
            name="uq_operations_provider_payment_id",
        ),
    )

    op.create_table(
        "events",
        sa.Column(
            "event_id",
            sa.BigInteger(),
            sa.Identity(always=False),
            nullable=False,
        ),
        sa.Column(
            "operation_id",
            sa.String(),
            nullable=False,
        ),
        sa.Column(
            "type",
            event_type,
            nullable=False,
        ),
        sa.Column(
            "from_status",
            operation_status,
            nullable=True,
        ),
        sa.Column(
            "to_status",
            operation_status,
            nullable=False,
        ),
        sa.Column(
            "message",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["operation_id"],
            ["operations.operation_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("event_id"),
    )

    op.create_index(
        "ix_events_operation_id_event_id",
        "events",
        ["operation_id", "event_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_events_operation_id_event_id",
        table_name="events",
    )
    op.drop_table("events")
    op.drop_table("operations")

    bind = op.get_bind()

    event_type.drop(bind, checkfirst=True)
    operation_status.drop(bind, checkfirst=True)
