from httpx import Response

from leogent.domain.errors import ProviderError


def retryable_status(status_code: int) -> bool:
    return status_code in {408, 409, 425, 429} or status_code >= 500


def redact(value: str, secret: str | None) -> str:
    if secret:
        return value.replace(secret, "[redacted]")
    return value


def error_from_response(
    provider_name: str,
    response: Response,
    secret: str | None,
) -> ProviderError:
    body = redact(response.text[:1000].strip(), secret)
    detail = f": {body}" if body else ""
    return ProviderError(
        f"{provider_name} returned HTTP {response.status_code}{detail}",
        retryable=retryable_status(response.status_code),
        status_code=response.status_code,
    )
