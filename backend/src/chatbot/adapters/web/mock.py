from __future__ import annotations

from chatbot.domain.conversation.ports.web_tools import (
    PageFetcher,
    SearchResult,
    WebSearch,
)


class MockWebSearch(WebSearch):
    """Deterministic search results for tests / offline runs."""

    def __init__(self, results: list[SearchResult] | None = None) -> None:
        self._results = results or [
            SearchResult(
                title="Example Domain",
                url="https://example.com/",
                snippet="This domain is for use in illustrative examples.",
            ),
        ]
        self.calls: list[tuple[str, int]] = []

    async def search(self, query: str, max_results: int) -> list[SearchResult]:
        self.calls.append((query, max_results))
        return self._results[:max_results]


class MockPageFetcher(PageFetcher):
    """Returns canned page text for tests."""

    def __init__(self, text: str = "Example page body text.") -> None:
        self._text = text
        self.calls: list[str] = []

    async def fetch(self, url: str) -> str:
        self.calls.append(url)
        return self._text
