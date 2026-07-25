from fastapi import FastAPI, status


app = FastAPI(
    title="Resilient payment gateway",
    version="0.1.0",
)


@app.get(
    "/health",
    status_code=status.HTTP_200_OK,
    tags=["system"],
    summary="Check service health",
)
async def health() -> dict[str, str]:
    return {"status": "ok"}
