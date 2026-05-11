"""High-level AI helper used by routes. Reads settings from DB, dispatches via provider."""

from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy.orm import Session

from .providers import ProviderError, build_provider
from .settings_store import get_settings, is_configured

SYSTEM_PROMPT = """You are a vocabulary helper for a Chinese learner of English.
For the given English word or short phrase, return STRICT JSON with these fields:
{
  "text": "<the lemma form of the word, lowercase>",
  "phonetic": "<US IPA phonetic in slashes, e.g. /ˌser.ənˈdɪp.ə.ti/>",
  "pos": "<part of speech: n. / v. / adj. / adv. / phr. — multiple separated by /; if multiple meanings, list main one first>",
  "translation": "<concise Chinese meanings, separate multiple with ；>",
  "examples": [
    {"en": "<natural English sentence using the word in this specific context>", "zh": "<accurate Chinese translation>"},
    ...
  ]
}

Rules for examples:
- Generate THREE examples, each from a CLEARLY DIFFERENT angle so the learner sees the word from multiple sides:
    1) everyday casual conversation (e.g. with friends/family)
    2) professional or workplace context
    3) written narrative / story / article
- Each example MUST contain the target word (any inflection form is fine).
- Examples must feel like real spoken or written modern English — not textbook clichés.
- Translations should be natural Chinese, not literal word-by-word.
- Output ONLY the JSON object, no markdown fences, no commentary."""


def _extract_json(raw: str) -> dict[str, Any]:
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


async def fetch_word_payload(word: str, db: Session) -> dict[str, Any]:
    row = get_settings(db)
    if not is_configured(row):
        raise RuntimeError(
            "AI is not configured yet. Open Settings and fill in provider / API key / model."
        )

    try:
        provider = build_provider(row.provider_type, row.base_url, row.api_key, row.model)
        content = await provider.chat(SYSTEM_PROMPT, word.strip(), json_mode=True)
    except ProviderError as e:
        raise RuntimeError(str(e)) from e

    try:
        payload = _extract_json(content)
    except Exception as e:
        raise RuntimeError(f"AI returned non-JSON: {content[:200]}") from e

    payload.setdefault("text", word.strip().lower())
    payload.setdefault("phonetic", "")
    payload.setdefault("pos", "")
    payload.setdefault("translation", "")
    cleaned: list[dict[str, str]] = []
    for ex in (payload.get("examples") or [])[:5]:
        if isinstance(ex, dict) and ex.get("en"):
            cleaned.append({"en": str(ex["en"]).strip(), "zh": str(ex.get("zh", "")).strip()})
    payload["examples"] = cleaned
    return payload
