from uuid import UUID

from pydantic import Field

from leogent.domain.common import DomainModel, Usage
from leogent.domain.enums import TerminationReason


class RunState(DomainModel):
    session_id: UUID
    current_step: int = Field(default=0, ge=0)
    context_tokens: int = Field(default=0, ge=0)
    usage: Usage = Field(default_factory=Usage)
    termination_reason: TerminationReason | None = None
