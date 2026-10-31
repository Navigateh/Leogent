from pathlib import Path
from typing import Annotated

import typer

from leogent.config.loader import load_config_from_search
from leogent.domain.errors import LeogentError
from leogent.domain.model import Message, MessageRole, ModelRequest
from leogent.providers.base import ModelProvider
from leogent.providers.factory import create_provider
from leogent.sessions.runner import execute_turn
from leogent.sessions.sqlite import SQLiteSessionStore, default_database_path


def run_once(provider: ModelProvider, prompt: str, *, stream: bool = False) -> str:
    if not prompt.strip():
        raise typer.BadParameter("prompt must not be empty")
    request = ModelRequest(
        messages=(Message(role=MessageRole.USER, content=prompt),),
    )
    tool_calls = ()
    if stream and provider.capabilities.supports_streaming:
        parts: list[str] = []
        for chunk in provider.stream(request):
            if chunk.text_delta:
                parts.append(chunk.text_delta)
                typer.echo(chunk.text_delta, nl=False)
            if chunk.tool_calls:
                tool_calls = chunk.tool_calls
        text = "".join(parts)
        if text:
            typer.echo()
    else:
        response = provider.complete(request)
        text = response.content or ""
        if text:
            typer.echo(text)
        tool_calls = response.tool_calls

    if tool_calls:
        names = ", ".join(call.name for call in tool_calls)
        typer.echo(
            f"Model requested tool calls ({names}); tool execution starts in Milestone 4.",
            err=True,
        )
    return text


def register(app: typer.Typer) -> None:
    @app.command("run")
    def run_command(
        prompt: Annotated[str, typer.Argument(help="Prompt to send to the model.")],
        no_tui: Annotated[
            bool,
            typer.Option("--no-tui", help="Use plain single-turn output."),
        ] = False,
        provider_name: Annotated[
            str | None,
            typer.Option("--provider", help="Provider profile to use."),
        ] = None,
        stream: Annotated[
            bool,
            typer.Option("--stream/--no-stream", help="Stream text when supported."),
        ] = True,
    ) -> None:
        """Send one prompt to a configured model provider."""
        del no_tui
        if not prompt.strip():
            raise typer.BadParameter("prompt must not be empty")
        provider: ModelProvider | None = None
        store: SQLiteSessionStore | None = None
        try:
            config = load_config_from_search(Path.cwd())
            provider = create_provider(config, provider_name=provider_name)
            store = SQLiteSessionStore(default_database_path())
            result = execute_turn(
                store,
                provider,
                prompt,
                stream=stream,
                on_text=lambda text: typer.echo(text, nl=False),
            )
            if result.text:
                typer.echo()
            if result.response.tool_calls:
                names = ", ".join(call.name for call in result.response.tool_calls)
                typer.echo(
                    f"Model requested tool calls ({names}); tool execution starts in Milestone 4.",
                    err=True,
                )
            typer.echo(f"session {result.session.id}", err=True)
        except LeogentError as error:
            typer.echo(f"Error: {error}", err=True)
            raise typer.Exit(1) from None
        finally:
            if store is not None:
                store.close()
            if provider is not None:
                provider.close()
