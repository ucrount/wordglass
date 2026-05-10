"""OpenAI-compatible client. Works with DeepSeek, OpenAI, Claude proxy, local Ollama, etc."""

import json
import re
from typing import Any

import httpx

from .config import settings

SYSTEM_PROMPT = """You are a vocabulary helper for a Chinese learner of English.
For the given English word or short phrase, return STRICT JSON with these fields:
{
  "text": "<the lemma form of the word, lowercase>",
  "phonetic": "<US IPA phonetic in slashes, e.g. /ˌser.ənˈdɪp.ə.ti/>",
  "pos": "<part of speech: n. / v. / adj. / adv. / phr. — multiple separated by /; if multiple meanings, list main one first>",
  "translation": "<concise Chinese meanings, separate multiple with ；>",
  "examples": [
    {"en": "<natural English sentence using the word in a real-life conversational context>", "zh": "<accurate Chinese translation>"},
    {"en": "...", "zh": "..."},
    {"en": "...", "zh": "..."}
  ]
}

Rules:
- Examples must feel like real spoken or written modern English, not textbook.
- Each example must contain the target word (any inflection form is fine).
- 3 examples, varied register (casual / professional / written).
- Output ONLY the JSON object, no markdown fences, no commentary."""


def _extract_json(raw: str) -> dict[str, Any]:
    """Tolerant JSON extraction — strips fences and grabs the first {...} block."""
    s = raw.strip()
    s = re.sub(r"^```(?:json)?\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", s, re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


async def fetch_word_payload(word: str) -> dict[str, Any]:
    if not settings.AI_API_KEY:
        raise RuntimeError("AI_API_KEY is not configured. Edit backend/.env first.")

    url = settings.AI_BASE_URL.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.AI_API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": settings.AI_MODEL,
        "temperature": 0.4,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": word.strip()},
        ],
        "response_format": {"type": "json_object"},
    }

    async with httpx.AsyncClient(timeout=60) as client:
        try:
            resp = await client.post(url, headers=headers, json=body)
        except httpx.RequestError as e:
            raise RuntimeError(f"AI request failed: {e}") from e

    if resp.status_code >= 400:
        # Some providers don't support response_format; retry without it.
        if "response_format" in resp.text or resp.status_code == 400:
            body.pop("response_format", None)
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(url, headers=headers, json=body)
        if resp.status_code >= 400:
            raise RuntimeError(f"AI {resp.status_code}: {resp.text[:300]}")

    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    payload = _extract_json(content)

    payload.setdefault("text", word.strip().lower())
    payload.setdefault("phonetic", "")
    payload.setdefault("pos", "")
    payload.setdefault("translation", "")
    examples = payload.get("examples") or []
    cleaned_examples = []
    for ex in examples[:5]:
        if isinstance(ex, dict) and ex.get("en"):
            cleaned_examples.append({"en": str(ex["en"]).strip(), "zh": str(ex.get("zh", "")).strip()})
    payload["examples"] = cleaned_examples
    return payload
