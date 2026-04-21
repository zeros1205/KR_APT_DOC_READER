"""
patch_posts9.py — 기존 포스트 일괄 패치

변경 사항:
  1. [공고버튼]  Section 3 최하단에 모집공고문 보기 버튼 복원 (notice_url 사용)
  2. [실거주]   실거주 의무 "공고문 확인 필요" → 민영·비상한제 → "없음"
               공공분양 → "해당없음"
"""

import json
import re
import sys
from pathlib import Path

POSTS_DIR = Path(__file__).parent / "output" / "posts"

# ─── [공고버튼] Section 3 최하단 버튼 HTML 템플릿 ──────────────────────────────
NOTICE_BTN_TEMPLATE = (
    '\n  <div style="margin-top:24px;text-align:center;">'
    '<a href="{url}" target="_blank" rel="noopener" '
    'style="display:inline-flex;align-items:center;gap:8px;'
    'background:var(--c-primary, #CC5F3F);color:#fff;font-size:15px;font-weight:700;'
    'padding:14px 28px;border-radius:8px;text-decoration:none;letter-spacing:-0.2px;'
    'box-shadow:0 2px 8px rgba(0,0,0,0.15);transition:background 200ms;" '
    'onmouseover="this.style.background=\'var(--c-primary-dark, #A84830)\'" '
    'onmouseout="this.style.background=\'var(--c-primary, #CC5F3F)\'">'
    '📋 모집공고문 보기 →</a></div>'
)

# Section 3 끝 → Section 4(청약 신청자격) 구분선 패턴
# 버튼이 이미 없을 때: \n\n</div>\n\n\n<!-- 구분선 -->\n...\nSECTION 4 — 청약 신청자격
_SEC3_END_PAT = re.compile(
    r'(\n\n)(</div>)(\n\n\n<!-- 구분선 -->[\s\S]*?SECTION 4 — 청약 신청자격)',
    re.DOTALL,
)

# ─── [실거주] 정책 카드 실거주 의무 값 패치 패턴 ────────────────────────────────
_LIVE_REQ_PAT = re.compile(
    r'(>실거주 의무</div>\s*<div[^>]*>)(공고문 확인 필요)(</div>)',
    re.DOTALL,
)


def patch_post(post_dir: Path, dry_run: bool = False) -> bool:
    html_path = post_dir / "post.html"
    meta_path = post_dir / "post_meta.json"

    if not html_path.exists() or not meta_path.exists():
        print("  ─ 파일 없음, 건너뜀")
        return False

    html = html_path.read_text(encoding="utf-8")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    notice_url = meta.get("notice_url", "")
    changed = False

    # ── [공고버튼] Section 3 최하단 복원 ─────────────────────────────────────
    # 버튼이 이미 있으면 건너뜀
    if "모집공고문 보기" in html:
        print("  [공고버튼] 이미 있음, 건너뜀")
    elif not notice_url:
        print("  [공고버튼] notice_url 없음, 건너뜀")
    else:
        btn_html = NOTICE_BTN_TEMPLATE.format(url=notice_url)
        new_html = _SEC3_END_PAT.sub(
            lambda m: m.group(1) + btn_html + '\n' + m.group(2) + m.group(3),
            html, count=1
        )
        if new_html != html:
            html = new_html
            changed = True
            print("  [공고버튼] Section 3 최하단 버튼 복원")
        else:
            print("  [공고버튼] ⚠️ 삽입 패턴 미매칭")

    # ── [실거주] 의무 값 패치 ─────────────────────────────────────────────────
    is_public = "공공분양" in post_dir.name
    has_price_cap = bool(re.search(r'분양가\s*상한제', html[:3000]))

    if is_public:
        new_live_val = "해당없음"
    elif has_price_cap:
        new_live_val = None  # 분양가상한제 → 공고문 필요, 건드리지 않음
    else:
        new_live_val = "없음"

    if new_live_val:
        new_html = _LIVE_REQ_PAT.sub(
            lambda m: m.group(1) + new_live_val + m.group(3),
            html, count=1
        )
        if new_html != html:
            html = new_html
            changed = True
            print(f"  [실거주] '공고문 확인 필요' → '{new_live_val}'")
        else:
            # 이미 다른 값이거나 이미 수정됨
            pass

    if not changed:
        print("  ─ 변경 없음")
        return False

    if not dry_run:
        html_path.write_text(html, encoding="utf-8")

    return True


def main():
    dry_run = "--dry-run" in sys.argv
    if dry_run:
        print("=== DRY-RUN 모드 (파일 수정 없음) ===\n")

    posts = sorted(POSTS_DIR.glob("*/post.html"))
    print(f"총 {len(posts)}개 포스트 처리 시작\n")

    changed_count = 0
    for post_path in posts:
        post_dir = post_path.parent
        print(f"[{post_dir.name}]")
        if patch_post(post_dir, dry_run=dry_run):
            changed_count += 1
        print()

    print(f"완료: {changed_count}/{len(posts)}개 파일 변경{'(dry-run)' if dry_run else ''}")


if __name__ == "__main__":
    main()
