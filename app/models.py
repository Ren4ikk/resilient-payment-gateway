import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Identity,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class OperationStatus(str, enum.Enum):
    CREATED = "CREATED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"


class EventType(str, enum.Enum):
    CREATED = "CREATED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    RECEIPT_IGNORED = "RECEIPT_IGNORED"


operation_status_enum = SqlEnum(
    OperationStatus,
    name="operation_status",
)

event_type_enum = SqlEnum(
    EventType,
    name="event_type",
)


class Operation(Base):
    __tablename__ = "operations"

    __table_args__ = (
        CheckConstraint(
            "amount > 0",
            name="ck_operations_amount_positive",
        ),
        CheckConstraint(
            "currency = 'RUB'",
            name="ck_operations_currency_rub",
        ),
        UniqueConstraint(
            "provider_payment_id",
            name="uq_operations_provider_payment_id",
        ),
    )

    operation_id: Mapped[str] = mapped_column(
        String(),
        primary_key=True,
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(20, 2),
        nullable=False,
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[OperationStatus] = mapped_column(
        operation_status_enum,
        nullable=False,
        default=OperationStatus.CREATED,
        server_default=OperationStatus.CREATED.value,
    )

    provider_payment_id: Mapped[str | None] = mapped_column(
        String(),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class Event(Base):
    __tablename__ = "events"

    __table_args__ = (
        Index(
            "ix_events_operation_id_event_id",
            "operation_id",
            "event_id",
        ),
    )

    event_id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )

    operation_id: Mapped[str] = mapped_column(
        ForeignKey(
            "operations.operation_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    type: Mapped[EventType] = mapped_column(
        event_type_enum,
        nullable=False,
    )

    from_status: Mapped[OperationStatus | None] = mapped_column(
        operation_status_enum,
        nullable=True,
    )

    to_status: Mapped[OperationStatus] = mapped_column(
        operation_status_enum,
        nullable=False,
    )

    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )