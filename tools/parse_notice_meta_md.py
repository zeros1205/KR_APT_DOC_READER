"""parse_notice_meta_md.py — 입력 시트 MD 를 파싱해 메타 dict 반환.

`output/notice_url_exports/YYYY-MM-DD_notice_urls.md` 표를 읽어 notice_id 별
8필드(규제 5 + 납부 3) 값을 추출한다. 모든 필드 누락이면 dict 에 포함하지 않고,
일부라도 채워진 행은 누락 키를 빈 문자열로 반환해 호출자가 검증할 수 있게 한다.

사용 예 (CLI):
  python tools/parse_notice_meta_md.py output/notice_url_exports/...md
    → 표준출력에 JSON 한 줄(공고별 메타 dict)

  python tools/parse_notice_meta_md.py --pending-only output/.../...md
    → 미입력 행만 출력 (검증·중단용)

라이브러리로 사용 시 `parse_md(path)` 호출.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REQUIRED_KEYS = (
    "regulated_zone",
    "readmission_limit",
    "resale_restriction",
    "live_requirement",
    "price_cap",
    "contract_ratio",
    "midterm_ratio",
    "balance_ratio",
)

# 표 헤더 순서(export_notice_urls._write_md 와 동기):
# 공고번호 | 단지명 | 모집공고일 | 당첨자 발표일 | 청약홈 링크 | 권장 PDF | 규제지역 | 재당첨 | 전매 | 거주의무 | 분양가상한제 | 계약금 | 중도금 | 잔금 | 상태
COL_INDEX = {
    "notice_id": 0,
    "apt_name": 1,
    "regulated_zone": 6,
    "readmission_limit": 7,
    "resale_restriction": 8,
    "live_requirement": 9,
    "price_cap": 10,
    "contract_ratio": 11,
    "midterm_ratio": 12,
    "balance_ratio": 13,
    "status": 14,
}

EXPECTED_COL_COUNT = 15
BLANK_TOKENS = {"_", "-", ""}


def _strip_pct(value: str) -> str:
    """`5%` → `5`. 비율 필드를 manual_finance 의 contract_ratio 등에 맞추기 위해."""
    v = value.strip()
    if v.endswith("%"):
        v = v[:-1].strip()
    return v


def parse_md(path: Path) -> dict[str, dict[str, str]]:
    """notice_id → {field: value} dict 반환. 한 행이라도 일부 입력이 있으면 포함."""
    out: dict[str, dict[str, str]] = {}
    if not path.exists():
        return out
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line.startswith("|"):
            continue
        cols = [c.strip() for c in line.strip("|").split("|")]
        if len(cols) < EXPECTED_COL_COUNT:
            continue
        notice_id = cols[COL_INDEX["notice_id"]]
        if not notice_id or notice_id == "공고번호" or notice_id.startswith("---"):
            continue
        # 모든 메타 셀이 비어있으면 행 자체를 스킵 (그래도 데이터는 의미 없음).
        meta = {
            key: cols[COL_INDEX[key]].strip()
            for key in REQUIRED_KEYS
        }
        if all(v in BLANK_TOKENS for v in meta.values()):
            continue
        # 비율 필드는 % 제거하고 숫자(또는 빈문자) 만 저장
        for k in ("contract_ratio", "midterm_ratio", "balance_ratio"):
            meta[k] = _strip_pct(meta[k])
        # 빈 토큰을 빈 문자열로 정규화
        for k, v in list(meta.items()):
            if v in BLANK_TOKENS:
                meta[k] = ""
        meta["apt_name"] = cols[COL_INDEX["apt_name"]]
        meta["status"] = cols[COL_INDEX["status"]]
        out[notice_id] = meta
    return out


def validate(parsed: dict[str, dict[str, str]]) -> dict[str, list[str]]:
    """notice_id 별 누락 키 리스트 반환. 빈 리스트면 완전 입력."""
    missing: dict[str, list[str]] = {}
    for notice_id, meta in parsed.items():
        empty_keys = [k for k in REQUIRED_KEYS if not meta.get(k)]
        if empty_keys:
            missing[notice_id] = empty_keys
    return missing


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("md_path", help="입력 시트 MD 파일 경로")
    parser.add_argument("--pending-only", action="store_true",
                        help="누락 필드가 있는 행만 출력 (검증·중단용)")
    parser.add_argument("--strict", action="store_true",
                        help="누락이 하나라도 있으면 exit 1")
    args = parser.parse_args()

    path = Path(args.md_path)
    parsed = parse_md(path)
    if args.pending_only:
        pending = validate(parsed)
        print(json.dumps(pending, ensure_ascii=False, indent=2))
        return 1 if (pending and args.strict) else 0
    print(json.dumps(parsed, ensure_ascii=False, indent=2))
    if args.strict:
        return 1 if validate(parsed) else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
