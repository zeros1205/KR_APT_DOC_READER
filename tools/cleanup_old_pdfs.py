"""발행 완료된 공고의 오래된 PDF를 input/pdfs 에서 정리한다.

페이지 생성이 끝나면 원본 PDF는 더 이상 빌드에 필요하지 않지만 계속
쌓여 저장소 용량을 잡아먹는다. 이 스크립트는 processed_notices.json 에
있는(=이미 발행된) 공고의 PDF 중, git 커밋 이력상 "최초 업로드일"로부터
일정 기간이 지난 파일만 삭제한다.

아직 페이지 생성이 안 된 공고의 PDF는 절대 건드리지 않는다 — 지우면
codex-페이지 생성이 그 공고의 PDF를 더 이상 찾지 못해 발행이 막힌다.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PDF_DIR = ROOT / "input" / "pdfs"
PROCESSED_FILE = ROOT / "output" / "processed_notices.json"

RETENTION_SECONDS = 7 * 24 * 60 * 60
NOTICE_ID_RE = re.compile(r"\d{9,10}")


def _load_processed() -> set[str]:
    if not PROCESSED_FILE.exists():
        return set()
    try:
        data = json.loads(PROCESSED_FILE.read_text(encoding="utf-8-sig"))
    except Exception:
        return set()
    return {str(item) for item in data}


def _extract_notice_id(filename: str) -> str | None:
    match = NOTICE_ID_RE.search(filename)
    return match.group(0) if match else None


def _added_at_epoch(path: Path) -> int | None:
    """git 커밋 이력에서 이 파일이 처음 추가된 시각(unix epoch)을 구한다.

    실제로 shallow clone(fetch-depth=1)에서는 git log 가 항상 최신 커밋 1개만
    보여줘 이 함수가 무의미해진다 — 호출하는 워크플로우는 반드시
    `actions/checkout@v4` 를 `fetch-depth: 0` 으로 실행해야 한다.
    """
    rel = path.relative_to(ROOT).as_posix()
    result = subprocess.run(
        ["git", "log", "--follow", "--diff-filter=A", "--format=%at", "--", rel],
        cwd=ROOT, capture_output=True, text=True,
    )
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if lines:
        return int(lines[-1])  # 가장 오래된(=최초 추가) 커밋

    # --diff-filter=A 로 못 찾으면(리네임 이력 등 예외 상황) 마지막으로 이 파일을
    # 건드린 커밋 시각으로 대체한다 — 없는 것보다는 보수적으로 안전한 근사치.
    result = subprocess.run(
        ["git", "log", "-1", "--format=%at", "--", rel],
        cwd=ROOT, capture_output=True, text=True,
    )
    line = result.stdout.strip()
    return int(line) if line else None


def main() -> None:
    if not PDF_DIR.exists():
        print("[cleanup] input/pdfs 없음 — 종료")
        print("[cleanup] DELETED_COUNT=0")
        return

    processed = _load_processed()
    now = int(time.time())
    deleted: list[str] = []
    skipped_not_processed = 0
    skipped_no_id = 0
    skipped_no_date = 0

    for path in sorted(PDF_DIR.glob("*.pdf")):
        notice_id = _extract_notice_id(path.name)
        if not notice_id:
            skipped_no_id += 1
            print(f"[cleanup] 공고번호를 인식할 수 없어 건너뜀: {path.name}")
            continue

        if notice_id not in processed:
            skipped_not_processed += 1
            continue

        added_at = _added_at_epoch(path)
        if added_at is None:
            skipped_no_date += 1
            print(f"[cleanup] 업로드 날짜를 확인할 수 없어 건너뜀: {path.name}")
            continue

        age_days = (now - added_at) // 86400
        if now - added_at < RETENTION_SECONDS:
            continue

        print(f"[cleanup] 삭제: {path.name} ({age_days}일 경과)")
        path.unlink()
        deleted.append(path.name)

    print(
        f"[cleanup] 삭제 {len(deleted)}건 / 미발행이라 스킵 {skipped_not_processed}건 / "
        f"공고번호 인식 실패 {skipped_no_id}건 / 날짜 확인 실패 {skipped_no_date}건"
    )
    print(f"[cleanup] DELETED_COUNT={len(deleted)}")


if __name__ == "__main__":
    main()
