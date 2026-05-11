"""Google Gemini provider (generativelanguage.googleapis.com)."""

from __future__ import annotations

from typing import Any

import httpx

from .base import Provider, ProviderError


class GoogleProvider(Provider):
    name = "google"

    async def chat(self, system: str, user: str, *, json_mode: bool = False) -> str:
        url = f"{self.base_url}/v1beta/models/{self.model}:generateContent"
        body: dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": 0.4},
        }
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        if json_mode:
            body["generationConfig"]["responseMimeType"] = "application/json"

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(url, params={"key": self.api_key}, json=body)

        if resp.status_code >= 400:
            raise ProviderError(f"{resp.status_code}: {resp.text[:300]}")

        data = resp.json()
        try:
            parts = data["candidates"][0]["content"]["parts"]
            return "".join(p.get("text", "") for p in parts)
        except (KeyError, IndexError, TypeError) as e:
            raise ProviderError(f"unexpected response shape: {data}") from e

    async def list_models(self) -> list[str]:
        url = f"{self.base_url}/v1beta/models"
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(url, params={"key": self.api_key})
        if resp.status_code >= 400:
            raise ProviderError(f"{resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        items = data.get("models") or []
        result: list[str] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            # Filter to text-generation models
            methods = item.get("supportedGenerationMethods") or []
            if methods and "generateContent" not in methods:
                continue
            full_name = item.get("name", "")
            # name like "models/gemini-1.5-pro" → strip prefix
            short = full_name.split("/", 1)[-1] if "/" in full_name else full_name
            if short:
                result.append(short)
        return result
