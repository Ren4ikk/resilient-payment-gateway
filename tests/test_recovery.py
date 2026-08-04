import asyncio
import subprocess
from pathlib import Path
from uuid import uuid4

import httpx
import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


async def run_compose(*arguments: str) -> None:
    await asyncio.to_thread(
        subprocess.run,
        ["docker", "compose", *arguments],
        cwd=PROJECT_ROOT,
        check=True,
    )


async def wait_for_health(
    client: httpx.AsyncClient,
) -> None:
    for _ in range(40):
        try:
            response = await client.get("/health")

            if response.status_code == 200:
                return
        except httpx.RequestError:
            pass

        await asyncio.sleep(0.5)

    pytest.fail(
        "Candidate service did not become healthy"
    )


async def wait_for_final_status(
    client: httpx.AsyncClient,
    operation_id: str,
) -> dict[str, object]:
    for _ in range(60):
        try:
            response = await client.get(
                f"/operations/{operation_id}"
            )

            if response.status_code == 200:
                operation = response.json()

                if operation["status"] in {
                    "COMPLETED",
                    "REJECTED",
                }:
                    return operation
        except httpx.RequestError:
            pass

        await asyncio.sleep(0.5)

    pytest.fail(
        "Operation did not reach final status "
        "after candidate-service restart"
    )


@pytest.mark.asyncio
async def test_processing_operation_recovers_after_restart() -> None:
    operation_id = f"recovery-{uuid4()}"

    async with httpx.AsyncClient(
        base_url="http://localhost:8080",
        timeout=5.0,
        trust_env=False,
    ) as client:
        await run_compose(
            "stop",
            "provider-simulator",
        )

        try:
            create_response = await client.post(
                "/operations",
                json={
                    "operationId": operation_id,
                    "amount": "1000.00",
                    "currency": "RUB",
                    "description": "Recovery test",
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

            operation_response = await client.get(
                f"/operations/{operation_id}"
            )

            assert operation_response.status_code == 200
            assert (
                operation_response.json()["status"]
                == "PROCESSING"
            )

            await run_compose(
                "restart",
                "candidate-service",
            )

            await wait_for_health(client)

            await run_compose(
                "start",
                "provider-simulator",
            )

            operation = await wait_for_final_status(
                client,
                operation_id,
            )

            assert (
                operation["providerPaymentId"]
                is not None
            )

            events_response = await client.get(
                f"/operations/{operation_id}/events"
            )

            assert events_response.status_code == 200

            events = events_response.json()
            event_types = [
                event["type"]
                for event in events
            ]

            assert event_types.count("CREATED") == 1
            assert event_types.count("PROCESSING") == 1
            assert (
                event_types.count(operation["status"])
                == 1
            )

        finally:
            await run_compose(
                "start",
                "candidate-service",
            )
            await run_compose(
                "start",
                "provider-simulator",
            )
