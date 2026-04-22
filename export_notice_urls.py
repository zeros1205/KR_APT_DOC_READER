"""
청약홈 공공데이터 API에서 최근 공고의 단지명과 상세페이지 URL만 추출한다.

출력:
  - output/notice_urls.csv
  - output/notice_urls.md
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import sys
from pathlib import Path
from datetime import datetime, timedelta

from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR / "pipeline"))

load_dotenv(BASE_DIR / ".env")

from agents.collector import CheongYakAPI  # noqa: E402

OUTPUT_DIR = BASE_DIR / "output"


def _write_outputs(rows: list[dict[str, str]]) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = OUTPUT_DIR / "notice_urls.csv"
    md_path = OUTPUT_DIR / "notice_urls.md"

    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["apt_name", "notice_url"])
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# 청약홈 상세페이지 URL 목록",
        "",
        "| 단지명 | 청약홈 상세페이지 URL |",
        "|---|---|",
    ]
    for row in rows:
        apt_name = row["apt_name"].replace("|", "\\|")
        notice_url = row["notice_url"].replace("|", "\\|")
        lines.append(f"| {apt_name} | {notice_url} |")

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return csv_path, md_path


async def main() -> None:
    parser = argparse.ArgumentParser(description="청약홈 상세페이지 URL 추출")
    parser.add_argument("--days", type=int, default=7, help="최근 N일 공고 수집")
    args = parser.parse_args()

    print(f"[수집] 최근 {args.days}일 공고 조회 중...")
    api = CheongYakAPI()
    start_date = (datetime.now() - timedelta(days=args.days)).strftime("%Y-%m-%d")

    docs: list[dict] = []
    page = 1
    per_page = 50
    while True:
        items = await api.get_list(page=page, per_page=per_page, start_date=start_date)
        if not items:
            break
        docs.extend(items)
        if len(items) < per_page:
            break
        page += 1

    seen: set[str] = set()
    rows: list[dict[str, str]] = []
    for doc in docs:
        apt_name = str(doc.get("HOUSE_NM", "")).strip()
        notice_url = str(doc.get("PBLANC_URL", "")).strip()
        if not apt_name or not notice_url:
            continue
        if notice_url in seen:
            continue
        seen.add(notice_url)
        rows.append({"apt_name": apt_name, "notice_url": notice_url})

    csv_path, md_path = _write_outputs(rows)
    print(f"[완료] {len(rows)}건 저장")
    print(f"CSV: {csv_path}")
    print(f"MD : {md_path}")


if __name__ == "__main__":
    asyncio.run(main())
