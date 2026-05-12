from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
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
from ..auth import verify_token
from ..db import SessionLocal, get_db
from ..models import Example, Word
from ..offline_dict import has_ecdict, has_tatoeba
from ..schemas import WordBrief, WordCreate, WordOut
from ..settings_store import get_settings, is_configured

router = APIRouter(prefix="/api/words", tags=["words"], dependencies=[Depends(verify_token)])


@router.get("/offline-status")
def offline_status():
    """Tell the frontend which offline data files are loaded."""
    return {"ecdict": has_ecdict(), "tatoeba": has_tatoeba()}


async def _enrich_word(word_id: int, do_category: bool, do_examples: bool) -> None:
    """Runs AFTER the response is sent. Owns its own DB session so it doesn't
    race with the request session that's already closed.

    Each step is best-effort — failures are swallowed because they're not
    visible to the user anyway, and the next add_word run will retry.
    """
    db = SessionLocal()
    try:
        word = db.get(Word, word_id)
        if word is None:
            return

        if do_category and not (word.category or ""):
            cat = await categorize_word(word.text, db)
            if cat:
                word.category = cat
                db.commit()

        if do_examples and not word.examples:
            examples = await generate_examples(word.text, word.translation or "", db)
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
):
    text = payload.text.strip().lower()
    existing = db.query(Word).filter(Word.text == text).first()
    if existing:
        return existing

    local = lookup_local(text)

    if local is not None:
        word = Word(
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

        # If AI is configured, fill missing fields after the response is sent.
        # The frontend polls /api/words/{id} for a few seconds to see updates.
        settings_row = get_settings(db)
        if is_configured(settings_row):
            need_category = True  # always empty at this point
            need_examples = len(word.examples) == 0
            if need_category or need_examples:
                background_tasks.add_task(
                    _enrich_word, word.id, need_category, need_examples
                )
        return word

    # ECDICT miss — must use AI synchronously to get any word data at all.
    try:
        ai_payload = await fetch_word_payload(text, db)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    word = Word(
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
def categories(db: Session = Depends(get_db)):
    """All known categories + counts. Returns the curated list with 0 for
    categories that don't have any words yet, so the UI can show full picture."""
    rows = (
        db.query(Word.category, func.count(Word.id))
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
async def recategorize(db: Session = Depends(get_db)):
    """Batch-assign categories to all uncategorized words. One AI call per
    batch of 20 — much cheaper than calling once per word."""
    uncategorized = db.query(Word).filter((Word.category == "") | (Word.category.is_(None))).all()
    if not uncategorized:
        return {"updated": 0, "total": 0}

    BATCH = 20
    updated = 0
    for i in range(0, len(uncategorized), BATCH):
        chunk = uncategorized[i : i + BATCH]
        words = [w.text for w in chunk]
        try:
            results = await categorize_words_batch(words, db)
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
):
    query = db.query(Word)
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
def get_word(word_id: int, db: Session = Depends(get_db)):
    w = db.get(Word, word_id)
    if not w:
        raise HTTPException(status_code=404, detail="word not found")
    return w


@router.delete("/{word_id}")
def delete_word(word_id: int, db: Session = Depends(get_db)):
    w = db.get(Word, word_id)
    if not w:
        raise HTTPException(status_code=404, detail="word not found")
    db.delete(w)
    db.commit()
    return {"ok": True}
