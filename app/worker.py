import asyncio
import logging
import random
from dataclasses import dataclass
from decimal import Decimal

import httpx
from sqlalchemy import select, update

from app.database import async_session_factory
from app.models import Operation, OperationStatus
from app.provider_client import (
    ProviderClient,
    ProviderPaymentResponse,
)


logger = logging.getLogger(__name__)


def calculate_retry_delay(
    attempt: int,
    *,
    base_delay_seconds: float,
    max_delay_seconds: float,
    jitter_seconds: float,
) -> float:
    backoff_seconds = min(
        base_delay_seconds * 2 ** (attempt - 1),
        max_delay_seconds,
    )

    return backoff_seconds + random.uniform(
        0.0,
        jitter_seconds,
    )


@dataclass(frozen=True, slots=True)
class PendingOperation:
    operation_id: str
    amount: Decimal
    currency: str


class ProviderPaymentIdConflictError(RuntimeError):
    pass


async def load_pending_operation(
    excluded_operation_ids: set[str] | None = None,
) -> PendingOperation | None:
    async with async_session_factory() as session:
        statement = (
            select(Operation)
            .where(
                Operation.status == OperationStatus.PROCESSING,
            )
            .order_by(Operation.created_at.asc())
            .limit(1)
        )

        if excluded_operation_ids:
            statement = statement.where(
                Operation.operation_id.not_in(
                    excluded_operation_ids
                )
            )

        result = await session.execute(statement)
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


async def process_operation(
    operation: PendingOperation,
    provider_client: ProviderClient,
) -> ProviderPaymentResponse:
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

    return provider_response


async def process_pending_operation_once(
    provider_client: ProviderClient,
) -> tuple[PendingOperation, ProviderPaymentResponse] | None:
    operation = await load_pending_operation()

    if operation is None:
        return None

    provider_response = await process_operation(
        operation,
        provider_client,
    )

    return operation, provider_response


async def process_operation_with_retries(
    operation: PendingOperation,
    provider_client: ProviderClient,
    *,
    max_attempts: int = 5,
    base_retry_delay_seconds: float = 1.0,
    max_retry_delay_seconds: float = 8.0,
    jitter_seconds: float = 0.5,
) -> bool:
    for attempt in range(1, max_attempts + 1):
        try:
            await process_operation(
                operation,
                provider_client,
            )

            return True

        except httpx.HTTPStatusError as error:
            if error.response.status_code != 503:
                raise

            logger.warning(
                "Provider returned 503 for operation %s, "
                "attempt %d/%d",
                operation.operation_id,
                attempt,
                max_attempts,
            )

        except httpx.RequestError as error:
            logger.warning(
                "Provider network error for operation %s, "
                "attempt %d/%d: %s",
                operation.operation_id,
                attempt,
                max_attempts,
                error,
            )

        if attempt < max_attempts:
            retry_delay_seconds = calculate_retry_delay(
                attempt,
                base_delay_seconds=(
                    base_retry_delay_seconds
                ),
                max_delay_seconds=(
                    max_retry_delay_seconds
                ),
                jitter_seconds=jitter_seconds,
            )

            logger.warning(
                "Retrying provider request for operation "
                "%s in %.2f seconds",
                operation.operation_id,
                retry_delay_seconds,
            )

            await asyncio.sleep(
                retry_delay_seconds
            )

    return False


async def run_provider_worker(
    provider_client: ProviderClient,
    *,
    poll_interval_seconds: float = 1.0,
) -> None:
    handled_operation_ids: set[str] = set()

    while True:
        operation = await load_pending_operation(
            handled_operation_ids
        )

        if operation is None:
            await asyncio.sleep(poll_interval_seconds)
            continue

        try:
            processed = await process_operation_with_retries(
                operation,
                provider_client,
            )
        except httpx.HTTPStatusError as error:
            logger.error(
                "Provider returned non-retryable status %d "
                "for operation %s",
                error.response.status_code,
                operation.operation_id,
            )

            handled_operation_ids.add(
                operation.operation_id
            )
            continue

        handled_operation_ids.add(
            operation.operation_id
        )

        if not processed:
            logger.error(
                "Provider retries exhausted for operation %s",
                operation.operation_id,
            )
