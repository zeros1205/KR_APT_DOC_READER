"""complex_type_tagger.py — 단지 유형 다층 태깅.

목적
  입지분석 본문이 단지마다 똑같은 어조로 흘러가는 문제를 해소하기 위해,
  단지의 본질을 드러내는 7개 축의 태그를 자동 추론한다. 프롬프트 입력으로
  넘기면 LLM 이 강조 축을 다르게 선택하도록 유도할 수 있다.

7개 축
  1. district_type      신도시 / 재건축·재개발 / 정비사업 / 일반
  2. supply_special     일반 / 조합원취소분 / 잔여세대 / 무순위 / 보류지 / 임의공급
  3. tenure_type        분양 / 토지임대부 / 분양전환공공임대
  4. scale_tier         소규모(<100) / 중형(100~999) / 대단지(>=1000)
  5. size_profile       소형(전용 60↓) / 중형(60~85) / 중대형(85↑) — 가중 평균 + 비중
  6. special_supply_intensity   특별공급비중 낮음(<20%) / 보통(20~50%) / 높음(>=50%)
  7. price_tier         초고가(평당 1억↑) / 고가(평당 5천↑) / 중상 / 중 / 저
                        (서울·수도권 핵심 vs 지방 차별화에 활용)

사용
  python -m pipeline.complex_type_tagger 2026000048 2026000058 ...

라이브러리:
  from pipeline.complex_type_tagger import tag_notice
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NOTICE_CACHE_DIR = ROOT / "output" / "data_cache" / "notices"

# ──────────────────────────────────────────────
# 신도시 / 정비사업 패턴
# ──────────────────────────────────────────────

# 주소·단지명에 등장하면 신도시로 본다. 새 신도시 추가 시 여기에 명시.
NEW_TOWN_KEYWORDS = [
    "위례", "동탄", "동탄2", "동탄3",
    "세종", "행정중심복합도시",
    "검단", "검단신도시",
    "고덕국제", "고덕신도시", "고덕국제신도시",
    "다산", "다산신도시",
    "미사강변", "미사",
    "교하", "운정", "운정신도시",
    "삼송", "원흥",
    "평촌", "광교", "광교신도시",
    "마곡", "마곡지구",
    "송도", "송도국제",
    "청라", "청라국제",
    "별내", "별내신도시",
    "위례신도시", "감일",
    "옥정", "옥정신도시",
    "양주신도시",
    "지구", "공공주택지구",
]

REDEVELOP_KEYWORDS = [
    "재건축", "재개발", "정비사업", "도시정비", "주택재개발", "주택재건축",
    "도시환경정비", "가로주택", "지역주택",
]

SPECIAL_SUPPLY_PATTERNS = {
    "조합원취소분": ["조합원 취소", "조합원취소", "조합원 자격상실", "제명세대"],
    "잔여세대": ["잔여세대", "잔여 세대"],
    "무순위": ["무순위"],
    "보류지": ["보류지"],
    "임의공급": ["임의공급", "임의 공급"],
    "재공급": ["재공급", "취소후", "취소 후"],
}

TENURE_PATTERNS = {
    "토지임대부": ["토지임대부"],
    "분양전환공공임대": ["분양전환", "공공임대", "공공건설임대"],
}

# 평형 분류 (전용 면적 ㎡)
SIZE_BUCKETS = [
    (60.0, "소형"),
    (85.0, "중형"),
    (float("inf"), "중대형"),
]


def _load_notice(notice_id: str) -> dict:
    path = NOTICE_CACHE_DIR / f"{notice_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"캐시 없음: {path}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _all_text(payload: dict) -> str:
    """단지명·주소·raw_text 를 합친 검색 텍스트."""
    doc = payload.get("document", {}) or {}
    parts = [
        payload.get("apt_name", "") or "",
        doc.get("apt_name", "") or "",
        doc.get("supply_address", "") or "",
        doc.get("raw_text", "") or "",
    ]
    return " ".join(p for p in parts if p)


def _district_type(text: str) -> str:
    for kw in REDEVELOP_KEYWORDS:
        if kw in text:
            return "재건축·재개발"
    for kw in NEW_TOWN_KEYWORDS:
        if kw in text:
            return "신도시"
    return "일반"


def _supply_special(text: str) -> str:
    for label, keywords in SPECIAL_SUPPLY_PATTERNS.items():
        for kw in keywords:
            if kw in text:
                return label
    return "일반"


def _tenure_type(text: str, payload: dict) -> str:
    for label, keywords in TENURE_PATTERNS.items():
        for kw in keywords:
            if kw in text:
                return label
    return "분양"


def _scale_tier(total_units: int | None) -> str:
    if not total_units:
        return "미상"
    if total_units < 100:
        return "소규모"
    if total_units < 1000:
        return "중형"
    return "대단지"


def _size_profile(unit_types: list[dict]) -> dict:
    """전용면적 가중 분포 계산. 비중 % 와 대표 라벨."""
    if not unit_types:
        return {"label": "미상", "buckets": {}}
    total_units = 0
    bucket_units = {label: 0 for _, label in SIZE_BUCKETS}
    for ut in unit_types:
        try:
            area = float(ut.get("SUPLY_AR") or ut.get("EXCLUSE_AR") or 0) or 0
        except Exception:
            area = 0
        for limit, label in SIZE_BUCKETS:
            if area < limit:
                u = int(ut.get("SUPLY_HSHLDCO") or ut.get("TOT_SUPLY_HSHLDCO") or
                        ut.get("ETC_HSHLDCO") or 0)
                if u == 0:
                    # raw_text 에 일반+특별 합계가 있는 경우가 많아 임의 fallback
                    u = 1
                bucket_units[label] += u
                total_units += u
                break
    if not total_units:
        return {"label": "미상", "buckets": {}}
    pct = {k: round(v * 100 / total_units, 1) for k, v in bucket_units.items()}
    label = max(pct, key=pct.get)
    return {"label": label, "buckets": pct}


def _special_supply_intensity(unit_types: list[dict], total_units: int | None) -> str:
    """특별공급 세대 / 총공급 세대 비중. unit_types 의 SPSPLY_HSHLDCO 합산."""
    if not unit_types or not total_units:
        return "미상"
    sp = 0
    for ut in unit_types:
        try:
            sp += int(ut.get("SPSPLY_HSHLDCO") or 0)
        except Exception:
            pass
    if total_units == 0:
        return "미상"
    pct = sp * 100 / total_units
    if pct < 20:
        return "낮음"
    if pct < 50:
        return "보통"
    return "높음"


def _max_price_per_pyeong(unit_types: list[dict]) -> float | None:
    """타입별 분양가/공급면적 으로 평당가 (만원/평) 최대값. 평=3.3058㎡"""
    best = None
    for ut in unit_types:
        try:
            price = float(ut.get("SUPLY_PRICE") or 0)
            area = float(ut.get("SUPLY_AR") or 0)
            if price > 0 and area > 0:
                per_pyeong = price / (area / 3.3058)
                if best is None or per_pyeong > best:
                    best = per_pyeong
        except Exception:
            continue
    return best


def _price_tier(per_pyeong: float | None) -> str:
    if per_pyeong is None:
        return "미상"
    if per_pyeong >= 10000:
        return "초고가"
    if per_pyeong >= 5000:
        return "고가"
    if per_pyeong >= 3000:
        return "중상"
    if per_pyeong >= 1500:
        return "중"
    return "저"


def tag_notice(payload: dict) -> dict:
    """캐시 payload 한 건의 7개 축 태그를 dict 로 반환."""
    text = _all_text(payload)
    doc = payload.get("document", {}) or {}
    unit_types = payload.get("unit_types") or []
    total_units = doc.get("total_units")
    try:
        total_units = int(total_units) if total_units is not None else None
    except Exception:
        total_units = None

    size = _size_profile(unit_types)
    per_pyeong = _max_price_per_pyeong(unit_types)

    return {
        "district_type": _district_type(text),
        "supply_special": _supply_special(text),
        "tenure_type": _tenure_type(text, payload),
        "scale_tier": _scale_tier(total_units),
        "size_profile": size["label"],
        "size_distribution": size["buckets"],
        "special_supply_intensity": _special_supply_intensity(unit_types, total_units),
        "price_tier": _price_tier(per_pyeong),
        "_signals": {
            "total_units": total_units,
            "max_per_pyeong_manwon": int(per_pyeong) if per_pyeong else None,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("notice_ids", nargs="+")
    parser.add_argument("--json", action="store_true", help="JSON 출력")
    args = parser.parse_args()

    results = {}
    for nid in args.notice_ids:
        try:
            payload = _load_notice(nid)
        except FileNotFoundError as exc:
            print(f"❌ {nid}: {exc}")
            continue
        results[nid] = tag_notice(payload)

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 0

    for nid, tags in results.items():
        print(f"=== {nid} ===")
        for k, v in tags.items():
            if k.startswith("_") or k == "size_distribution":
                continue
            print(f"  {k:25s} {v}")
        if tags.get("size_distribution"):
            dist = tags["size_distribution"]
            dist_str = " · ".join(f"{k} {v}%" for k, v in dist.items() if v > 0)
            print(f"  size_distribution         {dist_str}")
        s = tags.get("_signals") or {}
        if s:
            print(f"  (signals: units={s.get('total_units')} per_pyeong={s.get('max_per_pyeong_manwon')}만원/평)")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
