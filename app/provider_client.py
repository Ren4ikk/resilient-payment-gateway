from decimal import Decimal
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field


class ProviderPaymentResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    provider_payment_id: str = Field(
        validation_alias="providerPaymentId",
        min_length=1,
    )
    status: Literal["ACCEPTED"]


class ProviderClient:
    def __init__(
        self,
        base_url: str,
        timeout_seconds: float = 5.0,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=httpx.Timeout(timeout_seconds),
        )

    async def create_payment(
        self,
        *,
        operation_id: str,
        amount: Decimal,
        currency: str,
    ) -> ProviderPaymentResponse:
        response = await self._client.post(
            "/payments",
            headers={
                "Idempotency-Key": operation_id,
                "X-Correlation-ID": operation_id,
            },
            json={
                "operationId": operation_id,
                "amount": format(amount, ".2f"),
                "currency": currency,
            },
        )

        response.raise_for_status()

        return ProviderPaymentResponse.model_validate(
            response.json()
        )

    async def aclose(self) -> None:
        await self._client.aclose()