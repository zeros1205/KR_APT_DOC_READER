"""
database.py
────────────────────────────────────────────────────
PostgreSQL/SQLite 데이터베이스 설정
SQLAlchemy ORM 기본 구성
────────────────────────────────────────────────────
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

# DB 연결 설정
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./apt_reader.db")

# SQLite 또는 PostgreSQL
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False}
    )
else:
    # PostgreSQL
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """의존성 주입용 DB 세션"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """모든 테이블 생성"""
    from models import Base
    Base.metadata.create_all(bind=engine)
    print("✅ 데이터베이스 테이블 생성 완료")
