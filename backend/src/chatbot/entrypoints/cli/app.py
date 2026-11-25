from __future__ import annotations

from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.patch_stdout import patch_stdout

from chatbot.entrypoints.cli.commands import Session, handle_command
from chatbot.entrypoints.cli.dependencies import CliContext
from chatbot.entrypoints.cli.parser import expand_references
from chatbot.entrypoints.cli.rendering import (
    console,
    print_attachments,
    print_conversation_list,
    print_error,
    print_system,
    stream_events,
)

STARTUP_LIMIT = 5


async def run(ctx: CliContext) -> None:
    session = Session()
    pending = await _startup_pick(ctx, session)

    prompt = PromptSession(history=InMemoryHistory())

    if pending:
        await _handle_user_message(pending, ctx, session)

    while True:
        try:
            with patch_stdout():
                line = await prompt.prompt_async("you ❯ ", multiline=False)
        except (EOFError, KeyboardInterrupt):
            print_system("bye.")
            return

        line = line.strip()
        if not line:
            continue

        if line.startswith("/"):
            should_quit = await handle_command(line, ctx, session)
            if should_quit:
                return
            continue

        await _handle_user_message(line, ctx, session)


async def _handle_user_message(line: str, ctx: CliContext, session: Session) -> None:
    if session.active_id is None:
        conv = await ctx.create.execute(ctx.acting_user)
        session.active_id = conv.id

    expanded = expand_references(line, ctx.cwd)
    print_attachments(expanded.attachments, expanded.skipped)

    try:
        await stream_events(
            ctx.send.stream(
                session.active_id, ctx.acting_user, expanded.content, language=ctx.language
            )
        )
    except Exception as e:  # noqa: BLE001 — surface any LLM/DB failure
        print_error(f"{type(e).__name__}: {e}")


async def _startup_pick(ctx: CliContext, session: Session) -> str | None:
    """Return any message to send immediately (when user types text instead of a number)."""
    convs = await ctx.list.execute(ctx.acting_user)
    recent = convs[:STARTUP_LIMIT]
    session.last_listing = recent

    console.print("[bold]Chatbot CLI[/bold]  (type /help for commands)")
    if recent:
        console.print("Recent conversations:")
        rows = [(i + 1, c.id, c.title, c.created_at) for i, c in enumerate(recent)]
        print_conversation_list(rows)
        console.print(f"  [cyan]{len(recent) + 1:>2}[/cyan]  [new conversation]")
        console.print(
            "[dim](press Enter for new, type a number to resume, "
            "or just type your message to start a new conversation with it)[/dim]"
        )
    else:
        console.print(
            "No conversations yet — type your first message "
            "or press Enter for an empty new conversation."
        )

    while True:
        try:
            choice = (await PromptSession().prompt_async("pick ❯ ")).strip()
        except (EOFError, KeyboardInterrupt):
            raise SystemExit(0) from None

        if choice.lower() in ("/quit", "/exit", "/q"):
            raise SystemExit(0) from None

        if not choice:
            await _start_new(ctx, session)
            return None

        try:
            n = int(choice)
        except ValueError:
            # Non-numeric → new conversation, send the text as the first message
            await _start_new(ctx, session)
            return choice

        if n == len(recent) + 1 or (not recent and n == 1):
            await _start_new(ctx, session)
            return None
        if 1 <= n <= len(recent):
            chosen = recent[n - 1]
            session.active_id = chosen.id
            print_system(f"resumed: {chosen.title or '(untitled)'}")
            return None
        print_error("out of range")


async def _start_new(ctx: CliContext, session: Session) -> None:
    conv = await ctx.create.execute(ctx.acting_user)
    session.active_id = conv.id
    print_system(f"started new conversation {str(conv.id)[:8]}")
