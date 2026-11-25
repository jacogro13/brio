from __future__ import annotations

from abc import ABC, abstractmethod


class AbstractAttachmentStorage(ABC):
    """Port: object-storage operations for conversation attachments.

    Concrete implementation: ``GarageStorageAdapter`` (S3-compatible, Garage);
    ``NullAttachmentStorage`` (in-memory) is the fallback when no Garage endpoint
    is configured, mirroring the LLM mock fallback. Keys follow the scheme
    ``conversations/{conversation_id}/{attachment_id}/{filename}`` so every blob
    for a conversation shares the ``conversations/{cid}/`` prefix.
    """

    @abstractmethod
    async def upload_file(self, key: str, data: bytes, content_type: str) -> None:
        """Upload bytes to the given object-storage key."""
        ...

    @abstractmethod
    async def get_file(self, key: str) -> bytes:
        """Download and return the full contents of the object at ``key``."""
        ...

    @abstractmethod
    async def delete_prefix(self, prefix: str) -> None:
        """Delete every object whose key starts with ``prefix``.

        Lets a caller wipe all of a conversation's blobs (the
        ``conversations/{cid}/`` prefix) in one call. No-op if nothing matches.
        """
        ...
