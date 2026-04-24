"""
init_db.py
────────────────────────────────────────────────────
데이터베이스 초기화 및 마이그레이션 실행
────────────────────────────────────────────────────
"""

import sys
from pathlib import Path

# 상대 import 설정
sys.path.insert(0, str(Path(__file__).parent))

from database import init_db, engine
from models import Base
from migrate_to_db import migrate_existing_data


def main():
    print("=" * 60)
    print("🔧 데이터베이스 초기화")
    print("=" * 60)

    # 1. 모든 테이블 생성
    print("\n1️⃣  테이블 생성 중...")
    Base.metadata.create_all(bind=engine)
    print("   ✅ 테이블 생성 완료")

    # 2. 기존 JSON 데이터 마이그레이션
    print("\n2️⃣  기존 데이터 마이그레이션 중...")
    migrate_existing_data()

    print("\n" + "=" * 60)
    print("✅ 데이터베이스 초기화 완료!")
    print("=" * 60)
    print("\n다음 단계:")
    print("- FastAPI 백엔드: python pipeline/api.py")
    print("- 포스팅 생성: python run.py --sample")


if __name__ == "__main__":
    main()
