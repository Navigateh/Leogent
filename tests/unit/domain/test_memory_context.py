from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

from leogent.domain.context import ContextPlan, ContextSection, ContextSource
from leogent.domain.memory import MemoryItem, MemoryScope, MemoryType
from leogent.domain.skill import SkillDescriptor
from leogent.domain.state import RunState


def test_project_memory_requires_scope_key() -> None:
    with pytest.raises(ValidationError):
        MemoryItem(
            memory_type=MemoryType.SEMANTIC,
            scope=MemoryScope.PROJECT,
            content="Uses Python",
            confidence=0.9,
        )


def test_global_memory_rejects_project_scope_key() -> None:
    with pytest.raises(ValidationError):
        MemoryItem(
            memory_type=MemoryType.PREFERENCE,
            scope=MemoryScope.GLOBAL,
            scope_key="project-a",
            content="Prefers concise answers",
            confidence=0.9,
        )


def test_context_plan_estimates_total_from_sections() -> None:
    plan = ContextPlan(
        context_window=8192,
        budget_tokens=4096,
        sections=(
            ContextSection(source=ContextSource.SYSTEM, content="rules", estimated_tokens=12),
            ContextSection(source=ContextSource.USER, content="task", estimated_tokens=8),
        ),
    )

    assert plan.estimated_tokens == 20


def test_skill_descriptor_round_trip_preserves_resources() -> None:
    descriptor = SkillDescriptor(
        name="code-review",
        description="Review code changes",
        path=Path("skills/code-review"),
        resources=("references/checklist.md",),
    )

    restored = SkillDescriptor.model_validate_json(descriptor.model_dump_json())

    assert restored == descriptor


def test_run_state_round_trip_preserves_session_id() -> None:
    session_id = UUID("00000000-0000-0000-0000-000000000001")
    state = RunState(session_id=session_id, current_step=2)

    restored = RunState.model_validate_json(state.model_dump_json())

    assert restored.session_id == session_id
    assert restored.current_step == 2
