from pathlib import Path

from pydantic import Field

from leogent.domain.common import DomainModel


class SkillDescriptor(DomainModel):
    name: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    description: str = Field(min_length=1)
    version: str = Field(default="0.1.0", min_length=1)
    path: Path
    resources: tuple[str, ...] = ()
