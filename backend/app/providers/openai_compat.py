"""OpenAI-compatible provider (works for OpenAI, DeepSeek, Groq, local Ollama, etc.)."""

from __future__ import annotations

from typing import Any

import httpx

from .base import Provider, ProviderError

# Shared connection pool. A fresh httpx.AsyncClient per request would re-do TLS
# (200-500ms over the wire to a CN-blocked endpoint) on every AI call; reusing
# one keeps the TCP+TLS session warm for subsequent requests in the same
# process. Created lazily so importing this module is still side-effect-free.
_shared_client: httpx.AsyncClient | None = None


def _client() -> httpx.AsyncClient:
    global _shared_client
    if _shared_client is None:
        _shared_client = httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, connect=10.0),
            limits=httpx.Limits(max_keepalive_connections=20, keepalive_expiry=300),
            http2=False,
        )
    return _shared_client


class OpenAIProvider(Provider):
    name = "openai"

    async def chat(
        self,
        system: str,
        user: str,
        *,
        json_mode: bool = False,
        max_tokens: int | None = None,
    ) -> str:
        url = f"{self.base_url}/chat/completions"
        body: dict[str, Any] = {
            "model": self.model,
            "temperature": 0.4,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        if max_tokens is not None:
            body["max_tokens"] = max_tokens

        client = _client()
        resp = await client.post(url, headers=self._headers(), json=body)

        if resp.status_code >= 400:
            # Some providers don't accept response_format → retry once without it
            if json_mode and resp.status_code == 400:
                body.pop("response_format", None)
                resp = await client.post(url, headers=self._headers(), json=body)
            if resp.status_code >= 400:
                raise ProviderError(f"{resp.status_code}: {resp.text[:300]}")

        data = resp.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise ProviderError(f"unexpected response shape: {data}") from e

    async def list_models(self) -> list[str]:
        url = f"{self.base_url}/models"
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(url, headers=self._headers())
        if resp.status_code >= 400:
            raise ProviderError(f"{resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        items = data.get("data") or data.get("models") or []
        return [item.get("id") or item.get("name", "") for item in items if isinstance(item, dict)]

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
