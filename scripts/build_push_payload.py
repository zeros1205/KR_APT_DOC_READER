"""scripts/build_push_payload.py

KST 발송 윈도우 안에 새로 생성된 포스트(post_meta.json)를 추출해
Cloudflare Worker `/push/dispatch` 에 보낼 JSON 페이로드를 stdout 으로 출력한다.

윈도우:
  --window=morning   → KST 00:00:00 ≤ generated_at < 10:00:00
  --window=afternoon → KST 10:00:00 ≤ generated_at < 17:00:00

기준 날짜:
  --date=YYYY-MM-DD (기본값: 오늘 KST)

generated_at 은 datetime.now().isoformat() 으로 기록되며 GitHub Actions
러너는 UTC 이므로 tzinfo 없으면 UTC 로 간주하고 KST 로 변환한다.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
POSTS_DIR = ROOT / "output" / "posts"
SITE_ORIGIN = "https://apt-note.com"
KST = timezone(timedelta(hours=9))


def parse_generated_at(raw: str) -> datetime | None:
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(KST)


def coerce_int(value) -> int:
    if value is None:
        return 0
    if isinstance(value, int):
        return value
    text = str(value).strip().replace(",", "")
    if not text:
        return 0
    digits = "".join(ch for ch in text if ch.isdigit())
    return int(digits) if digits else 0


def window_bounds(date_kst: datetime, window: str) -> tuple[datetime, datetime]:
    midnight = datetime.combine(date_kst.date(), time(0, 0), tzinfo=KST)
    if window == "morning":
        return midnight, midnight + timedelta(hours=10)
    if window == "afternoon":
        return midnight + timedelta(hours=10), midnight + timedelta(hours=17)
    raise ValueError(f"unknown window: {window}")


def iter_post_meta(posts_dir: Path) -> Iterable[tuple[str, dict]]:
    if not posts_dir.exists():
        return
    for child in sorted(posts_dir.iterdir()):
        meta_path = child / "post_meta.json"
        if not meta_path.is_file():
            continue
        try:
            with meta_path.open(encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError):
            continue
        yield child.name, data


def build_post_entry(notice_id: str, meta: dict) -> dict | None:
    region = (meta.get("region_category") or "").strip()
    apt_name = (meta.get("apt_name") or "").strip()
    if not region or not apt_name:
        return None
    post_url = f"{SITE_ORIGIN}/posts/{notice_id}/post.html"
    return {
        "notice_id": notice_id,
        "region": region,
        "apt_name": apt_name,
        "total_households": coerce_int(meta.get("total_households")),
        "post_url": post_url,
        "generated_at": meta.get("generated_at") or "",
    }


def collect(
    window: str,
    date_kst: datetime,
    posts_dir: Path = POSTS_DIR,
) -> list[dict]:
    start, end = window_bounds(date_kst, window)
    posts: list[dict] = []
    for notice_id, meta in iter_post_meta(posts_dir):
        ts = parse_generated_at(meta.get("generated_at") or "")
        if ts is None:
            continue
        if not (start <= ts < end):
            continue
        entry = build_post_entry(notice_id, meta)
        if entry is None:
            continue
        posts.append(entry)
    posts.sort(key=lambda p: (-p["total_households"], p["notice_id"]))
    return posts


def main() -> int:
    parser = argparse.ArgumentParser(description="Build push payload JSON")
    parser.add_argument("--window", choices=["morning", "afternoon"], required=True)
    parser.add_argument("--date", help="YYYY-MM-DD in KST (default: today)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--posts-dir",
        type=Path,
        default=POSTS_DIR,
        help="overrides output/posts directory",
    )
    args = parser.parse_args()

    if args.date:
        try:
            ref = datetime.strptime(args.date, "%Y-%m-%d").replace(tzinfo=KST)
        except ValueError:
            print(f"invalid --date: {args.date}", file=sys.stderr)
            return 2
    else:
        ref = datetime.now(tz=KST)

    posts = collect(args.window, ref, args.posts_dir)
    payload = {
        "window": args.window,
        "date_kst": ref.date().isoformat(),
        "posts": posts,
    }
    if args.dry_run:
        payload["dry_run"] = True
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    print(
        f"collected {len(posts)} post(s) for window={args.window} date={ref.date().isoformat()}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
