from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select, update

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


class ProviderPaymentIdConflictError(RuntimeError):
    pass


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


async def save_provider_payment_id(
    operation_id: str,
    provider_payment_id: str,
) -> None:
    async with async_session_factory() as session:
        async with session.begin():
            update_result = await session.execute(
                update(Operation)
                .where(
                    Operation.operation_id == operation_id,
                    Operation.provider_payment_id.is_(None),
                )
                .values(
                    provider_payment_id=provider_payment_id,
                )
            )

            if update_result.rowcount == 1:
                return

            operation = await session.get(
                Operation,
                operation_id,
            )

            if operation is None:
                raise RuntimeError(
                    f"Operation {operation_id!r} disappeared"
                )

            if (
                operation.provider_payment_id
                != provider_payment_id
            ):
                raise ProviderPaymentIdConflictError(
                    "Operation already has another "
                    "providerPaymentId"
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

    await save_provider_payment_id(
        operation_id=operation.operation_id,
        provider_payment_id=(
            provider_response.provider_payment_id
        ),
    )

    return operation, provider_response
