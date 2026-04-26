"""
Apply manually verified regulation fields to a cached notice.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE_DIR = Path(__file__).parent
NOTICE_CACHE_DIR = BASE_DIR / "output" / "data_cache" / "notices"


def _now_iso() -> str:
    return datetime.now(timezone(timedelta(hours=9))).isoformat(timespec="seconds")


def main() -> int:
    parser = argparse.ArgumentParser(description="Patch cached notice regulation fields")
    parser.add_argument("--notice-id", required=True)
    parser.add_argument("--regulated-zone", required=True)
    parser.add_argument("--readmission-limit", required=True)
    parser.add_argument("--resale-restriction", required=True)
    parser.add_argument("--live-requirement", required=True)
    parser.add_argument("--price-cap", required=True)
    parser.add_argument("--source", default="manual_verified")
    parser.add_argument("--query", default="")
    parser.add_argument("--evidence-url", action="append", default=[])
    parser.add_argument("--evidence-note", action="append", default=[])
    args = parser.parse_args()

    path = NOTICE_CACHE_DIR / f"{args.notice_id}.json"
    if not path.exists():
        print(f"[regulation] cache not found: {path}")
        return 1

    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    regulation = {
        "regulated_zone": args.regulated_zone,
        "is_hot_zone": "Y" if "투기과열지구" in args.regulated_zone else "N",
        "is_regulated_zone": "Y" if "청약과열지역" in args.regulated_zone else "N",
        "readmission_limit": args.readmission_limit,
        "resale_restriction": args.resale_restriction,
        "live_requirement": args.live_requirement,
        "price_cap": args.price_cap,
        "is_price_cap": "Y" if args.price_cap == "적용" else "N",
        "source": args.source,
        "query": args.query,
        "evidence_urls": args.evidence_url,
        "evidence_notes": args.evidence_note,
        "checked_at": _now_iso(),
    }

    payload["manual_regulation"] = regulation
    doc = payload.setdefault("document", {})
    for key in (
        "is_hot_zone",
        "readmission_limit",
        "resale_restriction",
        "live_requirement",
        "price_cap",
        "is_price_cap",
    ):
        doc[key] = regulation[key]
    doc["regulated_zone"] = regulation["regulated_zone"]

    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[regulation] patched: {path.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
