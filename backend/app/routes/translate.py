"""Free-form paragraph translation, AI-backed.

Supports both English → Chinese (default) and Chinese → English via the
`target_lang` field. Reader v2 (frontend) sets this based on the user's
direction toggle. Older clients omit the field and get the previous
English → Chinese behavior unchanged.
"""

from __future__ import annotations

from typing import Literal

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
    target_lang: Literal["zh", "en"] = "zh"


class TranslateOut(BaseModel):
    translation: str


SYSTEM_TO_ZH = (
    "You are a translator. Translate the user's English text to fluent, "
    "natural Simplified Chinese. Preserve paragraph breaks. "
    "Output ONLY the translation — no notes, no quotes, no English."
)

SYSTEM_TO_EN = (
    "You are a translator. Translate the user's Chinese text to fluent, "
    "natural English. Preserve paragraph breaks. "
    "Output ONLY the translation — no notes, no quotes, no Chinese."
)


@router.post("", response_model=TranslateOut)
async def translate(payload: TranslateIn, db: Session = Depends(get_db)):
    row = get_settings(db)
    if not is_configured(row):
        raise HTTPException(
            status_code=502,
            detail="AI 未配置，无法翻译整段文本。在右上角 ⚙ 设置中配一个 AI provider 再试。",
        )
    system = SYSTEM_TO_EN if payload.target_lang == "en" else SYSTEM_TO_ZH
    try:
        provider = build_provider(row.provider_type, row.base_url, row.api_key, row.model)
        content = await provider.chat(system, payload.text, max_tokens=2000)
    except ProviderError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {"translation": content.strip()}
