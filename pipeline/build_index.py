"""
build_index.py
──────────────────────────────────────────────
output/posts/*/post.html 을 읽어
output/index.html 프론트페이지를 생성한다.

정렬: rank1_date 기준 최신순 (모집공고일 proxy)
표시: 한 페이지 최대 12건, JS 페이지네이션
검색: 단지명 검색창 (탭 메뉴 하단)

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

POSTS_PER_PAGE = 12


def _extract_meta_from_html(html: str) -> dict:
    """post_meta.json 없는 포스트에서 메타데이터를 HTML로 추출"""
    meta = {}

    # apt_name — h1 에서 <br> 또는 </h1> 앞까지
    m = re.search(r'<h1[^>]*>\s*([\s\S]*?)(?:<br|</h1>)', html)
    meta["apt_name"] = re.sub(r'\s+', ' ', m.group(1).strip()) if m else ""
    meta["title"]    = meta["apt_name"]

    # rank1_date — 타임라인 "1순위 청약" 블록 날짜
    m = re.search(r'1순위 청약.*?>(20\d{2}-\d{2}-\d{2})<', html, re.DOTALL)
    meta["rank1_date"] = m.group(1) if m else ""

    # location — 공급 위치 카드
    m = re.search(
        r'공급 위치</div>.*?<div[^>]*font-size: 16px[^>]*>([^<]+)</div>',
        html, re.DOTALL,
    )
    meta["location"] = m.group(1).strip() if m else ""

    # SEO tags
    seo_idx = html.rfind("SEO")
    meta["tags"] = (
        re.findall(r'>#([^<]+)</span>', html[seo_idx : seo_idx + 3000])[:10]
        if seo_idx > 0 else []
    )

    # price_range — "X억 ~ Y억원" 패턴
    m = re.search(r'(\d+억[^\S\n]*[~\-][^\S\n]*\d+억[만원]*)', html)
    meta["price_range"] = m.group(1).strip() if m else ""

    return meta


def load_posts() -> list[dict]:
    import sys
    sys.path.insert(0, str(Path(__file__).parent))

    posts = []
    for post_path in POSTS_DIR.glob("*/post.html"):
        dir_path  = post_path.parent
        meta_path = dir_path / "post_meta.json"
        try:
            if meta_path.exists():
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            else:
                html = post_path.read_text(encoding="utf-8")
                meta = _extract_meta_from_html(html)

            meta["post_url"] = f"posts/{dir_path.name}/post.html"

            if not meta.get("region_category"):
                from regions import region_name_to_category
                meta["region_category"] = region_name_to_category(
                    meta.get("location", "")
                )
            if not meta.get("price_range"):
                meta["price_range"] = ""

            posts.append(meta)
        except Exception as e:
            print(f"  [경고] {dir_path} 파싱 실패: {e}")

    # 모집공고일 proxy = rank1_date, 내림차순 (최신순)
    posts.sort(
        key=lambda p: p.get("rank1_date", "") or p.get("notice_date", ""),
        reverse=True,
    )
    return posts


def _fmt_rank1(date_str: str) -> tuple[str, str]:
    if not date_str or date_str == "-":
        return ("", "")
    try:
        d = datetime.fromisoformat(date_str[:10])
        return (f"{d.month}월", f"{d.day}일")
    except Exception:
        return (date_str, "")


def _supply_info(title: str, apt_name: str) -> tuple[str, str, str, str]:
    combined = title + apt_name
    for kw, label, grad, tbg, tc in [
        ("무순위",   "무순위",        "linear-gradient(140deg,#3D7A1E 0%,#2D5E14 60%,#1E3F0D 100%)", "#D1FAE5", "#065F46"),
        ("불법행위", "불법행위재공급", "linear-gradient(140deg,#3D7A1E 0%,#2D5E14 60%,#1E3F0D 100%)", "#D1FAE5", "#065F46"),
        ("임의",     "임의공급",      "linear-gradient(140deg,#3D7A1E 0%,#2D5E14 60%,#1E3F0D 100%)", "#D1FAE5", "#065F46"),
        ("취소후",   "취소후재공급",  "linear-gradient(140deg,#3D7A1E 0%,#2D5E14 60%,#1E3F0D 100%)", "#D1FAE5", "#065F46"),
        ("잔여",     "잔여세대",      "linear-gradient(140deg,#3D7A1E 0%,#2D5E14 60%,#1E3F0D 100%)", "#D1FAE5", "#065F46"),
    ]:
        if kw in combined:
            return label, grad, tbg, tc
    return (
        "신규분양",
        "linear-gradient(140deg,#1D4ED8 0%,#1E40AF 60%,#1E3A8A 100%)",
        "#DBEAFE", "#1D4ED8",
    )


def _render_card(p: dict, serial: int) -> str:
    title    = p.get("title", "(제목 없음)")
    apt_name = p.get("apt_name", "")
    location = p.get("location", "")
    region   = p.get("region_category", "기타")
    price    = p.get("price_range", "")
    url      = p["post_url"]
    tags     = (p.get("tags") or [])[:4]

    supply_label, header_grad, tag_bg, tag_color = _supply_info(title, apt_name)
    month, day = _fmt_rank1(p.get("rank1_date", ""))

    if month and day:
        date_block = (
            '<div style="margin-top:auto;padding-top:12px;">'
            '<p style="font-size:11px;font-weight:600;color:rgba(255,255,255,0.55);'
            'letter-spacing:1.5px;margin-bottom:4px;">1순위 청약</p>'
            f'<p style="font-size:28px;font-weight:900;color:#fff;line-height:1;'
            f'letter-spacing:-0.5px;">{month} <span style="font-size:36px;">{day}</span></p>'
            '</div>'
        )
    else:
        date_block = ""

    price_block = (
        f'<p style="font-size:15px;font-weight:800;color:#1D4ED8;margin:0 0 16px 0;'
        f'letter-spacing:-0.3px;">💰 {price}</p>'
        if price else
        '<div style="margin-bottom:16px;"></div>'
    )

    tag_items = "".join(
        f'<span style="display:inline-block;background:{tag_bg};color:{tag_color};'
        f'font-size:11px;font-weight:700;padding:3px 9px;border-radius:4px;'
        f'margin:0 5px 5px 0;letter-spacing:0.3px;">#{t}</span>'
        for t in tags
    )

    serial_str = f"No.{serial:03d}"
    # apt_name을 소문자/공백 정규화 → 검색용 data 속성
    search_val = apt_name.replace('"', '&quot;')

    return f"""<article
  class="post-card"
  data-region="{region}"
  data-apt-name="{search_val}"
  onclick="location.href='{url}'"
>
  <div class="card-header" style="background:{header_grad};">
    <div style="position:absolute;inset:0;
      background-image:radial-gradient(rgba(255,255,255,0.08) 1.5px,transparent 1.5px);
      background-size:18px 18px;pointer-events:none;"></div>

    <div style="position:relative;display:flex;justify-content:space-between;align-items:flex-start;">
      <div>
        <p style="font-size:10px;font-weight:700;color:rgba(255,255,255,0.5);
                  letter-spacing:2px;margin-bottom:5px;">SUPPLY TYPE</p>
        <p style="font-size:18px;font-weight:900;color:#fff;letter-spacing:-0.3px;
                  line-height:1;">{supply_label}</p>
      </div>
      <span style="font-size:10px;font-weight:700;color:rgba(255,255,255,0.35);
                   letter-spacing:1px;">{serial_str}</span>
    </div>

    <div style="position:relative;margin-top:10px;">
      <span style="display:inline-block;background:rgba(255,255,255,0.15);
                   border:1px solid rgba(255,255,255,0.25);border-radius:4px;
                   font-size:11px;font-weight:700;color:rgba(255,255,255,0.9);
                   padding:3px 10px;letter-spacing:0.5px;">📍 {region}</span>
    </div>

    {date_block}
  </div>

  <div class="card-body">
    <p style="font-size:11px;font-weight:600;color:#9CA3AF;letter-spacing:1px;
              margin-bottom:6px;">COMPLEX</p>
    <h3 class="card-title">{title}</h3>
    <p style="font-size:13px;color:#6B7280;margin:0 0 14px 0;">{location}</p>
    {price_block}
    <div style="flex:1;min-height:28px;">{tag_items}</div>
  </div>

  <a href="{url}" class="card-cta" onclick="event.stopPropagation()">
    공고 분석 전문 보기
    <span style="margin-left:6px;font-size:16px;">→</span>
  </a>
</article>"""


def build() -> None:
    import sys
    sys.path.insert(0, str(Path(__file__).parent))

    posts = load_posts()
    print(f"  포스트 {len(posts)}건 로드")

    regions      = ["전체"] + sorted({p.get("region_category","기타") for p in posts if p.get("region_category")})
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
  background: #F1F5F9;
  color: #111827;
  -webkit-text-size-adjust: 100%;
}}

.tab-btn {{
  flex-shrink: 0;
  padding: 7px 18px;
  border-radius: 6px;
  border: 1.5px solid #CBD5E1;
  background: #fff;
  color: #64748B;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 150ms;
  font-family: inherit;
}}
.tab-btn:hover  {{ border-color: #1D4ED8; color: #1D4ED8; background: #EFF6FF; }}
.tab-btn.active {{ background: #1D4ED8; color: #fff; border-color: #1D4ED8; font-weight: 700; }}

.search-input {{
  width: 100%;
  max-width: 400px;
  padding: 10px 16px;
  border: 1.5px solid #CBD5E1;
  border-radius: 8px;
  font-size: 14px;
  color: #0F172A;
  background: #fff;
  outline: none;
  font-family: inherit;
  transition: border-color 150ms, box-shadow 150ms;
}}
.search-input:focus {{
  border-color: #1D4ED8;
  box-shadow: 0 0 0 3px rgba(29,78,216,0.12);
}}

.cards-grid {{
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 24px;
}}
@media (max-width: 960px)  {{ .cards-grid {{ grid-template-columns: repeat(2, 1fr); }} }}
@media (max-width: 580px)  {{ .cards-grid {{ grid-template-columns: 1fr; }} }}

.post-card {{
  background: #fff;
  border-radius: 12px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  cursor: pointer;
  transition: transform 200ms ease, box-shadow 200ms ease;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}}
.post-card:hover {{
  transform: translateY(-4px);
  box-shadow: 0 12px 32px rgba(0,0,0,0.13);
}}
.post-card.hidden {{ display: none !important; }}

.card-header {{
  position: relative;
  padding: 20px 20px 18px;
  min-height: 160px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}}
.card-body {{
  padding: 20px 20px 16px;
  flex: 1;
  display: flex;
  flex-direction: column;
}}
.card-title {{
  font-size: 15px;
  font-weight: 800;
  color: #0F172A;
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
  background: #0F172A;
  color: #fff;
  font-size: 13px;
  font-weight: 700;
  text-decoration: none;
  letter-spacing: 0.3px;
  transition: background 150ms;
}}
.card-cta:hover {{ background: #1D4ED8; }}

.hero-pattern {{
  position: absolute; inset: 0;
  background-image: radial-gradient(rgba(255,255,255,0.07) 1px, transparent 1px);
  background-size: 22px 22px;
  pointer-events: none;
}}

#no-result {{ display:none; text-align:center; padding:80px 20px; color:#94A3B8; font-size:15px; }}
#no-result.show {{ display:block; }}

/* 페이지네이션 */
.page-btn {{
  width: 36px;
  height: 36px;
  border-radius: 6px;
  border: 1.5px solid #CBD5E1;
  background: #fff;
  color: #64748B;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  font-family: inherit;
  transition: all 150ms;
}}
.page-btn:hover  {{ border-color: #1D4ED8; color: #1D4ED8; }}
.page-btn.active {{ background: #1D4ED8; color: #fff; border-color: #1D4ED8; font-weight: 700; }}
</style>
</head>
<body>

<header style="background:#0F172A;padding:0 24px;position:sticky;top:0;z-index:50;
               border-bottom:1px solid #1E293B;">
  <div style="max-width:1160px;margin:0 auto;display:flex;align-items:center;
              justify-content:space-between;height:54px;">
    <div style="display:flex;align-items:center;gap:10px;">
      <span style="display:inline-flex;align-items:center;justify-content:center;
                   width:30px;height:30px;background:#1D4ED8;border-radius:6px;
                   font-size:14px;">📝</span>
      <span style="color:#fff;font-size:15px;font-weight:800;letter-spacing:-0.3px;">
        정과장의 청약노트
      </span>
    </div>
    <a href="https://apply.lh.or.kr" target="_blank" rel="noopener"
       style="font-size:12px;color:#64748B;text-decoration:none;
              border:1px solid #334155;border-radius:6px;padding:5px 12px;
              transition:color 150ms;"
       onmouseover="this.style.color='#93C5FD'" onmouseout="this.style.color='#64748B'">
      청약홈 ↗
    </a>
  </div>
</header>


<section style="background:linear-gradient(140deg,#0F172A 0%,#1E293B 50%,#0F172A 100%);
                padding:64px 24px 60px;position:relative;overflow:hidden;">
  <div class="hero-pattern"></div>
  <div style="position:absolute;right:-20px;top:50%;transform:translateY(-50%);
              font-size:180px;font-weight:900;color:rgba(255,255,255,0.02);
              letter-spacing:-8px;pointer-events:none;line-height:1;user-select:none;">
    청약
  </div>

  <div style="max-width:1160px;margin:0 auto;position:relative;">
    <div style="display:inline-flex;align-items:center;gap:8px;
                background:rgba(29,78,216,0.25);border:1px solid rgba(29,78,216,0.4);
                border-radius:6px;padding:5px 14px;margin-bottom:20px;">
      <span style="width:6px;height:6px;background:#3B82F6;border-radius:50%;
                   display:inline-block;"></span>
      <span style="font-size:11px;font-weight:700;color:#93C5FD;letter-spacing:2px;">
        CHEONG-YAK NOTE
      </span>
    </div>

    <h1 style="font-size:clamp(28px,4.5vw,48px);font-weight:900;color:#fff;
               line-height:1.2;margin-bottom:16px;word-break:keep-all;letter-spacing:-1px;">
      복잡한 청약 공고문,<br>
      <span style="color:#60A5FA;">정과장이 쉽게 정리</span>해 드립니다
    </h1>

    <p style="font-size:15px;color:#94A3B8;line-height:1.7;
              max-width:480px;margin-bottom:40px;">
      한국부동산원 청약홈 공개 데이터를 AI로 분석하여<br>
      분양가 · 일정 · 입지 · Q&amp;A를 한 눈에 확인하세요.
    </p>

    <div style="display:flex;flex-wrap:wrap;gap:0;
                background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);
                border-radius:10px;overflow:hidden;max-width:480px;">
      <div style="flex:1;padding:16px 24px;border-right:1px solid rgba(255,255,255,0.08);">
        <div style="font-size:30px;font-weight:900;color:#fff;letter-spacing:-1px;">{total}</div>
        <div style="font-size:11px;color:#64748B;margin-top:2px;letter-spacing:0.5px;">분석 공고</div>
      </div>
      <div style="flex:1;padding:16px 24px;border-right:1px solid rgba(255,255,255,0.08);">
        <div style="font-size:30px;font-weight:900;color:#fff;letter-spacing:-1px;">{region_count}</div>
        <div style="font-size:11px;color:#64748B;margin-top:2px;letter-spacing:0.5px;">커버 지역</div>
      </div>
      <div style="flex:1;padding:16px 24px;">
        <div style="font-size:16px;font-weight:800;color:#fff;margin-top:4px;">{latest}</div>
        <div style="font-size:11px;color:#64748B;margin-top:2px;letter-spacing:0.5px;">최근 업데이트</div>
      </div>
    </div>
  </div>
</section>


<main style="max-width:1160px;margin:0 auto;padding:40px 24px 100px;">

  <!-- 섹션 헤더 -->
  <div style="display:flex;flex-wrap:wrap;align-items:center;
              justify-content:space-between;gap:16px;margin-bottom:24px;">
    <div>
      <p style="font-size:11px;font-weight:700;color:#94A3B8;letter-spacing:2px;
                margin-bottom:4px;">ANALYSIS REPORTS</p>
      <h2 style="font-size:20px;font-weight:800;color:#0F172A;letter-spacing:-0.3px;">
        분양 공고 분석 모음
      </h2>
    </div>
    <p id="result-count" style="font-size:13px;color:#94A3B8;">
      총 <strong style="color:#334155;">{total}</strong>건
    </p>
  </div>

  <!-- 지역 필터 탭 -->
  <div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:16px;">
    {region_tabs}
  </div>

  <!-- 단지명 검색 (탭 메뉴 하단) -->
  <div style="margin-bottom:28px;padding-bottom:24px;border-bottom:1px solid #E2E8F0;">
    <input
      type="text"
      id="search-input"
      class="search-input"
      placeholder="🔍 단지명 검색..."
      oninput="onSearch(event)"
      autocomplete="off"
    >
  </div>

  <!-- 카드 그리드 -->
  <div class="cards-grid" id="cards-grid">
    {cards_html}
  </div>
  <p id="no-result">해당 조건의 분석 공고가 없습니다.</p>

  <!-- 페이지네이션 -->
  <div id="pagination" style="display:flex;justify-content:center;gap:8px;
                               margin-top:40px;flex-wrap:wrap;"></div>

</main>


<footer style="background:#0F172A;padding:40px 24px;">
  <div style="max-width:1160px;margin:0 auto;">
    <div style="display:flex;flex-wrap:wrap;justify-content:space-between;
                gap:32px;padding-bottom:28px;border-bottom:1px solid #1E293B;">
      <div>
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:12px;">
          <span style="display:inline-flex;align-items:center;justify-content:center;
                       width:28px;height:28px;background:#1D4ED8;border-radius:6px;
                       font-size:13px;">📝</span>
          <span style="color:#fff;font-size:14px;font-weight:800;">정과장의 청약노트</span>
        </div>
        <p style="font-size:13px;color:#475569;line-height:1.7;max-width:320px;">
          한국부동산원 청약홈 공개 정보를 바탕으로<br>AI가 분석한 분양 공고 리포트입니다.
        </p>
      </div>
      <div style="font-size:12px;color:#334155;line-height:2;">
        <p>📌 데이터 출처: 한국부동산원 청약홈 · 공공데이터포털</p>
        <p>📌 국토교통부 실거래가 공개시스템</p>
        <p>⚠️ 본 콘텐츠는 투자 권유가 아닌 정보 제공 목적입니다.</p>
      </div>
    </div>
    <p style="font-size:12px;color:#334155;margin-top:20px;">
      © 2026 정과장의 청약노트. 실제 청약은 반드시 공식 기관에서 확인하세요.
    </p>
  </div>
</footer>


<script>
const POSTS_PER_PAGE = {POSTS_PER_PAGE};
let currentRegion = '전체';
let currentSearch = '';
let currentPage   = 1;

function getVisibleCards() {{
  const q = currentSearch.trim().replace(/\\s+/g, '');
  return Array.from(document.querySelectorAll('.post-card')).filter(card => {{
    const regionOk = currentRegion === '전체' || card.dataset.region === currentRegion;
    if (!regionOk) return false;
    if (!q) return true;
    const name = (card.dataset.aptName || '').replace(/\\s+/g, '');
    const title = (card.querySelector('.card-title')?.textContent || '').replace(/\\s+/g, '');
    return name.includes(q) || title.includes(q);
  }});
}}

function applyFilters() {{
  const allCards = document.querySelectorAll('.post-card');
  const visible  = getVisibleCards();
  const start    = (currentPage - 1) * POSTS_PER_PAGE;
  const end      = start + POSTS_PER_PAGE;

  allCards.forEach(c => c.classList.add('hidden'));
  visible.slice(start, end).forEach(c => c.classList.remove('hidden'));

  document.getElementById('result-count').innerHTML =
    `총 <strong style="color:#334155;">${{visible.length}}</strong>건`;
  document.getElementById('no-result').classList.toggle('show', visible.length === 0);

  renderPagination(visible.length);
}}

function renderPagination(total) {{
  const pages = Math.ceil(total / POSTS_PER_PAGE);
  const nav   = document.getElementById('pagination');
  if (pages <= 1) {{ nav.innerHTML = ''; return; }}

  let out = '';
  for (let i = 1; i <= pages; i++) {{
    const active = i === currentPage;
    out += `<button class="page-btn${{active ? ' active' : ''}}" onclick="goPage(${{i}})">${{i}}</button>`;
  }}
  nav.innerHTML = out;
}}

function goPage(n) {{
  currentPage = n;
  applyFilters();
  window.scrollTo({{ top: 0, behavior: 'smooth' }});
}}

function filterRegion(btn, region) {{
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  currentRegion = region;
  currentPage   = 1;
  applyFilters();
}}

function onSearch(e) {{
  currentSearch = e.target.value;
  currentPage   = 1;
  applyFilters();
}}

document.querySelector('.tab-btn[data-region="전체"]').classList.add('active');
applyFilters();
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
