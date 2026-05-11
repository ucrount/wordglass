"""OpenAI-compatible provider (works for OpenAI, DeepSeek, Groq, local Ollama, etc.)."""

from __future__ import annotations

from typing import Any

import httpx

from .base import Provider, ProviderError


class OpenAIProvider(Provider):
    name = "openai"

    async def chat(self, system: str, user: str, *, json_mode: bool = False) -> str:
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

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(url, headers=self._headers(), json=body)

        if resp.status_code >= 400:
            # Some providers don't accept response_format → retry once without it
            if json_mode and resp.status_code == 400:
                body.pop("response_format", None)
                async with httpx.AsyncClient(timeout=60) as client:
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
