_provider_retries_total = 0


def record_provider_retry() -> None:
    global _provider_retries_total

    _provider_retries_total += 1


def get_provider_retries_total() -> int:
    return _provider_retries_total
