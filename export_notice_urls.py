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
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR / "pipeline"))

from public_notices import is_public_notice_data

NOTICE_CACHE_DIR = BASE_DIR / "output" / "data_cache" / "notices"
PROCESSED_FILE = BASE_DIR / "output" / "processed_notices.json"
EXPORT_DIR = BASE_DIR / "output" / "notice_url_exports"
META_INPUTS_DIR = BASE_DIR / "output" / "notice_meta_inputs"
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
        if is_public_notice_data(doc):
            continue
        if not notice_id or not apt_name or not notice_url:
            continue

        # 사용자가 직접 검증한 manual_regulation 이 있으면 그 값을 우선,
        # 없으면 API 가 채워둔 doc 값을 prefill 후보로 표시한다.
        manual_reg = payload.get("manual_regulation") or {}
        manual_fin = payload.get("manual_finance") or {}

        def _reg(key: str) -> str:
            return str(manual_reg.get(key) or doc.get(key) or "").strip()

        def _pct(key: str) -> str:
            v = manual_fin.get(key)
            if v is None or v == "":
                return ""
            s = str(v).strip()
            # 사용자가 숫자만 입력했을 때 자동 %, 이미 % 가 있으면 그대로
            return s if s.endswith("%") else f"{s}%"

        regulated_zone = _reg("regulated_zone")
        readmission = _reg("readmission_limit")
        resale = _reg("resale_restriction")
        live_req = _reg("live_requirement")
        price_cap = _reg("price_cap")
        contract = _pct("contract_ratio")
        midterm = _pct("midterm_ratio")
        balance = _pct("balance_ratio")

        # 8 필드가 모두 비어있지 않으면 입력 완료로 판단.
        filled = all([regulated_zone, readmission, resale, live_req, price_cap,
                      contract, midterm, balance])

        rows.append(
            {
                "notice_id": notice_id,
                "apt_name": apt_name,
                "notice_date": str(doc.get("notice_date") or ""),
                "winner_date": str(doc.get("winner_date") or ""),
                "notice_url": notice_url,
                "expected_pdf": _expected_pdf_name(notice_id, apt_name),
                "regulated_zone": regulated_zone,
                "readmission": readmission,
                "resale": resale,
                "live_req": live_req,
                "price_cap": price_cap,
                "contract": contract,
                "midterm": midterm,
                "balance": balance,
                "filled": filled,
            }
        )
    return rows


def _yaml_quote(value: str) -> str:
    """간단한 YAML 스칼라 quoting. 한글·공백 안전."""
    v = (value or "").strip()
    if not v:
        return '""'
    # 콜론·해시·따옴표 등 문제 문자 포함 시 quote
    if any(c in v for c in [':', '#', "'", '"', '\n']) or v.startswith(('-', '?', '!', '&', '*', '[', '{')):
        escaped = v.replace('"', '\\"')
        return f'"{escaped}"'
    return v


def _write_meta_yaml(row: dict[str, str]) -> Path:
    """공고당 한 개의 YAML 파일 작성. 사용자 편집을 모바일에서도 쉽게 하기 위한 채널.

    이미 파일이 있으면 사용자 편집을 보존하기 위해 덮어쓰지 않는다 (멱등).
    """
    META_INPUTS_DIR.mkdir(parents=True, exist_ok=True)
    yml_path = META_INPUTS_DIR / f"{row['notice_id']}.yml"
    if yml_path.exists():
        return yml_path

    # 납부비율은 숫자(% 제거)로 — patch_notice_payment 가 그대로 사용 가능
    def _num(value: str) -> str:
        v = (value or "").strip().rstrip("%").strip()
        return v if v else '""'

    body = (
        f"# {row['apt_name']}\n"
        f"# 청약홈: {row['notice_url']}\n"
        f"\n"
        f"notice_id: \"{row['notice_id']}\"\n"
        f"\n"
        f"regulated_zone: {_yaml_quote(row.get('regulated_zone', ''))}\n"
        f"readmission_limit: {_yaml_quote(row.get('readmission', ''))}\n"
        f"resale_restriction: {_yaml_quote(row.get('resale', ''))}\n"
        f"live_requirement: {_yaml_quote(row.get('live_req', ''))}\n"
        f"price_cap: {_yaml_quote(row.get('price_cap', ''))}\n"
        f"\n"
        f"contract_ratio: {_num(row.get('contract', ''))}\n"
        f"midterm_ratio: {_num(row.get('midterm', ''))}\n"
        f"balance_ratio: {_num(row.get('balance', ''))}\n"
    )
    yml_path.write_text(body, encoding="utf-8")
    return yml_path


def _write_md(rows: list[dict[str, str]], filename_date: str) -> Path:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    md_path = EXPORT_DIR / f"{filename_date}_notice_urls.md"

    filled_n = sum(1 for r in rows if r.get("filled"))
    pending_n = len(rows) - filled_n

    lines = [
        "# 청약홈 상세페이지 URL · 수동 입력 시트",
        "",
        f"- 생성일: {filename_date}",
        f"- 대상 공고: {len(rows)}건  (입력 완료 {filled_n}건 / 대기 {pending_n}건)",
        f"- PDF 업로드 폴더: `input/pdfs/`",
        "",
        "## 입력 안내",
        "",
        "1. 청약홈 상세 페이지에서 PDF 모집공고문을 받아 `input/pdfs/` 에 업로드.",
        "2. 아래 표의 8개 메타 필드를 채우고 커밋. 자동 추출된 값이 prefilled 되어 있으니 검토만 하면 됩니다.",
        "3. 8필드가 모두 채워진 행은 다음 빌드에서 `상태` 컬럼이 `✅` 로 갱신됩니다.",
        "4. `codex-페이지 생성` 워크플로우 실행 시 모든 행이 `✅` 인지 검증 후 진행합니다.",
        "",
        "### 필드 형식",
        "",
        "- **규제지역**: `투기과열지구` / `청약과열지역` / `조정대상지역` / `비규제지역`",
        "- **재당첨 / 전매 / 거주의무**: 예 `10년`, `없음`",
        "- **분양가상한제**: `적용` / `미적용`",
        "- **계약금 / 중도금 / 잔금**: 비율(예 `10%` `60%` `30%`). 숫자만 입력해도 자동으로 % 가 붙음. 세 값 합계 100% 권장",
        "",
        "| 공고번호 | 단지명 | 모집공고일 | 당첨자 발표일 | 청약홈 링크 | 권장 PDF 파일명 | 규제지역 | 재당첨 | 전매 | 거주의무 | 분양가상한제 | 계약금 | 중도금 | 잔금 | 상태 |",
        "|---|---|---:|---:|---|---|---|---|---|---|---|---:|---:|---:|:-:|",
    ]
    for row in rows:
        status = "✅" if row.get("filled") else "☐"
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
                    _safe_cell(row["regulated_zone"]) or "_",
                    _safe_cell(row["readmission"]) or "_",
                    _safe_cell(row["resale"]) or "_",
                    _safe_cell(row["live_req"]) or "_",
                    _safe_cell(row["price_cap"]) or "_",
                    _safe_cell(row["contract"]) or "_",
                    _safe_cell(row["midterm"]) or "_",
                    _safe_cell(row["balance"]) or "_",
                    status,
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

    # 공고당 YAML 입력 파일 생성 (이미 있으면 사용자 편집 보존, 신규만 생성)
    new_yml = 0
    for row in rows:
        yml_path = _write_meta_yaml(row)
        if yml_path.stat().st_mtime > (yml_path.stat().st_ctime - 1):  # 방금 생성 추정 보정
            pass
    # 더 정확히는 created 추적이 복잡하므로 단순히 폴더 카운트 출력
    yml_total = sum(1 for _ in META_INPUTS_DIR.glob("*.yml")) if META_INPUTS_DIR.exists() else 0
    print(f"[export] notice_meta_inputs YAML 총 {yml_total}개 (신규는 자동 생성, 기존은 보존)")


if __name__ == "__main__":
    main()
