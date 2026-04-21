"""
patch_posts6.py — 전체 11개 포스트 UI/UX 일괄 패치

변경 내용:
  1. 분양가 범위 카드: 타입명 내 소수점 4자리 → 1자리 반올림
  2. 입지 분석: 별점 행 제거, 본문 텍스트만 유지
  3. 공급위치 카드: 네이버 지도 아이콘(N) 우측 정렬로 재구성
  4. 모집공고문 다운로드 → 바로가기 + 청약홈 상세 URL로 교체
  5. 팔레트 B/C CSS: 새 디자인 색상 적용
  6. 팔레트 콘텐츠 반영: 메인 래퍼 id="post-wrap" + CSS override

실행: python patch_posts6.py
"""
import re
from pathlib import Path

POSTS_DIR = Path(__file__).parent / "output" / "posts"

# ── 청약홈 공고 상세 URL 맵 ────────────────────────────────────────
APPLYHOME_DETAIL = "https://www.applyhome.co.kr/ai/aia/selectSubscrptDetailView.do?houseManageNo={n}&pblancNo={n}"
LH_LIST = "https://apply.lh.or.kr/lhapply/apply/wt/wrtanc/selectWrtancList.do?mi=1027"

NOTICE_URLS = {
    "강릉 우미 린 더 프리미어":
        APPLYHOME_DETAIL.format(n="2026000089"),
    "경기광주역 롯데캐슬 시그니처 1단지":
        APPLYHOME_DETAIL.format(n="2026000107"),
    "고덕신도시 아테라 A-63블록 공공분양주택":
        APPLYHOME_DETAIL.format(n="2026000124"),
    "공덕역자이르네":
        APPLYHOME_DETAIL.format(n="2026000114"),
    "도안자이 센텀리체 2단지":
        APPLYHOME_DETAIL.format(n="2026000105"),
    "동탄 그웬 160 (동탄2 B11BL)":
        APPLYHOME_DETAIL.format(n="2026000113"),
    "두산위브더제니스 구미(조합원취소분)":
        "https://www.applyhome.co.kr/ai/aia/selectSubscrptListView.do",
    "문수로 라티에르 673":
        APPLYHOME_DETAIL.format(n="2026000121"),
    "엘리프 창원":
        APPLYHOME_DETAIL.format(n="2026000110"),
    "용인 고림 동문 디 이스트":
        APPLYHOME_DETAIL.format(n="2026000112"),
    "인천가정2지구 B2블록 공공분양주택(후속사업)":
        LH_LIST,
}

# ── 네이버 지도 아이콘 SVG ─────────────────────────────────────────
NAVER_ICON_A = """<a href="{url}" target="_blank" rel="noopener"
   title="네이버 지도에서 보기"
   style="flex-shrink:0;display:inline-flex;align-items:center;justify-content:center;
          width:38px;height:38px;border-radius:8px;text-decoration:none;transition:opacity 150ms;"
   onmouseover="this.style.opacity='0.8'" onmouseout="this.style.opacity='1'">
  <svg width="38" height="38" viewBox="0 0 38 38" fill="none" xmlns="http://www.w3.org/2000/svg">
    <rect width="38" height="38" rx="8" fill="#03C75A"/>
    <path d="M9 9v20h5.6l10.2-13.7V29H30V9h-5.6L14.2 22.7V9z" fill="white"/>
  </svg>
</a>"""

# ── 팔레트 B : Deep Crimson × Navy ───────────────────────────────
PALETTE_B_CSS = """/* ─── 팔레트 B : Deep Crimson × Navy ─── */
html[data-palette="B"] {
  --c-primary:        #c1121f;
  --c-primary-dark:   #780000;
  --c-primary-light:  #fde8e0;
  --c-primary-stripe: rgba(193,18,31,0.06);
  --c-accent:         #669bbc;
  --c-bg:             #fdf5ec;
  --c-surface:        #ffffff;
  --c-dark:           #003049;
  --c-mid:            #4e6e80;
  --c-light-gray:     #c8dbe8;
  --c-hero-bg:        #f5e8d5;
  --c-nav-bg:         #003049;
  --c-green:          #669bbc;
  --c-green-dark:     #3d7299;
  --c-green-light:    #e0eff7;
  --c-card-grad-new:        linear-gradient(145deg,#c1121f 0%,#780000 100%);
  --c-card-grad-resupply:   linear-gradient(145deg,#669bbc 0%,#3d7299 100%);
  --c-cta-bg:               #003049;
  --c-cta-hover:            #001e30;
  --c-tag-new-bg:           #fde8e0;
  --c-tag-new-text:         #780000;
  --c-tag-resupply-bg:      #e0eff7;
  --c-tag-resupply-text:    #3d7299;
}"""

# ── 팔레트 C : Punch Red × Oxford Navy ──────────────────────────
PALETTE_C_CSS = """/* ─── 팔레트 C : Punch Red × Oxford Navy ─── */
html[data-palette="C"] {
  --c-primary:        #e63946;
  --c-primary-dark:   #c22030;
  --c-primary-light:  #fce8ea;
  --c-primary-stripe: rgba(230,57,70,0.07);
  --c-accent:         #457b9d;
  --c-bg:             #f0f8fb;
  --c-surface:        #ffffff;
  --c-dark:           #1d3557;
  --c-mid:            #4a6a8a;
  --c-light-gray:     #a8dadc;
  --c-hero-bg:        #e4f3f8;
  --c-nav-bg:         #1d3557;
  --c-green:          #a8dadc;
  --c-green-dark:     #457b9d;
  --c-green-light:    #eaf6f8;
  --c-card-grad-new:        linear-gradient(145deg,#e63946 0%,#c22030 100%);
  --c-card-grad-resupply:   linear-gradient(145deg,#a8dadc 0%,#457b9d 100%);
  --c-cta-bg:               #1d3557;
  --c-cta-hover:            #0f2035;
  --c-tag-new-bg:           #fce8ea;
  --c-tag-new-text:         #c22030;
  --c-tag-resupply-bg:      #eaf6f8;
  --c-tag-resupply-text:    #457b9d;
}"""

# ── 팔레트 콘텐츠 반영용 CSS ─────────────────────────────────────
PALETTE_CONTENT_CSS = """/* ─── 팔레트 콘텐츠 반영 ─── */
#post-wrap { background: var(--c-bg) !important; }"""


def normalize_type_name(name: str) -> str:
    """'059.9880A' → '60.0A', '048.6543' → '48.7'"""
    def repl(m):
        area = round(float(m.group(1)), 1)
        suffix = m.group(2) or ""
        return f"{area:.1f}{suffix}"
    return re.sub(r'0*(\d+\.\d{2,}?)([A-Za-z타입]*)', repl, name)


def fix_price_range_typed(html: str) -> str:
    """분양가 범위 카드에서 타입명 소수점 정규화"""
    def repl(m):
        price = m.group(1)
        type_name = normalize_type_name(m.group(2))
        return f"{price}({type_name})"
    # Pattern: 금액(타입명) — price then (typename)
    return re.sub(r'([0-9억 ,~\-만원]+)\(([^)]+)\)', repl, html)


def remove_star_ratings(html: str) -> str:
    """별점 행 (★) 제거"""
    return re.sub(
        r'\s*<div style="font-size: 20px; font-weight: 800; color: [^;]+; margin-bottom: 8px; line-height: 1;">[★☆]+</div>',
        '',
        html,
    )


def fix_location_card(html: str, naver_url: str) -> str:
    """공급위치 카드: 기존 Naver 버튼 제거 → 우측 아이콘 레이아웃으로 재구성"""
    # 기존의 🗺️ 버튼 (href="...map.naver.com..." 포함된 a 태그) 제거
    html = re.sub(
        r'\s*<a\s+href="https://map\.naver\.com[^"]*"[^>]*>[\s\S]*?</a>',
        '',
        html,
        count=3,
    )

    # 공급 위치 카드 섹션 재구성
    # 현재 구조: label div + address div + scale div
    # 목표: label div + flex(address+scale | naver-icon)
    naver_icon = NAVER_ICON_A.format(url=naver_url)

    def restructure(m):
        label = m.group(1)   # "공급 위치" label div
        addr  = m.group(2)   # address div
        scale = m.group(3)   # scale div
        return (
            f'{label}\n'
            f'      <div style="display:flex;align-items:center;justify-content:space-between;gap:12px;">\n'
            f'        <div>\n'
            f'          {addr}\n'
            f'          {scale}\n'
            f'        </div>\n'
            f'        {naver_icon.strip()}\n'
            f'      </div>'
        )

    html = re.sub(
        r'(<div style="font-size: 14px;[^"]*"[^>]*>(?:📍 )?공급 위치</div>)\s*'
        r'(<div style="font-size: 16px;[^>]*>[^<]+</div>)\s*'
        r'(<div style="font-size: 14px;[^>]*>[^<]*</div>)',
        restructure,
        html,
        count=1,
        flags=re.DOTALL,
    )

    # v3.0 템플릿: flex 컨테이너는 있으나 naver 아이콘이 없는 경우 — 아이콘 삽입
    if '#03C75A' not in html:
        # 세대수 div 바로 뒤, 내부 wrapper </div> + flex container </div> 사이에 삽입
        html = re.sub(
            r'(세대</div>\s*</div>)(\s*</div>)',
            lambda m: m.group(1) + f'\n        {naver_icon.strip()}' + m.group(2),
            html,
            count=1,
            flags=re.DOTALL,
        )

    return html


def fix_notice_button(html: str, notice_url: str) -> str:
    """모집공고문 다운로드 → 바로가기 + 청약홈 URL"""
    # 기존 다운로드 버튼이 있으면 교체
    new_btn = (
        f'<div style="margin-top:24px;text-align:center;">'
        f'<a href="{notice_url}" target="_blank" rel="noopener noreferrer" '
        f'style="display:inline-flex;align-items:center;gap:8px;'
        f'background:var(--c-surface,#fff);color:var(--c-dark,#2c2925);'
        f'border:2px solid var(--c-primary,#d97757);'
        f'font-size:15px;font-weight:700;padding:12px 26px;border-radius:8px;'
        f'text-decoration:none;letter-spacing:-0.2px;'
        f'box-shadow:0 1px 4px rgba(0,0,0,0.08);transition:all 200ms;" '
        f'onmouseover="this.style.background=\'var(--c-primary,#d97757)\';this.style.color=\'#fff\'" '
        f'onmouseout="this.style.background=\'var(--c-surface,#fff)\';this.style.color=\'var(--c-dark,#2c2925)\'">'
        f'📋 모집공고문 바로가기</a></div>'
    )

    # 기존 다운로드 버튼 교체
    existing = re.search(
        r'<div style="margin-top:24px;text-align:center;"><a href="[^"]*"[^>]*>📄 모집공고문 다운로드</a></div>',
        html,
    )
    if existing:
        return html.replace(existing.group(0), new_btn)

    # 버튼이 없는 경우 타임라인 종료 직후에 삽입
    insert_after = re.search(r'</div>\s*<!--\s*end timeline\s*-->', html)
    if insert_after:
        pos = insert_after.end()
        return html[:pos] + '\n\n  ' + new_btn + '\n' + html[pos:]

    return html


def update_palette_bc(html: str) -> str:
    """팔레트 B/C CSS 업데이트"""
    # B 교체
    html = re.sub(
        r'/\* ─── 팔레트 B[^\*]*\*/\s*html\[data-palette="B"\]\s*\{[^}]+\}',
        PALETTE_B_CSS,
        html,
        flags=re.DOTALL,
    )
    # C 교체
    html = re.sub(
        r'/\* ─── 팔레트 C[^\*]*\*/\s*html\[data-palette="C"\]\s*\{[^}]+\}',
        PALETTE_C_CSS,
        html,
        flags=re.DOTALL,
    )
    return html


def add_palette_content_sync(html: str) -> str:
    """메인 래퍼에 id="post-wrap" 추가 + CSS override 삽입"""
    # CSS 추가 (이미 있으면 skip)
    if 'palette-content-sync' in html or '#post-wrap' in html:
        pass
    else:
        html = html.replace(
            'body { margin: 0; padding: 0; background: var(--c-bg); }',
            'body { margin: 0; padding: 0; background: var(--c-bg); }\n'
            + PALETTE_CONTENT_CSS,
        )

    # 메인 래퍼 div에 id 추가 (background: #FAF9F7 포함하는 첫 번째 div)
    if 'id="post-wrap"' not in html:
        html = re.sub(
            r'(<div style="\s*\n\s*background: #FAF9F7;)',
            r'<div id="post-wrap" style="\n  background: #FAF9F7;',
            html,
            count=1,
        )
    return html


def patch(html: str, apt_name: str) -> str:
    notice_url = NOTICE_URLS.get(apt_name, "https://www.applyhome.co.kr")
    naver_url  = _get_naver_url(html)

    html = fix_price_range_typed(html)
    html = remove_star_ratings(html)
    html = fix_location_card(html, naver_url)
    html = fix_notice_button(html, notice_url)
    html = update_palette_bc(html)
    html = add_palette_content_sync(html)
    return html


def _get_naver_url(html: str) -> str:
    """기존 Naver Maps URL 추출, 없으면 기본값"""
    m = re.search(r'href="(https://map\.naver\.com[^"]+)"', html)
    if m:
        return m.group(1)
    # 주소에서 URL 구성 (공급위치 div에서 추출)
    m2 = re.search(
        r'공급 위치</div>\s*<div[^>]*>([^<]+)</div>',
        html,
    )
    if m2:
        from urllib.parse import quote
        addr = m2.group(1).strip()
        return f"https://map.naver.com/v5/search/{quote(addr)}"
    return "https://map.naver.com"


def _extract_apt_name(html: str) -> str:
    """h1 텍스트에서 아파트명 추출 (br 앞까지)"""
    m = re.search(r'<h1[^>]*>\s*([\s\S]*?)\s*(?:<br|</h1>)', html)
    if m:
        return re.sub(r'\s+', ' ', m.group(1).strip())
    return ""


def main():
    import json
    patched = 0
    for post_path in sorted(POSTS_DIR.glob("*/post.html")):
        # post_meta.json이 있으면 우선 사용, 없으면 HTML에서 추출
        meta_path = post_path.parent / "post_meta.json"
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            apt_name = meta.get("apt_name", "")
        else:
            original_for_name = post_path.read_text(encoding="utf-8")
            apt_name = _extract_apt_name(original_for_name)

        original = post_path.read_text(encoding="utf-8")
        updated  = patch(original, apt_name)

        if updated != original:
            post_path.write_text(updated, encoding="utf-8")
            print(f"  패치 완료: {apt_name}")
            patched += 1
        else:
            print(f"  변경 없음: {apt_name}")

    print(f"\n총 {patched}개 파일 패치됨.")


if __name__ == "__main__":
    main()
