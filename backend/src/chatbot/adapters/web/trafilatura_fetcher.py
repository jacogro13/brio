from __future__ import annotations

import ipaddress
import logging
import socket
from functools import partial
from urllib.parse import urlparse

import httpx
from anyio import to_thread

from chatbot.domain.conversation.ports.web_tools import PageFetcher

logger = logging.getLogger(__name__)

_MAX_REDIRECTS = 3
_USER_AGENT = "Mozilla/5.0 (compatible; ChatbotWebTools/1.0)"


class UnsafeUrlError(ValueError):
    """Raised when a URL is rejected by the SSRF guard (non-http(s) scheme or a
    host that resolves to a private / loopback / reserved address)."""


def _assert_public_url(url: str) -> None:
    """SSRF guard: reject non-http(s) URLs and hosts that resolve to any
    private, loopback, link-local, reserved, or otherwise non-global address.

    The backend sits next to Postgres/Garage on a private network, so a fetch of
    ``http://10.100.0.1`` / ``http://localhost`` / ``http://169.254.169.254``
    must never reach them. We resolve the hostname and check **every** resolved
    address, not just the literal string."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise UnsafeUrlError(f"unsupported URL scheme: {parsed.scheme!r}")
    host = parsed.hostname
    if not host:
        raise UnsafeUrlError("URL has no host")
    try:
        infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror as exc:
        raise UnsafeUrlError(f"cannot resolve host {host!r}: {exc}") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global or ip.is_multicast:
            raise UnsafeUrlError(f"host {host!r} resolves to non-public address {ip}")


class TrafilaturaPageFetcher(PageFetcher):
    """Fetch a page over guarded HTTP and extract its readable text with
    ``trafilatura`` (house convention — Pasti/Blibiobot use it). We do the HTTP
    ourselves (rather than ``trafilatura.fetch_url``) so the SSRF guard runs on
    the initial host *and* on every redirect hop. Output is truncated to
    ``max_chars``."""

    def __init__(self, max_chars: int = 20_000, timeout: float = 20.0) -> None:
        self._max_chars = max_chars
        self._client = httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=False,
            headers={"User-Agent": _USER_AGENT},
        )

    async def fetch(self, url: str) -> str:
        html = await self._get_html(url)
        text = await to_thread.run_sync(partial(self._extract, html, url))
        if text is None:
            raise UnsafeUrlError(f"no readable content extracted from {url}")
        return text[: self._max_chars]

    async def _get_html(self, url: str) -> str:
        current = url
        for _ in range(_MAX_REDIRECTS + 1):
            _assert_public_url(current)
            resp = await self._client.get(current)
            if resp.is_redirect:
                location = resp.headers.get("location")
                if not location:
                    break
                current = str(httpx.URL(current).join(location))
                continue
            resp.raise_for_status()
            return resp.text
        raise UnsafeUrlError(f"too many redirects fetching {url}")

    def _extract(self, html: str, url: str) -> str | None:
        import trafilatura

        return trafilatura.extract(html, url=url, include_comments=False, include_tables=True)
