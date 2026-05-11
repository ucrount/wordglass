from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from ..ai import fetch_word_payload
from ..auth import verify_token
from ..db import get_db
from ..models import Example, Word
from ..schemas import WordBrief, WordCreate, WordOut

router = APIRouter(prefix="/api/words", tags=["words"], dependencies=[Depends(verify_token)])


@router.post("", response_model=WordOut)
async def add_word(payload: WordCreate, db: Session = Depends(get_db)):
    text = payload.text.strip().lower()
    existing = db.query(Word).filter(Word.text == text).first()
    if existing:
        return existing

    try:
        ai_payload = await fetch_word_payload(text, db)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    word = Word(
        text=ai_payload.get("text", text),
        phonetic=ai_payload.get("phonetic", ""),
        pos=ai_payload.get("pos", ""),
        translation=ai_payload.get("translation", ""),
    )
    for ex in ai_payload.get("examples", []):
        word.examples.append(Example(en=ex["en"], zh=ex.get("zh", "")))

    db.add(word)
    db.commit()
    db.refresh(word)
    return word


@router.get("", response_model=list[WordBrief])
def list_words(
    q: str | None = Query(default=None),
    mastery: int | None = Query(default=None, ge=0, le=5),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(Word)
    if q:
        like = f"%{q.lower()}%"
        query = query.filter(func.lower(Word.text).like(like) | Word.translation.like(f"%{q}%"))
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
