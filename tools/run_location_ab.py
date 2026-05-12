"""run_location_ab.py — 입지 분석 v1(production) vs v2(실험) A/B 실행 도구.

흐름
  1) notice_id 목록을 받아 각 단지의 production 결과(v1)는 post.html 에서 추출.
  2) v2 는 pipeline.agents.location_v2.generate_v2 로 새로 LLM 호출.
  3) 결과를 seo_audit/location_ab/<run_date>/ 폴더에 JSON 으로 저장.
  4) cliche·구체 정보·5-gram 일치율 등 측정 지표를 함께 기록.

API 키(`GEMINI_API_KEY`) 없으면 v2 는 _error 표시로 skip — 비교 산출물은 v1 만 들어감.

사용
  python tools/run_location_ab.py --targets 2026000030 2026000048 2026000058 2026000143
  python tools/run_location_ab.py --baseline               # PR #46 베이스라인 4단지
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))

NOTICE_CACHE_DIR = ROOT / "output" / "data_cache" / "notices"
POSTS_DIR = ROOT / "output" / "posts"
AUDIT_DIR = ROOT / "seo_audit" / "location_ab"

BASELINE_TARGETS = ["2026000030", "2026000048", "2026000058", "2026000143"]

LOCATION_RE = re.compile(
    r'(02\.\s*입지|입지\s*분석|주요\s*입지|위치\s*분석)(.*?)'
    r'(?=03\.|자금\s*계획|타입별\s*분양가|<!--\s*FOOTER|<!--\s*══|🗓|⚠️)',
    re.DOTALL,
)
TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")


def _kst_today() -> str:
    return datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d")


def _extract_v1_text(notice_id: str) -> str:
    """production post.html 에서 입지 분석 섹션 텍스트 추출."""
    p = POSTS_DIR / notice_id / "post.html"
    if not p.exists():
        return ""
    html = p.read_text(encoding="utf-8")
    m = LOCATION_RE.search(html)
    if not m:
        return ""
    text = TAG_RE.sub(" ", m.group(0))
    return WS_RE.sub(" ", text).strip()


def _load_payload(notice_id: str) -> dict:
    path = NOTICE_CACHE_DIR / f"{notice_id}.json"
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _facts_from_payload(payload: dict) -> dict:
    """orchestrator 가 만드는 facts 구조 근사 — v2 에이전트가 기대하는 필드만 채움."""
    doc = payload.get("document") or {}
    return {
        "apt_name": doc.get("apt_name") or payload.get("apt_name"),
        "location": doc.get("location"),
        "supply_location": doc.get("supply_location"),
        "notice_id": doc.get("notice_id") or payload.get("notice_id"),
        "notice_date": doc.get("notice_date"),
        "move_in_date": doc.get("move_in_month"),
        "regulated_zone": doc.get("regulated_zone"),
        "price_cap": doc.get("price_cap"),
        "resale_restriction": doc.get("resale_restriction"),
        "unit_types": payload.get("unit_types", []),
        "total_units": doc.get("total_units"),
    }


def _measure(text: str) -> dict:
    """tools.measure_location_diversity 의 정량 지표 재사용."""
    sys.path.insert(0, str(ROOT / "tools"))
    from measure_location_diversity import (
        CLICHE_TERMS,
        SPECIFIC_PATTERNS,
        count_cliches,
        count_specifics,
    )
    return {
        "chars": len(text),
        "cliche": count_cliches(text),
        "specific": count_specifics(text),
        "specific_density_per_1000": round(count_specifics(text) / max(len(text), 1) * 1000, 1),
    }


async def _run_v2(notice_id: str) -> dict:
    from pipeline.agents.location_v2 import generate_v2
    payload = _load_payload(notice_id)
    facts = _facts_from_payload(payload)
    return await generate_v2(facts, payload)


def _v2_text(result: dict) -> str:
    """v2 결과 dict 를 한 줄 텍스트로 평탄화 — 측정 지표 산출용."""
    if not result or result.get("_error"):
        return ""
    parts = [
        result.get("location_intro", ""),
        TAG_RE.sub(" ", result.get("subway_detail", "") or ""),
        TAG_RE.sub(" ", result.get("school_detail", "") or ""),
        TAG_RE.sub(" ", result.get("feature_detail", "") or ""),
    ]
    return WS_RE.sub(" ", " ".join(parts)).strip()


async def main_async(notice_ids: list[str], run_date: str) -> int:
    out_dir = AUDIT_DIR / run_date
    out_dir.mkdir(parents=True, exist_ok=True)

    summary: dict[str, dict] = {}
    for nid in notice_ids:
        print(f"\n=== {nid} ===")
        v1_text = _extract_v1_text(nid)
        v1_metrics = _measure(v1_text) if v1_text else {}
        print(f"  v1 (production): {v1_metrics}")

        try:
            v2_result = await _run_v2(nid)
        except Exception as exc:
            print(f"  v2 오류: {exc}")
            v2_result = {"_error": str(exc)}
        v2_text = _v2_text(v2_result)
        v2_metrics = _measure(v2_text) if v2_text else {}
        print(f"  v2 (experiment): {v2_metrics}")

        summary[nid] = {
            "v1": {"text": v1_text, "metrics": v1_metrics},
            "v2": {"result": v2_result, "text": v2_text, "metrics": v2_metrics},
        }

    out_path = out_dir / "ab_results.json"
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✅ A/B 결과 저장: {out_path.relative_to(ROOT)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--targets", nargs="+", default=[])
    parser.add_argument("--baseline", action="store_true",
                        help="PR #46 베이스라인 4단지 사용")
    parser.add_argument("--date", default="", help="저장 폴더 날짜 (YYYY-MM-DD)")
    args = parser.parse_args()

    targets = args.targets or (BASELINE_TARGETS if args.baseline else [])
    if not targets:
        parser.error("--targets 또는 --baseline 중 하나 필요")

    run_date = args.date or _kst_today()
    return asyncio.run(main_async(targets, run_date))


if __name__ == "__main__":
    sys.exit(main())
