from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select

from app.database import async_session_factory
from app.models import Operation, OperationStatus
from app.provider_client import (
    ProviderClient,
    ProviderPaymentResponse,
)


@dataclass(frozen=True, slots=True)
class PendingOperation:
    operation_id: str
    amount: Decimal
    currency: str


async def load_pending_operation() -> PendingOperation | None:
    async with async_session_factory() as session:
        result = await session.execute(
            select(Operation)
            .where(
                Operation.status == OperationStatus.PROCESSING,
                Operation.provider_payment_id.is_(None),
            )
            .order_by(Operation.created_at.asc())
            .limit(1)
        )

        operation = result.scalar_one_or_none()

        if operation is None:
            return None

        return PendingOperation(
            operation_id=operation.operation_id,
            amount=operation.amount,
            currency=operation.currency,
        )


async def process_pending_operation_once(
    provider_client: ProviderClient,
) -> tuple[PendingOperation, ProviderPaymentResponse] | None:
    operation = await load_pending_operation()

    if operation is None:
        return None

    provider_response = await provider_client.create_payment(
        operation_id=operation.operation_id,
        amount=operation.amount,
        currency=operation.currency,
    )

    return operation, provider_response
