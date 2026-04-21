"""
patch_posts10.py — 청약 규제 정보 카드 3항목 → 6항목 소급 변환

기존 3항목 → 신규 6항목 매핑:
  투기과열지구  → 규제지역 여부  (값 변환: "비해당"→"비규제지역")
  실거주 의무   → 거주의무기간   (값 그대로)
  전매제한      → 전매제한       (값 그대로)

신규 3항목 (HTML 내 텍스트 추출, 실패 시 "공고문 확인 필요"):
  재당첨 제한   → "재당첨 제한" 키워드 주변 텍스트
  분양가 상한제 → "분양가상한제 미적용/적용" 명시 여부
  택지 유형     → "민간택지/공공택지" 명시 여부

이미 새 형식("규제지역 여부" 포함)인 포스트는 건너뜀.
"""

import re
import sys
from pathlib import Path

POSTS_DIR = Path(__file__).parent / "output" / "posts"

# ─── 기존 3항목 카드 캡처 패턴 ───────────────────────────────────────────────
_OLD_CARD_PAT = re.compile(
    r'([ \t]*<!-- 청약 규제 정보 -->[\s\S]*?'
    r'투기과열지구</div>\s*<div[^>]*>([^<]+)</div>'
    r'[\s\S]*?'
    r'실거주 의무</div>\s*<div[^>]*>([^<]+)</div>'
    r'[\s\S]*?'
    r'전매제한</div>\s*<div[^>]*>([^<]+)</div>'
    r'\s*</div>\s*</div>\s*</div>)',
    re.DOTALL,
)


def _map_regulated_zone(hot_zone_val: str) -> str:
    v = hot_zone_val.strip()
    if v == "비해당":
        return "비규제지역"
    if v in ("공고문 확인 필요", ""):
        return "공고문 확인 필요"
    return v  # "해당 (투기과열지구)" 등 그대로


def _detect_price_cap(html: str) -> str:
    # "분양가상한제" 주변 20자씩 확인
    segments = re.findall(r'.{0,15}분양가\s*상한제.{0,20}', html)
    has_not = any("미적용" in s for s in segments)
    has_yes = any(("적용" in s and "미적용" not in s) for s in segments)
    if has_not:
        return "미적용"
    if has_yes:
        return "적용"
    return "공고문 확인 필요"


def _detect_land_type(html: str) -> str:
    if re.search(r'민간\s*택지', html):
        return "민간택지"
    if re.search(r'공공\s*(?:택지|주택지구)', html):
        return "공공택지"
    return "공고문 확인 필요"


def _detect_readmission(html: str) -> str:
    m = re.search(
        r'재당첨\s*제한[^。\n]{0,20}?(\d+년|없음|해당\s*없음|해당없음)',
        html,
    )
    if m:
        return m.group(1).replace(" ", "")
    return "공고문 확인 필요"


def _build_new_card(regulated: str, readmission: str, resale: str,
                    live_req: str, price_cap: str, land_type: str) -> str:
    return (
        "    <!-- 청약 규제 정보 -->\n"
        "    <div style=\"\n"
        "      flex: 1 1 100%;\n"
        "      background: #F5F2ED; border: 1px solid #DED9D1;\n"
        "      border-radius: 10px; padding: 18px 20px;\n"
        "      box-shadow: 0 1px 4px rgba(44,40,37,0.07);\n"
        "    \">\n"
        "      <div style=\"font-size: 14px; letter-spacing: 0.025em; color: var(--c-mid, #6A635C); margin-bottom: 12px;\">📋 청약 규제 정보</div>\n"
        "      <div style=\"display: flex; flex-wrap: wrap; gap: 12px;\">\n"
        "        <div style=\"flex: 1 1 calc(50% - 6px); min-width: 140px;\">\n"
        "          <div style=\"font-size: 12px; color: #A39D96; margin-bottom: 4px; letter-spacing: 0.5px;\">규제지역 여부</div>\n"
        f"          <div style=\"font-size: 14px; font-weight: 700; color: var(--c-dark);\">{regulated}</div>\n"
        "        </div>\n"
        "        <div style=\"flex: 1 1 calc(25% - 6px); min-width: 100px;\">\n"
        "          <div style=\"font-size: 12px; color: #A39D96; margin-bottom: 4px; letter-spacing: 0.5px;\">재당첨 제한</div>\n"
        f"          <div style=\"font-size: 14px; font-weight: 700; color: var(--c-dark);\">{readmission}</div>\n"
        "        </div>\n"
        "        <div style=\"flex: 1 1 calc(25% - 6px); min-width: 100px;\">\n"
        "          <div style=\"font-size: 12px; color: #A39D96; margin-bottom: 4px; letter-spacing: 0.5px;\">전매제한</div>\n"
        f"          <div style=\"font-size: 14px; font-weight: 700; color: var(--c-dark);\">{resale}</div>\n"
        "        </div>\n"
        "        <div style=\"flex: 1 1 calc(33.33% - 8px); min-width: 100px;\">\n"
        "          <div style=\"font-size: 12px; color: #A39D96; margin-bottom: 4px; letter-spacing: 0.5px;\">거주의무기간</div>\n"
        f"          <div style=\"font-size: 14px; font-weight: 700; color: var(--c-dark);\">{live_req}</div>\n"
        "        </div>\n"
        "        <div style=\"flex: 1 1 calc(33.33% - 8px); min-width: 100px;\">\n"
        "          <div style=\"font-size: 12px; color: #A39D96; margin-bottom: 4px; letter-spacing: 0.5px;\">분양가 상한제</div>\n"
        f"          <div style=\"font-size: 14px; font-weight: 700; color: var(--c-dark);\">{price_cap}</div>\n"
        "        </div>\n"
        "        <div style=\"flex: 1 1 calc(33.33% - 8px); min-width: 100px;\">\n"
        "          <div style=\"font-size: 12px; color: #A39D96; margin-bottom: 4px; letter-spacing: 0.5px;\">택지 유형</div>\n"
        f"          <div style=\"font-size: 14px; font-weight: 700; color: var(--c-dark);\">{land_type}</div>\n"
        "        </div>\n"
        "      </div>\n"
        "    </div>"
    )


def patch_post(html_path: Path, dry_run: bool = False) -> bool:
    html = html_path.read_text(encoding="utf-8")

    if "규제지역 여부</div>" in html:
        print("  ─ 이미 새 형식, 건너뜀")
        return False

    m = _OLD_CARD_PAT.search(html)
    if not m:
        print("  ⚠️ 패턴 미매칭")
        return False

    hot_zone_val = m.group(2).strip()
    live_req_val  = m.group(3).strip()
    resale_val    = m.group(4).strip()

    regulated   = _map_regulated_zone(hot_zone_val)
    readmission = _detect_readmission(html)
    price_cap   = _detect_price_cap(html)
    land_type   = _detect_land_type(html)

    new_card = _build_new_card(regulated, readmission, resale_val,
                               live_req_val, price_cap, land_type)
    new_html = html[: m.start()] + new_card + html[m.end():]

    print(f"  규제지역: {regulated} | 재당첨: {readmission}")
    print(f"  전매제한: {resale_val} | 거주의무: {live_req_val}")
    print(f"  분양가상한제: {price_cap} | 택지유형: {land_type}")

    if not dry_run:
        html_path.write_text(new_html, encoding="utf-8")
    return True


def main():
    dry_run = "--dry-run" in sys.argv
    if dry_run:
        print("=== DRY-RUN 모드 ===\n")

    posts = sorted(POSTS_DIR.glob("*/post.html"))
    print(f"총 {len(posts)}개 포스트 처리\n")

    changed = 0
    for p in posts:
        print(f"[{p.parent.name}]")
        if patch_post(p, dry_run=dry_run):
            changed += 1
        print()

    print(f"완료: {changed}/{len(posts)}개 변경{'(dry-run)' if dry_run else ''}")


if __name__ == "__main__":
    main()
