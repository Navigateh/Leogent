from typing import Self
from uuid import UUID, uuid4

from pydantic import Field, model_validator

from leogent.domain.common import DomainModel, UtcDateTime, utc_now
from leogent.domain.enums import MemoryScope, MemoryType


class MemoryItem(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    memory_type: MemoryType
    scope: MemoryScope
    scope_key: str | None = Field(default=None, min_length=1)
    content: str = Field(min_length=1)
    source_event_id: UUID | None = None
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    created_at: UtcDateTime = Field(default_factory=utc_now)
    last_accessed_at: UtcDateTime | None = None
    expires_at: UtcDateTime | None = None

    @model_validator(mode="after")
    def validate_scope_and_expiry(self) -> Self:
        if self.scope is MemoryScope.PROJECT and not self.scope_key:
            raise ValueError("project-scoped memory requires scope_key")
        if self.scope is MemoryScope.GLOBAL and self.scope_key is not None:
            raise ValueError("global-scoped memory cannot have scope_key")
        if self.expires_at is not None and self.expires_at <= self.created_at:
            raise ValueError("expires_at must be after created_at")
        return self
