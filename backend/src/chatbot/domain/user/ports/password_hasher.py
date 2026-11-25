from __future__ import annotations

from abc import ABC, abstractmethod


class PasswordHasher(ABC):
    """Port: one-way hashing and verification of user passwords (D7).

    Async because a real hasher is deliberately slow (~300 ms at bcrypt's default
    cost); adapters run the work in a thread so a login doesn't stall chat streams.
    """

    @abstractmethod
    async def hash(self, plain: str) -> str:
        """A self-describing hash (salt included) of a plaintext password."""

    @abstractmethod
    async def verify(self, plain: str, hashed: str) -> bool:
        """Whether the plaintext matches the hash. False on a malformed hash."""
