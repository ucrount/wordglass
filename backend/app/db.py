import secrets

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


def _add_column_if_missing(conn, table: str, column_name: str, ddl: str) -> None:
    """SQLite-safe idempotent ALTER TABLE ADD COLUMN."""
    inspector = inspect(conn)
    cols = {c["name"] for c in inspector.get_columns(table)}
    if column_name not in cols:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))


def ensure_schema():
    """Idempotent migrations: create new tables, add new columns, seed app_config."""
    # Create all tables that are missing
    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    # Add columns added after initial release
    with engine.begin() as conn:
        if "words" in tables:
            _add_column_if_missing(conn, "words", "category",
                                   "category VARCHAR(50) DEFAULT ''")
            _add_column_if_missing(conn, "words", "user_id",
                                   "user_id INTEGER REFERENCES users(id)")
        if "review_logs" in tables:
            _add_column_if_missing(conn, "review_logs", "user_id",
                                   "user_id INTEGER REFERENCES users(id)")
        if "settings" in tables:
            _add_column_if_missing(conn, "settings", "user_id",
                                   "user_id INTEGER REFERENCES users(id)")

    # Seed AppConfig singleton (id=1) with random invite_code + jwt_secret
    from .models import AppConfig
    with SessionLocal() as db:
        cfg = db.query(AppConfig).filter(AppConfig.id == 1).first()
        if cfg is None:
            cfg = AppConfig(
                id=1,
                invite_code=secrets.token_urlsafe(24),
                registration_enabled=1,
                jwt_secret=secrets.token_urlsafe(48),
            )
            db.add(cfg)
            db.commit()
