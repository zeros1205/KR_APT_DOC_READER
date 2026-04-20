"""
patch_posts2.py — 기존 11개 post.html 2차 패치
  1. <title> → '정과장의 청약노트'
  2. 헤더 flex 메타 div → 세로 배치 (데이터 없으면 행 숨김)
  3. 분양가 단위 오류 수정 (X억원 → 올바른 금액, 잘못된 만원 수정)
  4. area_sqm .2f → .1f (전용면적 소수점 한 자리)
"""
import re
import json
from pathlib import Path

POSTS_DIR = Path(__file__).parent / "output" / "posts"

SITE_NAME = "정과장의 청약노트"


# ── 금액 단위 보정 ──────────────────────────────────────────
def _fmt_manwon(n: int) -> str:
    uk = n // 10000
    man = n % 10000
    if uk > 0 and man > 0:
        return f"{uk}억 {man:,}만원"
    if uk > 0:
        return f"{uk}억원"
    return f"{man:,}만원"


def _fix_price_str(m) -> str:
    """'56200억원' → '5억 6,200만원' (억 숫자가 9999 초과 = 잘못된 원 단위)"""
    n = int(m.group(1).replace(",", ""))
    if n > 9999:
        return _fmt_manwon(n)
    return m.group(0)


def _fix_large_manwon(m) -> str:
    """'22,363,519만원' → '2,236만원' (3.3㎡당 잘못된 단위 — / 10000 보정)"""
    n = int(m.group(1).replace(",", ""))
    if n > 100_000:
        return f"{n // 10000:,}만원"
    return m.group(0)


# ── 헤더 메타 rows 빌더 ────────────────────────────────────
def _build_meta_rows(special: str, rank1: str, rank2: str, location: str) -> str:
    sub = "rgba(255,255,255,0.78)"
    strong = "#FFFFFF"
    rows = []
    for label, val in [
        ("특별공급", special),
        ("일반공급(1순위)", rank1),
        ("일반공급(2순위)", rank2),
        ("주소", location),
    ]:
        v = val.strip() if val else ""
        if not v:
            continue
        rows.append(
            f'<div style="margin-bottom:5px;">'
            f'<span style="color:{sub};font-size:13px;">{label}: </span>'
            f'<strong style="color:{strong};font-size:14px;">{v}</strong>'
            f'</div>'
        )
    return "\n    ".join(rows)


def patch(html: str, meta: dict) -> str:
    # 1. <title>
    html = re.sub(r'<title>[^<]*</title>', f'<title>{SITE_NAME}</title>', html)

    # 2. 헤더 flex 메타 div → 세로 배치
    flex_pat = re.compile(
        r'<div style="display: flex; flex-wrap: wrap; gap: 14px;">'
        r'\s*<span[^>]*>\s*📅 특별공급:.*?</div>',
        re.DOTALL,
    )
    m = flex_pat.search(html)
    if m:
        inner = m.group(0)
        # 값 추출
        special = ""
        rank1 = ""
        loc = ""
        s = re.search(r'특별공급:\s*<strong[^>]*>(.*?)</strong>', inner, re.DOTALL)
        if s:
            special = re.sub(r'<[^>]+>', '', s.group(1)).strip()
        r1 = re.search(r'1순위:\s*<strong[^>]*>(.*?)</strong>', inner, re.DOTALL)
        if r1:
            rank1 = re.sub(r'<[^>]+>', '', r1.group(1)).strip()
        # last strong = location
        locs = re.findall(r'<strong[^>]*>(.*?)</strong>', inner, re.DOTALL)
        if locs:
            loc = re.sub(r'<[^>]+>', '', locs[-1]).strip()

        # rank2 from meta
        rank2 = meta.get("rank2_date", "")
        if rank2 in ("-", "None", "null", None):
            rank2 = ""

        new_rows = _build_meta_rows(special, rank1, rank2, loc)
        html = html.replace(m.group(0), new_rows)

    # 3. 분양가 단위 수정
    #    a) 'X억원' where X > 9999
    html = re.sub(r'([\d,]+)억원', _fix_price_str, html)
    #    b) 잘못된 큰 만원 숫자 (3.3㎡당 등)
    html = re.sub(r'([\d,]{7,})만원', _fix_large_manwon, html)

    # 4. area_sqm 소수점 2자리 → 1자리
    #    (?!\d) 로 4자리 소수(타입코드 059.9010 등) 제외
    def round_area(m2):
        val = float(m2.group(1))
        return f"{round(val, 1):.1f}"
    html = re.sub(r'(\d{2,3}\.\d{2})(?!\d)', round_area, html)

    return html


def main():
    patched = 0
    for meta_path in sorted(POSTS_DIR.glob("*/post_meta.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        post_path = meta_path.parent / "post.html"
        if not post_path.exists():
            continue

        original = post_path.read_text(encoding="utf-8")
        updated = patch(original, meta)
        if updated != original:
            post_path.write_text(updated, encoding="utf-8")
            print(f"  패치 완료: {post_path.parent.name}")
            patched += 1
        else:
            print(f"  변경 없음: {post_path.parent.name}")

    print(f"\n총 {patched}개 파일 패치됨.")


if __name__ == "__main__":
    main()
