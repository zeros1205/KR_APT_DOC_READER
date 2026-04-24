#!/usr/bin/env python3
"""
check_status.py
────────────────────────────────────────────────
orchestrator_v2 파이프라인 상태 확인 유틸리티

사용법:
    python check_status.py                   # 전체 상태 확인
    python check_status.py --api             # API 키만 확인
    python check_status.py --db              # 데이터베이스만 확인
    python check_status.py --files           # 파일 구조만 확인
────────────────────────────────────────────────
"""

import sys
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    print("❌ python-dotenv not installed. Run: pip install python-dotenv")
    sys.exit(1)

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR / "pipeline"))

load_dotenv(BASE_DIR / ".env")


def check_env_files():
    """환경 파일 확인"""
    print("\n📁 환경 파일")
    print("─" * 40)

    env_file = BASE_DIR / ".env"
    env_example = BASE_DIR / ".env.example"

    if env_file.exists():
        print(f"✅ .env 파일 존재 ({env_file.stat().st_size} bytes)")
    else:
        print(f"❌ .env 파일 없음")
        if env_example.exists():
            print(f"   💡 .env.example를 참고하여 .env 생성하세요")

    if env_example.exists():
        print(f"✅ .env.example 존재")
    else:
        print(f"⚠️  .env.example 없음")


def check_api_keys():
    """API 키 확인"""
    print("\n🔑 API 키")
    print("─" * 40)

    keys = {
        "GEMINI_API_KEY": "Google Gemini LLM",
        "PUBLIC_DATA_API_KEY": "청약홈 공공데이터",
        "UNSPLASH_ACCESS_KEY": "Unsplash 이미지 (선택)",
        "PEXELS_API_KEY": "Pexels 이미지 (선택)"
    }

    for key_name, description in keys.items():
        value = os.getenv(key_name, "")
        if value:
            # 마스크 처리
            masked = f"{value[:5]}...{value[-5:]}" if len(value) > 10 else "***"
            status = "✅" if key_name.endswith("API_KEY") else "ℹ️ "
            print(f"{status} {key_name}: {masked} ({len(value)} chars)")
        else:
            status = "❌" if "GEMINI" in key_name or "PUBLIC_DATA" in key_name else "⚠️ "
            print(f"{status} {key_name}: 설정되지 않음")


def check_database():
    """데이터베이스 확인"""
    print("\n💾 데이터베이스")
    print("─" * 40)

    try:
        from pipeline.database import DATABASE_URL
    except ImportError:
        DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./apt_reader.db")

    print(f"📊 설정: {DATABASE_URL}")

    if "sqlite" in DATABASE_URL:
        db_path = Path(DATABASE_URL.replace("sqlite:///", ""))
        if db_path.exists():
            size_mb = db_path.stat().st_size / (1024 * 1024)
            print(f"✅ SQLite DB 존재 ({size_mb:.2f} MB)")
        else:
            print(f"⚠️  SQLite DB 없음 (첫 실행 시 자동 생성됨)")
    elif "postgresql" in DATABASE_URL:
        print(f"✅ PostgreSQL 설정됨")
    else:
        print(f"❌ 알 수 없는 데이터베이스 타입")


def check_files():
    """파일 구조 확인"""
    print("\n📂 파일 구조")
    print("─" * 40)

    required_files = {
        "pipeline/orchestrator_v2.py": "메인 파이프라인",
        "pipeline/html_renderer.py": "HTML 렌더링",
        "pipeline/models.py": "DB 모델",
        "pipeline/database.py": "DB 설정",
        "pipeline/config.py": "설정",
        "run_v2.py": "진입점",
        "ORCHESTRATOR_V2.md": "문서"
    }

    for file_path, description in required_files.items():
        full_path = BASE_DIR / file_path
        if full_path.exists():
            print(f"✅ {file_path}")
        else:
            print(f"❌ {file_path} (필수)")

    output_dir = BASE_DIR / "output"
    if output_dir.exists():
        posts_dir = output_dir / "posts"
        post_count = len(list(posts_dir.glob("*"))) if posts_dir.exists() else 0
        print(f"✅ output/ 디렉토리 ({post_count} 포스팅)")
    else:
        print(f"⚠️  output/ 디렉토리 없음 (첫 실행 시 생성됨)")


def check_dependencies():
    """의존성 확인"""
    print("\n📦 의존성")
    print("─" * 40)

    packages = {
        "google.genai": "Google Gemini SDK",
        "sqlalchemy": "SQLAlchemy ORM",
        "dotenv": "환경 변수 로드",
        "requests": "HTTP 요청",
    }

    for module_name, description in packages.items():
        try:
            __import__(module_name)
            print(f"✅ {module_name}")
        except ImportError:
            print(f"❌ {module_name} (설치: pip install -r requirements.txt)")


def check_configuration():
    """설정 확인"""
    print("\n⚙️  설정")
    print("─" * 40)

    try:
        from pipeline.config import BLOG_THEME
        print(f"📌 BLOG_THEME: {BLOG_THEME}")
        print(f"🤖 LLM_MODEL: gemini-1.5-flash (기본값)")
    except Exception as e:
        print(f"⚠️  설정 로드 부분 실패: {e}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="orchestrator_v2 상태 확인")
    parser.add_argument("--api", action="store_true", help="API 키만 확인")
    parser.add_argument("--db", action="store_true", help="데이터베이스만 확인")
    parser.add_argument("--files", action="store_true", help="파일 구조만 확인")
    args = parser.parse_args()

    print("\n" + "=" * 40)
    print("  orchestrator_v2 상태 확인")
    print("=" * 40)
    print(f"프로젝트 경로: {BASE_DIR}")
    print(f"시간: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if args.api:
        check_api_keys()
    elif args.db:
        check_database()
    elif args.files:
        check_files()
    else:
        # 전체 확인
        check_env_files()
        check_api_keys()
        check_dependencies()
        check_database()
        check_files()
        check_configuration()

    print("\n" + "=" * 40)
    print("  상태 확인 완료")
    print("=" * 40)

    # 최소 요구사항 확인
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    if not gemini_key:
        print("\n⚠️  주의:")
        print("  • GEMINI_API_KEY가 설정되지 않았습니다.")
        print("  • 파이프라인은 더미 데이터로 실행됩니다.")
        print("  • 실제 데이터는 API 키 설정 후 처리하세요.")
        print("\n  https://ai.google.dev → 'Get API Key' 버튼 클릭")
    else:
        print("\n✅ 파이프라인 실행 준비 완료!")
        print("  python run_v2.py --sample  # 테스트 실행")


if __name__ == "__main__":
    main()
