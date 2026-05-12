"""refresh_ui_freeze.py — UI_FREEZE_MANIFEST.json 해시 일괄 갱신 헬퍼.

UI 보호 파일을 정당하게 수정한 직후 호출. 현재 디스크의 파일 해시를 다시
계산해 manifest 를 덮어쓰고, 어느 파일이 갱신됐는지 diff 미리보기를 출력.

사용
  python tools/refresh_ui_freeze.py            # 갱신 + 변경 요약 출력
  python tools/refresh_ui_freeze.py --dry-run  # 변경 카운트만 보고

설계
  - manifest 의 'files' 항목을 신뢰 — 새 파일 자동 추가하지 않음.
  - 보호 대상 추가/제거는 별도 PR 로 의도적으로 manifest 를 편집.
  - check_ui_freeze.py 와 동일한 해시 알고리즘 사용 (텍스트 파일 LF 정규화).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_FILE = ROOT / "UI_FREEZE_MANIFEST.json"
TEXT_SUFFIXES = {".html", ".py", ".css", ".js", ".json", ".md", ".txt", ".yml", ".yaml"}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    data = path.read_bytes()
    if path.suffix.lower() in TEXT_SUFFIXES:
        data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    h.update(data)
    return h.hexdigest().upper()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="변경 카운트만 출력")
    args = parser.parse_args()

    manifest = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
    files = manifest.get("files") or {}

    updates: list[tuple[str, str, str]] = []  # (rel_path, before, after)
    missing: list[str] = []
    for rel_path, meta in files.items():
        path = ROOT / rel_path
        if not path.exists():
            missing.append(rel_path)
            continue
        before = str(meta.get("sha256", "")).upper()
        after = _sha256(path)
        if before != after:
            updates.append((rel_path, before, after))
            if not args.dry_run:
                meta["sha256"] = after

    if missing:
        print(f"⚠️  manifest 에 등록됐지만 디스크에 없는 파일 {len(missing)}건:")
        for m in missing:
            print(f"   - {m}")

    if not updates:
        print("[ui-freeze] 갱신 대상 없음 — 모든 보호 파일 해시가 manifest 와 일치합니다.")
        return 0

    print(f"[ui-freeze] {'(dry-run) ' if args.dry_run else ''}갱신 대상 {len(updates)}건:")
    for rel_path, before, after in updates:
        print(f"   {rel_path}")
        print(f"     before: {before[:16]}...")
        print(f"     after : {after[:16]}...")

    if args.dry_run:
        return 0

    MANIFEST_FILE.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"\n✅ {MANIFEST_FILE.name} 갱신 완료. PR 본문에 변경 사유를 함께 기재하세요.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
