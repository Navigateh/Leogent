from typing import Annotated, Literal, Self, TypeAlias

from pydantic import Field, model_validator

from leogent.domain.common import DomainModel
from leogent.domain.enums import MemoryScope, MemoryType
from leogent.domain.model import ToolCall


class ToolCallAction(DomainModel):
    type: Literal["call_tool"] = "call_tool"
    call: ToolCall


class LoadSkillAction(DomainModel):
    type: Literal["load_skill"] = "load_skill"
    name: str = Field(min_length=1)


class RememberAction(DomainModel):
    type: Literal["remember"] = "remember"
    content: str = Field(min_length=1)
    memory_type: MemoryType
    scope: MemoryScope
    scope_key: str | None = None
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_scope_key(self) -> Self:
        if self.scope is MemoryScope.PROJECT and not self.scope_key:
            raise ValueError("project-scoped memory requires scope_key")
        if self.scope is MemoryScope.GLOBAL and self.scope_key is not None:
            raise ValueError("global-scoped memory cannot have scope_key")
        return self


class SearchMemoryAction(DomainModel):
    type: Literal["search_memory"] = "search_memory"
    query: str = Field(min_length=1)
    limit: int = Field(default=5, gt=0, le=20)
    scope: MemoryScope | None = None
    scope_key: str | None = None

    @model_validator(mode="after")
    def validate_scope_key(self) -> Self:
        if self.scope is MemoryScope.PROJECT and not self.scope_key:
            raise ValueError("project-scoped search requires scope_key")
        if self.scope is MemoryScope.GLOBAL and self.scope_key is not None:
            raise ValueError("global-scoped search cannot have scope_key")
        return self


class FinishAction(DomainModel):
    type: Literal["finish"] = "finish"
    answer: str = Field(min_length=1)


Action: TypeAlias = Annotated[
    ToolCallAction | LoadSkillAction | RememberAction | SearchMemoryAction | FinishAction,
    Field(discriminator="type"),
]
