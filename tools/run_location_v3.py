"""run_location_v3.py — v3 (Gemini 추천 프롬프트, 단지명·주소만) 단독 실행.

실험 목적: 단지명·주소만 LLM 에 던지고 Gemini Grounding(Google Search) 으로
나머지 정보를 채우게 한 뒤 결과 품질을 본다. v1·v2 와 완전 분리.

저장 경로
  seo_audit/location_v3/<run_date>/results.json
  seo_audit/location_v3/<run_date>/report.md

사용
  python tools/run_location_v3.py --baseline
  python tools/run_location_v3.py --targets 2026000058 ...
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

AUDIT_DIR = ROOT / "seo_audit" / "location_v3"
NOTICE_CACHE_DIR = ROOT / "output" / "data_cache" / "notices"

BASELINE_TARGETS = ["2026000030", "2026000048", "2026000058", "2026000143"]


def _kst_today() -> str:
    return datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d")


def _load_input(notice_id: str) -> tuple[str, str]:
    """캐시 JSON 에서 단지명·주소만 추출."""
    path = NOTICE_CACHE_DIR / f"{notice_id}.json"
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    doc = payload.get("document") or {}
    apt_name = (doc.get("apt_name") or payload.get("apt_name") or "").strip()
    address = (doc.get("supply_location") or doc.get("location") or "").strip()
    return apt_name, address


def _plain_text(body_md: str) -> str:
    text = re.sub(r"^#{1,6}\s+", "", body_md, flags=re.MULTILINE)
    text = re.sub(r"^\s*[-*]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _measure(text: str) -> dict:
    sys.path.insert(0, str(ROOT / "tools"))
    from measure_location_diversity import count_cliches, count_specifics
    return {
        "chars": len(text),
        "cliche": count_cliches(text),
        "specific": count_specifics(text),
        "specific_density_per_1000": round(count_specifics(text) / max(len(text), 1) * 1000, 1),
    }


async def _run_v3(notice_id: str) -> dict:
    from pipeline.agents.location_v3 import generate_v3
    apt_name, address = _load_input(notice_id)
    print(f"  입력: apt_name={apt_name!r} address={address!r}")
    return await generate_v3(apt_name, address)


async def main_async(notice_ids: list[str], run_date: str) -> int:
    out_dir = AUDIT_DIR / run_date
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "results.json"

    summary: dict[str, dict] = {}
    for nid in notice_ids:
        print(f"\n=== {nid} (v3) ===")
        try:
            result = await _run_v3(nid)
        except Exception as exc:
            print(f"  v3 오류: {exc}")
            result = {"_error": str(exc)}
        body_md = result.get("body_md", "") if isinstance(result, dict) else ""
        plain = _plain_text(body_md)
        metrics = _measure(plain) if plain else {}
        print(f"  metrics: {metrics}")
        if isinstance(result, dict):
            meta = result.get("_meta") or {}
            print(f"  meta: grounding={meta.get('grounding')} thinking={meta.get('thinking')} model={meta.get('model')}")
        summary[nid] = {
            "result": result,
            "plain_text": plain,
            "metrics": metrics,
        }

    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✅ 저장: {out_path.relative_to(ROOT)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--targets", nargs="+", default=[])
    parser.add_argument("--baseline", action="store_true")
    parser.add_argument("--date", default="")
    args = parser.parse_args()

    targets = args.targets or (BASELINE_TARGETS if args.baseline else [])
    if not targets:
        parser.error("--targets 또는 --baseline 중 하나 필요")

    run_date = args.date or _kst_today()
    return asyncio.run(main_async(targets, run_date))


if __name__ == "__main__":
    sys.exit(main())
