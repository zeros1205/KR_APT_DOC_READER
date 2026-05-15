"""Unit tests for scripts/build_push_payload.py"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_push_payload import (  # noqa: E402
    KST,
    coerce_int,
    collect,
    parse_generated_at,
    window_bounds,
)


def write_meta(posts_dir: Path, notice_id: str, payload: dict) -> Path:
    post_dir = posts_dir / notice_id
    post_dir.mkdir(parents=True, exist_ok=True)
    meta = post_dir / "post_meta.json"
    meta.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return meta


def test_parse_generated_at_naive_assumes_utc():
    dt = parse_generated_at("2026-05-15T01:30:00")
    assert dt.tzinfo == KST
    assert dt.hour == 10  # UTC 01:30 = KST 10:30
    assert dt.minute == 30


def test_parse_generated_at_with_offset_preserved():
    dt = parse_generated_at("2026-05-15T01:30:00+00:00")
    assert dt.astimezone(timezone.utc).hour == 1


def test_coerce_int_handles_strings():
    assert coerce_int("501") == 501
    assert coerce_int("1,234") == 1234
    assert coerce_int(None) == 0
    assert coerce_int("미정") == 0


def test_window_bounds_morning_afternoon():
    date_kst = datetime(2026, 5, 15, 0, 0, tzinfo=KST)
    morning_start, morning_end = window_bounds(date_kst, "morning")
    assert morning_start.hour == 0 and morning_end.hour == 10
    afternoon_start, afternoon_end = window_bounds(date_kst, "afternoon")
    assert afternoon_start.hour == 10 and afternoon_end.hour == 17


def test_collect_filters_by_window_kst(tmp_path: Path):
    posts_dir = tmp_path / "posts"
    posts_dir.mkdir()
    # KST 09:30 (UTC 00:30) → morning window
    write_meta(
        posts_dir,
        "A001",
        {
            "apt_name": "Alpha",
            "region_category": "서울",
            "total_households": "100",
            "generated_at": "2026-05-15T00:30:00",
        },
    )
    # KST 10:00 → afternoon (boundary belongs to afternoon)
    write_meta(
        posts_dir,
        "A002",
        {
            "apt_name": "Beta",
            "region_category": "서울",
            "total_households": "200",
            "generated_at": "2026-05-15T01:00:00",
        },
    )
    # KST 16:59:59 → afternoon
    write_meta(
        posts_dir,
        "A003",
        {
            "apt_name": "Gamma",
            "region_category": "경기도",
            "total_households": "1500",
            "generated_at": "2026-05-15T07:59:59",
        },
    )
    # KST 17:00 → out of range
    write_meta(
        posts_dir,
        "A004",
        {
            "apt_name": "Delta",
            "region_category": "인천",
            "total_households": "300",
            "generated_at": "2026-05-15T08:00:00",
        },
    )
    # Missing required fields
    write_meta(posts_dir, "A005", {"generated_at": "2026-05-15T03:00:00"})

    ref = datetime(2026, 5, 15, 9, 0, tzinfo=KST)

    morning = collect("morning", ref, posts_dir)
    assert [p["notice_id"] for p in morning] == ["A001"]
    assert morning[0]["total_households"] == 100

    afternoon = collect("afternoon", ref, posts_dir)
    # Sort by total_households desc → Gamma(1500) > Beta(200)
    assert [p["notice_id"] for p in afternoon] == ["A003", "A002"]
    assert afternoon[0]["region"] == "경기도"


def test_collect_lower_bound_exclusive_at_10am(tmp_path: Path):
    posts_dir = tmp_path / "posts"
    posts_dir.mkdir()
    # KST exactly 10:00:00.000 → afternoon
    write_meta(
        posts_dir,
        "B001",
        {
            "apt_name": "Edge",
            "region_category": "서울",
            "total_households": "1",
            "generated_at": "2026-05-15T01:00:00",
        },
    )
    ref = datetime(2026, 5, 15, 12, 0, tzinfo=KST)
    morning = collect("morning", ref, posts_dir)
    afternoon = collect("afternoon", ref, posts_dir)
    assert morning == []
    assert [p["notice_id"] for p in afternoon] == ["B001"]


def test_collect_skips_unparseable(tmp_path: Path):
    posts_dir = tmp_path / "posts"
    posts_dir.mkdir()
    write_meta(
        posts_dir,
        "C001",
        {
            "apt_name": "Bad",
            "region_category": "서울",
            "generated_at": "not-a-date",
        },
    )
    ref = datetime(2026, 5, 15, 9, 0, tzinfo=KST)
    assert collect("morning", ref, posts_dir) == []
