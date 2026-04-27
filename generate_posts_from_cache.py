"""
Generate posts from cached notice data.

This path does not call the public data API. It reads
`output/data_cache/notices/*.json`, restores NoticeDocument objects, runs the
existing post generation pipeline, and rebuilds the front page outputs.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR / "pipeline"))

from dotenv import load_dotenv

load_dotenv(BASE_DIR / ".env")

from agents.collector import NoticeDocument
from check_ui_freeze import check_ui_freeze
from orchestrator import run_pipeline_from_doc
from pipeline.index_renderer import build_front_index


NOTICE_CACHE_DIR = BASE_DIR / "output" / "data_cache" / "notices"
PROCESSED_FILE = BASE_DIR / "output" / "processed_notices.json"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _load_processed() -> set[str]:
    if not PROCESSED_FILE.exists():
        return set()
    raw = PROCESSED_FILE.read_text(encoding="utf-8-sig").strip()
    if not raw:
        return set()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        print("[warning] processed_notices.json 파싱 실패 -> 빈 히스토리로 진행")
        return set()
    return {str(item) for item in data}


def _save_processed(processed_ids: set[str]) -> None:
    PROCESSED_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROCESSED_FILE.write_text(
        json.dumps(sorted(processed_ids), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _stringify_none(value: Any) -> Any:
    if value is None:
        return ""
    return value


def _doc_from_payload(payload: dict[str, Any]) -> NoticeDocument:
    data = dict(payload.get("document") or {})
    manual_regulation = payload.get("manual_regulation") or {}
    if manual_regulation:
        data.update(
            {
                key: manual_regulation[key]
                for key in (
                    "regulated_zone",
                    "is_hot_zone",
                    "readmission_limit",
                    "resale_restriction",
                    "live_requirement",
                    "price_cap",
                    "is_price_cap",
                )
                if key in manual_regulation
            }
        )
    fields = NoticeDocument.__dataclass_fields__
    normalized = {key: _stringify_none(data.get(key, "")) for key in fields}
    normalized["tables"] = data.get("tables") or []
    normalized["pdf_path"] = None
    doc = NoticeDocument(**normalized)
    if manual_regulation:
        policy_lines = [
            f"[규제] regulated_zone: {manual_regulation.get('regulated_zone', '')}",
            f"[규제] is_hot_zone: {manual_regulation.get('is_hot_zone', '')}",
            f"[규제] readmission_limit: {manual_regulation.get('readmission_limit', '')}",
            f"[규제] resale_restriction: {manual_regulation.get('resale_restriction', '')}",
            f"[규제] live_requirement: {manual_regulation.get('live_requirement', '')}",
            f"[규제] price_cap: {manual_regulation.get('price_cap', '')}",
            f"[규제] is_price_cap: {manual_regulation.get('is_price_cap', '')}",
        ]
        doc.raw_text = f"{doc.raw_text}\n\n" + "\n".join(policy_lines)
    return doc


def _iter_payloads(*, include_manual: bool) -> list[tuple[Path, dict[str, Any]]]:
    if not NOTICE_CACHE_DIR.exists():
        return []
    payloads: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(NOTICE_CACHE_DIR.glob("*.json")):
        payload = _load_json(path)
        if payload.get("requires_manual_input") and not include_manual:
            continue
        payloads.append((path, payload))
    return payloads


async def main() -> None:
    parser = argparse.ArgumentParser(description="Generate post pages from cached notice data")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of cache notices, 0 means no limit")
    parser.add_argument(
        "--notice-id",
        action="append",
        default=[],
        help="Generate a specific cached notice_id. Can be passed multiple times.",
    )
    parser.add_argument("--include-manual", action="store_true", help="Also process notices marked for manual review")
    parser.add_argument("--include-processed", action="store_true", help="Do not skip processed_notices.json entries")
    parser.add_argument("--skip-ui-freeze-check", action="store_true", help="Skip frozen UI/layout hash check")
    parser.add_argument("--no-build-index", action="store_true", help="Skip front page/sitemap/robots regeneration")
    parser.add_argument("--dry-run", action="store_true", help="Load cache and print selected notices without generation")
    args = parser.parse_args()

    if not args.skip_ui_freeze_check:
        failures = check_ui_freeze()
        if failures:
            print("[ui-freeze] frozen UI/layout files changed. Generation stopped.")
            for failure in failures:
                print(f"  - {failure}")
            raise SystemExit(1)
        print("[ui-freeze] OK")

    processed_ids = _load_processed()
    payloads = _iter_payloads(include_manual=args.include_manual)
    selected: list[tuple[Path, dict[str, Any]]] = []
    for path, payload in payloads:
        notice_id = str(payload.get("notice_id") or "")
        if args.notice_id and notice_id not in {str(item) for item in args.notice_id}:
            continue
        if notice_id in processed_ids and not args.include_processed:
            continue
        selected.append((path, payload))
        if args.limit > 0 and len(selected) >= args.limit:
            break

    print(f"[cache] selected {len(selected)} notice(s)")
    for path, payload in selected:
        status = "manual_review" if payload.get("requires_manual_input") else "ready"
        print(f"  - {payload.get('notice_id')} {payload.get('apt_name')} ({status}) {path.relative_to(BASE_DIR)}")

    if args.dry_run:
        print("[cache] dry-run complete")
        return

    results: list[Path] = []
    failed: list[str] = []
    for _, payload in selected:
        doc = _doc_from_payload(payload)
        print(f"\n[generate] {doc.notice_id} {doc.apt_name}")
        try:
            saved = await run_pipeline_from_doc(doc)
            if saved:
                results.append(saved)
                processed_ids.add(doc.notice_id)
                print(f"  - saved: {saved}")
            else:
                failed.append(doc.apt_name or doc.notice_id)
        except Exception as e:
            failed.append(doc.apt_name or doc.notice_id)
            print(f"  - failed: {e}")

    if results:
        _save_processed(processed_ids)
        print(f"[processed] updated: {PROCESSED_FILE.relative_to(BASE_DIR)}")

    if not args.no_build_index:
        build_front_index()

    print(f"[generate] success={len(results)} failed={len(failed)}")
    if failed:
        print("[generate] failed notices: " + ", ".join(failed))


if __name__ == "__main__":
    asyncio.run(main())
