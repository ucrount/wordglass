from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from .db import Base


class Word(Base):
    __tablename__ = "words"

    id = Column(Integer, primary_key=True)
    text = Column(String(100), unique=True, nullable=False, index=True)
    phonetic = Column(String(120), default="")
    pos = Column(String(40), default="")
    translation = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    mastery = Column(Integer, default=0, index=True)
    review_count = Column(Integer, default=0)
    correct_count = Column(Integer, default=0)
    next_review_at = Column(DateTime, default=datetime.utcnow, index=True)

    examples = relationship(
        "Example", back_populates="word", cascade="all, delete-orphan", order_by="Example.id"
    )
    reviews = relationship("ReviewLog", back_populates="word", cascade="all, delete-orphan")


class Example(Base):
    __tablename__ = "examples"

    id = Column(Integer, primary_key=True)
    word_id = Column(Integer, ForeignKey("words.id", ondelete="CASCADE"), index=True)
    en = Column(Text, nullable=False)
    zh = Column(Text, default="")

    word = relationship("Word", back_populates="examples")


class ReviewLog(Base):
    __tablename__ = "review_logs"

    id = Column(Integer, primary_key=True)
    word_id = Column(Integer, ForeignKey("words.id", ondelete="CASCADE"), index=True)
    mode = Column(String(20))  # word_en2zh / word_zh2en / cloze / sentence
    result = Column(String(10))  # again / hard / good / easy
    reviewed_at = Column(DateTime, default=datetime.utcnow, index=True)

    word = relationship("Word", back_populates="reviews")


class Setting(Base):
    """Single-row settings table. id is always 1."""

    __tablename__ = "settings"

    id = Column(Integer, primary_key=True)
    provider_type = Column(String(20), default="openai")  # openai / anthropic / google
    base_url = Column(String(255), default="")
    api_key = Column(Text, default="")
    model = Column(String(100), default="")
    auth_token = Column(String(255), default="")  # optional bearer for API access
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
