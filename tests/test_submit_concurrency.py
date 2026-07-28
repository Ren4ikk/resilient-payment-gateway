import asyncio
from uuid import uuid4

import httpx
import pytest


SUBMIT_REQUEST_COUNT = 20


@pytest.mark.asyncio
async def test_concurrent_submit_creates_one_processing_event() -> None:
    operation_id = f"concurrency-{uuid4()}"

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
                "description": "Concurrency test",
            },
        )

        assert create_response.status_code == 201, create_response.text

        submit_responses = await asyncio.gather(
            *[
                client.post(f"/operations/{operation_id}/submit")
                for _ in range(SUBMIT_REQUEST_COUNT)
            ]
        )

        submit_statuses = [
            response.status_code
            for response in submit_responses
        ]

        assert submit_statuses.count(202) == 1, submit_statuses
        assert submit_statuses.count(200) == 19, submit_statuses

        operation_response = await client.get(
            f"/operations/{operation_id}"
        )

        assert operation_response.status_code == 200
        assert operation_response.json()["status"] == "PROCESSING"

        events_response = await client.get(
            f"/operations/{operation_id}/events"
        )

        assert events_response.status_code == 200

        events = events_response.json()

        processing_events = [
            event
            for event in events
            if event["type"] == "PROCESSING"
        ]

        assert len(events) == 2, events
        assert len(processing_events) == 1, events
        assert processing_events[0]["fromStatus"] == "CREATED"
        assert processing_events[0]["toStatus"] == "PROCESSING"
