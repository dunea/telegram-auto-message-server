from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings


def build_session_factory(settings: Settings) -> sessionmaker[Session]:
    """创建 SQLAlchemy Session 工厂。"""
    pool_size = max(1, int(settings.db_pool_size))
    max_overflow = max(0, int(settings.db_pool_max_overflow))
    engine = create_engine(
        settings.mysql_dsn,
        pool_pre_ping=True,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_recycle=int(settings.db_pool_recycle_seconds),
        pool_timeout=int(settings.db_pool_timeout_seconds),
    )
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)
