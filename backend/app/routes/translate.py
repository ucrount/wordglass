"""Free-form English → Chinese paragraph translation, AI-backed.

Used by the Dashboard reader panel: paste a passage, get a Chinese translation
side-by-side. We don't try to be clever (no caching, no chunking, no streaming
for v1) — Deepseek/OpenAI handle 200-500-word passages in 2-5s, which is fine.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import verify_token
from ..db import get_db
from ..providers import ProviderError, build_provider
from ..settings_store import get_settings, is_configured

router = APIRouter(prefix="/api/translate", tags=["translate"], dependencies=[Depends(verify_token)])


class TranslateIn(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)


class TranslateOut(BaseModel):
    translation: str


SYSTEM = (
    "You are a translator. Translate the user's English text to fluent, "
    "natural Simplified Chinese. Preserve paragraph breaks. "
    "Output ONLY the translation — no notes, no quotes, no English."
)


@router.post("", response_model=TranslateOut)
async def translate(payload: TranslateIn, db: Session = Depends(get_db)):
    row = get_settings(db)
    if not is_configured(row):
        raise HTTPException(
            status_code=502,
            detail="AI 未配置，无法翻译整段文本。在右上角 ⚙ 设置中配一个 AI provider 再试。",
        )
    try:
        provider = build_provider(row.provider_type, row.base_url, row.api_key, row.model)
        content = await provider.chat(SYSTEM, payload.text, max_tokens=2000)
    except ProviderError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {"translation": content.strip()}
