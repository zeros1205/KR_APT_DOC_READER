"""patch_posts_noindex.py — 만료·thin content 통합 noindex 처리.

기존 발행 포스트(output/posts/<id>/post.html)의 robots 메타를 다음 정책에 따라
양방향 동기:
  - 만료 (winner_date + NOINDEX_AFTER_DAYS <= today) OR
  - Thin content (본문 글자수·표 등 임계치 미달)
  → 'noindex, follow'
  - 그 외 → 'index, follow'

신규 빌드에선 html_renderer 가 만료를 자동 처리하나, thin content 판정은
빌드된 HTML 측정이 필요해 본 후처리 단계에서 결정함.

설계 원칙
  - 멱등성: 이미 올바른 디렉티브이면 skip
  - 양방향: 정책 통과 시 'index, follow' 로 복귀
  - dry-run / limit / today 옵션

사용
  python tools/patch_posts_noindex.py [--dry-run] [--limit N] [--today YYYY-MM-DD]
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
from seo_policy import NOINDEX_AFTER_DAYS, should_noindex  # noqa: E402

ROBOTS_RE = re.compile(r'(<meta name="robots" content=")([^"]*)(">)')


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

    html = html_path.read_text(encoding="utf-8")
    match = ROBOTS_RE.search(html)
    if not match:
        return {"ok": False, "reason": "no robots meta"}

    noindex, reason = should_noindex(winner_date=winner_date, html=html, today=today)
    desired = "noindex, follow" if noindex else "index, follow"
    current = match.group(2).strip().lower().replace(" ", "")
    if current == desired.replace(" ", ""):
        return {"ok": True, "changed": False, "directive": desired, "reason": reason}
    new_html = ROBOTS_RE.sub(f'\\g<1>{desired}\\g<3>', html, count=1)
    return {
        "ok": True,
        "changed": True,
        "from": match.group(2),
        "to": desired,
        "reason": reason,
        "winner_date": winner_date,
        "html": new_html,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--today", default="", help="기준일 (YYYY-MM-DD). 기본: 시스템 오늘")
    parser.add_argument("--verbose", action="store_true", help="thin content 사유까지 출력")
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
        "set_noindex_expired": 0,
        "set_noindex_thin": 0,
        "set_index": 0,
        "skipped": 0,
        "missing": 0,
    }
    thin_samples: list[str] = []

    for d in dirs:
        counts["total"] += 1
        result = patch_post(d, today)
        if not result.get("ok"):
            counts["missing"] += 1
            continue
        if not result["changed"]:
            counts["skipped"] += 1
            if result.get("reason", "").startswith("thin") and args.verbose:
                print(f"  · {d.name}: already noindex ({result['reason']})")
            continue
        if result["to"] == "noindex, follow":
            reason = result.get("reason", "")
            if reason.startswith("thin"):
                counts["set_noindex_thin"] += 1
                thin_samples.append(f"{d.name}: {reason}")
            else:
                counts["set_noindex_expired"] += 1
        else:
            counts["set_index"] += 1
        if not args.dry_run:
            (d / "post.html").write_text(result["html"], encoding="utf-8")

    mode = "[DRY RUN]" if args.dry_run else "[APPLIED]"
    print(f"{mode} 기준일 {today} / 만료 임계 D+{NOINDEX_AFTER_DAYS}")
    print(f"  총 {counts['total']}건 처리")
    print(f"    noindex (만료)              →  {counts['set_noindex_expired']}건")
    print(f"    noindex (thin content)      →  {counts['set_noindex_thin']}건")
    print(f"    index 로 복귀               →  {counts['set_index']}건")
    print(f"    이미 정책 일치 (skip)        →  {counts['skipped']}건")
    if counts["missing"]:
        print(f"    post.html / robots meta 없음 →  {counts['missing']}건")
    if thin_samples and args.verbose:
        print("\n  Thin content 사례:")
        for s in thin_samples[:10]:
            print(f"    - {s}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
