from __future__ import annotations

import sys
from collections.abc import AsyncIterator, Iterable
from datetime import datetime
from uuid import UUID

from rich.console import Console

from chatbot.entrypoints.cli.parser import Attachment

console = Console()


def print_attachments(
    attachments: Iterable[Attachment], skipped: Iterable[tuple[str, str]]
) -> None:
    for att in attachments:
        kind = "📁" if att.kind == "dir" else "📎"
        console.print(f"[dim]{kind} included {att.path.name} ({att.size_bytes} bytes)[/dim]")
    for token, reason in skipped:
        console.print(f"[yellow]⚠ skipped {token}: {reason}[/yellow]")


def print_conversation_list(rows: list[tuple[int, UUID, str | None, datetime]]) -> None:
    if not rows:
        console.print("[dim](no conversations yet)[/dim]")
        return
    for idx, _id, title, created in rows:
        label = title or "(untitled)"
        if len(label) > 60:
            label = label[:57] + "..."
        console.print(f"  [cyan]{idx:>2}[/cyan]  {label}  [dim]{created:%Y-%m-%d %H:%M}[/dim]")


def print_user_prefix() -> None:
    console.print("[bold green]you[/bold green] ❯ ", end="")


def print_assistant_prefix() -> None:
    console.print("[bold magenta]bot[/bold magenta] ❯ ", end="")


def print_system(msg: str) -> None:
    console.print(f"[dim]{msg}[/dim]")


def print_error(msg: str) -> None:
    console.print(f"[red]error:[/red] {msg}")


async def stream_events(events: AsyncIterator[dict]) -> str:
    """Consume typed event dicts from a use case, print tokens, return full text.

    Reasoning (``thinking`` events) is buffered and printed dimmed just before
    the answer begins; only the answer text is returned.
    """
    accumulated = ""
    thinking = ""
    answer_started = False

    def _start_answer() -> None:
        nonlocal answer_started
        if answer_started:
            return
        if thinking.strip():
            console.print(thinking.strip(), style="dim italic")
        print_assistant_prefix()
        answer_started = True

    async for event in events:
        etype = event.get("type")
        if etype == "error":
            print_error(event.get("message", "unknown error"))
            continue
        if etype == "thinking":
            thinking += event.get("content", "")
            continue
        if etype == "tool_start":
            tool = event.get("tool", "tool")
            detail = event.get("query") or event.get("url") or ""
            console.print(f"[dim]🔧 {tool}: {detail}[/dim]")
            continue
        if etype == "tool_end":
            mark = "✓" if event.get("ok") else "✗"
            console.print(f"[dim]   {mark} {event.get('summary', '')}[/dim]")
            continue
        if etype == "done":
            continue
        if etype == "token":
            token = event.get("content", "")
            if token:
                _start_answer()
                accumulated += token
                sys.stdout.write(token)
                sys.stdout.flush()
    _start_answer()  # ensure prefix/thinking print even if no answer tokens arrived
    sys.stdout.write("\n")
    sys.stdout.flush()
    return accumulated
