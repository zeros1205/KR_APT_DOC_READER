"""
patch_posts8.py — 기존 포스트 일괄 패치

변경 사항:
  1. [전매제한] 자금계획 섹션 하단 전매제한 안내 카드 삭제
  2. [별점]    입지 카드 내 ★ 별점 div 삭제
  3. [지도버튼] 네이버 지도 핀 SVG → 컬러테마 버튼 스타일 "위치 보기" 링크로 교체
"""

import re
import sys
from pathlib import Path

POSTS_DIR = Path(__file__).parent / "output" / "posts"

# ─── [지도버튼] 새 "위치 보기" 버튼 (컬러테마 버튼과 동일 스타일) ──────────
NEW_NAVER_BTN = (
    '<a href="{href}" target="_blank" rel="noopener"'
    ' style="flex-shrink:0;display:inline-flex;align-items:center;gap:5px;background:transparent;'
    'border:1px solid var(--c-primary, #CC5F3F);border-radius:6px;padding:5px 11px;'
    'text-decoration:none;font-size:12px;color:var(--c-primary, #CC5F3F);font-family:inherit;'
    'transition:all 150ms;white-space:nowrap;"'
    ' onmouseover="this.style.opacity=\'0.75\'" onmouseout="this.style.opacity=\'1\'">'
    '<svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor" style="flex-shrink:0;">'
    '<path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z'
    'm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/>'
    '</svg>'
    '위치 보기</a>'
)

# 네이버 지도 anchor 패턴 — 두 가지 변형을 차례로 시도:
#   1. title="네이버 지도에서 보기" 속성이 있는 경우 (핀 SVG / N-사각형 SVG)
#   2. 링크 텍스트에 "네이버 지도에서 보기"가 있는 경우 (🗺️ 텍스트 버튼 스타일)
_NAVER_WITH_TITLE_PAT = re.compile(
    r'<a href="(https://map\.naver\.com[^"]*)"[\s\S]*?'
    r'title="네이버 지도에서 보기"[\s\S]*?</a>',
    re.DOTALL,
)
_NAVER_WITH_TEXT_PAT = re.compile(
    r'<a href="(https://map\.naver\.com[^"]*)"[\s\S]*?'
    r'네이버 지도에서 보기[\s\S]*?</a>',
    re.DOTALL,
)

# 별점 div 패턴: ★/☆ 문자를 포함하는 font-size:20px 스타일 div
_STAR_DIV_PAT = re.compile(
    r'\n[ \t]*<div style="font-size: 20px; font-weight: 800; color: [^"]*;'
    r' margin-bottom: 8px; line-height: 1;">[★☆]+</div>',
)
# 별점 인라인 패턴: 텍스트 내 괄호 안 별점 주석 — "(★★★☆☆ 도보 15분)" 등
_STAR_INLINE_PAT = re.compile(r'\s*\([^)]*[★☆][^)]*\)')

# 전매제한 알림 블록 패턴
_RESALE_ALERT_PAT = re.compile(
    r'\n?[ \t]*<!-- 전매제한 알림 -->.*?</div>\n?',
    re.DOTALL,
)


def patch_post(path: Path, dry_run: bool = False) -> bool:
    original = path.read_text(encoding="utf-8")
    html = original
    changed = False

    # ── [전매제한] 안내 카드 삭제 ───────────────────────────────────
    new_html = _RESALE_ALERT_PAT.sub('', html)
    if new_html != html:
        html = new_html
        changed = True
        print("  [전매제한] 안내 카드 삭제")

    # ── [별점] ★ 별점 div 삭제 ──────────────────────────────────────
    new_html = _STAR_DIV_PAT.sub('', html)
    if new_html != html:
        count = len(_STAR_DIV_PAT.findall(html))
        html = new_html
        changed = True
        print(f"  [별점] 별점 div {count}개 삭제")

    # ── [별점] 인라인 텍스트 별점 주석 삭제 ──────────────────────────
    new_html = _STAR_INLINE_PAT.sub('', html)
    if new_html != html:
        count = len(_STAR_INLINE_PAT.findall(html))
        html = new_html
        changed = True
        print(f"  [별점] 인라인 별점 주석 {count}개 삭제")

    # ── [지도버튼] 핀 SVG / 텍스트 버튼 → 위치 보기 버튼 ──────────────
    # "위치 보기" 버튼이 이미 적용된 경우 건너뜀
    if '위치 보기' not in html:
        def replace_naver(m: re.Match) -> str:
            return NEW_NAVER_BTN.format(href=m.group(1))

        # title 속성 방식 먼저 시도 (핀/N-사각형 SVG)
        new_html = _NAVER_WITH_TITLE_PAT.sub(replace_naver, html)
        if new_html == html:
            # 텍스트 링크 방식 시도 (🗺️ 텍스트 버튼)
            new_html = _NAVER_WITH_TEXT_PAT.sub(replace_naver, html)
        if new_html != html:
            html = new_html
            changed = True
            print("  [지도버튼] 네이버 지도 핀 → 위치 보기 버튼 교체")
        else:
            print("  [지도버튼] ⚠️ 패턴 미매칭")
    else:
        print("  [지도버튼] 이미 적용됨, 건너뜀")

    if not changed:
        print("  ─ 변경 없음")
        return False

    if not dry_run:
        path.write_text(html, encoding="utf-8")

    return True


def main():
    dry_run = "--dry-run" in sys.argv
    if dry_run:
        print("=== DRY-RUN 모드 (파일 수정 없음) ===\n")

    posts = sorted(POSTS_DIR.glob("*/post.html"))
    print(f"총 {len(posts)}개 포스트 처리 시작\n")

    changed_count = 0
    for post_path in posts:
        name = post_path.parent.name
        print(f"[{name}]")
        if patch_post(post_path, dry_run=dry_run):
            changed_count += 1
        print()

    print(f"완료: {changed_count}/{len(posts)}개 파일 변경{'(dry-run)' if dry_run else ''}")


if __name__ == "__main__":
    main()
