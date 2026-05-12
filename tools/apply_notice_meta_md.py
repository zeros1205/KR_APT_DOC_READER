"""apply_notice_meta_md.py — MD 입력 시트의 8필드 메타를 캐시 JSON 에 일괄 주입.

가장 최신 `output/notice_url_exports/*_notice_urls.md` 또는 --md 로 지정한 파일을
파싱해 notice_id 별로 다음 patch 를 수행한다.

  - 규제 5필드 → patch_notice_regulation.py (서브프로세스 호출)
  - 납부 3필드 → patch_notice_payment.py     (서브프로세스 호출)

8필드가 모두 채워지지 않은 notice_id 는 skip + 보고.
이미 동일 값이 캐시에 있으면 patch 도구가 멱등 처리.

사용
  python tools/apply_notice_meta_md.py [--md PATH] [--dry-run] [--strict]

--strict: 미완료 행이 하나라도 있으면 exit 1 (codex-generate-pages.yml 게이트용)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXPORT_DIR = ROOT / "output" / "notice_url_exports"
NOTICE_CACHE_DIR = ROOT / "output" / "data_cache" / "notices"

sys.path.insert(0, str(ROOT / "tools"))
from parse_notice_meta_md import REQUIRED_KEYS, parse_md, validate  # noqa: E402


def _latest_md() -> Path | None:
    if not EXPORT_DIR.exists():
        return None
    files = sorted(EXPORT_DIR.glob("*_notice_urls.md"))
    return files[-1] if files else None


def _patch_regulation(notice_id: str, meta: dict[str, str], dry_run: bool) -> int:
    cmd = [
        sys.executable, str(ROOT / "patch_notice_regulation.py"),
        "--notice-id", notice_id,
        "--regulated-zone", meta["regulated_zone"],
        "--readmission-limit", meta["readmission_limit"],
        "--resale-restriction", meta["resale_restriction"],
        "--live-requirement", meta["live_requirement"],
        "--price-cap", meta["price_cap"],
        "--source", "md_input_sheet",
        "--query", "auto-applied from notice_urls.md",
    ]
    if dry_run:
        print("    [dry-run]", " ".join(cmd))
        return 0
    return subprocess.run(cmd, cwd=ROOT).returncode


def _patch_payment(notice_id: str, meta: dict[str, str], dry_run: bool) -> int:
    cmd = [
        sys.executable, str(ROOT / "tools" / "patch_notice_payment.py"),
        "--notice-id", notice_id,
        "--contract-ratio", meta["contract_ratio"],
        "--midterm-ratio", meta["midterm_ratio"],
        "--balance-ratio", meta["balance_ratio"],
        "--source", "md_input_sheet",
    ]
    if dry_run:
        print("    [dry-run]", " ".join(cmd))
        return 0
    return subprocess.run(cmd, cwd=ROOT).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--md", default="", help="입력 시트 MD 경로 (생략 시 가장 최신)")
    parser.add_argument("--dry-run", action="store_true", help="patch 명령만 출력")
    parser.add_argument("--strict", action="store_true",
                        help="미완료 행이 하나라도 있으면 exit 1")
    args = parser.parse_args()

    md_path = Path(args.md) if args.md else _latest_md()
    if not md_path or not md_path.exists():
        print("❌ 입력 시트 MD 를 찾을 수 없습니다. export_notice_urls.py 를 먼저 실행하세요.")
        return 1
    print(f"[apply] MD: {md_path}")

    parsed = parse_md(md_path)
    if not parsed:
        print("[apply] 입력된 행이 없습니다.")
        return 0

    missing = validate(parsed)
    if missing:
        print(f"⚠️  미완료 행 {len(missing)}건 — patch 에서 제외:")
        for nid, keys in list(missing.items())[:20]:
            print(f"  - {nid}: {', '.join(keys)} 누락")
        if len(missing) > 20:
            print(f"  ... 외 {len(missing) - 20}건")

    applied = 0
    failed: list[str] = []
    for notice_id, meta in parsed.items():
        if notice_id in missing:
            continue
        cache_path = NOTICE_CACHE_DIR / f"{notice_id}.json"
        if not cache_path.exists():
            print(f"  · {notice_id}: 캐시 없음, skip")
            continue
        rc_reg = _patch_regulation(notice_id, meta, args.dry_run)
        rc_pay = _patch_payment(notice_id, meta, args.dry_run)
        if rc_reg != 0 or rc_pay != 0:
            failed.append(notice_id)
            continue
        applied += 1

    print()
    print(f"[apply] 완료 {applied}건 / 미완료 {len(missing)}건 / 실패 {len(failed)}건")
    if failed:
        print(f"  실패 notice_id: {', '.join(failed[:10])}")

    if args.strict and (missing or failed):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
