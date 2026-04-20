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

# ── Claude 디자인 컬러 팔레트 ──────────────────────
C = {
    "bg":          "#FAF9F7",   # 본문 배경 (따뜻한 크림)
    "hero_bg":     "#0D0E12",   # 히어로 배경 (거의 블랙)
    "nav_bg":      "#0D0E12",
    "orange":      "#DA7756",   # Claude 코랄 오렌지 (메인 액센트)
    "orange_dark": "#B85C38",
    "orange_light":"#FCEEE8",   # 오렌지 연한 배경
    "green":       "#3D7A1E",   # 재공급 계열
    "green_dark":  "#2D5E14",
    "green_light": "#EDF7E6",
    "card_bg":     "#FFFFFF",
    "border":      "#EAE8E4",
    "text":        "#1A1A1A",
    "text2":       "#4A4A4A",
    "muted":       "#8A8A8A",
    "footer_bg":   "#0D0E12",
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
            posts.append(meta)
        except Exception as e:
            print(f"  [경고] {meta_path} 파싱 실패: {e}")
    return posts


def _fmt_rank1(date_str: str) -> tuple[str, str]:
    if not date_str or date_str == "-":
        return ("", "")
    try:
        d = datetime.fromisoformat(date_str[:10])
        return (f"{d.month}월", f"{d.day}일")
    except Exception:
        return (date_str, "")


def _supply_info(title: str, apt_name: str) -> tuple[str, str, str, str, str]:
    """(label, header_grad, tag_bg, tag_color, cta_color)"""
    combined = title + apt_name
    resupply_keywords = [
        ("무순위",   "무순위"),
        ("불법행위", "불법행위재공급"),
        ("임의",     "임의공급"),
        ("취소후",   "취소후재공급"),
        ("잔여",     "잔여세대"),
    ]
    for kw, label in resupply_keywords:
        if kw in combined:
            grad = f"linear-gradient(140deg,{C['green']} 0%,{C['green_dark']} 100%)"
            return label, grad, C["green_light"], C["green"], C["green"]
    grad = f"linear-gradient(140deg,{C['orange']} 0%,{C['orange_dark']} 100%)"
    return "신규분양", grad, C["orange_light"], C["orange_dark"], C["orange"]


def _render_card(p: dict, serial: int) -> str:
    title    = p.get("title", "(제목 없음)")
    apt_name = p.get("apt_name", "")
    location = p.get("location", "")
    region   = p.get("region_category", "기타")
    price    = p.get("price_range", "")
    url      = p["post_url"]
    tags     = (p.get("tags") or [])[:4]

    supply_label, header_grad, tag_bg, tag_color, cta_color = _supply_info(title, apt_name)
    month, day = _fmt_rank1(p.get("rank1_date", ""))

    date_block = (
        f'<div style="margin-top:auto;padding-top:14px;">'
        f'<p style="font-size:10px;font-weight:600;color:rgba(255,255,255,0.5);'
        f'letter-spacing:1.5px;margin-bottom:4px;">1순위 청약</p>'
        f'<p style="font-size:26px;font-weight:900;color:#fff;line-height:1;letter-spacing:-0.5px;">'
        f'{month} <span style="font-size:34px;">{day}</span></p>'
        f'</div>'
        if month and day else ""
    )

    price_block = (
        f'<p style="font-size:14px;font-weight:800;color:{cta_color};'
        f'margin:0 0 16px 0;letter-spacing:-0.2px;">💰 {price}</p>'
        if price else
        '<div style="margin-bottom:16px;"></div>'
    )

    tag_items = "".join(
        f'<span style="display:inline-block;background:{tag_bg};color:{tag_color};'
        f'font-size:11px;font-weight:700;padding:3px 9px;border-radius:4px;'
        f'margin:0 5px 5px 0;letter-spacing:0.2px;">#{t}</span>'
        for t in tags
    )

    serial_str = f"No.{serial:03d}"

    return f"""<article
  class="post-card"
  data-region="{region}"
  onclick="location.href='{url}'"
>
  <div class="card-header" style="background:{header_grad};">
    <div style="position:absolute;inset:0;
      background-image:radial-gradient(rgba(255,255,255,0.07) 1.5px,transparent 1.5px);
      background-size:20px 20px;pointer-events:none;"></div>

    <div style="position:relative;display:flex;justify-content:space-between;align-items:flex-start;">
      <div>
        <p style="font-size:9px;font-weight:700;color:rgba(255,255,255,0.45);
                  letter-spacing:2px;margin-bottom:4px;text-transform:uppercase;">공급 유형</p>
        <p style="font-size:17px;font-weight:900;color:#fff;letter-spacing:-0.2px;line-height:1;">
          {supply_label}
        </p>
      </div>
      <span style="font-size:10px;font-weight:600;color:rgba(255,255,255,0.3);
                   letter-spacing:1px;">{serial_str}</span>
    </div>

    <div style="position:relative;margin-top:10px;">
      <span style="display:inline-block;
                   background:rgba(255,255,255,0.14);border:1px solid rgba(255,255,255,0.22);
                   border-radius:4px;font-size:11px;font-weight:600;
                   color:rgba(255,255,255,0.88);padding:3px 10px;">📍 {region}</span>
    </div>

    {date_block}
  </div>

  <div class="card-body">
    <p style="font-size:10px;font-weight:700;color:{C['muted']};letter-spacing:1.5px;
              margin-bottom:5px;text-transform:uppercase;">단지 분석</p>
    <h3 class="card-title">{title}</h3>
    <p style="font-size:13px;color:{C['muted']};margin:0 0 14px 0;line-height:1.5;">
      {location}
    </p>
    {price_block}
    <div style="flex:1;min-height:26px;">{tag_items}</div>
  </div>

  <a href="{url}" class="card-cta" style="background:{cta_color};"
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
    latest_raw   = posts[0].get("generated_at", "") if posts else ""
    try:
        ld = datetime.fromisoformat(latest_raw[:10])
        latest = f"{ld.year}.{ld.month:02d}.{ld.day:02d}"
    except Exception:
        latest = latest_raw[:10] if latest_raw else "-"

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
  background: {C['bg']};
  color: {C['text']};
  -webkit-text-size-adjust: 100%;
}}

/* ── 탭 ── */
.tab-btn {{
  flex-shrink: 0;
  padding: 7px 18px;
  border-radius: 6px;
  border: 1.5px solid {C['border']};
  background: {C['card_bg']};
  color: {C['muted']};
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
  background: {C['card_bg']};
  border-radius: 12px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  cursor: pointer;
  border: 1px solid {C['border']};
  transition: transform 200ms ease, box-shadow 200ms ease;
}}
.post-card:hover {{
  transform: translateY(-4px);
  box-shadow: 0 14px 36px rgba(0,0,0,0.11);
}}
.post-card.hidden {{ display: none !important; }}

.card-header {{
  position: relative;
  padding: 20px 20px 18px;
  min-height: 158px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}}
.card-body {{
  padding: 18px 20px 14px;
  flex: 1;
  display: flex;
  flex-direction: column;
  border-bottom: 1px solid {C['border']};
}}
.card-title {{
  font-size: 15px;
  font-weight: 800;
  color: {C['text']};
  line-height: 1.45;
  margin: 0 0 8px 0;
  word-break: keep-all;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}}
.card-cta {{
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 13px 20px;
  color: #fff;
  font-size: 13px;
  font-weight: 700;
  text-decoration: none;
  letter-spacing: 0.2px;
  transition: opacity 150ms;
}}
.card-cta:hover {{ opacity: 0.88; }}

/* ── 히어로 ── */
.hero-dots {{
  position: absolute; inset: 0;
  background-image: radial-gradient(rgba(255,255,255,0.06) 1px, transparent 1px);
  background-size: 22px 22px;
  pointer-events: none;
}}

/* ── 빈 결과 ── */
#no-result {{ display:none; text-align:center; padding:80px 20px; color:{C['muted']}; font-size:15px; }}
#no-result.show {{ display:block; }}
</style>
</head>
<body>

<!-- ══ 네비 ══ -->
<header style="background:{C['nav_bg']};padding:0 24px;position:sticky;top:0;z-index:50;
               border-bottom:1px solid #1E2028;">
  <div style="max-width:1160px;margin:0 auto;display:flex;align-items:center;
              justify-content:space-between;height:54px;">
    <div style="display:flex;align-items:center;gap:10px;">
      <span style="display:inline-flex;align-items:center;justify-content:center;
                   width:30px;height:30px;background:{C['orange']};border-radius:6px;
                   font-size:15px;flex-shrink:0;">📝</span>
      <span style="color:#fff;font-size:15px;font-weight:800;letter-spacing:-0.3px;">
        정과장의 청약노트
      </span>
    </div>
    <a href="https://apply.lh.or.kr" target="_blank" rel="noopener"
       style="font-size:12px;color:#64748B;text-decoration:none;
              border:1px solid #2A2D36;border-radius:6px;padding:5px 12px;
              transition:color 150ms;white-space:nowrap;"
       onmouseover="this.style.color='#DA7756'" onmouseout="this.style.color='#64748B'">
      청약홈 바로가기 ↗
    </a>
  </div>
</header>


<!-- ══ 히어로 ══ -->
<section style="background:{C['hero_bg']};padding:64px 24px 60px;
                position:relative;overflow:hidden;">
  <div class="hero-dots"></div>

  <!-- 배경 장식 원 -->
  <div style="position:absolute;right:-80px;top:-80px;width:360px;height:360px;
              border-radius:50%;background:radial-gradient(circle,rgba(218,119,86,0.12) 0%,transparent 70%);
              pointer-events:none;"></div>

  <div style="max-width:1160px;margin:0 auto;position:relative;">

    <!-- 뱃지 -->
    <div style="display:inline-flex;align-items:center;gap:8px;
                background:rgba(218,119,86,0.15);
                border:1px solid rgba(218,119,86,0.35);
                border-radius:6px;padding:5px 14px;margin-bottom:22px;">
      <span style="width:6px;height:6px;background:{C['orange']};border-radius:50%;
                   display:inline-block;flex-shrink:0;"></span>
      <span style="font-size:11px;font-weight:700;color:{C['orange']};letter-spacing:1.5px;">
        청약 공고 분석 서비스
      </span>
    </div>

    <h1 style="font-size:clamp(28px,4.5vw,48px);font-weight:900;color:#fff;
               line-height:1.2;margin-bottom:16px;word-break:keep-all;letter-spacing:-1px;">
      복잡한 청약 공고문,<br>
      <span style="color:{C['orange']};">정과장이 쉽게 정리</span>해 드립니다
    </h1>

    <p style="font-size:15px;color:#8A8EA0;line-height:1.75;
              max-width:460px;margin-bottom:44px;word-break:keep-all;">
      한국부동산원 청약홈 공개 데이터를 AI로 분석하여<br>
      분양가 · 일정 · 입지 · Q&amp;A를 한 눈에 확인하세요.
    </p>

    <!-- 통계 바 -->
    <div style="display:inline-flex;border:1px solid #23262F;border-radius:10px;
                overflow:hidden;background:#13151A;">
      <div style="padding:16px 28px;border-right:1px solid #23262F;text-align:center;">
        <div style="font-size:28px;font-weight:900;color:#fff;letter-spacing:-1px;">{total}</div>
        <div style="font-size:11px;color:#4A5060;margin-top:3px;letter-spacing:0.5px;">분석 공고</div>
      </div>
      <div style="padding:16px 28px;border-right:1px solid #23262F;text-align:center;">
        <div style="font-size:28px;font-weight:900;color:#fff;letter-spacing:-1px;">{region_count}</div>
        <div style="font-size:11px;color:#4A5060;margin-top:3px;letter-spacing:0.5px;">커버 지역</div>
      </div>
      <div style="padding:16px 28px;text-align:center;">
        <div style="font-size:15px;font-weight:800;color:#fff;margin-top:5px;">{latest}</div>
        <div style="font-size:11px;color:#4A5060;margin-top:3px;letter-spacing:0.5px;">최근 업데이트</div>
      </div>
    </div>

  </div>
</section>


<!-- ══ 메인 ══ -->
<main style="max-width:1160px;margin:0 auto;padding:44px 24px 100px;">

  <!-- 섹션 헤더 -->
  <div style="display:flex;flex-wrap:wrap;align-items:flex-end;
              justify-content:space-between;gap:16px;margin-bottom:22px;">
    <div>
      <p style="font-size:10px;font-weight:700;color:{C['muted']};
                letter-spacing:2px;margin-bottom:5px;">ANALYSIS REPORTS</p>
      <h2 style="font-size:20px;font-weight:800;color:{C['text']};letter-spacing:-0.3px;">
        분양 공고 분석 모음
      </h2>
    </div>
    <p id="result-count" style="font-size:13px;color:{C['muted']};">
      총 <strong style="color:{C['text2']};">{total}</strong>건
    </p>
  </div>

  <!-- 지역 필터 탭 -->
  <div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:32px;
              padding-bottom:24px;border-bottom:1px solid {C['border']};">
    {region_tabs}
  </div>

  <!-- 카드 그리드 -->
  <div class="cards-grid" id="cards-grid">
    {cards_html}
  </div>
  <p id="no-result">해당 지역의 분석 공고가 없습니다.</p>

</main>


<!-- ══ 푸터 ══ -->
<footer style="background:{C['footer_bg']};padding:40px 24px;">
  <div style="max-width:1160px;margin:0 auto;">
    <div style="display:flex;flex-wrap:wrap;justify-content:space-between;
                gap:32px;padding-bottom:28px;border-bottom:1px solid #1E2028;">
      <div>
        <div style="display:flex;align-items:center;gap:9px;margin-bottom:12px;">
          <span style="display:inline-flex;align-items:center;justify-content:center;
                       width:28px;height:28px;background:{C['orange']};border-radius:6px;
                       font-size:14px;flex-shrink:0;">📝</span>
          <span style="color:#fff;font-size:14px;font-weight:800;">정과장의 청약노트</span>
        </div>
        <p style="font-size:13px;color:#4A5060;line-height:1.7;max-width:300px;">
          한국부동산원 청약홈 공개 정보를 바탕으로<br>AI가 분석한 분양 공고 리포트입니다.
        </p>
      </div>
      <div style="font-size:12px;color:#3A3E4A;line-height:2.2;">
        <p>📌 데이터 출처: 한국부동산원 청약홈 · 공공데이터포털</p>
        <p>📌 국토교통부 실거래가 공개시스템</p>
        <p>⚠️ 투자 권유가 아닌 정보 제공 목적입니다.</p>
      </div>
    </div>
    <p style="font-size:12px;color:#3A3E4A;margin-top:20px;">
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
    `총 <strong style="color:{C['text2']};">${{visible}}</strong>건`;
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
