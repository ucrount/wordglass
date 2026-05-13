from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import current_user
from ..db import get_db
from ..models import ReviewLog, User, Word
from ..review import apply_review
from ..schemas import ReviewIn, WordOut

router = APIRouter(prefix="/api/review", tags=["review"], dependencies=[Depends(current_user)])


@router.get("/due", response_model=list[WordOut])
def due_words(
    limit: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    now = datetime.utcnow()
    return (
        db.query(Word)
        .filter(Word.user_id == user.id, Word.next_review_at <= now)
        .order_by(Word.next_review_at.asc())
        .limit(limit)
        .all()
    )


@router.post("")
def submit_review(
    payload: ReviewIn,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    word = db.get(Word, payload.word_id)
    if not word or word.user_id != user.id:
        raise HTTPException(status_code=404, detail="word not found")

    new_mastery, next_at = apply_review(word.mastery, payload.result)
    word.mastery = new_mastery
    word.next_review_at = next_at
    word.review_count += 1
    if payload.result in {"good", "easy"}:
        word.correct_count += 1

    db.add(ReviewLog(user_id=user.id, word_id=word.id, mode=payload.mode, result=payload.result))
    db.commit()
    db.refresh(word)
    return {
        "ok": True,
        "mastery": word.mastery,
        "next_review_at": word.next_review_at.isoformat(),
    }
