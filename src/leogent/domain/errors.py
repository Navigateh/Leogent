from leogent.domain.enums import ErrorCode


class LeogentError(Exception):
    """Base exception for expected Leogent failures."""

    code = ErrorCode.INTERNAL
    retryable = False


class ConfigurationError(LeogentError):
    code = ErrorCode.CONFIGURATION
