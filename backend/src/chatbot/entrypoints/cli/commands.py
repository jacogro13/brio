from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from chatbot.domain.conversation.model import Conversation
from chatbot.entrypoints.cli.dependencies import CliContext
from chatbot.entrypoints.cli.rendering import (
    print_conversation_list,
    print_error,
    print_system,
)

HELP_TEXT = """\
Slash commands:
  /new                 start a new conversation
  /list                show recent conversations (numbered)
  /switch <n>          switch to conversation by index from last /list
  /delete <n>          delete conversation by index from last /list
  /help                show this help
  /quit                exit (Ctrl-D also works)

Reference files in your message with @path (paths are relative to the
directory you launched the CLI from). Directories give a non-recursive
listing. Paths outside cwd, binaries, and files larger than 100 KB are skipped.
"""


@dataclass
class Session:
    active_id: UUID | None = None
    last_listing: list[Conversation] = field(default_factory=list)


class CommandHandled(Exception):
    """Raised by command handlers to short-circuit the main loop."""


async def handle_command(line: str, ctx: CliContext, session: Session) -> bool:
    """Dispatch a slash command. Returns True if the REPL should quit."""
    parts = line.strip().split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    if cmd in ("/quit", "/exit", "/q"):
        return True
    if cmd == "/help":
        print_system(HELP_TEXT)
        return False
    if cmd == "/new":
        await _cmd_new(ctx, session)
        return False
    if cmd == "/list":
        await _cmd_list(ctx, session)
        return False
    if cmd == "/switch":
        await _cmd_switch(arg, ctx, session)
        return False
    if cmd == "/delete":
        await _cmd_delete(arg, ctx, session)
        return False

    print_error(f"unknown command: {cmd}. Type /help.")
    return False


async def _cmd_new(ctx: CliContext, session: Session) -> None:
    conv = await ctx.create.execute(ctx.acting_user)
    session.active_id = conv.id
    print_system(f"started new conversation {_short(conv.id)}")


async def _cmd_list(ctx: CliContext, session: Session) -> None:
    convs = await ctx.list.execute(ctx.acting_user)
    session.last_listing = convs
    rows = [(i + 1, c.id, c.title, c.created_at) for i, c in enumerate(convs)]
    print_conversation_list(rows)


async def _cmd_switch(arg: str, ctx: CliContext, session: Session) -> None:
    conv = _pick(arg, session)
    if conv is None:
        return
    session.active_id = conv.id
    print_system(f"switched to: {conv.title or '(untitled)'}")


async def _cmd_delete(arg: str, ctx: CliContext, session: Session) -> None:
    conv = _pick(arg, session)
    if conv is None:
        return
    await ctx.delete.execute(conv.id, ctx.acting_user)
    if session.active_id == conv.id:
        session.active_id = None
    session.last_listing = [c for c in session.last_listing if c.id != conv.id]
    print_system(f"deleted: {conv.title or '(untitled)'}")


def _pick(arg: str, session: Session) -> Conversation | None:
    if not arg.strip():
        print_error("usage: /switch <n>  (n is from /list)")
        return None
    try:
        idx = int(arg.strip())
    except ValueError:
        print_error("argument must be a number")
        return None
    if not session.last_listing:
        print_error("no listing yet — run /list first")
        return None
    if not (1 <= idx <= len(session.last_listing)):
        print_error(f"index out of range (1..{len(session.last_listing)})")
        return None
    return session.last_listing[idx - 1]


def _short(uuid: UUID) -> str:
    return str(uuid)[:8]
