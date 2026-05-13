"""Free-form paragraph translation, AI-backed."""

from __future__ import annotations

import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import current_user
from ..db import get_db
from ..log import log_event, new_request_id, now_ms
from ..models import User
from ..providers import ProviderError, build_provider
from ..settings_store import get_settings, is_configured

router = APIRouter(prefix="/api/translate", tags=["translate"], dependencies=[Depends(current_user)])


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


def _system_for(target_lang: str) -> str:
    return SYSTEM_TO_EN if target_lang == "en" else SYSTEM_TO_ZH


@router.post("", response_model=TranslateOut)
async def translate(
    payload: TranslateIn,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    row = get_settings(db, user.id)
    if not is_configured(row):
        raise HTTPException(
            status_code=502,
            detail="AI 未配置，无法翻译整段文本。在右上角 ⚙ 设置中配一个 AI provider 再试。",
        )
    try:
        provider = build_provider(row.provider_type, row.base_url, row.api_key, row.model)
        content = await provider.chat(_system_for(payload.target_lang), payload.text, max_tokens=2000)
    except ProviderError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {"translation": content.strip()}


@router.post("/stream")
async def translate_stream(
    payload: TranslateIn,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    row = get_settings(db, user.id)
    if not is_configured(row):
        raise HTTPException(
            status_code=502,
            detail="AI 未配置，无法翻译整段文本。在右上角 ⚙ 设置中配一个 AI provider 再试。",
        )
    system = _system_for(payload.target_lang)

    rid = new_request_id()
    t0 = now_ms()
    log_event(
        "translate.start",
        rid=rid,
        target_lang=payload.target_lang,
        text_len=len(payload.text),
        provider=row.provider_type,
        model=row.model,
    )

    async def gen():
        chunks = 0
        first_chunk_ms = None
        try:
            provider = build_provider(row.provider_type, row.base_url, row.api_key, row.model)
            log_event("translate.provider_built", rid=rid, ms=round(now_ms() - t0, 1))
            async for chunk in provider.chat_stream(system, payload.text, max_tokens=2000):
                if first_chunk_ms is None:
                    first_chunk_ms = round(now_ms() - t0, 1)
                    log_event("translate.first_chunk", rid=rid, ms=first_chunk_ms, len=len(chunk))
                chunks += 1
                yield f"data: {json.dumps({'delta': chunk}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            log_event(
                "translate.done",
                rid=rid,
                chunks=chunks,
                total_ms=round(now_ms() - t0, 1),
                first_chunk_ms=first_chunk_ms,
            )
        except ProviderError as e:
            log_event("translate.error", rid=rid, error=str(e)[:200], ms=round(now_ms() - t0, 1))
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
