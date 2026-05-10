from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class ExampleOut(BaseModel):
    id: int
    en: str
    zh: str

    class Config:
        from_attributes = True


class WordCreate(BaseModel):
    text: str = Field(..., min_length=1, max_length=100)


class WordOut(BaseModel):
    id: int
    text: str
    phonetic: str
    pos: str
    translation: str
    mastery: int
    review_count: int
    correct_count: int
    created_at: datetime
    next_review_at: datetime
    examples: List[ExampleOut]

    class Config:
        from_attributes = True


class WordBrief(BaseModel):
    id: int
    text: str
    phonetic: str
    translation: str
    mastery: int
    created_at: datetime

    class Config:
        from_attributes = True


class ReviewIn(BaseModel):
    word_id: int
    mode: str
    result: str  # again / hard / good / easy


class StatsOut(BaseModel):
    total: int
    due_today: int
    mastered: int
    added_this_week: int


class AiWordPayload(BaseModel):
    """Shape of what the AI is asked to return."""

    text: str
    phonetic: str = ""
    pos: str = ""
    translation: str = ""
    examples: List[dict] = []
