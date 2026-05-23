from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session
from typing import Generator
from app.config import get_settings


def _build_engine():
    settings = get_settings()
    url = settings.database_url
    kwargs: dict = {
        "pool_pre_ping": True,
        "pool_recycle": 1800,
    }
    # Neon / PgBouncer pooler endpoints don't support server-side params
    if "-pooler." in url or "pgbouncer" in url.lower():
        kwargs["pool_size"] = 1
        kwargs["max_overflow"] = 0
    else:
        kwargs["pool_size"] = 10
        kwargs["max_overflow"] = 20

    return create_engine(url, **kwargs)


engine = _build_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
