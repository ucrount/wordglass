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
    category: str
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
    category: str
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


class SettingsOut(BaseModel):
    """Settings as returned to the client. The api_key is masked."""

    provider_type: str
    base_url: str
    api_key_set: bool  # whether a key is stored (don't return the key itself)
    api_key_preview: str  # e.g. "sk-...c9f" for confirmation
    model: str
    auth_token_set: bool
    configured: bool  # convenience: True if all required fields are present


class SettingsIn(BaseModel):
    """Incoming settings payload. api_key empty means 'keep existing'."""

    provider_type: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None  # if "", we leave existing; if None, also leave existing
    model: Optional[str] = None
    auth_token: Optional[str] = None


class ModelListOut(BaseModel):
    models: List[str]


class TestResultOut(BaseModel):
    ok: bool
    echo: Optional[str] = None
    error: Optional[str] = None


# ─── Settings v2: AI logs, system logs, curl preview, classified test ─────


class AiCallRecord(BaseModel):
    id: int
    ts: float
    kind: str
    provider: str
    model: str
    base_url: str
    system: str = ""
    user: str = ""
    response: str = ""
    status: str = "ok"
    error: Optional[str] = None
    http_status: Optional[int] = None
    json_mode: Optional[bool] = None
    max_tokens: Optional[int] = None
    chunks: Optional[int] = None
    first_chunk_ms: Optional[float] = None
    ms: float = 0.0


class AiLogsOut(BaseModel):
    items: List[AiCallRecord]


class SystemLogRecord(BaseModel):
    id: int
    ts: float
    event: str

    class Config:
        extra = "allow"


class SystemLogsOut(BaseModel):
    items: List[SystemLogRecord]


class CurlIn(BaseModel):
    provider_type: str
    base_url: str
    api_key: Optional[str] = ""
    model: str
    reveal_key: bool = False


class CurlOut(BaseModel):
    command: str


class TestResultV2(BaseModel):
    ok: bool
    category: str = ""
    detail: str = ""
    raw: str = ""
    echo: str = ""
    ms: float = 0
