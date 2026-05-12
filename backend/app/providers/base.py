"""Abstract chat provider interface."""

from __future__ import annotations

import abc
from typing import Any


class ProviderError(Exception):
    """Raised when an upstream provider request fails or returns malformed data."""


class Provider(abc.ABC):
    """A chat-completion provider with optional model listing.

    All providers must accept a `system` instruction string and a single `user`
    prompt, and return the model's text reply. Concrete subclasses encapsulate
    the wire format (OpenAI chat/completions, Anthropic messages, Google
    generateContent) so callers never need to branch.
    """

    name: str = ""

    def __init__(self, base_url: str, api_key: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    @abc.abstractmethod
    async def chat(
        self,
        system: str,
        user: str,
        *,
        json_mode: bool = False,
        max_tokens: int | None = None,
    ) -> str:
        """Send a single chat turn and return the assistant text content.

        max_tokens is a hint — providers that don't support it should ignore it.
        """

    @abc.abstractmethod
    async def list_models(self) -> list[str]:
        """Return available model IDs for this provider/account."""

    async def test(self) -> dict[str, Any]:
        """Cheap probe — say 'hi' and confirm a response comes back."""
        text = await self.chat("Reply with just: OK", "ping", json_mode=False)
        return {"ok": True, "echo": text[:120]}
