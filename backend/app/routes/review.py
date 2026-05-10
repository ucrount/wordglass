from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import verify_token
from ..db import get_db
from ..models import ReviewLog, Word
from ..review import apply_review
from ..schemas import ReviewIn, WordOut

router = APIRouter(prefix="/api/review", tags=["review"], dependencies=[Depends(verify_token)])


@router.get("/due", response_model=list[WordOut])
def due_words(limit: int = 50, db: Session = Depends(get_db)):
    now = datetime.utcnow()
    return (
        db.query(Word)
        .filter(Word.next_review_at <= now)
        .order_by(Word.next_review_at.asc())
        .limit(limit)
        .all()
    )


@router.post("")
def submit_review(payload: ReviewIn, db: Session = Depends(get_db)):
    word = db.get(Word, payload.word_id)
    if not word:
        raise HTTPException(status_code=404, detail="word not found")

    new_mastery, next_at = apply_review(word.mastery, payload.result)
    word.mastery = new_mastery
    word.next_review_at = next_at
    word.review_count += 1
    if payload.result in {"good", "easy"}:
        word.correct_count += 1

    db.add(ReviewLog(word_id=word.id, mode=payload.mode, result=payload.result))
    db.commit()
    db.refresh(word)
    return {
        "ok": True,
        "mastery": word.mastery,
        "next_review_at": word.next_review_at.isoformat(),
    }
