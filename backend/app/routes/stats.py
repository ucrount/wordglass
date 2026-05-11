from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Date, cast, func
from sqlalchemy.orm import Session

from ..auth import verify_token
from ..db import get_db
from ..models import ReviewLog, Word
from ..schemas import StatsOut

router = APIRouter(prefix="/api/stats", tags=["stats"], dependencies=[Depends(verify_token)])


@router.get("", response_model=StatsOut)
def stats(db: Session = Depends(get_db)):
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    total = db.query(Word).count()
    due = db.query(Word).filter(Word.next_review_at <= now).count()
    mastered = db.query(Word).filter(Word.mastery >= 5).count()
    week = db.query(Word).filter(Word.created_at >= week_ago).count()
    return StatsOut(total=total, due_today=due, mastered=mastered, added_this_week=week)


@router.get("/heatmap")
def heatmap(days: int = Query(default=35, ge=7, le=180), db: Session = Depends(get_db)):
    """Daily activity (adds + reviews) for the heatmap calendar widget."""
    since = datetime.utcnow() - timedelta(days=days)

    reviews = (
        db.query(cast(ReviewLog.reviewed_at, Date), func.count())
        .filter(ReviewLog.reviewed_at >= since)
        .group_by(cast(ReviewLog.reviewed_at, Date))
        .all()
    )
    adds = (
        db.query(cast(Word.created_at, Date), func.count())
        .filter(Word.created_at >= since)
        .group_by(cast(Word.created_at, Date))
        .all()
    )

    by_day: dict[str, int] = {}
    for d, c in reviews:
        by_day[str(d)] = by_day.get(str(d), 0) + c
    for d, c in adds:
        by_day[str(d)] = by_day.get(str(d), 0) + c

    return {"days": by_day, "since": since.date().isoformat()}
