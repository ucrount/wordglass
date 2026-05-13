"""OpenAI-compatible provider (works for OpenAI, DeepSeek, Groq, local Ollama, etc.)."""

from __future__ import annotations

import json
import time
from typing import Any, AsyncIterator

import httpx

from ..log_buffer import add_ai_call
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

        t0 = time.monotonic()
        record: dict[str, Any] = {
            "kind": "chat",
            "provider": self.name,
            "model": self.model,
            "base_url": self.base_url,
            "system": system,
            "user": user,
            "json_mode": json_mode,
            "max_tokens": max_tokens,
        }
        client = _client()
        try:
            resp = await client.post(url, headers=self._headers(), json=body)
            if resp.status_code >= 400:
                # Some providers don't accept response_format → retry once without it
                if json_mode and resp.status_code == 400:
                    body.pop("response_format", None)
                    resp = await client.post(url, headers=self._headers(), json=body)
                if resp.status_code >= 400:
                    err = f"{resp.status_code}: {resp.text[:300]}"
                    record.update({
                        "status": "error",
                        "error": err,
                        "http_status": resp.status_code,
                        "ms": round((time.monotonic() - t0) * 1000, 1),
                    })
                    add_ai_call(record)
                    raise ProviderError(err)

            data = resp.json()
            try:
                content = data["choices"][0]["message"]["content"]
            except (KeyError, IndexError) as e:
                err = f"unexpected response shape: {data}"
                record.update({
                    "status": "error",
                    "error": err,
                    "ms": round((time.monotonic() - t0) * 1000, 1),
                })
                add_ai_call(record)
                raise ProviderError(err) from e

            record.update({
                "status": "ok",
                "http_status": resp.status_code,
                "response": content,
                "ms": round((time.monotonic() - t0) * 1000, 1),
            })
            add_ai_call(record)
            return content
        except httpx.HTTPError as e:
            # Networking errors before/after response — record them too.
            record.update({
                "status": "error",
                "error": f"{type(e).__name__}: {e}",
                "ms": round((time.monotonic() - t0) * 1000, 1),
            })
            add_ai_call(record)
            raise ProviderError(f"{type(e).__name__}: {e}") from e

    async def chat_stream(
        self,
        system: str,
        user: str,
        *,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        url = f"{self.base_url}/chat/completions"
        body: dict[str, Any] = {
            "model": self.model,
            "temperature": 0.4,
            "stream": True,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if max_tokens is not None:
            body["max_tokens"] = max_tokens

        t0 = time.monotonic()
        accumulated: list[str] = []
        first_chunk_ms: float | None = None
        record: dict[str, Any] = {
            "kind": "stream",
            "provider": self.name,
            "model": self.model,
            "base_url": self.base_url,
            "system": system,
            "user": user,
            "max_tokens": max_tokens,
        }
        client = _client()
        try:
            async with client.stream("POST", url, headers=self._headers(), json=body) as resp:
                if resp.status_code >= 400:
                    text = (await resp.aread()).decode("utf-8", errors="replace")
                    err = f"{resp.status_code}: {text[:300]}"
                    record.update({
                        "status": "error",
                        "error": err,
                        "http_status": resp.status_code,
                        "ms": round((time.monotonic() - t0) * 1000, 1),
                    })
                    add_ai_call(record)
                    raise ProviderError(err)
                async for raw_line in resp.aiter_lines():
                    if not raw_line or not raw_line.startswith("data:"):
                        continue
                    payload = raw_line[5:].strip()
                    if payload == "[DONE]":
                        break
                    try:
                        obj = json.loads(payload)
                        delta = obj.get("choices", [{}])[0].get("delta", {}).get("content")
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
                    if delta:
                        if first_chunk_ms is None:
                            first_chunk_ms = round((time.monotonic() - t0) * 1000, 1)
                        accumulated.append(delta)
                        yield delta
            record.update({
                "status": "ok",
                "http_status": 200,
                "response": "".join(accumulated),
                "chunks": len(accumulated),
                "first_chunk_ms": first_chunk_ms,
                "ms": round((time.monotonic() - t0) * 1000, 1),
            })
            add_ai_call(record)
        except ProviderError:
            raise
        except httpx.HTTPError as e:
            record.update({
                "status": "error",
                "error": f"{type(e).__name__}: {e}",
                "response": "".join(accumulated),
                "ms": round((time.monotonic() - t0) * 1000, 1),
            })
            add_ai_call(record)
            raise ProviderError(f"{type(e).__name__}: {e}") from e

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
