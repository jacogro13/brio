from __future__ import annotations

import pytest

from chatbot.adapters.extraction.text_extraction import TextExtractionAdapter


@pytest.mark.asyncio
async def test_extracts_utf8_text():
    adapter = TextExtractionAdapter()
    text = await adapter.extract("notes.md", "text/markdown", b"# Hello\nworld")
    assert text == "# Hello\nworld"


@pytest.mark.asyncio
async def test_extracts_code_by_extension_even_with_generic_content_type():
    adapter = TextExtractionAdapter()
    text = await adapter.extract("main.py", "application/octet-stream", b"print('hi')")
    assert text == "print('hi')"


@pytest.mark.asyncio
async def test_images_return_none():
    adapter = TextExtractionAdapter()
    assert await adapter.extract("cat.png", "image/png", b"\x89PNG\r\n") is None


@pytest.mark.asyncio
async def test_truncates_to_cap():
    adapter = TextExtractionAdapter(max_extracted_chars=10)
    text = await adapter.extract("big.txt", "text/plain", b"x" * 100)
    assert text is not None
    assert text.startswith("x" * 10)
    assert "truncated" in text


@pytest.mark.asyncio
async def test_malformed_pdf_returns_none_not_raises():
    adapter = TextExtractionAdapter()
    assert await adapter.extract("broken.pdf", "application/pdf", b"not a pdf") is None


@pytest.mark.asyncio
async def test_extracts_real_pdf_text():
    pypdf = pytest.importorskip("pypdf")
    from io import BytesIO

    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = BytesIO()
    writer.write(buf)
    adapter = TextExtractionAdapter()
    # A blank page extracts to empty → None (no readable text).
    assert await adapter.extract("blank.pdf", "application/pdf", buf.getvalue()) is None
