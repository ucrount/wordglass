from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Date, cast, func
from sqlalchemy.orm import Session

from ..auth import current_user
from ..db import get_db
from ..models import ReviewLog, User, Word
from ..schemas import StatsOut

router = APIRouter(prefix="/api/stats", tags=["stats"], dependencies=[Depends(current_user)])


@router.get("", response_model=StatsOut)
def stats(db: Session = Depends(get_db), user: User = Depends(current_user)):
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    base = db.query(Word).filter(Word.user_id == user.id)
    total = base.count()
    due = base.filter(Word.next_review_at <= now).count()
    mastered = base.filter(Word.mastery >= 5).count()
    week = base.filter(Word.created_at >= week_ago).count()
    return StatsOut(total=total, due_today=due, mastered=mastered, added_this_week=week)


@router.get("/heatmap")
def heatmap(
    days: int = Query(default=35, ge=7, le=180),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Daily activity (adds + reviews) for the heatmap calendar widget."""
    since = datetime.utcnow() - timedelta(days=days)

    reviews = (
        db.query(cast(ReviewLog.reviewed_at, Date), func.count())
        .filter(ReviewLog.user_id == user.id, ReviewLog.reviewed_at >= since)
        .group_by(cast(ReviewLog.reviewed_at, Date))
        .all()
    )
    adds = (
        db.query(cast(Word.created_at, Date), func.count())
        .filter(Word.user_id == user.id, Word.created_at >= since)
        .group_by(cast(Word.created_at, Date))
        .all()
    )

    by_day: dict[str, int] = {}
    for d, c in reviews:
        by_day[str(d)] = by_day.get(str(d), 0) + c
    for d, c in adds:
        by_day[str(d)] = by_day.get(str(d), 0) + c

    return {"days": by_day, "since": since.date().isoformat()}


@router.get("/weak-words")
def weak_words(
    limit: int = Query(default=5, ge=1, le=20),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Return top-N words the user has reviewed but gets wrong most often.

    Sort key:
      1. wrong_count = review_count - correct_count, DESC
      2. mastery, ASC
      3. created_at, DESC (tie-breaker, newer first)

    Only words with review_count > 0 are considered — never-reviewed words
    aren't "weak", they're just "未练".
    """
    rows = (
        db.query(Word)
        .filter(Word.user_id == user.id, Word.review_count > 0)
        .order_by(
            (Word.review_count - Word.correct_count).desc(),
            Word.mastery.asc(),
            Word.created_at.desc(),
        )
        .limit(limit)
        .all()
    )
    return {
        "items": [
            {
                "id": w.id,
                "text": w.text,
                "translation": w.translation or "",
                "phonetic": w.phonetic or "",
                "mastery": w.mastery,
                "review_count": w.review_count,
                "correct_count": w.correct_count,
                "wrong_count": (w.review_count or 0) - (w.correct_count or 0),
            }
            for w in rows
        ]
    }
