import logging

from chatbot.domain.conversation.ports.attachment_storage import AbstractAttachmentStorage

logger = logging.getLogger(__name__)


class NullAttachmentStorage(AbstractAttachmentStorage):
    """In-memory attachment storage — the fallback when no Garage endpoint is
    configured (mirrors the LLM mock fallback). Bytes live in a process-local
    dict, so uploads/downloads work end-to-end for local dev and e2e without a
    Garage container; nothing survives a restart.
    """

    def __init__(self) -> None:
        self._store: dict[str, bytes] = {}
        logger.info("Using NullAttachmentStorage (no GARAGE_ENDPOINT configured)")

    async def upload_file(self, key: str, data: bytes, content_type: str) -> None:
        self._store[key] = data

    async def get_file(self, key: str) -> bytes:
        try:
            return self._store[key]
        except KeyError:
            raise FileNotFoundError(key) from None

    async def delete_prefix(self, prefix: str) -> None:
        for key in [k for k in self._store if k.startswith(prefix)]:
            del self._store[key]
