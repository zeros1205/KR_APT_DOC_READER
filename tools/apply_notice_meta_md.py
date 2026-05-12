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

try:
    import parse_notice_meta_yml as _yml_mod  # noqa: E402
    parse_yml_dir = _yml_mod.parse_dir
except ImportError:
    _yml_mod = None  # type: ignore[assignment]
    parse_yml_dir = None  # type: ignore[assignment]


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

    # YAML 입력 파일이 있으면 같은 notice_id 에 한해 MD 값을 덮어쓴다.
    # 모바일에서 YAML 한 파일만 수정한 경우 그 값이 정본으로 적용되도록.
    yml_parse_errors: list[tuple[str, str]] = []
    if parse_yml_dir is not None:
        try:
            yml_parsed = parse_yml_dir()
        except RuntimeError as exc:
            print(f"⚠️  YAML 파서 비활성: {exc}")
            yml_parsed = {}
        if _yml_mod is not None:
            yml_parse_errors = list(_yml_mod.parse_errors)
        if yml_parsed:
            print(f"[apply] YAML 입력 {len(yml_parsed)}건 발견 — MD 값보다 우선 적용")
            for nid, meta in yml_parsed.items():
                # _source/_path 등 부가 키 제거하고 REQUIRED 만 머지.
                # YAML 에 비어있는 값(잘못된 prefill 을 사용자가 의도적으로
                # 지운 경우 포함) 도 그대로 덮어쓴다 — 빈 값이면 validate 가
                # 미입력으로 잡아 patch 에서 자동 제외됨.
                clean = {k: meta.get(k, "") for k in REQUIRED_KEYS}
                if nid in parsed:
                    parsed[nid].update(clean)
                else:
                    parsed[nid] = clean
        if yml_parse_errors:
            # 파싱 실패한 YAML 은 사용자 편집이 silently dropped 될 위험이 있어
            # 명확히 경고. strict 모드 호출자(워크플로우)에게도 전파.
            print(f"❌ YAML 파싱 실패 {len(yml_parse_errors)}건 — 해당 사용자 편집 무시됨:")
            for path, msg in yml_parse_errors:
                print(f"   - {path}: {msg}")

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

    if args.strict and (missing or failed or yml_parse_errors):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
