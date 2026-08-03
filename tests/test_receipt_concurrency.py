import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest


RECEIPT_REQUEST_COUNT = 20


@pytest.mark.asyncio
async def test_concurrent_duplicate_receipts_create_one_event() -> None:
    operation_id = f"receipt-concurrency-{uuid4()}"
    provider_payment_id = str(uuid4())

    async with httpx.AsyncClient(
        base_url="http://localhost:8080",
        timeout=10.0,
        trust_env=False,
    ) as client:
        create_response = await client.post(
            "/operations",
            json={
                "operationId": operation_id,
                "amount": "1000.00",
                "currency": "RUB",
                "description": "Receipt concurrency test",
            },
        )

        assert create_response.status_code == 201, (
            create_response.text
        )

        submit_response = await client.post(
            f"/operations/{operation_id}/submit"
        )

        assert submit_response.status_code == 202, (
            submit_response.text
        )

        receipt = {
            "providerPaymentId": provider_payment_id,
            "operationId": operation_id,
            "result": "COMPLETED",
            "message": "Payment completed",
            "occurredAt": datetime.now(UTC).isoformat(),
        }

        receipt_responses = await asyncio.gather(
            *[
                client.post(
                    "/receipts",
                    json=receipt,
                )
                for _ in range(RECEIPT_REQUEST_COUNT)
            ]
        )

        receipt_statuses = [
            response.status_code
            for response in receipt_responses
        ]

        assert receipt_statuses == (
            [204] * RECEIPT_REQUEST_COUNT
        ), receipt_statuses

        operation_response = await client.get(
            f"/operations/{operation_id}"
        )

        assert operation_response.status_code == 200

        operation = operation_response.json()

        assert operation["status"] == "COMPLETED"
        assert (
            operation["providerPaymentId"]
            == provider_payment_id
        )

        events_response = await client.get(
            f"/operations/{operation_id}/events"
        )

        assert events_response.status_code == 200

        events = events_response.json()

        completed_events = [
            event
            for event in events
            if event["type"] == "COMPLETED"
        ]

        ignored_events = [
            event
            for event in events
            if event["type"] == "RECEIPT_IGNORED"
        ]

        assert len(events) == 3, events
        assert len(completed_events) == 1, events
        assert len(ignored_events) == 0, events
        assert completed_events[0]["fromStatus"] == "PROCESSING"
        assert completed_events[0]["toStatus"] == "COMPLETED"
