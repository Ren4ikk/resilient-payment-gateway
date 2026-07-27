import re
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import OperationStatus


_AMOUNT_PATTERN = re.compile(r"^(?:0|[1-9]\d{0,17})(?:\.\d{1,2})?$")


class OperationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_id: str = Field(
        validation_alias="operationId",
        serialization_alias="operationId",
        min_length=1,
        strict=True,
    )
    amount: Decimal
    currency: Literal["RUB"]
    description: str | None = None

    @field_validator("operation_id")
    @classmethod
    def validate_operation_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("operationId must not be blank")

        if value != value.strip():
            raise ValueError(
                "operationId must not have leading or trailing whitespace"
            )

        return value

    @field_validator("amount", mode="before")
    @classmethod
    def validate_amount(cls, value: object) -> Decimal:
        if not isinstance(value, str):
            raise ValueError("amount must be a string")

        if _AMOUNT_PATTERN.fullmatch(value) is None:
            raise ValueError(
                "amount must contain at most 18 integer digits "
                "and at most 2 fractional digits"
            )

        amount = Decimal(value)

        if amount <= 0:
            raise ValueError("amount must be greater than zero")

        return amount


class OperationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    operation_id: str = Field(serialization_alias="operationId")
    amount: Decimal
    currency: Literal["RUB"]
    description: str | None
    status: OperationStatus
    provider_payment_id: str | None = Field(
        serialization_alias="providerPaymentId"
    )
