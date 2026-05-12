"""High-level AI helper used by routes. Reads settings from DB, dispatches via provider.

Offline-first: ECDICT supplies word data and Tatoeba supplies example sentences
without ever calling AI. AI is only consulted (when configured) to assign a
category — and as a full fallback when ECDICT misses the word entirely.
"""

from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy.orm import Session

from . import offline_dict
from .providers import ProviderError, build_provider
from .settings_store import get_settings, is_configured

CATEGORIES: list[str] = [
    "日常物品",
    "食物饮料",
    "动物植物",
    "人物职业",
    "情感心理",
    "时间日期",
    "地点旅行",
    "自然环境",
    "科技数码",
    "教育学术",
    "工作商务",
    "家庭关系",
    "身体健康",
    "动作行为",
    "性格描述",
    "抽象概念",
    "艺术文化",
    "其他",
]

CATEGORY_LIST_STR = " | ".join(CATEGORIES)

SYSTEM_PROMPT = f"""You are a vocabulary helper for a Chinese learner of English.
For the given English word or short phrase, return STRICT JSON with these fields:
{{
  "text": "<the lemma form of the word, lowercase>",
  "phonetic": "<US IPA phonetic in slashes, e.g. /ˌser.ənˈdɪp.ə.ti/>",
  "pos": "<part of speech: n. / v. / adj. / adv. / phr.>",
  "translation": "<concise Chinese meanings, separate multiple with ；>",
  "category": "<one of: {CATEGORY_LIST_STR}>",
  "examples": [
    {{"en": "<simplest, ~6-10 words, beginner sentence>", "zh": "..."}},
    {{"en": "<casual conversation, slightly longer>", "zh": "..."}},
    {{"en": "<professional/workplace context>", "zh": "..."}},
    {{"en": "<written narrative or descriptive>", "zh": "..."}},
    {{"en": "<formal/academic/news writing, complex>", "zh": "..."}}
  ]
}}

Category rules:
- Pick the SINGLE category that best fits the word's primary meaning.
- Use 其他 only when nothing else fits at all.
- Be consistent: same kind of word should always end up in the same bucket.

Rules for examples:
- Generate FIVE examples, ORDERED FROM EASIEST TO HARDEST. The numbered position matters.
  1) Simplest — short, basic vocabulary, present tense, everyday context.
  2) Casual conversation — natural spoken English, slightly more complex.
  3) Professional or workplace context — typical business communication.
  4) Written narrative or descriptive — richer vocabulary.
  5) Formal / academic / news writing — complex sentence structure.
- Each example MUST contain the target word (any inflection form is fine).
- Examples must feel like real modern English, not textbook clichés.
- Translations should be natural Chinese, not literal word-by-word.
- Output ONLY the JSON object, no markdown fences, no commentary."""


def _extract_json(raw: str) -> Any:
    """Tolerant JSON extraction — handles fences, leading prose, both {} and []."""
    s = raw.strip()
    s = re.sub(r"^```(?:json)?\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        for pattern in (r"\{.*\}", r"\[.*\]"):
            match = re.search(pattern, s, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    continue
        raise


def lookup_local(word: str) -> dict[str, Any] | None:
    """Pure-local lookup. ECDICT for word data, Tatoeba for examples.

    Returns the payload on hit, None on ECDICT miss. Never raises, never calls
    the network. Category is always "" — the caller decides whether/how to fill
    it asynchronously.
    """
    text = word.strip().lower()
    if not text:
        return None
    ecdict_hit = offline_dict.lookup_ecdict(text)
    if ecdict_hit is None:
        return None
    examples = offline_dict.search_tatoeba(ecdict_hit["text"], limit=5)
    return {
        "text": ecdict_hit["text"],
        "phonetic": ecdict_hit["phonetic"],
        "pos": ecdict_hit["pos"],
        "translation": ecdict_hit["translation"],
        "category": "",
        "examples": examples,
    }


async def fetch_word_payload(word: str, db: Session) -> dict[str, Any]:
    """ECDICT-miss fallback. Calls AI for the full payload — slow, but
    unavoidable for words the offline dictionary doesn't know. Raises
    RuntimeError if AI isn't configured.
    """
    text = word.strip().lower()
    if not text:
        raise RuntimeError("空查询")

    settings_row = get_settings(db)
    if not is_configured(settings_row):
        raise RuntimeError(
            "本地词典里找不到这个词，而 AI 还没配置。打开右上角 ⚙ 设置一个 AI provider 再试。"
        )
    return await _full_ai_payload(text, settings_row)


async def categorize_word(word: str, db: Session) -> str:
    """Async AI categorisation for one word — meant for BackgroundTasks.
    Silently returns "" if AI isn't configured or the call fails.
    """
    settings_row = get_settings(db)
    if not is_configured(settings_row):
        return ""
    try:
        return await _categorize_one(word, settings_row)
    except Exception:
        return ""


async def generate_examples(word: str, translation: str, db: Session) -> list[dict[str, str]]:
    """Ask AI for 5 example sentences for a word we already have basic data on.
    Used when Tatoeba came up empty.
    """
    settings_row = get_settings(db)
    if not is_configured(settings_row):
        return []

    try:
        provider = build_provider(
            settings_row.provider_type, settings_row.base_url, settings_row.api_key, settings_row.model
        )
        hint = f" (中文释义: {translation})" if translation else ""
        prompt = (
            f'Generate 5 English example sentences for the word "{word}"{hint}, '
            f"ordered from easiest (short, basic) to hardest (formal, complex). "
            f"Each example must contain the word (any inflection). "
            f"Provide a natural Chinese translation for each.\n\n"
            f'Return STRICT JSON: {{"examples":[{{"en":"...","zh":"..."}},...]}}'
        )
        content = await provider.chat(
            "You generate vocabulary example sentences. Respond in JSON only.",
            prompt,
            json_mode=True,
            max_tokens=800,
        )
        data = _extract_json(content)
    except Exception:
        return []

    raw_examples = (
        data.get("examples", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
    )
    cleaned: list[dict[str, str]] = []
    for ex in raw_examples[:5]:
        if isinstance(ex, dict) and ex.get("en"):
            cleaned.append({"en": str(ex["en"]).strip(), "zh": str(ex.get("zh", "")).strip()})
    return cleaned


async def _full_ai_payload(word: str, settings_row: Any) -> dict[str, Any]:
    """Original full-AI flow — used when ECDICT misses but AI is configured."""
    try:
        provider = build_provider(
            settings_row.provider_type, settings_row.base_url, settings_row.api_key, settings_row.model
        )
        content = await provider.chat(SYSTEM_PROMPT, word, json_mode=True)
    except ProviderError as e:
        raise RuntimeError(str(e)) from e

    try:
        payload = _extract_json(content)
    except Exception as e:
        raise RuntimeError(f"AI returned non-JSON: {content[:200]}") from e

    if not isinstance(payload, dict):
        raise RuntimeError("AI returned unexpected JSON shape (not an object)")

    payload.setdefault("text", word)
    payload.setdefault("phonetic", "")
    payload.setdefault("pos", "")
    payload.setdefault("translation", "")
    cat = payload.get("category", "").strip()
    payload["category"] = cat if cat in CATEGORIES else ""

    cleaned: list[dict[str, str]] = []
    for ex in (payload.get("examples") or [])[:5]:
        if isinstance(ex, dict) and ex.get("en"):
            cleaned.append({"en": str(ex["en"]).strip(), "zh": str(ex.get("zh", "")).strip()})
    payload["examples"] = cleaned
    return payload


async def _categorize_one(word: str, settings_row: Any) -> str:
    """One-word category lookup. Trimmed prompt + tight max_tokens to keep
    latency under a second even on Deepseek/OpenAI."""
    provider = build_provider(
        settings_row.provider_type, settings_row.base_url, settings_row.api_key, settings_row.model
    )
    prompt = f'Word: {word}\nCategories: {CATEGORY_LIST_STR}\nJSON: {{"category":"..."}}'
    content = await provider.chat(
        "Pick the single best Chinese category for the given English word. JSON only.",
        prompt,
        json_mode=True,
        max_tokens=40,
    )
    data = _extract_json(content)
    if isinstance(data, dict):
        cat = str(data.get("category", "")).strip()
        if cat in CATEGORIES:
            return cat
    return ""


async def categorize_words_batch(
    words: list[str], db: Session
) -> dict[str, str]:
    """Classify a batch of words into categories via one AI call.
    Returns {word: category} for words that were successfully classified.
    """
    if not words:
        return {}

    row = get_settings(db)
    if not is_configured(row):
        raise RuntimeError("AI not configured")

    provider = build_provider(row.provider_type, row.base_url, row.api_key, row.model)
    word_list = "\n".join(f"- {w}" for w in words)
    prompt = f"""Classify each English word into ONE category from this list:
{CATEGORY_LIST_STR}

Words:
{word_list}

Return STRICT JSON:
{{"results": [{{"word": "<word>", "category": "<category>"}}, ...]}}

Output ONLY the JSON, in the same order as the input."""

    try:
        content = await provider.chat(
            "You are a vocabulary categorizer. Respond in JSON only.",
            prompt,
            json_mode=True,
        )
        data = _extract_json(content)
    except (ProviderError, Exception):
        return {}

    items = data.get("results", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
    result: dict[str, str] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        w = str(item.get("word", "")).strip().lower()
        c = str(item.get("category", "")).strip()
        if w and c in CATEGORIES:
            result[w] = c
    return result
