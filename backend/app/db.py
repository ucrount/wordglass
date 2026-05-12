from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import settings

connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_schema():
    """Idempotent migrations for columns added after initial release.

    SQLAlchemy's create_all only creates missing tables — it won't add
    new columns to an existing table. We apply lightweight ALTER TABLE
    statements here for any columns the current code expects.
    """
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    if "words" in tables:
        cols = {c["name"] for c in inspector.get_columns("words")}
        if "category" not in cols:
            with engine.begin() as conn:
                conn.execute(
                    text("ALTER TABLE words ADD COLUMN category VARCHAR(50) DEFAULT ''")
                )
