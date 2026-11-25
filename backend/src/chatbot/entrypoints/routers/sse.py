from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi.responses import StreamingResponse


def sse_stream(events: AsyncIterator[dict]) -> StreamingResponse:
    """Frame a stream of plain event dicts as an ``text/event-stream`` response.

    Use cases yield typed event dicts (``{"type": "token"|"done"|"error", ...}``);
    the SSE ``data: {json}\\n\\n`` framing lives here, out of the use case.
    """

    async def _framed() -> AsyncIterator[str]:
        async for event in events:
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        _framed(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
