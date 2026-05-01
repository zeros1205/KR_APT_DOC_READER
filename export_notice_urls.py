"""
Export CheongYakHome detail URLs from cached public-data notices.

This script does not call the public data API. It reads
`output/data_cache/notices/*.json` and writes a date-stamped Markdown file for
manual PDF download.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).parent
NOTICE_CACHE_DIR = BASE_DIR / "output" / "data_cache" / "notices"
PROCESSED_FILE = BASE_DIR / "output" / "processed_notices.json"
EXPORT_DIR = BASE_DIR / "output" / "notice_url_exports"
PDF_DIRS = (BASE_DIR / "input" / "pdfs", BASE_DIR / "output" / "pdfs")
DELETED_NOTICES_FILE = BASE_DIR / "output" / "data_cache" / "deleted_notices.json"


def _kst_today() -> str:
    return datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _load_processed() -> set[str]:
    if not PROCESSED_FILE.exists():
        return set()
    try:
        data = json.loads(PROCESSED_FILE.read_text(encoding="utf-8-sig"))
    except Exception:
        return set()
    return {str(item) for item in data}


def _load_deleted_notice_ids() -> set[str]:
    if not DELETED_NOTICES_FILE.exists():
        return set()
    try:
        data = json.loads(DELETED_NOTICES_FILE.read_text(encoding="utf-8-sig"))
    except Exception:
        return set()
    if isinstance(data, list):
        return {str(item.get("notice_id") if isinstance(item, dict) else item) for item in data if item}
    if isinstance(data, dict):
        return {str(item) for item in data.get("notice_ids", [])}
    return set()


def _safe_cell(value: object) -> str:
    return str(value or "").strip().replace("|", "\\|")


def _notice_url(payload: dict[str, Any]) -> str:
    doc = payload.get("document") or {}
    raw = payload.get("detail_raw") or {}
    return str(doc.get("notice_url") or raw.get("PBLANC_URL") or "").strip()


def _expected_pdf_name(notice_id: str, apt_name: str) -> str:
    safe_name = re.sub(r'[<>:"/\\\\|?*]+', "_", apt_name).strip()
    return f"{notice_id} {safe_name} 입주자모집공고문.pdf"


def _has_pdf(notice_id: str) -> bool:
    if not notice_id:
        return False
    for directory in PDF_DIRS:
        if not directory.exists():
            continue
        for path in directory.glob(f"{notice_id}*.pdf"):
            if path.is_file():
                return True
    return False


def _iter_rows(*, include_processed: bool, include_with_pdf: bool) -> list[dict[str, str]]:
    processed = _load_processed()
    deleted_notice_ids = _load_deleted_notice_ids()
    rows: list[dict[str, str]] = []
    if not NOTICE_CACHE_DIR.exists():
        return rows

    for path in sorted(NOTICE_CACHE_DIR.glob("*.json")):
        payload = _load_json(path)
        doc = payload.get("document") or {}
        notice_id = str(payload.get("notice_id") or doc.get("notice_id") or path.stem).strip()
        apt_name = str(payload.get("apt_name") or doc.get("apt_name") or "").strip()
        notice_url = _notice_url(payload)
        has_pdf = _has_pdf(notice_id)

        if notice_id in deleted_notice_ids:
            continue
        if not include_processed and notice_id in processed:
            continue
        if not include_with_pdf and has_pdf:
            continue
        if not notice_id or not apt_name or not notice_url:
            continue

        rows.append(
            {
                "notice_id": notice_id,
                "apt_name": apt_name,
                "notice_date": str(doc.get("notice_date") or ""),
                "winner_date": str(doc.get("winner_date") or ""),
                "notice_url": notice_url,
                "expected_pdf": _expected_pdf_name(notice_id, apt_name),
            }
        )
    return rows


def _write_md(rows: list[dict[str, str]], filename_date: str) -> Path:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    md_path = EXPORT_DIR / f"{filename_date}_notice_urls.md"

    lines = [
        "# 청약홈 상세페이지 URL 목록",
        "",
        f"- 생성일: {filename_date}",
        f"- 대상 공고: {len(rows)}건",
        f"- PDF 업로드 폴더: `input/pdfs/`",
        "",
        "| 공고번호 | 단지명 | 모집공고일 | 당첨자 발표일 | 청약홈 링크 | 권장 PDF 파일명 |",
        "|---|---|---:|---:|---|---|",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _safe_cell(row["notice_id"]),
                    _safe_cell(row["apt_name"]),
                    _safe_cell(row["notice_date"]),
                    _safe_cell(row["winner_date"]),
                    _safe_cell(row["notice_url"]),
                    f"`{_safe_cell(row['expected_pdf'])}`",
                ]
            )
            + " |"
        )

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Export cached CheongYakHome notice URLs to Markdown")
    parser.add_argument("--include-processed", action="store_true", help="Include notices already listed in processed_notices.json")
    parser.add_argument("--include-with-pdf", action="store_true", help="Include notices that already have matching PDFs")
    parser.add_argument("--date", default=_kst_today(), help="Output filename date, YYYY-MM-DD")
    args = parser.parse_args()

    rows = _iter_rows(include_processed=args.include_processed, include_with_pdf=args.include_with_pdf)
    md_path = _write_md(rows, args.date)
    print(f"[export] {len(rows)} rows")
    print(f"[export] {md_path}")


if __name__ == "__main__":
    main()
