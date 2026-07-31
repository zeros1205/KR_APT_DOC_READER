"""cleanup_old_pdfs.py — 당첨자발표일 경과 공고의 원본 PDF 삭제.

GitHub 저장소 용량 관리를 위해 `input/pdfs/`에 커밋된 원본 모집공고문 PDF 중
당첨자발표일(winner_date)이 기준일보다 CUTOFF_MONTHS개월 이상 지난 공고의
PDF만 삭제한다. `output/posts/` 는 절대 건드리지 않는다 — 공고 페이지는
post_meta.json / post.html 만으로 렌더링되며 원본 PDF에 의존하지 않는다.

사용
  python tools/cleanup_old_pdfs.py [--dry-run] [--months N] [--today YYYY-MM-DD]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PDF_DIR = ROOT / "input" / "pdfs"
POSTS_DIR = ROOT / "output" / "posts"

CUTOFF_MONTHS = 2

NOTICE_ID_RE = re.compile(r"(20\d{8})")


def _parse_winner_date(value: object) -> date | None:
    text = "" if value is None else str(value).strip()
    if not text or text in {"-", "null", "None"}:
        return None
    text = text.split(" ~ ", 1)[0].strip().replace(".", "-")
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _months_before(today: date, months: int) -> date:
    y, m = today.year, today.month - months
    while m <= 0:
        m += 12
        y -= 1
    d = min(today.day, 28)
    return date(y, m, d)


def load_winner_dates() -> dict[str, date | None]:
    winner_by_notice: dict[str, date | None] = {}
    if not POSTS_DIR.exists():
        return winner_by_notice
    for post_dir in POSTS_DIR.iterdir():
        meta_path = post_dir / "post_meta.json"
        if not meta_path.exists():
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        notice_id = str(meta.get("notice_id") or post_dir.name)
        winner_by_notice[notice_id] = _parse_winner_date(meta.get("winner_date"))
    return winner_by_notice


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--months", type=int, default=CUTOFF_MONTHS, help=f"기준 개월 수 (기본 {CUTOFF_MONTHS})")
    parser.add_argument("--today", default="", help="기준일 YYYY-MM-DD (기본: 시스템 오늘)")
    args = parser.parse_args()

    today = date.fromisoformat(args.today) if args.today else date.today()
    cutoff = _months_before(today, args.months)

    if not PDF_DIR.exists():
        print(f"PDF 디렉터리 없음: {PDF_DIR}", file=sys.stderr)
        return 1

    winner_by_notice = load_winner_dates()

    deleted: list[tuple[str, str, date]] = []
    kept: list[tuple[str, str]] = []
    unknown: list[str] = []

    for pdf_path in sorted(PDF_DIR.glob("*.pdf")):
        match = NOTICE_ID_RE.search(pdf_path.name)
        if not match:
            unknown.append(pdf_path.name)
            continue
        notice_id = match.group(1)
        winner_date = winner_by_notice.get(notice_id)
        if winner_date is None:
            unknown.append(pdf_path.name)
            continue
        if winner_date < cutoff:
            deleted.append((notice_id, pdf_path.name, winner_date))
            if not args.dry_run:
                pdf_path.unlink()
        else:
            kept.append((notice_id, pdf_path.name))

    mode = "[DRY RUN]" if args.dry_run else "[APPLIED]"
    print(f"{mode} 기준일 {today} / 삭제 임계 당첨자발표일 < {cutoff} ({args.months}개월 이상 경과)")
    print(f"  삭제 대상: {len(deleted)}건")
    for notice_id, name, winner_date in deleted:
        print(f"    - {notice_id} (당첨자발표 {winner_date}): {name}")
    print(f"  유지: {len(kept)}건")
    if unknown:
        print(f"  당첨자발표일 확인 불가 (건드리지 않음): {len(unknown)}건")
        for name in unknown:
            print(f"    - {name}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
