import json
from pathlib import Path
from typing import Annotated
from uuid import UUID

import typer

from leogent.config.loader import load_config_from_search
from leogent.domain.errors import LeogentError, SessionNotFound
from leogent.domain.event import Event, Session
from leogent.providers.base import ModelProvider
from leogent.providers.factory import create_provider
from leogent.sessions.runner import execute_turn
from leogent.sessions.sqlite import SQLiteSessionStore, default_database_path


def _database_path(database: Path | None) -> Path:
    return database if database is not None else default_database_path()


def _session_id(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as error:
        raise SessionNotFound(f"Invalid session id: {value}") from error


def _event_line(event: Event) -> str:
    payload = json.dumps(event.payload, ensure_ascii=False, separators=(",", ":"))
    occurred_at = event.occurred_at.isoformat()
    return f"{event.sequence:>3}  {event.event_type.value:<18} {occurred_at}  {payload}"


def _print_session(session: Session, events: tuple[Event, ...]) -> None:
    typer.echo(f"Session: {session.id}")
    typer.echo(f"Status:  {session.status.value}")
    typer.echo(f"Created: {session.created_at.isoformat()}")
    typer.echo(f"Updated: {session.updated_at.isoformat()}")
    if session.parent_session_id is not None:
        typer.echo(f"Forked:  {session.parent_session_id} @ {session.fork_event_sequence}")
    typer.echo("Events:")
    for event in events:
        typer.echo(_event_line(event))


def register(app: typer.Typer) -> None:
    sessions_app = typer.Typer(no_args_is_help=True, help="Inspect and branch sessions.")

    @sessions_app.command("list")
    def list_command(
        limit: Annotated[int, typer.Option("--limit", min=1, max=200)] = 20,
        database: Annotated[
            Path | None,
            typer.Option("--db", help="Override the session database path."),
        ] = None,
    ) -> None:
        """List recently updated sessions."""
        try:
            with SQLiteSessionStore(_database_path(database)) as store:
                sessions = store.list_sessions(limit=limit)
                if not sessions:
                    typer.echo("No sessions found.")
                    return
                for session in sessions:
                    typer.echo(
                        f"{session.id}  {session.status.value:<9}  {session.updated_at.isoformat()}"
                    )
        except LeogentError as error:
            typer.echo(f"Error: {error}", err=True)
            raise typer.Exit(1) from None

    @sessions_app.command("show")
    def show_command(
        session_id: Annotated[str, typer.Argument(help="Session ID.")],
        database: Annotated[
            Path | None,
            typer.Option("--db", help="Override the session database path."),
        ] = None,
    ) -> None:
        """Print one session and its ordered events."""
        try:
            with SQLiteSessionStore(_database_path(database)) as store:
                session = store.get_session(_session_id(session_id))
                _print_session(session, store.get_events(session.id))
        except LeogentError as error:
            typer.echo(f"Error: {error}", err=True)
            raise typer.Exit(1) from None

    @sessions_app.command("fork")
    def fork_command(
        session_id: Annotated[str, typer.Argument(help="Source session ID.")],
        at_sequence: Annotated[
            int,
            typer.Option("--at", min=1, help="Last source event to copy."),
        ],
        database: Annotated[
            Path | None,
            typer.Option("--db", help="Override the session database path."),
        ] = None,
    ) -> None:
        """Fork a session from an event prefix."""
        try:
            with SQLiteSessionStore(_database_path(database)) as store:
                child = store.fork_session(_session_id(session_id), at_sequence)
                typer.echo(str(child.id))
        except LeogentError as error:
            typer.echo(f"Error: {error}", err=True)
            raise typer.Exit(1) from None

    app.add_typer(sessions_app, name="sessions")

    @app.command("resume")
    def resume_command(
        session_id: Annotated[str, typer.Argument(help="Session ID to resume.")],
        prompt: Annotated[
            str | None,
            typer.Argument(help="Optional next prompt."),
        ] = None,
        no_tui: Annotated[
            bool,
            typer.Option("--no-tui", help="Use plain output."),
        ] = False,
        provider_name: Annotated[
            str | None,
            typer.Option("--provider", help="Provider profile to use."),
        ] = None,
        stream: Annotated[
            bool,
            typer.Option("--stream/--no-stream", help="Stream text when supported."),
        ] = True,
        database: Annotated[
            Path | None,
            typer.Option("--db", help="Override the session database path."),
        ] = None,
    ) -> None:
        """Show a session or continue it with one new prompt."""
        del no_tui
        provider: ModelProvider | None = None
        try:
            with SQLiteSessionStore(_database_path(database)) as store:
                resolved_id = _session_id(session_id)
                if prompt is None:
                    session = store.get_session(resolved_id)
                    _print_session(session, store.get_events(session.id))
                    return
                if not prompt.strip():
                    raise typer.BadParameter("prompt must not be empty")

                config = load_config_from_search(Path.cwd())
                provider = create_provider(config, provider_name=provider_name)
                result = execute_turn(
                    store,
                    provider,
                    prompt,
                    session_id=resolved_id,
                    stream=stream,
                    on_text=lambda text: typer.echo(text, nl=False),
                )
                if result.text:
                    typer.echo()
                typer.echo(f"session {result.session.id}", err=True)
        except LeogentError as error:
            typer.echo(f"Error: {error}", err=True)
            raise typer.Exit(1) from None
        finally:
            if provider is not None:
                provider.close()
