"""parse_notice_meta_yml.py — YAML 입력 파일을 파싱해 메타 dict 반환.

`output/notice_meta_inputs/<notice_id>.yml` 파일을 모두 읽어 notice_id 별
{field: value} dict 를 반환. MD 파서와 동일한 시맨틱.

YAML 키 (모두 1depth):
  notice_id
  regulated_zone, readmission_limit, resale_restriction,
  live_requirement, price_cap
  contract_ratio, midterm_ratio, balance_ratio

CLI 사용
  python tools/parse_notice_meta_yml.py [--pending-only] [--strict]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
META_INPUTS_DIR = ROOT / "output" / "notice_meta_inputs"

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

try:
    import yaml  # PyYAML
except ImportError:
    yaml = None  # type: ignore[assignment]


def _stringify(v: object) -> str:
    if v is None:
        return ""
    return str(v).strip()


def parse_dir(directory: Path = META_INPUTS_DIR) -> dict[str, dict[str, str]]:
    """폴더의 모든 *.yml 파일을 읽어 notice_id → 메타 dict 반환."""
    out: dict[str, dict[str, str]] = {}
    if not directory.exists():
        return out
    if yaml is None:
        raise RuntimeError("PyYAML 미설치 — `pip install pyyaml` 필요")

    for path in sorted(directory.glob("*.yml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            print(f"⚠️  YAML 파싱 실패 {path.name}: {exc}", file=sys.stderr)
            continue
        if not isinstance(data, dict):
            continue
        notice_id = _stringify(data.get("notice_id")) or path.stem
        meta = {key: _stringify(data.get(key)) for key in REQUIRED_KEYS}
        if all(not v for v in meta.values()):
            continue
        # 비율 필드는 % 가 끼어 있어도 제거
        for k in ("contract_ratio", "midterm_ratio", "balance_ratio"):
            if meta[k].endswith("%"):
                meta[k] = meta[k][:-1].strip()
        meta["_source"] = "yml"
        meta["_path"] = str(path.relative_to(ROOT))
        out[notice_id] = meta
    return out


def validate(parsed: dict[str, dict[str, str]]) -> dict[str, list[str]]:
    """notice_id 별 누락 키 리스트 반환."""
    missing: dict[str, list[str]] = {}
    for notice_id, meta in parsed.items():
        empty_keys = [k for k in REQUIRED_KEYS if not meta.get(k)]
        if empty_keys:
            missing[notice_id] = empty_keys
    return missing


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pending-only", action="store_true",
                        help="누락 필드가 있는 행만 출력")
    parser.add_argument("--strict", action="store_true",
                        help="누락 있으면 exit 1")
    args = parser.parse_args()

    parsed = parse_dir()
    if args.pending_only:
        pending = validate(parsed)
        print(json.dumps(pending, ensure_ascii=False, indent=2))
        return 1 if (pending and args.strict) else 0

    print(json.dumps(parsed, ensure_ascii=False, indent=2))
    if args.strict and validate(parsed):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
