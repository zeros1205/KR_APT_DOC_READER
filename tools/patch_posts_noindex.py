"""patch_posts_noindex.py — 만료 포스트 일괄 noindex 처리.

기존 발행 포스트(output/posts/<id>/post.html)의 robots 메타를 winner_date 기준
NOINDEX_AFTER_DAYS 일 경과 시 'noindex, follow' 로 전환.
신규 빌드에선 html_renderer 가 자동 처리하므로 본 스크립트는 기존 자산
일괄 보강 + 일별 임계치 변경 시 재실행용.

설계 원칙
  - 멱등성: 이미 올바른 robots 디렉티브이면 skip
  - 양방향 동기: noindex 대상이 다시 활성이 되어야 한다면 (재발표 등) 'index, follow'
    로도 되돌릴 수 있도록 정책-기반 갱신
  - dry-run + limit 지원

사용
  python tools/patch_posts_noindex.py [--dry-run] [--limit N]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = ROOT / "output" / "posts"

if str(ROOT / "pipeline") not in sys.path:
    sys.path.insert(0, str(ROOT / "pipeline"))
from seo_policy import NOINDEX_AFTER_DAYS, is_noindex_eligible as _is_noindex_eligible  # noqa: E402

ROBOTS_RE = re.compile(r'(<meta name="robots" content=")([^"]*)(">)')


def _desired_directive(winner_date: str, today: date) -> str:
    return "noindex, follow" if _is_noindex_eligible(winner_date, today=today) else "index, follow"


def patch_post(post_dir: Path, today: date) -> dict:
    meta_path = post_dir / "post_meta.json"
    html_path = post_dir / "post.html"
    if not html_path.exists():
        return {"ok": False, "reason": "no post.html"}
    winner_date = ""
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            winner_date = str(meta.get("winner_date") or "")
        except Exception:
            pass

    desired = _desired_directive(winner_date, today)
    html = html_path.read_text(encoding="utf-8")
    match = ROBOTS_RE.search(html)
    if not match:
        return {"ok": False, "reason": "no robots meta"}
    current = match.group(2).strip().lower()
    if current.replace(" ", "") == desired.replace(" ", ""):
        return {"ok": True, "changed": False, "directive": desired}
    new_html = ROBOTS_RE.sub(f'\\g<1>{desired}\\g<3>', html, count=1)
    return {
        "ok": True,
        "changed": True,
        "from": match.group(2),
        "to": desired,
        "winner_date": winner_date,
        "html": new_html,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--today", default="", help="기준일 (YYYY-MM-DD). 기본: 시스템 오늘")
    args = parser.parse_args()

    today = date.fromisoformat(args.today) if args.today else date.today()

    if not POSTS_DIR.exists():
        print(f"❌ 포스트 디렉터리 없음: {POSTS_DIR}", file=sys.stderr)
        return 1

    dirs = sorted([d for d in POSTS_DIR.iterdir() if d.is_dir()])
    if args.limit:
        dirs = dirs[: args.limit]

    counts = {
        "total": 0,
        "set_noindex": 0,
        "set_index": 0,
        "skipped": 0,
        "missing": 0,
    }

    for d in dirs:
        counts["total"] += 1
        result = patch_post(d, today)
        if not result.get("ok"):
            counts["missing"] += 1
            continue
        if not result["changed"]:
            counts["skipped"] += 1
            continue
        if result["to"] == "noindex, follow":
            counts["set_noindex"] += 1
        else:
            counts["set_index"] += 1
        if not args.dry_run:
            (d / "post.html").write_text(result["html"], encoding="utf-8")

    mode = "[DRY RUN]" if args.dry_run else "[APPLIED]"
    print(f"{mode} 기준일 {today} / 임계치 D+{NOINDEX_AFTER_DAYS}")
    print(f"  총 {counts['total']}건 처리")
    print(f"    noindex,follow 로 전환     →  {counts['set_noindex']}건")
    print(f"    index,follow 로 복귀       →  {counts['set_index']}건")
    print(f"    이미 정책 일치 (skip)       →  {counts['skipped']}건")
    if counts["missing"]:
        print(f"    post.html / robots meta 없음 →  {counts['missing']}건")

    return 0


if __name__ == "__main__":
    sys.exit(main())
