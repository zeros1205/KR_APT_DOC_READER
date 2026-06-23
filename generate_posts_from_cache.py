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
from agents.pdf_finance import extract_finance_from_pdf, find_local_pdf_in_dirs
from agents.pdf_policy import extract_policy_from_pdf, pdf_is_text_extractable
from check_ui_freeze import check_ui_freeze
from orchestrator import run_pipeline_from_doc
from pipeline.index_renderer import build_front_index
from public_notices import is_public_notice_data, is_public_notice_doc


NOTICE_CACHE_DIR = BASE_DIR / "output" / "data_cache" / "notices"
PDF_DIRS = (BASE_DIR / "input" / "pdfs", BASE_DIR.parent / "PDF", BASE_DIR / "output" / "pdfs")
PROCESSED_FILE = BASE_DIR / "output" / "processed_notices.json"
DELETED_NOTICES_FILE = BASE_DIR / "output" / "data_cache" / "deleted_notices.json"
PDF_POLICY_MUST_CONFIRM_KEYS = (
    "resale_restriction",
)


class ImagePdfSkip(Exception):
    """텍스트 레이어가 없는 스캔(이미지) PDF — hard-fail 대신 수기입력 필요로 graceful skip한다."""

    def __init__(self, notice_id: str, apt_name: str, pdf_name: str) -> None:
        self.notice_id = notice_id
        self.apt_name = apt_name
        self.pdf_name = pdf_name
        super().__init__(
            f"{notice_id} {apt_name} ({pdf_name}) — 텍스트 레이어 없는 이미지 PDF(규제·납부 표 추출 불가)"
        )


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


def _doc_from_payload(payload: dict[str, Any], *, require_pdf_policy: bool = False) -> NoticeDocument:
    data = dict(payload.get("document") or {})
    manual_regulation = payload.get("manual_regulation") or {}
    manual_finance = dict(payload.get("manual_finance") or {})
    notice_id = str(payload.get("notice_id") or data.get("notice_id") or "")
    local_pdf = find_local_pdf_in_dirs(PDF_DIRS, notice_id)
    if local_pdf:
        extracted_policy = extract_policy_from_pdf(local_pdf)
        pdf_regulation = {
            key: extracted_policy[key]
            for key in (
                "regulated_zone",
                "is_hot_zone",
                "readmission_limit",
                "resale_restriction",
                "live_requirement",
                "price_cap",
                "is_price_cap",
            )
            if extracted_policy.get(key)
        }
        if extracted_policy.get("price_cap"):
            pdf_regulation["is_price_cap"] = "Y" if extracted_policy["price_cap"] == "적용" else "N"
        missing_must_confirm_keys = [
            key
            for key in PDF_POLICY_MUST_CONFIRM_KEYS
            if not (manual_regulation.get(key) or pdf_regulation.get(key))
        ]
        has_policy_override = any(
            manual_regulation.get(key) or pdf_regulation.get(key)
            for key in (
                "regulated_zone",
                "readmission_limit",
                "resale_restriction",
                "live_requirement",
                "price_cap",
            )
        )
        if require_pdf_policy and not is_public_notice_data(data) and (missing_must_confirm_keys or not has_policy_override):
            apt_name = payload.get("apt_name") or data.get("apt_name") or ""
            # 스캔 이미지 PDF는 텍스트·표 자체가 없어 추출이 원천 불가 → hard-fail 대신 graceful skip.
            if not pdf_is_text_extractable(local_pdf):
                raise ImagePdfSkip(notice_id, apt_name, local_pdf.name)
            raise ValueError(
                "PDF 정책 추출 실패: "
                f"{notice_id} {apt_name} "
                f"({local_pdf.name}). 공고문 전매제한/재당첨제한/거주의무/분양가상한제 항목을 "
                "읽지 못했으므로 manual_regulation을 입력하거나 PDF 추출 로직을 보강하세요."
            )
        if pdf_regulation:
            manual_regulation = {**manual_regulation, **pdf_regulation}
        extracted_finance = extract_finance_from_pdf(local_pdf)
        if extracted_finance.has_core_ratios:
            manual_finance.update(
                {
                    "contract_ratio": extracted_finance.contract_ratio,
                    "midterm_ratio": extracted_finance.midterm_ratio,
                    "balance_ratio": extracted_finance.balance_ratio,
                    "midterm_count": extracted_finance.midterm_count,
                    "midterm_fixed_amount": extracted_finance.midterm_fixed_amount,
                    "source_pdf": extracted_finance.source_pdf,
                    "source_page": extracted_finance.source_page,
                }
            )
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
    normalized["pdf_policy_text"] = ""
    doc = NoticeDocument(**normalized)
    if manual_regulation:
        policy_lines = [
            f"[PDF 정책] regulated_zone: {manual_regulation.get('regulated_zone', '')}",
            f"[PDF 정책] is_hot_zone: {manual_regulation.get('is_hot_zone', '')}",
            f"[PDF 정책] readmission_limit: {manual_regulation.get('readmission_limit', '')}",
            f"[PDF 정책] resale_restriction: {manual_regulation.get('resale_restriction', '')}",
            f"[PDF 정책] live_requirement: {manual_regulation.get('live_requirement', '')}",
            f"[PDF 정책] price_cap: {manual_regulation.get('price_cap', '')}",
            f"[PDF 정책] is_price_cap: {manual_regulation.get('is_price_cap', '')}",
        ]
        doc.raw_text = f"{doc.raw_text}\n\n" + "\n".join(policy_lines)
        doc.pdf_policy_text = "\n".join(policy_lines)
    if manual_finance:
        finance_lines = [
            "[자금계획]",
        ]
        if manual_finance.get("contract_amount"):
            finance_lines.append(f"계약금 금액: {manual_finance.get('contract_amount')}")
        else:
            finance_lines.append(f"계약금: {manual_finance.get('contract_ratio', '')}%")
        if manual_finance.get("midterm_fixed_amount"):
            finance_lines.append(f"중도금 정액: {manual_finance.get('midterm_fixed_amount')}")
        else:
            finance_lines.append(f"중도금: {manual_finance.get('midterm_ratio', '')}%")
        if manual_finance.get("balance_label"):
            finance_lines.append(f"잔금: {manual_finance.get('balance_label')}")
        else:
            finance_lines.append(f"잔금: {manual_finance.get('balance_ratio', '')}%")
        if manual_finance.get("midterm_count"):
            finance_lines.append(f"중도금 납부 횟수: {manual_finance.get('midterm_count')}회")
        if manual_finance.get("loan_info"):
            finance_lines.append(f"중도금 대출: {manual_finance.get('loan_info')}")
        if manual_finance.get("source_pdf"):
            finance_lines.append(f"자금계획 출처 PDF: {manual_finance.get('source_pdf')}")
        if manual_finance.get("source_page"):
            finance_lines.append(f"자금계획 출처 페이지: {manual_finance.get('source_page')}")
        doc.raw_text = f"{doc.raw_text}\n\n" + "\n".join(finance_lines)
    return doc


def _has_local_pdf(payload: dict[str, Any]) -> bool:
    data = payload.get("document") or {}
    notice_id = str(payload.get("notice_id") or data.get("notice_id") or "")
    return bool(find_local_pdf_in_dirs(PDF_DIRS, notice_id))


def _iter_payloads(*, include_manual: bool) -> list[tuple[Path, dict[str, Any]]]:
    if not NOTICE_CACHE_DIR.exists():
        return []
    deleted_notice_ids = _load_deleted_notice_ids()
    payloads: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(NOTICE_CACHE_DIR.glob("*.json")):
        payload = _load_json(path)
        notice_id = str(payload.get("notice_id") or (payload.get("document") or {}).get("notice_id") or path.stem)
        if notice_id in deleted_notice_ids:
            continue
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
    parser.add_argument("--no-build-index", action="store_true", help="Skip front post index/sitemap/robots regeneration")
    parser.add_argument(
        "--build-index-shell",
        action="store_true",
        help="Also regenerate output/index.html. Default only updates posts_index.json/sitemap/robots.",
    )
    parser.add_argument("--require-pdf", action="store_true", help="Only generate notices that have a matching local PDF")
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
        if args.require_pdf and not _has_local_pdf(payload):
            print(f"[cache] PDF 없음 -> 건너뜀: {notice_id} {payload.get('apt_name')}")
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
    skipped: list[str] = []
    for _, payload in selected:
        # 실패/스킵 보고는 payload 식별자로 고정한다. _doc_from_payload가 예외를 던지면
        # doc이 직전 반복 값을 가리켜 엉뚱한 단지로 오보고되던 버그를 방지한다.
        data = payload.get("document") or {}
        p_notice_id = str(payload.get("notice_id") or data.get("notice_id") or "")
        p_apt_name = payload.get("apt_name") or data.get("apt_name") or p_notice_id
        try:
            doc = _doc_from_payload(payload, require_pdf_policy=args.require_pdf)
            print(f"\n[generate] {doc.notice_id} {doc.apt_name}")
            if is_public_notice_doc(doc):
                processed_ids.add(doc.notice_id)
                print("  - public notice: post generation skipped; front card will link to ApplyHome")
                continue
            saved = await run_pipeline_from_doc(doc)
            if saved:
                results.append(saved)
                processed_ids.add(doc.notice_id)
                print(f"  - saved: {saved}")
            else:
                failed.append(p_apt_name)
        except ImagePdfSkip as skip:
            skipped.append(p_apt_name)
            print(f"  - skip(이미지 PDF·수기입력 필요): {skip}")
        except Exception as e:
            failed.append(p_apt_name)
            print(f"  - failed: {e}")

    if results or selected:
        _save_processed(processed_ids)
        print(f"[processed] updated: {PROCESSED_FILE.relative_to(BASE_DIR)}")

    if not args.no_build_index:
        build_front_index(render_shell=args.build_index_shell)

    print(f"[generate] success={len(results)} failed={len(failed)} skipped={len(skipped)}")
    if failed:
        print("[generate] failed notices: " + ", ".join(failed))
    if skipped:
        # 접두사를 "[generate] "로 시작하지 않게 해 알림 파서가 생성 단지로 오인하지 않도록 한다.
        print("[skip] image-pdf notices (수기입력 필요): " + ", ".join(skipped))


if __name__ == "__main__":
    asyncio.run(main())
