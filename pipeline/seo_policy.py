"""seo_policy.py — 색인 정책 헬퍼.

의존성 없는 단일 함수 모듈. html_renderer / index_renderer / 일괄 패치 스크립트가
모두 동일한 임계치·판정 로직을 공유하도록 분리해 두었음.
"""

from __future__ import annotations

from datetime import date


# 부동산 청약의 검색 트래픽 곡선은 D+30 부근에서 첫 급락이 일어나,
# 그 시점이 사이트 평균 콘텐츠 가치 신호를 유지하기 가장 좋은 분기점.
NOINDEX_AFTER_DAYS = 30


def _parse_yyyymmdd(value: object) -> date | None:
    text = "" if value is None else str(value).strip()
    if not text or text in {"-", "null", "None"}:
        return None
    text = text.split(" ~ ", 1)[0].strip()
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def is_noindex_eligible(winner_date: object, today: date | None = None) -> bool:
    wd = _parse_yyyymmdd(winner_date)
    if not wd:
        return False
    base = today or date.today()
    return (base - wd).days >= NOINDEX_AFTER_DAYS
