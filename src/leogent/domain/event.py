from typing import Self
from uuid import UUID, uuid4

from pydantic import Field, JsonValue, model_validator

from leogent.domain.common import DomainModel, UtcDateTime, utc_now
from leogent.domain.enums import EventType, SessionStatus


class Event(DomainModel):
    event_id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    sequence: int = Field(ge=1)
    event_type: EventType
    occurred_at: UtcDateTime = Field(default_factory=utc_now)
    payload: dict[str, JsonValue] = Field(default_factory=dict)


class Session(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    status: SessionStatus = SessionStatus.ACTIVE
    created_at: UtcDateTime = Field(default_factory=utc_now)
    updated_at: UtcDateTime = Field(default_factory=utc_now)
    parent_session_id: UUID | None = None
    fork_event_sequence: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_times_and_fork(self) -> Self:
        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot precede created_at")
        has_parent = self.parent_session_id is not None
        has_sequence = self.fork_event_sequence is not None
        if has_parent != has_sequence:
            raise ValueError("fork requires both parent_session_id and fork_event_sequence")
        if self.parent_session_id == self.id:
            raise ValueError("a session cannot be its own parent")
        return self
