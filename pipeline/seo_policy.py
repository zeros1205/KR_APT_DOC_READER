"""seo_policy.py — 색인 정책 헬퍼.

의존성 없는 단일 함수 모듈. html_renderer / index_renderer / 일괄 패치 스크립트가
모두 동일한 임계치·판정 로직을 공유하도록 분리해 두었음.
"""

from __future__ import annotations

import re
from datetime import date


# 부동산 청약의 검색 트래픽 곡선은 D+30 부근에서 첫 급락이 일어나,
# 그 시점이 사이트 평균 콘텐츠 가치 신호를 유지하기 가장 좋은 분기점.
NOINDEX_AFTER_DAYS = 30

# Thin content 임계치. 측정 기준은 <body> 안에서 HTML 주석·script·style 을 제거한
# 순수 텍스트 길이. 현재 모든 정상 포스트가 4500자 이상이라 4000자는 회귀 방어용.
THIN_CONTENT_MIN_TEXT_LEN = 4000
# 분양가·일정 표가 비정상적으로 빈약한 페이지(=데이터 수집 실패) 차단.
THIN_CONTENT_MIN_TR = 3
# 표 자체가 없는 페이지는 분양가 정보가 전혀 없다는 뜻 → 무조건 thin.
THIN_CONTENT_MIN_TABLES = 1


_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_SCRIPT_STYLE_RE = re.compile(r"<(script|style)\b[^>]*>.*?</\1\s*>", re.DOTALL | re.IGNORECASE)
_BODY_RE = re.compile(r"<body[^>]*>(.*?)</body>", re.DOTALL | re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


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
    """당첨자 발표 후 NOINDEX_AFTER_DAYS 이상 경과 시 True."""
    wd = _parse_yyyymmdd(winner_date)
    if not wd:
        return False
    base = today or date.today()
    return (base - wd).days >= NOINDEX_AFTER_DAYS


def measure_content(html: str) -> dict:
    """포스트 HTML 의 콘텐츠 밀도 지표 측정.

    측정 절차: <body> 추출 → HTML 주석 제거 → <script>·<style> 제거 → 태그 제거
    → 공백 정규화. 본문 텍스트 길이와 표·표행 카운트를 반환.
    """
    body_match = _BODY_RE.search(html)
    body = body_match.group(1) if body_match else html
    body = _COMMENT_RE.sub(" ", body)
    body = _SCRIPT_STYLE_RE.sub(" ", body)
    text = _TAG_RE.sub(" ", body)
    text = _WS_RE.sub(" ", text).strip()
    return {
        "text_len": len(text),
        "tables": len(re.findall(r"<table\b", html, re.IGNORECASE)),
        "tr": len(re.findall(r"<tr\b", html, re.IGNORECASE)),
    }


def is_thin_content(html: str) -> tuple[bool, list[str]]:
    """Thin content 판정. (bool, 이유 리스트) 반환."""
    m = measure_content(html)
    reasons: list[str] = []
    if m["text_len"] < THIN_CONTENT_MIN_TEXT_LEN:
        reasons.append(f"text_len={m['text_len']} < {THIN_CONTENT_MIN_TEXT_LEN}")
    if m["tables"] < THIN_CONTENT_MIN_TABLES:
        reasons.append(f"tables={m['tables']} < {THIN_CONTENT_MIN_TABLES}")
    if m["tr"] < THIN_CONTENT_MIN_TR:
        reasons.append(f"tr={m['tr']} < {THIN_CONTENT_MIN_TR}")
    return (bool(reasons), reasons)


def should_noindex(*, winner_date: object, html: str, today: date | None = None) -> tuple[bool, str]:
    """만료 OR thin content 결합 판정. (bool, 사유) 반환.

    사유 문자열은 patch 스크립트 / lint 가 보고에 활용.
    """
    if is_noindex_eligible(winner_date, today=today):
        return True, "expired"
    thin, reasons = is_thin_content(html)
    if thin:
        return True, "thin:" + ",".join(reasons)
    return False, ""

