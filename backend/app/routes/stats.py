from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import verify_token
from ..db import get_db
from ..models import Word
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
