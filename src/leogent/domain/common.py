from datetime import UTC, datetime
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field


class DomainModel(BaseModel):
    """Base model for immutable, strictly validated domain values."""

    model_config = ConfigDict(extra="forbid", frozen=True)


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def normalize_datetime(value: object) -> datetime:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError as error:
            raise ValueError("datetime must be an ISO 8601 value") from error
    if not isinstance(value, datetime):
        raise ValueError("datetime value is required")
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


UtcDateTime = Annotated[datetime, BeforeValidator(normalize_datetime)]


class Usage(DomainModel):
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class GenerationParameters(DomainModel):
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    top_p: float = Field(default=1.0, gt=0.0, le=1.0)
    max_output_tokens: int = Field(default=4096, gt=0)
    stop: tuple[str, ...] = ()
