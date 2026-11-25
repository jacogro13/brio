from __future__ import annotations

import io
import logging

from anyio import to_thread

from chatbot.domain.conversation.ports.text_extractor import AbstractTextExtractor

logger = logging.getLogger(__name__)


class TextExtractionAdapter(AbstractTextExtractor):
    """Lift model-visible text from an uploaded file.

    - PDF → text via ``pypdf`` (per-page text joined with blank lines).
    - text / code / markdown → decoded as UTF-8 (with a latin-1 fallback).
    - images and anything undecodable → ``None`` (blob stored, not shown to LLM).

    The result is truncated to ``max_extracted_chars`` so a large upload can't
    blow the LLM's context budget. Never raises: a failed parse returns ``None``.
    """

    def __init__(self, max_extracted_chars: int = 40_000) -> None:
        self._max_chars = max_extracted_chars

    async def extract(self, filename: str, content_type: str, data: bytes) -> str | None:
        ctype = (content_type or "").lower()
        if ctype.startswith("image/"):
            return None

        if ctype == "application/pdf" or filename.lower().endswith(".pdf"):
            text = await to_thread.run_sync(self._extract_pdf, data)
        else:
            text = self._decode_text(data)

        if not text:
            return None
        return self._truncate(text)

    def _extract_pdf(self, data: bytes) -> str | None:
        try:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(data))
            pages = [page.extract_text() or "" for page in reader.pages]
            text = "\n\n".join(p.strip() for p in pages if p.strip())
            return text or None
        except Exception:
            logger.warning("PDF text extraction failed", exc_info=True)
            return None

    def _decode_text(self, data: bytes) -> str | None:
        for encoding in ("utf-8", "latin-1"):
            try:
                return data.decode(encoding)
            except (UnicodeDecodeError, ValueError):
                continue
        return None

    def _truncate(self, text: str) -> str:
        if len(text) <= self._max_chars:
            return text
        return text[: self._max_chars] + "\n\n[...truncated...]"
