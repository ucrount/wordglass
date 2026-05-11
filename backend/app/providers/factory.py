"""Provider factory + UI presets."""

from __future__ import annotations

from .anthropic import AnthropicProvider
from .base import Provider, ProviderError
from .google import GoogleProvider
from .openai_compat import OpenAIProvider

# Presets shown in the Settings UI. The frontend can render these as a select.
PROVIDER_PRESETS: list[dict] = [
    {
        "id": "openai",
        "label": "OpenAI 兼容",
        "description": "DeepSeek / OpenAI / Groq / Ollama / 任意 OpenAI 协议",
        "examples": [
            {"name": "DeepSeek", "base_url": "https://api.deepseek.com/v1", "model": "deepseek-chat"},
            {"name": "OpenAI", "base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini"},
            {"name": "Groq", "base_url": "https://api.groq.com/openai/v1", "model": "llama-3.1-70b-versatile"},
            {"name": "Ollama 本地", "base_url": "http://127.0.0.1:11434/v1", "model": "qwen2.5:7b"},
        ],
    },
    {
        "id": "anthropic",
        "label": "Anthropic Claude",
        "description": "官方 Claude API",
        "examples": [
            {"name": "Anthropic", "base_url": "https://api.anthropic.com", "model": "claude-sonnet-4-6"},
        ],
    },
    {
        "id": "google",
        "label": "Google Gemini",
        "description": "Google AI Studio / Gemini API",
        "examples": [
            {"name": "Gemini", "base_url": "https://generativelanguage.googleapis.com", "model": "gemini-2.0-flash-exp"},
        ],
    },
]


def build_provider(provider_type: str, base_url: str, api_key: str, model: str) -> Provider:
    if not api_key:
        raise ProviderError("API key is empty — configure it in Settings first.")
    if not base_url:
        raise ProviderError("Base URL is empty.")
    if not model:
        raise ProviderError("Model is empty.")

    p = provider_type.lower()
    if p in {"openai", "openai_compat"}:
        return OpenAIProvider(base_url, api_key, model)
    if p == "anthropic":
        return AnthropicProvider(base_url, api_key, model)
    if p == "google":
        return GoogleProvider(base_url, api_key, model)
    raise ProviderError(f"unknown provider type: {provider_type}")
