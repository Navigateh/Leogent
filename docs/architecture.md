# Leogent Architecture

This document describes the architecture currently implemented by Milestones 0
through 3. Later milestones add behavior behind the interfaces described here.

## Package Layers

```text
CLI
 │
 ├── config
 │    ├── models
 │    ├── paths
 │    └── loader
 │
 ├── providers
 │    ├── OpenAI-compatible
 │    ├── Anthropic
 │    └── scripted mock
 │
 ├── sessions
 │    ├── SQLite migrations
 │    ├── append-only event store
 │    └── single-turn runner
 │
 └── domain
      ├── model and actions
      ├── events and session state
      ├── memory and skills
      └── context plans
```

The `domain` package is infrastructure-independent. It does not import the CLI,
configuration loader, a provider SDK, SQLite, or MCP. All domain values are
immutable Pydantic models with strict field validation.

## Domain Boundaries

The implemented domain models and provider boundary cover:

- Messages, generation parameters, model requests, model responses, and usage.
- Tool definitions, tool calls, and normalized tool results.
- Internal actions such as tool calls, memory operations, Skill loading, and
  finishing a run.
- Session events, Session metadata, and reconstructed run state.
- Long-term memory items, Skill descriptors, and context plans.
- Normalized provider capabilities, streaming chunks, and request validation.
- OpenAI-compatible and Anthropic request/response conversion.

The domain contracts do not perform I/O. Provider adapters translate HTTP
requests and streaming events into the contracts but do not execute tools or
run an Agent Loop.

## Configuration Flow

Configuration loading has three stages:

1. Read an optional global JSON file and the nearest project
   `.leogent/config.json`.
2. Deep-merge them, with project values taking precedence.
3. Validate the complete merged document once as `AppConfig`.

`LEOGENT_DEFAULT_PROVIDER` can override the selected provider after merging.
Relative Transformers model paths are resolved from the configuration file that
provided the path. `LEOGENT_HOME` overrides the user data directory.

API keys are never configuration values. Provider profiles contain an
environment variable name such as `CLOUD_API_KEY`, and `resolve_api_key` reads
that variable only when requested. Validation errors raised by the loader omit
invalid input values.

## Runtime Direction

Milestones 2 and 3 connect persisted model I/O through:

```text
CLI run/resume
  -> SessionStore (create or restore)
  -> Provider factory -> ModelProvider
  -> append model response
  -> SessionStore (rebuild state, list, show, fork)
```

Future milestones connect these contracts through:

```text
Session events -> ContextBuilder -> ModelProvider
                               -> DecisionPolicy
                               -> ActionExecutor -> MCP / Memory / Skills
                               -> Session events
```

The event log is the source of truth for Session recovery. The model context
will remain a per-request projection constructed by policy.

## Current Non-Goals

Milestones 0 through 3 do not implement the Agent Loop, MCP, memory storage or
retrieval, context compaction, Skill loading, or TUI rendering. They also provide
no sandbox or permission boundary.
