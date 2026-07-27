from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.models import Event, EventType, Operation, OperationStatus
from app.schemas import (
    EventResponse,
    OperationCreateRequest,
    OperationResponse,
)

app = FastAPI(
    title="Resilient payment gateway",
    version="0.1.0",
)

DatabaseSession = Annotated[
    AsyncSession,
    Depends(get_db_session),
]


@app.get(
    "/health",
    status_code=status.HTTP_200_OK,
    tags=["system"],
    summary="Check service health",
)
async def health(session: DatabaseSession) -> dict[str, str]:
    try:
        await session.execute(text("SELECT 1"))
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable",
        ) from error

    return {"status": "ok"}


@app.post(
    "/operations",
    response_model=OperationResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["operations"],
    summary="Create operation",
)
async def create_operation(
    payload: OperationCreateRequest,
    session: DatabaseSession,
) -> OperationResponse:
    operation = Operation(
        operation_id=payload.operation_id,
        amount=payload.amount,
        currency=payload.currency,
        description=payload.description,
        status=OperationStatus.CREATED,
        provider_payment_id=None,
    )

    event = Event(
        operation_id=payload.operation_id,
        type=EventType.CREATED,
        from_status=None,
        to_status=OperationStatus.CREATED,
        message="Operation created",
    )

    try:
        async with session.begin():
            session.add(operation)
            await session.flush()

            session.add(event)
    except IntegrityError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Operation with this operationId already exists",
        ) from error

    return OperationResponse.model_validate(operation)


@app.get(
    "/operations/{operation_id}",
    response_model=OperationResponse,
    status_code=status.HTTP_200_OK,
    tags=["operations"],
    summary="Get operation",
)
async def get_operation(
    operation_id: str,
    session: DatabaseSession,
) -> OperationResponse:
    operation = await session.get(Operation, operation_id)

    if operation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Operation not found",
        )

    return OperationResponse.model_validate(operation)


@app.get(
    "/operations/{operation_id}/events",
    response_model=list[EventResponse],
    status_code=status.HTTP_200_OK,
    tags=["operations"],
    summary="Get operation events",
)
async def get_operation_events(
    operation_id: str,
    session: DatabaseSession,
) -> list[EventResponse]:
    operation = await session.get(Operation, operation_id)

    if operation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Operation not found",
        )

    result = await session.execute(
        select(Event)
        .where(Event.operation_id == operation_id)
        .order_by(Event.event_id.asc())
    )

    events = result.scalars().all()

    return [
        EventResponse.model_validate(event)
        for event in events
    ]
