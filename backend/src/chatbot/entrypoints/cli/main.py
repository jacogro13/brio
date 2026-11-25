from __future__ import annotations

import asyncio

from chatbot.entrypoints.cli.app import run
from chatbot.entrypoints.cli.dependencies import build_context, resolve_user_id
from chatbot.entrypoints.cli.rendering import print_error


async def _run_and_close(ctx) -> None:
    try:
        # User resolution needs the DB, so it runs inside the event loop; a bad
        # choice exits cleanly (engine still disposed by the finally).
        ctx.user_id = await resolve_user_id(ctx)
        await run(ctx)
    finally:
        await ctx.close()


def main() -> None:
    try:
        ctx = build_context()
    except RuntimeError as e:
        print_error(str(e))
        raise SystemExit(1) from e
    try:
        asyncio.run(_run_and_close(ctx))
    except RuntimeError as e:
        print_error(str(e))
        raise SystemExit(1) from e


if __name__ == "__main__":
    main()
