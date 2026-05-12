"""patch_notice_payment.py — manual_finance 스키마로 납부비율 패치.

generate_posts_from_cache._doc_from_payload 가 payload["manual_finance"] 의
contract_ratio / midterm_ratio / balance_ratio 를 읽어 자금계획 본문에
"계약금: {ratio}%" 형식으로 렌더링한다. 본 도구는 그 스키마에 정확히 맞춰
캐시 JSON 을 패치한다.

값은 % 기호 없는 숫자(또는 숫자 문자열)로 저장. (Codex P1 참조)

사용
  python tools/patch_notice_payment.py \
    --notice-id 2026000098 \
    --contract-ratio 5 \
    --midterm-ratio 60 \
    --balance-ratio 35 \
    [--source manual_verified_YYYY-MM-DD]

멱등성: 동일 값이 이미 있으면 변경 없이 종료.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NOTICE_CACHE_DIR = ROOT / "output" / "data_cache" / "notices"


def _now_iso() -> str:
    return datetime.now(timezone(timedelta(hours=9))).isoformat(timespec="seconds")


def _normalize_ratio(value: str) -> str:
    """`5%` 같은 입력이 들어와도 안전하게 % 제거."""
    v = (value or "").strip()
    if v.endswith("%"):
        v = v[:-1].strip()
    return v


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--notice-id", required=True)
    parser.add_argument("--contract-ratio", required=True, help="계약금 비율 숫자 (예: 5)")
    parser.add_argument("--midterm-ratio", required=True, help="중도금 비율 숫자 (예: 60)")
    parser.add_argument("--balance-ratio", required=True, help="잔금 비율 숫자 (예: 35)")
    parser.add_argument("--source", default="manual_verified")
    parser.add_argument("--source-page", default="user-input")
    args = parser.parse_args()

    path = NOTICE_CACHE_DIR / f"{args.notice_id}.json"
    if not path.exists():
        print(f"[payment] cache not found: {path}")
        return 1

    payload = json.loads(path.read_text(encoding="utf-8-sig"))

    new_finance = {
        "contract_ratio": _normalize_ratio(args.contract_ratio),
        "midterm_ratio": _normalize_ratio(args.midterm_ratio),
        "balance_ratio": _normalize_ratio(args.balance_ratio),
        "source_pdf": args.source,
        "source_page": args.source_page,
        "checked_at": _now_iso(),
    }

    existing = payload.get("manual_finance") or {}
    # 핵심 3필드가 동일하면 멱등 처리 (checked_at 갱신만 피함)
    same = all(
        str(existing.get(k, "")).strip() == str(new_finance[k]).strip()
        for k in ("contract_ratio", "midterm_ratio", "balance_ratio")
    )
    if same and existing:
        print(f"[payment] already up-to-date: {args.notice_id}")
        return 0

    # 다른 보조 필드(예: midterm_count, contract_amount 등) 가 있으면 보존
    merged = dict(existing)
    merged.update(new_finance)
    payload["manual_finance"] = merged

    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"[payment] patched: {args.notice_id} "
        f"({new_finance['contract_ratio']}/{new_finance['midterm_ratio']}/{new_finance['balance_ratio']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
