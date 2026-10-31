from leogent.domain.enums import ErrorCode


class LeogentError(Exception):
    """Base exception for expected Leogent failures."""

    code = ErrorCode.INTERNAL
    retryable = False


class ConfigurationError(LeogentError):
    code = ErrorCode.CONFIGURATION


class SessionError(LeogentError):
    code = ErrorCode.SESSION


class SessionNotFound(SessionError):
    pass


class DuplicateEvent(SessionError):
    pass


class ContextWindowExceeded(LeogentError):
    code = ErrorCode.VALIDATION


class ProviderError(LeogentError):
    code = ErrorCode.PROVIDER

    def __init__(
        self,
        message: str,
        *,
        retryable: bool = False,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.status_code = status_code
