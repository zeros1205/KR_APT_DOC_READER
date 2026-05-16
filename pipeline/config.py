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

# 프로젝트 루트의 .env 가 정식 위치. cwd/.env 는 fallback (개발 편의용).
# 프로젝트 루트가 우선순위 높도록 먼저 로드 — load_dotenv 는 기본적으로 기존 환경
# 변수를 덮어쓰지 않으므로(override=False), 먼저 로드된 값이 우선 사용됨.
load_dotenv(BASE_DIR / ".env")
if Path.cwd() != BASE_DIR:
    load_dotenv()  # cwd/.env 가 다른 경우만 추가 로드


def _clear_dead_local_proxy() -> None:
    """
    잘못 주입된 로컬 프록시(127.0.0.1:9)를 제거한다.

    Codex/터미널 환경에 따라 HTTP(S)_PROXY가 dead endpoint로 설정되는 경우가 있어
    OpenAI/Chroma 임베딩/Gemini 외부 호출이 전부 Connection error로 실패한다.
    실제 프록시를 쓰는 환경은 건드리지 않고, 죽어 있는 loopback:9 값만 제거한다.
    """
    dead_proxy_hosts = ("127.0.0.1:9", "localhost:9")
    proxy_keys = (
        "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
        "http_proxy", "https_proxy", "all_proxy",
    )
    for key in proxy_keys:
        value = os.getenv(key, "").strip()
        if value and any(host in value for host in dead_proxy_hosts):
            os.environ.pop(key, None)


_clear_dead_local_proxy()

# ── OpenAI ──
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
LLM_EXTRACT_MODEL = "gpt-5.4"      # 팩트 추출
LLM_CONTENT_MODEL = "gpt-5.4"  # 서술형 콘텐츠 생성·검증
LLM_EMBED_MODEL = "text-embedding-3-small"

# ── Google Gemini (입지 분석 전용) ──
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
LLM_LOCATION_MODEL = os.getenv("LLM_LOCATION_MODEL", "gemini-3.1-flash-lite")

# ── OpenAI 팩트체크 ──
LLM_FACTCHECK_MODEL = "gpt-5.4-mini"

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
