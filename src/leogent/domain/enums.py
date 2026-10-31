from enum import StrEnum


class MessageRole(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class EventType(StrEnum):
    SESSION_STARTED = "session_started"
    USER_MESSAGE = "user_message"
    MODEL_REQUEST = "model_request"
    MODEL_RESPONSE = "model_response"
    ACTION_REQUESTED = "action_requested"
    TOOL_COMPLETED = "tool_completed"
    MEMORY_WRITTEN = "memory_written"
    MEMORY_RETRIEVED = "memory_retrieved"
    MEMORY_DELETED = "memory_deleted"
    SKILL_LOADED = "skill_loaded"
    CONTEXT_COMPACTED = "context_compacted"
    RUN_FINISHED = "run_finished"
    RUN_FAILED = "run_failed"


class SessionStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TerminationReason(StrEnum):
    COMPLETED = "completed"
    MAX_STEPS = "max_steps"
    TOKEN_BUDGET = "token_budget"
    CANCELLED = "cancelled"
    ERROR = "error"


class MemoryType(StrEnum):
    SEMANTIC = "semantic"
    EPISODIC = "episodic"
    PROCEDURAL = "procedural"
    PREFERENCE = "preference"


class MemoryScope(StrEnum):
    PROJECT = "project"
    GLOBAL = "global"


class ContextSource(StrEnum):
    SYSTEM = "system"
    USER = "user"
    PENDING_TOOL = "pending_tool"
    RECENT_EVENT = "recent_event"
    SUMMARY = "summary"
    MEMORY = "memory"
    SKILL = "skill"


class ErrorCode(StrEnum):
    CONFIGURATION = "configuration"
    SESSION = "session"
    VALIDATION = "validation"
    PROVIDER = "provider"
    TOOL = "tool"
    MEMORY = "memory"
    CONTEXT = "context"
    INTERNAL = "internal"
