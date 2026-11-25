from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping


class TokenService(ABC):
    """Port: minting and verifying bearer tokens (D7).

    Speaks in plain values: the subject is the user id as a string, and Chatbot passes
    ``username`` as the only extra claim (the frontend reads it for display). Sync:
    signing and verifying an HS256 token takes microseconds.
    """

    @abstractmethod
    def issue(self, subject: str, claims: Mapping[str, str | int | bool]) -> str:
        """A signed token carrying the subject, the extra claims and an expiry."""

    @abstractmethod
    def decode(self, token: str) -> str:
        """The token's subject.

        Raises ``TokenExpired`` if it has expired, ``InvalidToken`` for anything else
        (bad signature, garbage, no subject). Both live in ``domain/user/model.py``.
        """
