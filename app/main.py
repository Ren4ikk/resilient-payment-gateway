from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session

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