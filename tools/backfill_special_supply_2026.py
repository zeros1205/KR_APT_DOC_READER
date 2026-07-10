"""
backfill_special_supply_2026.py
────────────────────────────────────────────────────
2026 청약제도(주택공급규칙 2026-06-15 개정) 반영 이전에 생성된 포스트의
특별공급 요건 문구를 최신 정책 문구로 일괄 교체한다.

배경:
  _special_supply_standard_requirements_2026 의 구버전 문구로 생성된 기존
  포스트에 아래 두 유형의 낡은 요건 문장이 남아 있다.
    - 다자녀: "미성년 자녀 3명 이상" → 2자녀 완화 반영 "2명 이상(태아 포함)"
    - 신생아: 혼인기간 무관(2026-06-15 신설)이라는 핵심 누락

이 문장들은 LLM이 아니라 결정론적 함수가 넣은 것이므로, 해당 문장만
치환하면 입지분석 v3 섹션 등 나머지 콘텐츠를 전혀 건드리지 않는다.
post.html 과 post_meta.json 양쪽을 동일하게 갱신한다.

사용:
  python tools/backfill_special_supply_2026.py           # 실제 적용
  python tools/backfill_special_supply_2026.py --dry-run  # 집계만
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
POSTS_DIR = BASE_DIR / "output" / "posts"

# 구버전 문장 → 신버전 문장 (pipeline/orchestrator.py 의
# _special_supply_standard_requirements_2026 개정 내용과 1:1 대응)
REPLACEMENTS: dict[str, str] = {
    # 다자녀 sentence 1
    "입주자모집공고일 기준 미성년 자녀 3명 이상인 무주택세대구성원을 기본으로 봅니다.":
        "입주자모집공고일 기준 미성년 자녀 2명 이상(태아 포함)인 무주택세대구성원을 기본으로 봅니다.",
    # 신생아 sentence 1
    "입주자모집공고일 기준 출생 또는 입양 2년 이내 자녀가 있는 무주택세대구성원 여부를 기본으로 봅니다.":
        "입주자모집공고일 기준 만 2세 미만(출생·입양 2년 이내) 자녀가 있는 무주택세대구성원이면 혼인 여부·혼인기간과 무관하게 신청할 수 있는 것이 기본입니다.",
    # 신생아 sentence 2
    "공공분양과 민영주택의 기준 차이, 소득·자산 기준, 청약통장 요건을 반드시 확인해야 합니다.":
        "민영주택은 2026-06-15부터 신생아 특별공급이 별도 물량으로 신설되었으며, 공공분양과의 기준 차이·소득·자산·청약통장 요건을 반드시 확인해야 합니다.",
}


def _apply(text: str) -> tuple[str, int]:
    hits = 0
    for old, new in REPLACEMENTS.items():
        if old in text:
            hits += text.count(old)
            text = text.replace(old, new)
    return text, hits


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    changed_html = changed_meta = 0
    total_hits = 0
    v3_broken: list[str] = []

    for post_dir in sorted(POSTS_DIR.iterdir()):
        if not post_dir.is_dir():
            continue
        nid = post_dir.name

        html_path = post_dir / "post.html"
        if html_path.exists():
            original = html_path.read_text(encoding="utf-8")
            had_v3 = "v3-readable" in original
            new_html, hits = _apply(original)
            if hits:
                total_hits += hits
                if had_v3 and "v3-readable" not in new_html:
                    v3_broken.append(nid)  # 안전장치: 절대 발생하면 안 됨
                if not args.dry_run:
                    html_path.write_text(new_html, encoding="utf-8")
                changed_html += 1

        meta_path = post_dir / "post_meta.json"
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            items = meta.get("eligibility_special") or []
            touched = False
            for item in items:
                if not isinstance(item, dict):
                    continue
                reqs = item.get("requirements") or []
                new_reqs = [REPLACEMENTS.get(r, r) for r in reqs]
                if new_reqs != reqs:
                    item["requirements"] = new_reqs
                    touched = True
            if touched:
                changed_meta += 1
                if not args.dry_run:
                    meta_path.write_text(
                        json.dumps(meta, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )

    mode = "[dry-run] " if args.dry_run else ""
    print(f"{mode}post.html 갱신 {changed_html}건 / post_meta.json 갱신 {changed_meta}건 / 치환 문장 {total_hits}개")
    if v3_broken:
        raise SystemExit(f"❌ v3-readable 마커 손실 포스트: {v3_broken}")
    print("✅ v3-readable 마커 보존 확인")


if __name__ == "__main__":
    main()
