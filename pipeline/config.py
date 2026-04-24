"""
config.py - 전체 파이프라인 설정
환경 변수 또는 .env 파일에서 API 키 로드
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ── 프로젝트 경로 ──
BASE_DIR = Path(__file__).parent.parent
TEMPLATE_DIR = BASE_DIR / "templates"
OUTPUT_DIR = BASE_DIR / "output"
CHROMA_DIR = BASE_DIR / "chroma_db"

# cwd/.env와 프로젝트 루트 .env를 모두 시도
load_dotenv()
load_dotenv(BASE_DIR / ".env")

# ── Google Gemini (모든 LLM 작업 통합) ──
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
LLM_EXTRACT_MODEL = "gemini-3.1-pro"        # 팩트 추출 (Google Grounding 포함)
LLM_CONTENT_MODEL = "gemini-3.1-pro"        # 서술형 콘텐츠 생성·검증
LLM_FACTCHECK_MODEL = "gemini-3.1-pro"      # 팩트 체크
LLM_LOCATION_MODEL = "gemini-3.1-pro"       # 입지 분석 (Google Search Grounding)

# ── OpenAI (레거시 - 제거됨) ──
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")  # 보존용 (향후 제거)
LLM_EMBED_MODEL = "text-embedding-3-small"        # 임베딩은 아직 미사용

# ── 이미지 API ──
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY", "")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")
PREFERRED_IMAGE_SOURCE = "unsplash"   # "unsplash" | "pexels"

# ── 청약홈 공공데이터 API ──
PUBLIC_DATA_API_KEY = os.getenv("PUBLIC_DATA_API_KEY", "")
APARTMENT_API_BASE = "https://api.odcloud.kr/api/ApplyhomeInfoDetailSvc/v1"

# ── Kakao Local API ──
KAKAO_API_KEY = os.getenv("KAKAO_API_KEY", "")

# ── CTA URL (제휴/CPA 링크로 교체) ──
CTA_LOAN_COMPARE = os.getenv("CTA_LOAN_COMPARE", "https://finda.co.kr/")
CTA_INTERIOR = os.getenv("CTA_INTERIOR", "https://ohou.se/")
CTA_MOVING = os.getenv("CTA_MOVING", "https://www.zim.co.kr/")
CTA_TAX = os.getenv("CTA_TAX", "https://www.nts.go.kr/")
CTA_KAKAO_CHANNEL = os.getenv("CTA_KAKAO_CHANNEL", "https://pf.kakao.com/")

# ── 품질 게이트 ──
MIN_QUALITY_SCORE = 70       # 이하 시 재생성
MAX_CTA_PER_POST = 3         # 저품질 방어: 외부 링크 최대 3개
MIN_CHAR_COUNT = 6000        # 최소 글자 수

# ── 사이트 도메인 ──
SITE_URL = "https://apt-note.com"

# ── 블로그 테마 ──
# 선택지: claude / notion / airbnb / intercom / stripe / apple / mintlify
BLOG_THEME = os.getenv("BLOG_THEME", "claude")

# ── 스케줄 ──
CRON_HOUR = 9                # 매일 오전 9시 실행
MAX_POSTS_PER_DAY = 3        # 일 최대 포스팅 수
