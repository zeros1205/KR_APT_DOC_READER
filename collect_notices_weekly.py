"""
Weekly notice data collection cache builder.

This script is intentionally separate from post generation. It calls the public
data API, stores reusable notice JSON files, validates required fields, and
creates a manual review CSV for unresolved missing fields.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR / "pipeline"))

from dotenv import load_dotenv

load_dotenv(BASE_DIR / ".env")

from agents.collector import CheongYakAPI, _build_document, _from_openapi, _supply_category, _units_to_text


DATA_CACHE_DIR = BASE_DIR / "output" / "data_cache"
NOTICE_CACHE_DIR = DATA_CACHE_DIR / "notices"
MANUAL_REVIEW_DIR = DATA_CACHE_DIR / "manual_review"
INDEX_FILE = DATA_CACHE_DIR / "index.json"
MISSING_FIELDS_CSV = MANUAL_REVIEW_DIR / "missing_fields.csv"

REQUIRED_FIELDS = (
    "notice_id",
    "house_manage_no",
    "apt_name",
    "supply_address",
    "region_name",
    "supply_type",
    "total_units",
    "notice_date",
    "rank1_date",
    "winner_date",
    "notice_url",
    "unit_types",
)


def _now_iso() -> str:
    return datetime.now(timezone(timedelta(hours=9))).isoformat(timespec="seconds")


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, dict, set)):
        return bool(value)
    return True


def _rank1_date(doc_dict: dict[str, Any]) -> str:
    return (
        doc_dict.get("rank1_local_start")
        or doc_dict.get("rank1_near_start")
        or doc_dict.get("rank1_etc_start")
        or ""
    )


def _value_for_required_field(payload: dict[str, Any], field: str) -> Any:
    if field == "rank1_date":
        return _rank1_date(payload["document"])
    if field == "unit_types":
        return payload.get("unit_types", [])
    return payload["document"].get(field)


def _validate_payload(payload: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for field in REQUIRED_FIELDS:
        if not _has_value(_value_for_required_field(payload, field)):
            missing.append(field)
    return missing


def _merge_document_values(base: dict[str, Any], update: dict[str, Any], fields: list[str] | None = None) -> None:
    allowed = set(fields or update.keys())
    for key, value in update.items():
        if key not in allowed:
            continue
        if _has_value(value) and not _has_value(base.get(key)):
            base[key] = value


def _notice_cache_path(notice_id: str) -> Path:
    safe_notice_id = "".join(ch for ch in str(notice_id) if ch.isalnum() or ch in ("-", "_"))
    return NOTICE_CACHE_DIR / f"{safe_notice_id or 'unknown'}.json"


def _existing_notice_ids() -> set[str]:
    notice_ids: set[str] = set()
    if NOTICE_CACHE_DIR.exists():
        for path in NOTICE_CACHE_DIR.glob("*.json"):
            notice_ids.add(path.stem)
    return notice_ids


def _load_existing_payloads() -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    if not NOTICE_CACHE_DIR.exists():
        return payloads

    for path in sorted(NOTICE_CACHE_DIR.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(payload, dict):
            payloads.append(payload)
    return payloads


async def _build_payload(api: CheongYakAPI, item: dict[str, Any]) -> dict[str, Any]:
    normalized = _from_openapi(item)
    doc = _build_document(normalized)
    doc_dict = asdict(doc)

    detail: dict[str, Any] = {}
    if doc.house_manage_no:
        detail = await api.get_detail(doc.house_manage_no)
        if detail:
            detail_doc = _build_document(_from_openapi(detail))
            detail_doc_dict = asdict(detail_doc)
            for key, value in detail_doc_dict.items():
                if _has_value(value) and not _has_value(doc_dict.get(key)):
                    doc_dict[key] = value

    unit_types: list[dict[str, Any]] = []
    if doc_dict.get("house_manage_no"):
        unit_types = await api.get_unit_types(str(doc_dict["house_manage_no"]))

    category = _supply_category(str(doc_dict.get("supply_type") or ""))
    raw_text = str(doc_dict.get("raw_text") or "")
    if unit_types:
        raw_text += f"\n\n[주택형별 정보]\n{_units_to_text(unit_types)}"
    elif category == "무순위/재공급" and doc_dict.get("total_units"):
        raw_text += (
            f"\n\n[공급 정보]\n"
            f"공급유형: {doc_dict.get('supply_type') or ''}\n"
            f"잔여/공급 세대수: {doc_dict.get('total_units')}세대\n"
            f"※ 분양가는 공고문 원문을 직접 확인하세요."
        )
    doc_dict["raw_text"] = raw_text.strip()

    payload = {
        "schema_version": 1,
        "collected_at": _now_iso(),
        "source": "public_data_api",
        "notice_id": doc_dict.get("notice_id", ""),
        "house_manage_no": doc_dict.get("house_manage_no", ""),
        "apt_name": doc_dict.get("apt_name", ""),
        "document": doc_dict,
        "detail_raw": detail,
        "unit_types": unit_types,
        "notice_url_policy": "preserve_link_only_no_pdf_download",
        "retry_attempts": [],
        "missing_fields": [],
        "requires_manual_input": False,
        "manual_status": "none",
    }

    missing = _validate_payload(payload)
    if missing:
        await _retry_missing_fields(api, payload, missing)
        missing = _validate_payload(payload)
    payload["missing_fields"] = missing
    payload["requires_manual_input"] = bool(missing)
    payload["manual_status"] = "pending" if missing else "none"
    return payload


async def _retry_missing_fields(api: CheongYakAPI, payload: dict[str, Any], missing: list[str]) -> None:
    """Retry only the API calls that can fill currently missing fields."""
    doc = payload["document"]
    retried: list[str] = []

    document_fields = [field for field in missing if field not in {"rank1_date", "unit_types"}]
    if "rank1_date" in missing:
        document_fields.extend(("rank1_local_start", "rank1_near_start", "rank1_etc_start"))

    house_manage_no = str(doc.get("house_manage_no") or "")
    if document_fields and house_manage_no:
        detail = await api.get_detail(house_manage_no)
        if detail:
            detail_doc = asdict(_build_document(_from_openapi(detail)))
            _merge_document_values(doc, detail_doc, document_fields)
            payload["detail_raw_retry"] = detail
        retried.append("detail")

    if "unit_types" in missing and house_manage_no:
        unit_types = await api.get_unit_types(house_manage_no)
        if unit_types:
            payload["unit_types"] = unit_types
            raw_text = str(doc.get("raw_text") or "")
            if "[주택형별 정보]" not in raw_text:
                raw_text += f"\n\n[주택형별 정보]\n{_units_to_text(unit_types)}"
                doc["raw_text"] = raw_text.strip()
        retried.append("unit_types")

    payload["retry_attempts"].append(
        {
            "at": _now_iso(),
            "missing_before": missing,
            "calls": retried,
        }
    )


def _save_payload(payload: dict[str, Any]) -> Path:
    NOTICE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _notice_cache_path(str(payload.get("notice_id") or "unknown"))
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _write_index(payloads: list[dict[str, Any]]) -> None:
    DATA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    index = {
        "generated_at": _now_iso(),
        "count": len(payloads),
        "ready_count": sum(1 for payload in payloads if not payload.get("requires_manual_input")),
        "manual_review_count": sum(1 for payload in payloads if payload.get("requires_manual_input")),
        "notices": [
            {
                "notice_id": payload.get("notice_id"),
                "apt_name": payload.get("apt_name"),
                "requires_manual_input": payload.get("requires_manual_input"),
                "missing_fields": payload.get("missing_fields", []),
                "cache_path": str(_notice_cache_path(str(payload.get("notice_id") or "unknown")).relative_to(BASE_DIR)),
            }
            for payload in payloads
        ],
    }
    INDEX_FILE.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_manual_review(payloads: list[dict[str, Any]]) -> None:
    MANUAL_REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, str]] = []
    for payload in payloads:
        for field in payload.get("missing_fields", []):
            rows.append(
                {
                    "notice_id": str(payload.get("notice_id") or ""),
                    "apt_name": str(payload.get("apt_name") or ""),
                    "field": str(field),
                    "manual_value": "",
                    "status": "pending",
                    "note": "API retry failed or returned empty data",
                }
            )

    with MISSING_FIELDS_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=("notice_id", "apt_name", "field", "manual_value", "status", "note"),
        )
        writer.writeheader()
        writer.writerows(rows)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Weekly public-data notice cache builder")
    parser.add_argument("--days", type=int, default=7, help="Collect notices from the last N days")
    parser.add_argument(
        "--start-date",
        type=str,
        default="",
        help="Collect notices from a fixed start date (YYYY-MM-DD). Overrides --days.",
    )
    parser.add_argument("--limit", type=int, default=0, help="Limit number of notices, 0 means no limit")
    parser.add_argument(
        "--notice-id",
        action="append",
        default=[],
        help="Collect a specific PBLANC_NO. Can be passed multiple times.",
    )
    args = parser.parse_args()

    api = CheongYakAPI()
    existing_notice_ids = _existing_notice_ids()
    if args.notice_id:
        raw_list = []
        for notice_id in args.notice_id:
            if str(notice_id) in existing_notice_ids:
                print(f"[collect] 중복 공고번호 건너뜀: {notice_id}")
                continue
            print(f"[collect] 공고번호 직접 조회: {notice_id}")
            item = await api.get_detail_by_notice_id(str(notice_id))
            if item:
                raw_list.append(item)
            else:
                print(f"  - not found: {notice_id}")
    else:
        start_date = args.start_date.strip() or (datetime.now() - timedelta(days=args.days)).strftime("%Y-%m-%d")
        print(f"[collect] 공공데이터 API 조회 시작: {start_date} 이후")
        raw_list = []
        seen_ids: set[str] = set()
        page = 1
        per_page = 50
        target = args.limit if args.limit > 0 else 0
        while True:
            page_items = await api.get_list(page=page, per_page=per_page, start_date=start_date)
            if not page_items:
                break
            for item in page_items:
                normalized = _from_openapi(item)
                notice_id = str(normalized.get("notice_id") or "").strip()
                if not notice_id or notice_id in existing_notice_ids or notice_id in seen_ids:
                    continue
                seen_ids.add(notice_id)
                raw_list.append(item)
                if target and len(raw_list) >= target:
                    break
            if target and len(raw_list) >= target:
                break
            if len(page_items) < per_page:
                break
            page += 1

    new_payloads: list[dict[str, Any]] = []
    for i, item in enumerate(raw_list, 1):
        normalized = _from_openapi(item)
        print(f"[collect] {i}/{len(raw_list)} {normalized.get('apt_name') or normalized.get('notice_id')}")
        payload = await _build_payload(api, item)
        path = _save_payload(payload)
        new_payloads.append(payload)
        status = "manual_review" if payload["requires_manual_input"] else "ready"
        print(f"  - saved: {path.relative_to(BASE_DIR)} ({status})")

    all_payloads = _load_existing_payloads()
    _write_index(all_payloads)
    _write_manual_review(all_payloads)
    print(f"[collect] index: {INDEX_FILE.relative_to(BASE_DIR)}")
    print(f"[collect] manual review: {MISSING_FIELDS_CSV.relative_to(BASE_DIR)}")
    print(f"[collect] 신규 수집 완료: {len(new_payloads)}건")
    print(f"[collect] 전체 캐시 기준: {len(all_payloads)}건")


if __name__ == "__main__":
    asyncio.run(main())
