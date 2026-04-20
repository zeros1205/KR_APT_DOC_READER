"""
build_index.py
──────────────────────────────────────────────
output/posts/*/post_meta.json 을 읽어
output/index.html 프론트페이지를 생성한다.

실행:
  python pipeline/build_index.py
"""

import json
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
OUTPUT_DIR = ROOT / "output"
POSTS_DIR  = OUTPUT_DIR / "posts"
OUT_FILE   = OUTPUT_DIR / "index.html"


def load_posts() -> list[dict]:
    posts = []
    for meta_path in sorted(POSTS_DIR.glob("*/post_meta.json"), reverse=True):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            post_dir = meta_path.parent.name
            meta["post_url"] = f"posts/{post_dir}/post.html"
            # 기존 메타(region_category 없는 경우) 보정
            if not meta.get("region_category"):
                loc = meta.get("location", "")
                from regions import region_name_to_category
                meta["region_category"] = region_name_to_category(loc)
            if not meta.get("price_range"):
                meta["price_range"] = ""
            posts.append(meta)
        except Exception as e:
            print(f"  [경고] {meta_path} 파싱 실패: {e}")
    return posts


def _fmt_date(date_str: str) -> str:
    if not date_str or date_str == "-":
        return "-"
    try:
        d = datetime.fromisoformat(date_str[:10])
        return f"{d.month}월 {d.day}일"
    except Exception:
        return date_str


def _supply_badge(title: str, apt_name: str) -> tuple[str, str]:
    """(label, color) — title/apt_name에서 공급 유형 감지"""
    combined = (title + apt_name).lower()
    for kw, label, color in [
        ("무순위",   "무순위",       "#6BAF2E"),
        ("불법행위", "불법행위재공급","#6BAF2E"),
        ("임의",     "임의공급",     "#6BAF2E"),
        ("취소후",   "취소후재공급", "#6BAF2E"),
        ("잔여",     "잔여세대",     "#6BAF2E"),
    ]:
        if kw in combined:
            return label, color
    return "신규분양", "#3B82F6"


def _render_card(p: dict) -> str:
    supply_label, supply_color = _supply_badge(p.get("title",""), p.get("apt_name",""))
    region = p.get("region_category", "기타")
    rank1  = _fmt_date(p.get("rank1_date", ""))
    price  = p.get("price_range", "")
    subtitle = p.get("subtitle", "")
    rank1_html = (
        f'<span style="font-size:12px;color:#9CA3AF;">📅 1순위 '
        f'<strong style="color:#374151;">{rank1}</strong></span>'
        if rank1 and rank1 != "-" else ""
    )
    price_html = (
        f'<span style="font-size:12px;color:#9CA3AF;">💰 '
        f'<strong style="color:#374151;">{price}</strong></span>'
        if price else ""
    )
    tags_html = "".join(
        f'<span style="display:inline-block;background:#EFF6FF;color:#3B82F6;'
        f'font-size:11px;font-weight:600;padding:2px 8px;border-radius:20px;'
        f'margin:0 4px 4px 0;">#{t}</span>'
        for t in (p.get("tags") or [])[:4]
    )
    return f"""
<article
  class="post-card"
  data-region="{region}"
  style="background:#fff;border:1px solid #E5E7EB;border-radius:16px;
         overflow:hidden;display:flex;flex-direction:column;
         transition:transform 200ms,box-shadow 200ms;cursor:pointer;"
  onclick="location.href='{p['post_url']}'"
>
  <!-- 카드 헤더 컬러 바 -->
  <div style="height:4px;background:linear-gradient(90deg,{supply_color},{supply_color}88);"></div>

  <div style="padding:20px 20px 16px;flex:1;display:flex;flex-direction:column;">
    <!-- 뱃지 행 -->
    <div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:12px;">
      <span style="display:inline-flex;align-items:center;gap:4px;background:{supply_color}18;
                   color:{supply_color};font-size:11px;font-weight:700;letter-spacing:0.5px;
                   padding:3px 10px;border-radius:20px;">
        {supply_label}
      </span>
      <span style="display:inline-flex;align-items:center;gap:3px;background:#F3F4F6;
                   color:#6B7280;font-size:11px;font-weight:600;padding:3px 10px;border-radius:20px;">
        📍 {region}
      </span>
    </div>

    <!-- 제목 -->
    <h3 style="font-size:16px;font-weight:800;color:#111827;margin:0 0 8px 0;
               line-height:1.45;word-break:keep-all;">
      {p.get('title','(제목 없음)')}
    </h3>

    <!-- 부제 -->
    <p style="font-size:13px;color:#6B7280;margin:0 0 14px 0;line-height:1.5;">
      {subtitle}
    </p>

    <!-- 태그 -->
    <div style="flex:1;">{tags_html}</div>

    <!-- 메타 정보 -->
    <div style="border-top:1px solid #F3F4F6;margin-top:14px;padding-top:12px;
                display:flex;flex-wrap:wrap;gap:10px;">
      {rank1_html}
      {price_html}
    </div>
  </div>

  <!-- 더 보기 링크 -->
  <a href="{p['post_url']}"
     style="display:block;text-align:center;padding:12px;background:#F9FAFB;
            color:#3B82F6;font-size:13px;font-weight:700;text-decoration:none;
            border-top:1px solid #E5E7EB;letter-spacing:0.3px;"
     onclick="event.stopPropagation()">
    공고 분석 보기 →
  </a>
</article>"""


def build() -> None:
    posts = load_posts()
    print(f"  포스트 {len(posts)}건 로드")

    regions = ["전체"] + sorted({p.get("region_category","기타") for p in posts if p.get("region_category")})
    region_tabs = "".join(
        f'<button class="tab-btn" data-region="{r}" '
        f'style="flex-shrink:0;padding:8px 18px;border-radius:24px;border:1.5px solid #E5E7EB;'
        f'background:{"#3B82F6" if r=="전체" else "#fff"};'
        f'color:{"#fff" if r=="전체" else "#6B7280"};'
        f'font-size:13px;font-weight:{"700" if r=="전체" else "500"};cursor:pointer;'
        f'transition:all 150ms;" onclick="filterRegion(this,\'{r}\')">{r}</button>'
        for r in regions
    )
    cards_html = "".join(_render_card(p) for p in posts)
    total = len(posts)
    region_count = len(regions) - 1  # 전체 제외
    latest = _fmt_date(posts[0].get("generated_at", "")) if posts else "-"

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
    background: #F8FAFC;
    color: #111827;
    -webkit-text-size-adjust: 100%;
  }}
  .post-card:hover {{
    transform: translateY(-3px);
    box-shadow: 0 8px 24px rgba(0,0,0,0.10);
  }}
  .tab-btn:hover {{ border-color: #3B82F6 !important; color: #3B82F6 !important; }}
  .tab-btn.active {{
    background: #3B82F6 !important;
    color: #fff !important;
    border-color: #3B82F6 !important;
    font-weight: 700 !important;
  }}
  .post-card.hidden {{ display: none !important; }}
  #no-result {{ display:none; text-align:center; padding:60px 20px; color:#9CA3AF; font-size:16px; }}
  #no-result.show {{ display:block; }}

  /* 그리드 */
  .cards-grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 20px;
  }}
  @media (max-width: 900px) {{
    .cards-grid {{ grid-template-columns: repeat(2, 1fr); }}
  }}
  @media (max-width: 560px) {{
    .cards-grid {{ grid-template-columns: 1fr; }}
  }}

  /* 히어로 내 패턴 */
  .hero-pattern {{
    position: absolute; inset: 0;
    background-image: radial-gradient(rgba(255,255,255,0.06) 1px, transparent 1px);
    background-size: 24px 24px;
    pointer-events: none;
  }}
</style>
</head>
<body>

<!-- ═══ 헤더 ═══ -->
<header style="background:#1E293B;padding:0 20px;">
  <div style="max-width:1100px;margin:0 auto;display:flex;align-items:center;
              justify-content:space-between;height:56px;">
    <span style="color:#fff;font-size:16px;font-weight:800;letter-spacing:-0.3px;">
      📝 정과장의 청약노트
    </span>
    <a href="https://apply.lh.or.kr" target="_blank" rel="noopener"
       style="font-size:12px;color:#94A3B8;text-decoration:none;">
      청약홈 바로가기 ↗
    </a>
  </div>
</header>


<!-- ═══ 히어로 ═══ -->
<section style="background:linear-gradient(135deg,#1D4ED8 0%,#1E40AF 50%,#1E3A8A 100%);
                padding:56px 20px 52px;position:relative;overflow:hidden;">
  <div class="hero-pattern"></div>
  <div style="max-width:1100px;margin:0 auto;position:relative;">

    <p style="font-size:13px;font-weight:700;color:#93C5FD;letter-spacing:2px;
              margin-bottom:14px;">CHEONG-YAK NOTE</p>

    <h1 style="font-size:clamp(28px,5vw,44px);font-weight:900;color:#fff;
               line-height:1.25;margin-bottom:16px;word-break:keep-all;letter-spacing:-0.5px;">
      복잡한 청약 공고문,<br>
      <span style="color:#93C5FD;">정과장이 쉽게 정리</span>해 드립니다
    </h1>

    <p style="font-size:16px;color:#BFDBFE;line-height:1.6;max-width:520px;margin-bottom:36px;">
      한국부동산원 청약홈 공개 데이터를 AI로 분석하여<br>
      분양가·일정·입지·Q&amp;A를 한 눈에 확인하세요.
    </p>

    <!-- 통계 카드 -->
    <div style="display:flex;flex-wrap:wrap;gap:16px;">
      <div style="background:rgba(255,255,255,0.12);border:1px solid rgba(255,255,255,0.2);
                  border-radius:14px;padding:16px 24px;min-width:120px;">
        <div style="font-size:28px;font-weight:900;color:#fff;">{total}</div>
        <div style="font-size:12px;color:#93C5FD;margin-top:2px;">분석 공고</div>
      </div>
      <div style="background:rgba(255,255,255,0.12);border:1px solid rgba(255,255,255,0.2);
                  border-radius:14px;padding:16px 24px;min-width:120px;">
        <div style="font-size:28px;font-weight:900;color:#fff;">{region_count}</div>
        <div style="font-size:12px;color:#93C5FD;margin-top:2px;">지역 커버</div>
      </div>
      <div style="background:rgba(255,255,255,0.12);border:1px solid rgba(255,255,255,0.2);
                  border-radius:14px;padding:16px 24px;min-width:120px;">
        <div style="font-size:16px;font-weight:800;color:#fff;">{latest}</div>
        <div style="font-size:12px;color:#93C5FD;margin-top:2px;">최근 업데이트</div>
      </div>
    </div>
  </div>
</section>


<!-- ═══ 메인 콘텐츠 ═══ -->
<main style="max-width:1100px;margin:0 auto;padding:40px 20px 80px;">

  <!-- 지역 필터 -->
  <div style="margin-bottom:28px;">
    <p style="font-size:13px;font-weight:600;color:#9CA3AF;letter-spacing:0.5px;
              margin-bottom:12px;">지역별 필터</p>
    <div style="display:flex;flex-wrap:wrap;gap:8px;">
      {region_tabs}
    </div>
  </div>

  <!-- 결과 수 -->
  <p id="result-count" style="font-size:13px;color:#9CA3AF;margin-bottom:20px;">
    총 <strong style="color:#374151;">{total}</strong>건
  </p>

  <!-- 카드 그리드 -->
  <div class="cards-grid" id="cards-grid">
    {cards_html}
  </div>
  <p id="no-result">해당 지역의 분석 공고가 없습니다.</p>

</main>


<!-- ═══ 푸터 ═══ -->
<footer style="background:#1E293B;padding:32px 20px;">
  <div style="max-width:1100px;margin:0 auto;">
    <div style="display:flex;flex-wrap:wrap;justify-content:space-between;
                align-items:flex-start;gap:20px;margin-bottom:20px;">
      <div>
        <p style="font-size:15px;font-weight:800;color:#fff;margin-bottom:6px;">
          📝 정과장의 청약노트
        </p>
        <p style="font-size:13px;color:#64748B;line-height:1.6;">
          한국부동산원 청약홈 공개 정보를 바탕으로 AI가 작성한 분석 리포트입니다.
        </p>
      </div>
      <div style="font-size:12px;color:#475569;line-height:1.8;">
        <p>📌 데이터 출처: 한국부동산원 청약홈 · 공공데이터포털</p>
        <p>⚠️ 투자 권유가 아닌 정보 제공 목적입니다.</p>
      </div>
    </div>
    <div style="border-top:1px solid #334155;padding-top:16px;">
      <p style="font-size:12px;color:#475569;">
        © 2026 정과장의 청약노트. 본 콘텐츠는 참고용이며 실제 청약은 공식 기관에서 확인하세요.
      </p>
    </div>
  </div>
</footer>


<script>
function filterRegion(btn, region) {{
  // 탭 활성화
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');

  // 카드 필터
  const cards = document.querySelectorAll('.post-card');
  let visible = 0;
  cards.forEach(card => {{
    const match = region === '전체' || card.dataset.region === region;
    card.classList.toggle('hidden', !match);
    if (match) visible++;
  }});

  // 결과 수 업데이트
  document.getElementById('result-count').innerHTML =
    `총 <strong style="color:#374151;">${{visible}}</strong>건`;

  // 결과 없음 메시지
  document.getElementById('no-result').classList.toggle('show', visible === 0);
}}

// 초기 탭 활성화
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
