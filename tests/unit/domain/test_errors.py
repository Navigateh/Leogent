from leogent.domain.errors import ConfigurationError, ErrorCode, LeogentError


def test_configuration_error_exposes_code_and_retryability() -> None:
    error = ConfigurationError("invalid provider")

    assert isinstance(error, LeogentError)
    assert error.code is ErrorCode.CONFIGURATION
    assert error.retryable is False
    assert str(error) == "invalid provider"
