from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class SearchResult:
    """A single web search hit. ``snippet`` may be empty for engines that don't
    return one."""

    title: str
    url: str
    snippet: str = ""


class WebSearch(ABC):
    """Port for a web search engine (Phase 6 — web access)."""

    @abstractmethod
    async def search(self, query: str, max_results: int) -> list[SearchResult]: ...


class PageFetcher(ABC):
    """Port for fetching + extracting the readable text of a web page."""

    @abstractmethod
    async def fetch(self, url: str) -> str: ...
