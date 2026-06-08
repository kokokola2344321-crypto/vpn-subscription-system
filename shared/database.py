"""
Настройка базы данных и сессий SQLAlchemy
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
from shared.config import DATABASE_URL
from shared.models import Base
import logging

logger = logging.getLogger(__name__)

# Создаем engine
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    echo=False
)

# Создаем фабрику сессий
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Инициализация базы данных (создание таблиц)"""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("✅ База данных инициализирована")
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации БД: {e}")
        raise


def get_db() -> Generator[Session, None, None]:
    """Получить сессию БД (для FastAPI)"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
