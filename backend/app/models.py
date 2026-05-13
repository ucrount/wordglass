from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from .db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(20), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    is_admin = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login_at = Column(DateTime, nullable=True)


class AppConfig(Base):
    """Singleton row (id=1). Global app config not tied to any user."""

    __tablename__ = "app_config"

    id = Column(Integer, primary_key=True)
    invite_code = Column(String(64), default="")
    registration_enabled = Column(Integer, default=1)
    jwt_secret = Column(String(128), default="")


class Word(Base):
    __tablename__ = "words"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=True)
    text = Column(String(100), nullable=False, index=True)
    phonetic = Column(String(120), default="")
    pos = Column(String(40), default="")
    translation = Column(Text, default="")
    category = Column(String(50), default="", index=True)
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
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=True)
    word_id = Column(Integer, ForeignKey("words.id", ondelete="CASCADE"), index=True)
    mode = Column(String(20))
    result = Column(String(10))
    reviewed_at = Column(DateTime, default=datetime.utcnow, index=True)

    word = relationship("Word", back_populates="reviews")


class Setting(Base):
    """Per-user settings row. Each user has one row."""

    __tablename__ = "settings"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=True)
    provider_type = Column(String(20), default="openai")
    base_url = Column(String(255), default="")
    api_key = Column(Text, default="")
    model = Column(String(100), default="")
    auth_token = Column(String(255), default="")  # deprecated; JWT replaces this
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
