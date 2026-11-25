from __future__ import annotations

from abc import ABC, abstractmethod


class AbstractTextExtractor(ABC):
    """Port: lift model-visible text from an uploaded file at upload time.

    Concrete implementation: ``TextExtractionAdapter`` (UTF-8 for text/code/md,
    ``pypdf`` for PDF). Returns ``None`` when there is nothing the model can read
    (images, undecodable bytes) — the blob is still stored, it is just not shown
    to the LLM. Implementations must not raise on malformed input; a failed
    extraction returns ``None``.
    """

    @abstractmethod
    async def extract(self, filename: str, content_type: str, data: bytes) -> str | None:
        """Return the extracted text, or ``None`` if none is available."""
        ...
