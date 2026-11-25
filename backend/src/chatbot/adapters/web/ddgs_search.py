from __future__ import annotations

import logging
from functools import partial

from anyio import to_thread

from chatbot.domain.conversation.ports.web_tools import SearchResult, WebSearch

logger = logging.getLogger(__name__)


class DdgsWebSearch(WebSearch):
    """Web search via the ``ddgs`` library (DuckDuckGo). The library is
    synchronous, so every call is pushed onto the anyio thread pool. Errors are
    logged and surfaced as an empty result list — the tool loop turns that into a
    tool_result the model can react to, never a stream failure."""

    def __init__(self, region: str = "wt-wt", safesearch: str = "moderate") -> None:
        self._region = region
        self._safesearch = safesearch

    async def search(self, query: str, max_results: int) -> list[SearchResult]:
        try:
            rows = await to_thread.run_sync(partial(self._search_sync, query, max_results))
        except Exception:  # noqa: BLE001 — never let a search failure break the stream
            logger.exception("ddgs search failed for query=%r", query)
            return []
        return rows

    def _search_sync(self, query: str, max_results: int) -> list[SearchResult]:
        # Imported lazily so the dependency is only needed when web tools run.
        from ddgs import DDGS

        with DDGS() as ddgs:
            hits = ddgs.text(
                query,
                region=self._region,
                safesearch=self._safesearch,
                max_results=max_results,
            )
            return [
                SearchResult(
                    title=h.get("title", ""),
                    url=h.get("href", "") or h.get("url", ""),
                    snippet=h.get("body", ""),
                )
                for h in hits
            ]
