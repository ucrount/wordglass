import json

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from ..ai import (
    CATEGORIES,
    categorize_word,
    categorize_words_batch,
    fetch_word_payload,
    generate_examples,
    lookup_local,
)
from ..auth import current_user
from ..db import SessionLocal, get_db
from ..log import log_event, new_request_id, now_ms
from ..models import Example, User, Word
from ..offline_dict import has_ecdict, has_tatoeba, lookup_ecdict
from ..providers import ProviderError, build_provider
from ..schemas import WordBrief, WordCreate, WordOut
from ..settings_store import get_settings, is_configured

router = APIRouter(prefix="/api/words", tags=["words"], dependencies=[Depends(current_user)])


USAGE_SYSTEM = (
    "You are an English vocabulary teacher writing for Chinese learners. "
    "For the given English word or phrase, write a concise Chinese explanation "
    "with TWO sections in this exact format (Chinese only, no English explanations):\n\n"
    "【用法】\n"
    "1-2 sentences (40-80 Chinese characters): nuance, common usage scenarios, "
    "frequent collocations. Use 例 to introduce 1-2 short collocation examples in English.\n\n"
    "【记忆方法】\n"
    "1-2 sentences (30-60 Chinese characters): mnemonic tricks — etymology, "
    "association with similar-sounding Chinese, breakdown of word parts, or memorable image.\n\n"
    "Output ONLY the two sections with their markers. No greeting, no closing."
)


class UsageIn(BaseModel):
    text: str = Field(..., min_length=1, max_length=80)


@router.get("/offline-status")
def offline_status():
    """Tell the frontend which offline data files are loaded."""
    return {"ecdict": has_ecdict(), "tatoeba": has_tatoeba()}


@router.get("/preview")
def preview_word(
    text: str = Query(..., min_length=1, max_length=80),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Instant ECDICT lookup for the reader-panel tooltip. Never writes."""
    hit = lookup_ecdict(text.strip().lower())
    if hit is None:
        return {"found": False, "text": text}
    existing = db.query(Word.id).filter(
        Word.text == hit["text"], Word.user_id == user.id
    ).first()
    return {
        "found": True,
        "text": hit["text"],
        "phonetic": hit["phonetic"],
        "pos": hit["pos"],
        "translation": hit["translation"],
        "already_saved": existing is not None,
    }


async def _enrich_word(word_id: int, user_id: int, do_category: bool, do_examples: bool) -> None:
    """Runs AFTER the response is sent. Owns its own DB session."""
    db = SessionLocal()
    try:
        word = db.get(Word, word_id)
        if word is None or word.user_id != user_id:
            return

        if do_category and not (word.category or ""):
            cat = await categorize_word(word.text, db, user_id)
            if cat:
                word.category = cat
                db.commit()

        if do_examples and not word.examples:
            examples = await generate_examples(word.text, word.translation or "", db, user_id)
            if examples:
                for ex in examples:
                    word.examples.append(Example(en=ex["en"], zh=ex.get("zh", "")))
                db.commit()
    finally:
        db.close()


@router.post("", response_model=WordOut)
async def add_word(
    payload: WordCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    text = payload.text.strip().lower()
    existing = db.query(Word).filter(Word.text == text, Word.user_id == user.id).first()
    if existing:
        return existing

    local = lookup_local(text)

    if local is not None:
        word = Word(
            user_id=user.id,
            text=local["text"],
            phonetic=local["phonetic"],
            pos=local["pos"],
            translation=local["translation"],
            category="",
        )
        for ex in local["examples"]:
            word.examples.append(Example(en=ex["en"], zh=ex.get("zh", "")))
        db.add(word)
        db.commit()
        db.refresh(word)

        settings_row = get_settings(db, user.id)
        if is_configured(settings_row):
            need_category = True
            need_examples = len(word.examples) == 0
            if need_category or need_examples:
                background_tasks.add_task(
                    _enrich_word, word.id, user.id, need_category, need_examples
                )
        return word

    # ECDICT miss — must use AI synchronously to get any word data at all.
    try:
        ai_payload = await fetch_word_payload(text, db, user.id)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    word = Word(
        user_id=user.id,
        text=ai_payload.get("text", text),
        phonetic=ai_payload.get("phonetic", ""),
        pos=ai_payload.get("pos", ""),
        translation=ai_payload.get("translation", ""),
        category=ai_payload.get("category", ""),
    )
    for ex in ai_payload.get("examples", []):
        word.examples.append(Example(en=ex["en"], zh=ex.get("zh", "")))

    db.add(word)
    db.commit()
    db.refresh(word)
    return word


@router.get("/categories")
def categories(db: Session = Depends(get_db), user: User = Depends(current_user)):
    """All known categories + counts for current user."""
    rows = (
        db.query(Word.category, func.count(Word.id))
        .filter(Word.user_id == user.id)
        .group_by(Word.category)
        .all()
    )
    counts: dict[str, int] = {cat: 0 for cat in CATEGORIES}
    counts["未分类"] = 0
    for cat, count in rows:
        key = cat or "未分类"
        counts[key] = counts.get(key, 0) + count
    return {"counts": counts, "order": ["未分类"] + CATEGORIES}


@router.post("/recategorize")
async def recategorize(db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Batch-assign categories to all uncategorized words of current user."""
    uncategorized = db.query(Word).filter(
        Word.user_id == user.id,
        (Word.category == "") | (Word.category.is_(None)),
    ).all()
    if not uncategorized:
        return {"updated": 0, "total": 0}

    BATCH = 20
    updated = 0
    for i in range(0, len(uncategorized), BATCH):
        chunk = uncategorized[i : i + BATCH]
        words = [w.text for w in chunk]
        try:
            results = await categorize_words_batch(words, db, user.id)
        except RuntimeError as e:
            raise HTTPException(status_code=502, detail=str(e))
        for w in chunk:
            cat = results.get(w.text.lower())
            if cat:
                w.category = cat
                updated += 1
    db.commit()
    return {"updated": updated, "total": len(uncategorized)}


@router.get("", response_model=list[WordBrief])
def list_words(
    q: str | None = Query(default=None),
    category: str | None = Query(default=None),
    mastery: int | None = Query(default=None, ge=0, le=5),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    query = db.query(Word).filter(Word.user_id == user.id)
    if q:
        like = f"%{q.lower()}%"
        query = query.filter(func.lower(Word.text).like(like) | Word.translation.like(f"%{q}%"))
    if category is not None:
        if category == "未分类":
            query = query.filter((Word.category == "") | (Word.category.is_(None)))
        else:
            query = query.filter(Word.category == category)
    if mastery is not None:
        query = query.filter(Word.mastery == mastery)
    return query.order_by(desc(Word.created_at)).offset(offset).limit(limit).all()


@router.get("/{word_id}", response_model=WordOut)
def get_word(word_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    w = db.get(Word, word_id)
    if not w or w.user_id != user.id:
        raise HTTPException(status_code=404, detail="word not found")
    return w


@router.delete("/{word_id}")
def delete_word(word_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    w = db.get(Word, word_id)
    if not w or w.user_id != user.id:
        raise HTTPException(status_code=404, detail="word not found")
    db.delete(w)
    db.commit()
    return {"ok": True}


@router.post("/usage")
async def word_usage_stream(
    payload: UsageIn,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Stream AI-generated usage notes + mnemonic for a single word."""
    row = get_settings(db, user.id)
    if not is_configured(row):
        raise HTTPException(
            status_code=502,
            detail="AI 未配置，无法生成用法解释。在右上角 ⚙ 设置中配一个 AI provider 再试。",
        )

    rid = new_request_id()
    t0 = now_ms()
    log_event(
        "usage.start",
        rid=rid,
        word=payload.text.strip(),
        provider=row.provider_type,
        model=row.model,
    )

    async def gen():
        chunks = 0
        first_chunk_ms = None
        try:
            provider = build_provider(row.provider_type, row.base_url, row.api_key, row.model)
            log_event("usage.provider_built", rid=rid, ms=round(now_ms() - t0, 1))
            async for chunk in provider.chat_stream(
                USAGE_SYSTEM, payload.text.strip(), max_tokens=500
            ):
                if first_chunk_ms is None:
                    first_chunk_ms = round(now_ms() - t0, 1)
                    log_event("usage.first_chunk", rid=rid, ms=first_chunk_ms, len=len(chunk))
                chunks += 1
                yield f"data: {json.dumps({'delta': chunk}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            log_event(
                "usage.done",
                rid=rid,
                chunks=chunks,
                total_ms=round(now_ms() - t0, 1),
                first_chunk_ms=first_chunk_ms,
            )
        except ProviderError as e:
            log_event("usage.error", rid=rid, error=str(e)[:200], ms=round(now_ms() - t0, 1))
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
