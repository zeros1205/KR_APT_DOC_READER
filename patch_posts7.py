"""
patch_posts7.py — 기존 포스트 일괄 패치 (사용자 요청 #01a/b/c, #03, #05 + 팔레트)

변경 사항:
  1. [03] 모집공고문 버튼 제거 (타임라인·타입표 하단)
  2. [05] 전매제한 안내 카드 빈 내용 → 안내 문구 추가
  3. [01a] apt_intro "총 N세대 규모로" → "총 N세대가 공급되며"
  4. [01b] 공급 위치 카드 네이버 N 사각형 SVG → 위치 핀 SVG (블루-그린 그라디언트)
  5. [01c] 공급 위치 카드 하단에 청약 규제 정보 카드 추가
  6. [팔레트] 하드코딩 accent 색상을 CSS var() 참조로 변환 (전체 페이지 팔레트 반응)
"""

import re
import sys
from pathlib import Path

POSTS_DIR = Path(__file__).parent / "output" / "posts"

# ─── [01b] 새 위치 핀 SVG (블루→그린 그라디언트, 흰색 N) ───────────────────
NEW_NAVER_PIN = '''\
<a href="{href}" target="_blank" rel="noopener"
   title="네이버 지도에서 보기"
   style="flex-shrink:0;display:inline-flex;align-items:flex-end;justify-content:center;
          width:30px;height:42px;text-decoration:none;transition:opacity 150ms;"
   onmouseover="this.style.opacity=\'0.8\'" onmouseout="this.style.opacity=\'1\'">
  <svg width="30" height="42" viewBox="0 0 30 42" fill="none" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="naverPinGrad" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="#00B4D8"/>
        <stop offset="100%" stop-color="#03C75A"/>
      </linearGradient>
    </defs>
    <path d="M15 0C6.716 0 0 6.716 0 15c0 5.39 2.86 10.11 7.14 12.73L15 42l7.86-14.27C27.14 25.11 30 20.39 30 15 30 6.716 23.284 0 15 0z" fill="url(#naverPinGrad)"/>
    <path d="M9.5 9.5v11h2.6l5.2-7V20.5H20V9.5h-2.6l-5.2 7V9.5z" fill="white"/>
  </svg>
</a>'''

# ─── [01c] 청약 규제 정보 카드 (공급 위치 카드 하단에 추가) ───────────────────
POLICY_CARD_TEMPLATE = '''\

    <!-- 청약 규제 정보 -->
    <div style="
      flex: 1 1 100%;
      background: {surface}; border: 1px solid {border};
      border-radius: {radius}; padding: 18px 20px;
      box-shadow: {shadow};
    ">
      <div style="font-size: 14px; letter-spacing: 0.025em; color: {text2}; margin-bottom: 12px;">📋 청약 규제 정보</div>
      <div style="display: flex; flex-wrap: wrap; gap: 12px;">
        <div style="flex: 1 1 calc(33.33% - 8px); min-width: 110px;">
          <div style="font-size: 12px; color: {muted}; margin-bottom: 4px; letter-spacing: 0.5px;">투기과열지구</div>
          <div style="font-size: 14px; font-weight: 700; color: {text};">{hot_zone}</div>
        </div>
        <div style="flex: 1 1 calc(33.33% - 8px); min-width: 110px;">
          <div style="font-size: 12px; color: {muted}; margin-bottom: 4px; letter-spacing: 0.5px;">실거주 의무</div>
          <div style="font-size: 14px; font-weight: 700; color: {text};">{live_req}</div>
        </div>
        <div style="flex: 1 1 calc(33.33% - 8px); min-width: 110px;">
          <div style="font-size: 12px; color: {muted}; margin-bottom: 4px; letter-spacing: 0.5px;">전매제한</div>
          <div style="font-size: 14px; font-weight: 700; color: {text};">{resale}</div>
        </div>
      </div>
    </div>'''

# claude 테마 기준 색상값 (모든 기존 포스트가 claude 테마 사용)
CLAUDE_COLORS = {
    "surface": "#F5F2ED",
    "border": "#DED9D1",
    "radius": "10px",
    "shadow": "0 1px 4px rgba(44,40,37,0.07)",
    "text": "var(--c-dark)",    # CSS var only — 헤드 스타일에서 항상 정의됨
    "text2": "#6A635C",
    "muted": "#A39D96",
}

# ─── CSS 변수 치환 매핑 (claude 테마 기준) ───────────────────────────────────
# 포스트 바디의 하드코딩 hex → CSS var() 래퍼로 교체하여 팔레트 전환 반영
CSS_VAR_REWRITES = [
    # accent
    ("#CC5F3F", "var(--c-primary, #CC5F3F)"),
    ("#A84830", "var(--c-primary-dark, #A84830)"),
    ("#FDEEE8", "var(--c-primary-light, #FDEEE8)"),
    # bg / surface
    ("#FAF9F7", "var(--c-bg, #FAF9F7)"),
    # text
    ("#2C2825", "var(--c-dark, #2C2825)"),
    ("#6A635C", "var(--c-mid, #6A635C)"),
]


def _extract_resale_text(html: str) -> str:
    """기존 전매제한 안내 카드에서 텍스트 추출"""
    m = re.search(
        r'전매제한 안내</div>\s*<div[^>]*>(.*?)</div>',
        html, re.DOTALL
    )
    if m:
        txt = m.group(1).strip()
        if txt:
            return txt
    return ""


def patch_post(path: Path, dry_run: bool = False) -> bool:
    original = path.read_text(encoding="utf-8")
    html = original

    changed = False

    # ── [03] 모집공고문 버튼 제거 ────────────────────────────────────────────
    # "📋 모집공고문 바로가기" 또는 "📄 모집공고문 다운로드" 버튼 라인 제거
    new_html = re.sub(
        r'\n?[ \t]*<div style="margin-top:24px;text-align:center;">'
        r'<a href="[^"]*"[^>]*>(?:📋|📄)[^<]*(?:모집공고문|LH청약)[^<]*</a></div>',
        '',
        html
    )
    if new_html != html:
        html = new_html
        changed = True
        print(f"  [03] 모집공고문 버튼 제거")

    # ── [05] 전매제한 빈 내용 → 안내 문구 ────────────────────────────────────
    resale_text = _extract_resale_text(html)
    fallback = resale_text if resale_text else "공고문을 통해 전매제한 기간을 반드시 확인하세요."

    new_html = re.sub(
        r'(<div style="font-size: 15px; font-weight: 700; color: [^"]*; margin-bottom: 4px;">전매제한 안내</div>\s*'
        r'<div style="font-size: 16px; color: [^"]*;">)(</div>)',
        lambda m: m.group(1) + fallback + m.group(2),
        html
    )
    if new_html != html:
        html = new_html
        changed = True
        print(f"  [05] 전매제한 안내 문구 추가: {fallback[:40]}...")

    # ── [01a] apt_intro "N세대 규모로" → "N세대가 공급되며" ──────────────────
    new_html = re.sub(
        r'총\s*(\d[\d,]*)\s*세대\s*규모로',
        lambda m: f'총 {m.group(1)}세대가 공급되며',
        html
    )
    if new_html != html:
        html = new_html
        changed = True
        print(f"  [01a] apt_intro 규모로 → 공급되며 수정")

    # ── [01b] 네이버 N 사각형 SVG → 위치 핀 SVG ─────────────────────────────
    # 현재 패턴: <a href="..." ...><svg ...><rect fill="#03C75A"/>...</svg></a>
    # anchor href 추출 후 새 SVG로 교체
    naver_anchor_pattern = re.compile(
        r'<a href="(https://map\.naver\.com/[^"]*)"[^>]*title="네이버 지도에서 보기"[^>]*>.*?</a>',
        re.DOTALL
    )
    def replace_naver_anchor(m):
        href = m.group(1)
        return NEW_NAVER_PIN.format(href=href)

    new_html = naver_anchor_pattern.sub(replace_naver_anchor, html)
    if new_html != html:
        html = new_html
        changed = True
        print(f"  [01b] 네이버 위치 핀 SVG 교체")

    # ── [01c] 청약 규제 정보 카드 추가 ──────────────────────────────────────
    if "청약 규제 정보" not in html:
        # 규제 정보 카드는 공급 위치 카드 닫는 div 바로 다음 (~flex grid 닫기 직전)에 삽입
        # 패턴: 공급 위치 카드의 마지막 </div>\n    </div>\n\n  </div> 순서
        supply_card_end = re.compile(
            r'([ \t]*</div>\n[ \t]*</div>)\n(\n[ \t]*</div>\n</div>)',
            re.MULTILINE
        )
        # 전매제한 resale 텍스트 추출 (업데이트된 html에서)
        resale_in_card = _extract_resale_text(html)
        resale_display = resale_in_card if resale_in_card and resale_in_card != "공고문을 통해 전매제한 기간을 반드시 확인하세요." else "공고문 확인 필요"
        policy_card = POLICY_CARD_TEMPLATE.format(
            **CLAUDE_COLORS,
            hot_zone="공고문 확인 필요",
            live_req="공고문 확인 필요",
            resale=resale_display,
        )

        # 공급 위치 카드를 식별: "공급 위치</div>" 이후 첫 번째 패턴 교체
        # 더 안전한 방식: 단지 소개 섹션 끝(구분선 직전) 찾기
        # 구분선: <!-- 구분선 --> 직전 마지막 </div></div>에 삽입
        # 찾는 패턴: Section 1 마지막 flex grid 닫기
        section1_end = re.compile(
            r'([ \t]*</div>[ \t]*\n)([ \t]*</div>[ \t]*\n\n<!-- 구분선 -->)',
            re.MULTILINE
        )
        # 단지 소개 섹션의 flex grid 닫기 직전 패턴 (섹션 1 구분선 직전)
        # "01 · 단지 소개" 이후의 첫 번째 `  </div>\n</div>\n\n\n<!-- 구분선 -->`
        section1_pattern = re.compile(
            r'(01 · 단지 소개.*?)'   # 섹션1 시작
            r'([ \t]*</div>\n)(</div>\n\n\n<!-- 구분선 -->)',
            re.DOTALL
        )
        def insert_policy_card(m):
            return m.group(1) + policy_card + '\n\n' + m.group(2) + m.group(3)

        new_html = section1_pattern.sub(insert_policy_card, html, count=1)
        if new_html != html:
            html = new_html
            changed = True
            print(f"  [01c] 청약 규제 정보 카드 추가")
        else:
            print(f"  [01c] ⚠️ 청약 규제 정보 카드 삽입 패턴 미매칭")

    # ── [팔레트] accent 하드코딩 hex → CSS var() 참조 변환 ───────────────────
    # <style> 블록 이후의 포스트 바디 영역에서만 교체 (스타일 블록은 제외)
    style_end = html.find('</style>')
    if style_end == -1:
        body_start = 0
    else:
        body_start = style_end + len('</style>')

    head_part = html[:body_start]
    body_part = html[body_start:]

    palette_already_done = "var(--c-primary, #CC5F3F)" in body_part
    if not palette_already_done:
        for hex_val, css_var in CSS_VAR_REWRITES:
            new_body = body_part.replace(hex_val, css_var)
            if new_body != body_part:
                body_part = new_body
                changed = True

    new_html = head_part + body_part
    if new_html != html:
        html = new_html
        print(f"  [팔레트] accent 색상 CSS 변수 참조 변환")

    if not changed:
        print(f"  ─ 변경 없음")
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
