"""
build_index.py
──────────────────────────────────────────────
output/posts/*/post_meta.json 을 읽어
output/index.html 프론트페이지를 생성한다.

실행:
  python pipeline/build_index.py
"""

import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
OUTPUT_DIR = ROOT / "output"
POSTS_DIR  = OUTPUT_DIR / "posts"
OUT_FILE   = OUTPUT_DIR / "index.html"

# ── Anthropic 공식 브랜드 팔레트 ────────────────────
C = {
    "dark":       "#141413",
    "light":      "#faf9f5",
    "mid_gray":   "#b0aea5",
    "light_gray": "#e8e6dc",
    "orange":     "#d97757",
    "blue":       "#6a9bcc",
    "green":      "#788c5d",
    "orange_dark":  "#b85c38",
    "orange_light": "#fdf0ea",
    "green_dark":   "#57673f",
    "green_light":  "#edf2e6",
    "nav_bg":     "#2a2721",
    "footer_bg":  "#2a2721",
    "hero_bg":    "#f2efe6",
    "surface":    "#ffffff",
}


def load_posts() -> list[dict]:
    posts = []
    for meta_path in sorted(POSTS_DIR.glob("*/post_meta.json"), reverse=True):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            post_dir = meta_path.parent.name
            meta["post_url"] = f"posts/{post_dir}/post.html"
            if not meta.get("region_category"):
                from regions import region_name_to_category
                meta["region_category"] = region_name_to_category(meta.get("location", ""))
            if not meta.get("price_range"):
                meta["price_range"] = ""
            if "special_supply_date" not in meta:
                meta["special_supply_date"] = ""
            posts.append(meta)
        except Exception as e:
            print(f"  [경고] {meta_path} 파싱 실패: {e}")
    return posts


def _fmt_date(date_str: str) -> tuple[str, str]:
    """(월, 일) — 없으면 ('', '')"""
    if not date_str or date_str in ("-", "null", "None"):
        return ("", "")
    try:
        d = datetime.fromisoformat(date_str[:10])
        return (f"{d.month}월", f"{d.day}일")
    except Exception:
        return ("", "")


def _supply_info(title: str, apt_name: str) -> tuple[str, str, str, str]:
    """(label, header_grad, tag_bg, accent_color)"""
    combined = title + apt_name
    resupply = [
        ("무순위",   "무순위"),
        ("불법행위", "불법행위재공급"),
        ("임의",     "임의공급"),
        ("취소후",   "취소후재공급"),
        ("잔여",     "잔여세대"),
    ]
    for kw, label in resupply:
        if kw in combined:
            grad = f"linear-gradient(145deg,{C['green']} 0%,{C['green_dark']} 100%)"
            return label, grad, C["green_light"], C["green_dark"]
    grad = f"linear-gradient(145deg,{C['orange']} 0%,{C['orange_dark']} 100%)"
    return "신규분양", grad, C["orange_light"], C["orange_dark"]


def _date_cell(label: str, month: str, day: str, accent: str) -> str:
    """날짜 셀 — 월/일 숫자 크기 동일"""
    if not month:
        return (
            f'<div style="flex:1;padding:14px 16px;text-align:center;">'
            f'<p style="font-size:10px;font-weight:600;color:{C["mid_gray"]};'
            f'letter-spacing:1px;margin-bottom:8px;">{label}</p>'
            f'<p style="font-size:13px;color:{C["mid_gray"]};">미정</p>'
            f'</div>'
        )
    return (
        f'<div style="flex:1;padding:14px 16px;text-align:center;">'
        f'<p style="font-size:10px;font-weight:600;color:{C["mid_gray"]};'
        f'letter-spacing:1px;margin-bottom:8px;">{label}</p>'
        f'<p style="font-size:22px;font-weight:900;color:{accent};'
        f'line-height:1;letter-spacing:-0.5px;">'
        f'<span style="font-size:22px;">{month}</span>'
        f'<span style="font-size:22px;margin-left:3px;">{day}</span>'
        f'</p>'
        f'</div>'
    )


def _render_card(p: dict, serial: int) -> str:
    apt_name = p.get("apt_name", "(단지명 없음)")
    title    = p.get("title", apt_name)
    location = p.get("location", "")
    region   = p.get("region_category", "기타")
    url      = p["post_url"]
    tags     = (p.get("tags") or [])[:5]

    supply_label, header_grad, tag_bg, accent = _supply_info(title, apt_name)

    sp_month, sp_day   = _fmt_date(p.get("special_supply_date", ""))
    r1_month, r1_day   = _fmt_date(p.get("rank1_date", ""))

    serial_str = f"No.{serial:03d}"

    tag_items = "".join(
        f'<span style="display:inline-block;background:{tag_bg};color:{accent};'
        f'font-size:11px;font-weight:700;padding:3px 9px;border-radius:4px;'
        f'margin:0 5px 5px 0;letter-spacing:0.2px;">#{t}</span>'
        for t in tags
    )

    sp_cell = _date_cell("특별공급", sp_month, sp_day, accent)
    r1_cell = _date_cell("1순위", r1_month, r1_day, accent)

    return f"""<article
  class="post-card"
  data-region="{region}"
  onclick="location.href='{url}'"
>
  <!-- ── 카드 상단 헤더 ── -->
  <div class="card-header" style="background:{header_grad};">
    <!-- 도트 패턴 -->
    <div style="position:absolute;inset:0;
      background-image:radial-gradient(rgba(255,255,255,0.08) 1.5px,transparent 1.5px);
      background-size:18px 18px;pointer-events:none;"></div>

    <!-- ① 공급유형 + 시리얼 -->
    <div style="position:relative;display:flex;justify-content:space-between;
                align-items:center;margin-bottom:10px;">
      <span style="font-size:12px;font-weight:900;color:#fff;letter-spacing:0.3px;">
        {supply_label}
      </span>
      <span style="font-size:10px;font-weight:500;color:rgba(255,255,255,0.35);
                   letter-spacing:1px;">{serial_str}</span>
    </div>

    <!-- ② 지역 뱃지 -->
    <div style="position:relative;margin-bottom:12px;">
      <span style="display:inline-block;background:rgba(255,255,255,0.16);
                   border:1px solid rgba(255,255,255,0.26);border-radius:4px;
                   font-size:11px;font-weight:600;color:rgba(255,255,255,0.92);
                   padding:3px 10px;letter-spacing:0.3px;">📍 {region}</span>
    </div>

    <!-- ③ 단지명 (2줄 클램프) -->
    <p style="position:relative;font-size:15px;font-weight:800;color:#fff;
              line-height:1.4;word-break:keep-all;
              display:-webkit-box;-webkit-line-clamp:2;
              -webkit-box-orient:vertical;overflow:hidden;margin:0;">
      {apt_name}
    </p>
  </div>

  <!-- ── 카드 하단 ── -->

  <!-- ① 날짜 바 (특별공급 | 1순위) -->
  <div style="display:flex;border-bottom:1px solid {C['light_gray']};">
    {sp_cell}
    <div style="width:1px;background:{C['light_gray']};flex-shrink:0;margin:10px 0;"></div>
    {r1_cell}
  </div>

  <!-- ② 행정구역 -->
  <div style="padding:12px 16px;border-bottom:1px solid {C['light_gray']};">
    <p style="font-size:12px;color:{C['mid_gray']};margin:0;line-height:1.4;">
      📌 {location if location else "위치 정보 없음"}
    </p>
  </div>

  <!-- ③ 태그 -->
  <div style="padding:12px 16px 10px;flex:1;">
    {tag_items}
  </div>

  <!-- CTA -->
  <a href="{url}" class="card-cta" style="background:{accent};"
     onclick="event.stopPropagation()">
    공고 분석 전문 보기 →
  </a>
</article>"""


def build() -> None:
    import sys
    sys.path.insert(0, str(Path(__file__).parent))

    posts = load_posts()
    print(f"  포스트 {len(posts)}건 로드")

    regions      = ["전체"] + sorted({p.get("region_category", "기타") for p in posts if p.get("region_category")})
    total        = len(posts)
    region_count = len(regions) - 1

    region_tabs = "".join(
        f'<button class="tab-btn" data-region="{r}" '
        f'onclick="filterRegion(this,\'{r}\')">{r}</button>'
        for r in regions
    )
    cards_html = "".join(_render_card(p, i + 1) for i, p in enumerate(posts))

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>정과장의 청약노트 — 분양 공고 분석 모음</title>
<meta name="description" content="복잡한 청약 공고문을 쉽게 정리해 드리는 정과장의 청약노트. 전국 아파트 분양 공고 분석 모음.">
<style>
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: -apple-system, BlinkMacSystemFont, 'Apple SD Gothic Neo',
               'Malgun Gothic', '맑은 고딕', 'Noto Sans KR', sans-serif;
  background: {C['light']};
  color: {C['dark']};
  -webkit-text-size-adjust: 100%;
}}

/* ── 탭 ── */
.tab-btn {{
  flex-shrink: 0;
  padding: 7px 18px;
  border-radius: 6px;
  border: 1.5px solid {C['light_gray']};
  background: {C['surface']};
  color: {C['mid_gray']};
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 150ms;
  font-family: inherit;
}}
.tab-btn:hover  {{ border-color: {C['orange']}; color: {C['orange']}; }}
.tab-btn.active {{
  background: {C['orange']};
  color: #fff;
  border-color: {C['orange']};
  font-weight: 700;
}}

/* ── 그리드 ── */
.cards-grid {{
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 22px;
}}
@media (max-width: 960px) {{ .cards-grid {{ grid-template-columns: repeat(2, 1fr); }} }}
@media (max-width: 580px) {{ .cards-grid {{ grid-template-columns: 1fr; }} }}

/* ── 카드 ── */
.post-card {{
  background: {C['surface']};
  border-radius: 12px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  cursor: pointer;
  border: 1px solid {C['light_gray']};
  transition: transform 200ms ease, box-shadow 200ms ease;
}}
.post-card:hover {{
  transform: translateY(-4px);
  box-shadow: 0 12px 32px rgba(20,20,19,0.10);
}}
.post-card.hidden {{ display: none !important; }}

/* ── 카드 헤더 ── */
.card-header {{
  position: relative;
  padding: 16px 16px 18px;
  min-height: 130px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}}

/* ── CTA ── */
.card-cta {{
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 12px 16px;
  color: #fff;
  font-size: 13px;
  font-weight: 700;
  text-decoration: none;
  letter-spacing: 0.2px;
  transition: opacity 150ms;
  flex-shrink: 0;
}}
.card-cta:hover {{ opacity: 0.88; }}

/* ── 히어로 ── */
.hero-stripe {{
  position: absolute; inset: 0;
  background-image: repeating-linear-gradient(
    -55deg, transparent, transparent 28px,
    rgba(217,119,87,0.045) 28px, rgba(217,119,87,0.045) 29px
  );
  pointer-events: none;
}}

/* ── 빈 결과 ── */
#no-result {{ display:none; text-align:center; padding:80px 20px; color:{C['mid_gray']}; font-size:15px; }}
#no-result.show {{ display:block; }}
</style>
</head>
<body>

<!-- ══ 네비 ══ -->
<header style="background:{C['nav_bg']};padding:0 24px;position:sticky;top:0;z-index:50;
               border-bottom:2px solid {C['orange']};">
  <div style="max-width:1160px;margin:0 auto;display:flex;align-items:center;
              justify-content:space-between;height:54px;">
    <div style="display:flex;align-items:center;gap:10px;">
      <span style="display:inline-flex;align-items:center;justify-content:center;
                   width:30px;height:30px;background:{C['orange']};border-radius:6px;
                   font-size:15px;flex-shrink:0;">📝</span>
      <span style="color:{C['light']};font-size:15px;font-weight:800;letter-spacing:-0.3px;">
        정과장의 청약노트
      </span>
    </div>
    <a href="https://www.applyhome.co.kr/" target="_blank" rel="noopener"
       style="font-size:12px;color:{C['mid_gray']};text-decoration:none;
              border:1px solid #3d3a34;border-radius:6px;padding:5px 12px;
              transition:color 150ms;white-space:nowrap;"
       onmouseover="this.style.color='{C['orange']}'" onmouseout="this.style.color='{C['mid_gray']}'">
      청약홈 ↗
    </a>
  </div>
</header>


<!-- ══ 히어로 ══ -->
<section style="background:{C['hero_bg']};padding:72px 24px 68px;
                position:relative;overflow:hidden;">
  <div class="hero-stripe"></div>
  <div style="position:absolute;right:-60px;top:-60px;width:320px;height:320px;
              border-radius:50%;border:1px solid rgba(217,119,87,0.18);pointer-events:none;"></div>
  <div style="position:absolute;right:20px;top:20px;width:160px;height:160px;
              border-radius:50%;border:1px solid rgba(217,119,87,0.12);pointer-events:none;"></div>

  <div style="max-width:1160px;margin:0 auto;position:relative;">

    <div style="display:inline-flex;align-items:center;gap:8px;
                background:{C['orange_light']};border:1px solid rgba(217,119,87,0.3);
                border-radius:6px;padding:5px 14px;margin-bottom:24px;">
      <span style="width:7px;height:7px;background:{C['orange']};border-radius:50%;
                   display:inline-block;flex-shrink:0;"></span>
      <span style="font-size:11px;font-weight:700;color:{C['orange']};letter-spacing:1.5px;">
        청약 공고 분석 서비스
      </span>
    </div>

    <h1 style="font-size:clamp(28px,4.5vw,52px);font-weight:900;color:{C['dark']};
               line-height:1.18;margin-bottom:18px;word-break:keep-all;letter-spacing:-1.5px;">
      복잡한 청약 공고문,<br>
      <span style="color:{C['orange']};">정과장이 쉽게</span> 정리해 드립니다
    </h1>

    <p style="font-size:16px;color:{C['mid_gray']};line-height:1.75;
              max-width:460px;margin-bottom:44px;word-break:keep-all;">
      한국부동산원 청약홈 공개 데이터를 AI로 분석하여<br>
      분양가 · 일정 · 입지 · Q&amp;A를 한 눈에 확인하세요.
    </p>

    <!-- 통계 (분석공고 + 커버지역 — 최근 업데이트 제거) -->
    <div style="display:flex;flex-wrap:wrap;gap:12px;">
      <div style="background:{C['surface']};border:1px solid {C['light_gray']};
                  border-radius:10px;padding:18px 32px;text-align:center;">
        <div style="font-size:32px;font-weight:900;color:{C['orange']};letter-spacing:-1px;">
          {total}
        </div>
        <div style="font-size:12px;color:{C['mid_gray']};margin-top:4px;letter-spacing:0.3px;">
          분석 공고
        </div>
      </div>
      <div style="background:{C['surface']};border:1px solid {C['light_gray']};
                  border-radius:10px;padding:18px 32px;text-align:center;">
        <div style="font-size:32px;font-weight:900;color:{C['blue']};letter-spacing:-1px;">
          {region_count}
        </div>
        <div style="font-size:12px;color:{C['mid_gray']};margin-top:4px;letter-spacing:0.3px;">
          커버 지역
        </div>
      </div>
    </div>
  </div>
</section>

<div style="height:3px;background:linear-gradient(90deg,{C['orange']},{C['blue']},transparent);"></div>


<!-- ══ 메인 ══ -->
<main style="max-width:1160px;margin:0 auto;padding:44px 24px 100px;">

  <div style="display:flex;flex-wrap:wrap;align-items:flex-end;
              justify-content:space-between;gap:16px;margin-bottom:22px;">
    <div>
      <p style="font-size:10px;font-weight:700;color:{C['mid_gray']};
                letter-spacing:2px;margin-bottom:5px;">ANALYSIS REPORTS</p>
      <h2 style="font-size:22px;font-weight:800;color:{C['dark']};letter-spacing:-0.5px;">
        분양 공고 분석 모음
      </h2>
    </div>
    <p id="result-count" style="font-size:13px;color:{C['mid_gray']};">
      총 <strong style="color:{C['dark']};">{total}</strong>건
    </p>
  </div>

  <div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:32px;
              padding-bottom:24px;border-bottom:1px solid {C['light_gray']};">
    {region_tabs}
  </div>

  <div class="cards-grid" id="cards-grid">
    {cards_html}
  </div>
  <p id="no-result">해당 지역의 분석 공고가 없습니다.</p>

</main>


<!-- ══ 푸터 ══ -->
<footer style="background:{C['footer_bg']};padding:40px 24px;">
  <div style="max-width:1160px;margin:0 auto;">
    <div style="display:flex;flex-wrap:wrap;justify-content:space-between;
                gap:32px;padding-bottom:28px;
                border-bottom:1px solid rgba(255,255,255,0.07);">
      <div>
        <div style="display:flex;align-items:center;gap:9px;margin-bottom:12px;">
          <span style="display:inline-flex;align-items:center;justify-content:center;
                       width:28px;height:28px;background:{C['orange']};border-radius:6px;
                       font-size:14px;flex-shrink:0;">📝</span>
          <span style="color:{C['light']};font-size:14px;font-weight:800;">정과장의 청약노트</span>
        </div>
        <p style="font-size:13px;color:{C['mid_gray']};line-height:1.7;max-width:300px;">
          한국부동산원 청약홈 공개 정보를 바탕으로<br>AI가 분석한 분양 공고 리포트입니다.
        </p>
      </div>
      <div style="font-size:12px;color:#5a5750;line-height:2.2;">
        <p>📌 데이터 출처: 한국부동산원 청약홈 · 공공데이터포털</p>
        <p>📌 국토교통부 실거래가 공개시스템</p>
        <p>⚠️ 투자 권유가 아닌 정보 제공 목적입니다.</p>
      </div>
    </div>
    <p style="font-size:12px;color:#5a5750;margin-top:20px;">
      © 2026 정과장의 청약노트. 실제 청약은 반드시 공식 기관에서 확인하세요.
    </p>
  </div>
</footer>


<script>
function filterRegion(btn, region) {{
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  const cards = document.querySelectorAll('.post-card');
  let visible = 0;
  cards.forEach(card => {{
    const match = region === '전체' || card.dataset.region === region;
    card.classList.toggle('hidden', !match);
    if (match) visible++;
  }});
  document.getElementById('result-count').innerHTML =
    `총 <strong style="color:{C['dark']};">${{visible}}</strong>건`;
  document.getElementById('no-result').classList.toggle('show', visible === 0);
}}
document.querySelector('.tab-btn[data-region="전체"]').classList.add('active');
</script>

</body>
</html>"""

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(html, encoding="utf-8")
    print(f"✅ index.html 생성 완료: {OUT_FILE}  ({len(posts)}건)")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    build()
