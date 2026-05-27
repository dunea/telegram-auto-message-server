from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings


def build_session_factory(settings: Settings) -> sessionmaker[Session]:
    """创建 SQLAlchemy Session 工厂。"""
    engine = create_engine(settings.mysql_dsn, pool_pre_ping=True)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)
