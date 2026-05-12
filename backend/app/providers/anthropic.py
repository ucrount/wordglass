"""Anthropic Claude provider."""

from __future__ import annotations

from typing import Any

import httpx

from .base import Provider, ProviderError


class AnthropicProvider(Provider):
    name = "anthropic"

    async def chat(
        self,
        system: str,
        user: str,
        *,
        json_mode: bool = False,
        max_tokens: int | None = None,
    ) -> str:
        url = f"{self.base_url}/v1/messages"
        # Anthropic doesn't have an explicit JSON mode but follows prompt instructions well.
        if json_mode:
            system = (system or "") + "\n\nIMPORTANT: Reply with only valid JSON. No prose, no markdown fences."

        body: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens if max_tokens is not None else 2048,
            "messages": [{"role": "user", "content": user}],
        }
        if system:
            body["system"] = system

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(url, headers=self._headers(), json=body)

        if resp.status_code >= 400:
            raise ProviderError(f"{resp.status_code}: {resp.text[:300]}")

        data = resp.json()
        try:
            parts = data["content"]
            text_parts = [p.get("text", "") for p in parts if p.get("type") == "text"]
            return "".join(text_parts)
        except (KeyError, TypeError) as e:
            raise ProviderError(f"unexpected response shape: {data}") from e

    async def list_models(self) -> list[str]:
        url = f"{self.base_url}/v1/models"
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(url, headers=self._headers())
        if resp.status_code >= 400:
            raise ProviderError(f"{resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        items = data.get("data") or []
        return [item.get("id", "") for item in items if isinstance(item, dict) and item.get("id")]

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
