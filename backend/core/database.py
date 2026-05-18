"""Database engine and session factory."""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session
from .config import get_settings

settings = get_settings()

# Sync engine (used for most operations)
engine = create_engine(
    settings.database_url,
    connect_args={'check_same_thread': False} if 'sqlite' in settings.database_url else {},
    pool_pre_ping=True,
    echo=settings.debug,
)

# SQLite WAL mode for better concurrent reads
if 'sqlite' in settings.database_url:
    @event.listens_for(engine, 'connect')
    def _set_wal(conn, _):
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA foreign_keys=ON')

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency — yields a database session."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_all_tables():
    """Create all tables (called on startup). Import ALL models to register them."""
    from models import (  # noqa: F401
        user, patient, core_config, laboratory,
        blood_bank, biochemistry, inventory,
        microbiology, molecular,
        voice_settings, escalation, rejection,
        # New clinical models
        hematology, coagulation, serology, urinalysis,
        quality, staffhub, audit, surveillance,
        notifications,
        voice_biometric,
        # Worklist preparation & billing
        worklist, billing,
    )
    Base.metadata.create_all(bind=engine)
