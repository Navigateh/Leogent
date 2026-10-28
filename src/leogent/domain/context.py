from pydantic import Field

from leogent.domain.common import DomainModel
from leogent.domain.enums import ContextSource


class ContextSection(DomainModel):
    source: ContextSource
    source_id: str | None = None
    content: str
    estimated_tokens: int = Field(ge=0)


class ContextPlan(DomainModel):
    context_window: int = Field(gt=0)
    budget_tokens: int = Field(gt=0)
    sections: tuple[ContextSection, ...] = ()
    omitted_sources: tuple[str, ...] = ()

    @property
    def estimated_tokens(self) -> int:
        return sum(section.estimated_tokens for section in self.sections)
