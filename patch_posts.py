"""
patch_posts.py — 기존 11개 post.html 패치
  1. html 태그에 data-palette="A" 추가
  2. <head>에 Pretendard 폰트 + PALETTE_INIT_JS + PALETTE_CSS <style> 삽입
  3. <body> 태그 정리 + shared_nav 삽입
  4. </body> 전에 PALETTE_SWITCH_JS 삽입
  5. "정과장의 청약노트" div 삭제
  6. h1에서 <br>청약 핵심 정보 삭제
  7. 헤더 태그에서 📍 아이콘 삭제
  8. 위치 span에서 📍 아이콘 삭제
  9. "신규분양" → "공공분양" 또는 "민간분양"으로 교체
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "pipeline"))
from shared_ui import FONT_LINK, PALETTE_CSS, PALETTE_INIT_JS, PALETTE_SWITCH_JS, shared_nav

POSTS_DIR = Path(__file__).parent / "output" / "posts"

_PUBLIC_KW = ("공공분양", "공공임대", "행복주택", "국민임대", "lh", "sh공사",
              "경기주택", "인천도시공사", "주공", "공공지원")

RESUPPLY_KW = ("무순위", "불법행위", "임의공급", "취소후재공급", "잔여세대",
               "조합원취소")

NAV_HTML = shared_nav("../../")

HEAD_INJECT = f"""\
{FONT_LINK}
{PALETTE_INIT_JS}
<style>
{PALETTE_CSS}
body {{ margin: 0; padding: 0; background: var(--c-bg); }}
</style>"""

SCRIPT_INJECT = f"""<script>
{PALETTE_SWITCH_JS}
</script>"""


def _supply_label(apt_name: str) -> str:
    lo = apt_name.lower()
    for kw in RESUPPLY_KW:
        if kw in lo:
            return kw
    if any(kw in lo for kw in _PUBLIC_KW):
        return "공공분양"
    return "민간분양"


def patch(html: str, apt_name: str) -> str:
    # 1. html 태그 data-palette 추가
    html = re.sub(
        r'<html\s+lang="ko">',
        '<html lang="ko" data-palette="A">',
        html,
    )

    # 2. </head> 전에 FONT_LINK + PALETTE_INIT_JS + PALETTE_CSS 삽입
    #    (중복 방지: 이미 있으면 스킵)
    if "pretendardvariable" not in html:
        html = html.replace("</head>", f"{HEAD_INJECT}\n</head>", 1)

    # 3. <body ...> 정리 + shared_nav 삽입
    if "id=\"site-nav\"" not in html:
        # body 여는 태그 (style 포함 가능) → <body> + nav
        html = re.sub(
            r'<body[^>]*>',
            f'<body>\n{NAV_HTML}\n<div style="max-width:740px;margin:0 auto;padding:32px 16px 80px;">',
            html,
            count=1,
        )
        # </body> 전에 래퍼 닫기 + script 삽입
        html = html.replace("</body>", f"</div>\n{SCRIPT_INJECT}\n</body>", 1)

    # 4. "정과장의 청약노트" div 삭제
    html = re.sub(
        r'\s*<div[^>]*>\s*📝\s*정과장의 청약노트\s*</div>',
        '',
        html,
    )

    # 5. h1 에서 <br>청약 핵심 정보 삭제
    html = re.sub(r'<br\s*/?>\s*청약 핵심 정보', '', html)

    # 6. 헤더 태그 span에서 📍 삭제
    #    패턴: <span style="...">📍 지역명</span>
    html = re.sub(
        r'(>)\s*📍\s+([가-힣A-Za-z])',
        r'\1\2',
        html,
    )

    # 7. 위치 메타 span의 📍 삭제 (standalone 📍 <strong>)
    html = re.sub(
        r'📍\s+(<strong)',
        r'\1',
        html,
    )

    # 8. "신규분양" → 공공/민간분양 (헤더 span 텍스트만)
    label = _supply_label(apt_name)
    html = re.sub(
        r'(<span[^>]*>)\s*신규분양\s*(</span>)',
        rf'\g<1>{label}\2',
        html,
    )

    return html


def main():
    patched = 0
    for meta_path in sorted(POSTS_DIR.glob("*/post_meta.json")):
        import json
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        apt_name = meta.get("apt_name", meta_path.parent.name)

        post_path = meta_path.parent / "post.html"
        if not post_path.exists():
            continue

        original = post_path.read_text(encoding="utf-8")

        # 신규 save_post() 포맷 (site-nav 있음) → 정과장/핵심정보/아이콘만 정리
        if "id=\"site-nav\"" in original:
            html = original
            html = re.sub(r'\s*<div[^>]*>\s*📝\s*정과장의 청약노트\s*</div>', '', html)
            html = re.sub(r'<br\s*/?>\s*청약 핵심 정보', '', html)
            html = re.sub(r'(>)\s*📍\s+([가-힣A-Za-z])', r'\1\2', html)
            html = re.sub(r'📍\s+(<strong)', r'\1', html)
            label = _supply_label(apt_name)
            html = re.sub(r'(<span[^>]*>)\s*신규분양\s*(</span>)', rf'\g<1>{label}\2', html)
        else:
            html = patch(original, apt_name)

        if html != original:
            post_path.write_text(html, encoding="utf-8")
            print(f"  패치 완료: {post_path.parent.name}")
            patched += 1
        else:
            print(f"  변경 없음: {post_path.parent.name}")

    print(f"\n총 {patched}개 파일 패치됨.")


if __name__ == "__main__":
    main()
