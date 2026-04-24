"""
build_index.py
──────────────────────────────────────────────
output/posts/*/post_meta.json 을 읽어
output/index.html 프론트페이지를 생성한다.

실행:
  python pipeline/build_index.py
"""

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
OUTPUT_DIR = ROOT / "output"
POSTS_DIR  = OUTPUT_DIR / "posts"
OUT_FILE   = OUTPUT_DIR / "index.html"

SITE_URL  = "https://apt-note.com"
SITE_NAME = "정과장의 청약노트"

# 공공분양 키워드
_PUBLIC_KW = ("공공분양", "공공임대", "행복주택", "국민임대", "lh", "sh공사",
              "경기주택", "인천도시공사", "주공", "공공지원")


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


def _parse_date(date_str: str) -> datetime | None:
    if not date_str or date_str in ("-", "null", "None"):
        return None
    try:
        return datetime.fromisoformat(date_str[:10])
    except Exception:
        return None


def _supply_info(title: str, apt_name: str) -> tuple[str, str, str]:
    """(label, card_grad_cssvar, tag_type)
    tag_type: 'new' | 'resupply'
    """
    combined = title + " " + apt_name
    resupply_map = [
        ("무순위",   "무순위"),
        ("불법행위", "불법행위재공급"),
        ("임의",     "임의공급"),
        ("취소후",   "취소후재공급"),
        ("잔여",     "잔여세대"),
    ]
    for kw, label in resupply_map:
        if kw in combined:
            return label, "var(--c-card-grad-resupply)", "resupply"

    lo = combined.lower()
    label = "공공분양" if any(kw in lo for kw in _PUBLIC_KW) else "민간분양"
    return label, "var(--c-card-grad-new)", "new"


def _supply_filter_key(title: str, apt_name: str) -> str:
    label, _, tag_type = _supply_info(title, apt_name)
    return "재공급" if tag_type == "resupply" else label


def _date_cell(label: str, month: str, day: str) -> str:
    """날짜 셀 — 없으면 '-'"""
    if not month:
        return (
            f'<div style="flex:1;padding:12px 14px;text-align:center;">'
            f'<p style="font-size:10px;font-weight:600;color:var(--c-mid);'
            f'letter-spacing:1px;margin-bottom:5px;">{label}</p>'
            f'<p style="font-size:13px;color:var(--c-mid);">-</p>'
            f'</div>'
        )
    return (
        f'<div style="flex:1;padding:12px 14px;text-align:center;">'
        f'<p style="font-size:10px;font-weight:600;color:var(--c-mid);'
        f'letter-spacing:1px;margin-bottom:5px;">{label}</p>'
        f'<p style="font-size:16px;font-weight:700;color:var(--c-dark);line-height:1.3;">'
        f'{month} {day}</p>'
        f'</div>'
    )


def _render_filter_btn(label: str, count: int, js_value: str, group: str) -> str:
    return (
        f'<button class="tab-btn" data-group="{group}" data-value="{js_value}" '
        f'onclick="filterGroup(this,\'{group}\',\'{js_value}\')">'
        f'{label}<span class="tab-count"> ({count})</span>'
        f'</button>'
    )


def _render_featured(posts: list[dict]) -> str:
    featured = posts[:3]
    if not featured:
        return ""

    items: list[str] = []
    for idx, post in enumerate(featured, start=1):
        apt_name = post.get("apt_name", "(단지명 없음)")
        location = post.get("location", "위치 정보 없음")
        price = post.get("price_range") or "분양가 확인 필요"
        url = post["post_url"]
        label, _, _ = _supply_info(post.get("title", apt_name), apt_name)
        rank1_dt = _parse_date(post.get("rank1_date", ""))
        rank1_label = (
            f"{rank1_dt.month}월 {rank1_dt.day}일 1순위"
            if rank1_dt else "일정 확인 필요"
        )
        items.append(
            f"""
            <a href="{url}" style="display:flex;gap:16px;align-items:flex-start;
               padding:18px 0;text-decoration:none;border-top:{'0' if idx == 1 else '1px'} solid var(--c-light-gray);">
              <div style="width:40px;height:40px;border-radius:12px;display:flex;align-items:center;justify-content:center;
                          flex-shrink:0;background:var(--c-primary-light);color:var(--c-primary);font-size:16px;font-weight:900;">
                {idx}
              </div>
              <div style="min-width:0;flex:1;">
                <p style="font-size:11px;font-weight:800;letter-spacing:1px;color:var(--c-primary);margin-bottom:7px;">{label}</p>
                <p style="font-size:18px;font-weight:800;line-height:1.45;color:var(--c-dark);word-break:keep-all;margin-bottom:6px;">
                  {apt_name}
                </p>
                <p style="font-size:13px;color:var(--c-mid);line-height:1.6;margin-bottom:9px;">
                  {location}
                </p>
                <div style="display:flex;flex-wrap:wrap;gap:8px;">
                  <span style="display:inline-flex;align-items:center;padding:7px 10px;border-radius:999px;
                               background:var(--c-bg);font-size:12px;color:var(--c-dark);">
                    {price}
                  </span>
                  <span style="display:inline-flex;align-items:center;padding:7px 10px;border-radius:999px;
                               background:var(--c-bg);font-size:12px;color:var(--c-dark);">
                    {rank1_label}
                  </span>
                </div>
              </div>
            </a>
            """
        )
    return "".join(items)


def _render_card(p: dict, _serial: int) -> str:
    apt_name = p.get("apt_name", "(단지명 없음)")
    title    = p.get("title", apt_name)
    location = p.get("location", "")
    region   = p.get("region_category", "기타")
    url      = p["post_url"]
    tags     = (p.get("tags") or [])[:4]

    supply_label, header_grad, tag_type = _supply_info(title, apt_name)
    supply_key = _supply_filter_key(title, apt_name)
    price_range = p.get("price_range") or "분양가 확인 필요"
    move_in = p.get("move_in_date") or "입주 시기 확인 필요"

    sp_month, sp_day = _fmt_date(p.get("special_supply_date", ""))
    r1_month, r1_day = _fmt_date(p.get("rank1_date", ""))

    tag_items = "".join(
        f'<span style="display:inline-block;'
        f'background:var(--c-tag-{tag_type}-bg);'
        f'color:var(--c-tag-{tag_type}-text);'
        f'font-size:11px;font-weight:700;padding:3px 9px;border-radius:4px;'
        f'margin:0 4px 5px 0;letter-spacing:0.2px;">#{t}</span>'
        for t in tags
    )

    sp_cell = _date_cell("특별공급", sp_month, sp_day)
    r1_cell = _date_cell("1순위",    r1_month, r1_day)

    return f"""<article class="post-card" data-region="{region}" data-supply="{supply_key}" data-name="{apt_name}" onclick="location.href='{url}'">

  <!-- ── 카드 헤더 ── -->
  <div class="card-header" style="background:{header_grad};">
    <div style="position:absolute;inset:0;
      background-image:radial-gradient(rgba(255,255,255,0.07) 1.5px,transparent 1.5px);
      background-size:18px 18px;pointer-events:none;"></div>

    <!-- 공급유형 -->
    <div style="position:relative;margin-bottom:10px;">
      <span style="font-size:11px;font-weight:900;color:#fff;
                   letter-spacing:1px;text-transform:uppercase;">{supply_label}</span>
    </div>

    <!-- 단지명 -->
    <p style="position:relative;font-size:22px;font-weight:800;color:#fff;
              line-height:1.3;word-break:keep-all;
              display:-webkit-box;-webkit-line-clamp:2;
              -webkit-box-orient:vertical;overflow:hidden;margin:0;">
      {apt_name}
    </p>

    <div style="position:relative;margin-top:auto;padding-top:12px;">
      <span style="display:inline-flex;max-width:100%;align-items:center;padding:7px 10px;
                   border-radius:999px;background:rgba(255,255,255,0.14);
                   border:1px solid rgba(255,255,255,0.22);color:#fff;font-size:12px;font-weight:700;
                   white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
        {price_range}
      </span>
    </div>
  </div>

  <!-- ── 카드 하단 ── -->

  <!-- 날짜 바 -->
  <div style="display:flex;border-bottom:1px solid var(--c-light-gray);">
    {sp_cell}
    <div style="width:1px;background:var(--c-light-gray);flex-shrink:0;margin:10px 0;"></div>
    {r1_cell}
  </div>

  <!-- 행정구역 -->
  <div style="padding:11px 16px;border-bottom:1px solid var(--c-light-gray);">
    <p style="font-size:12px;font-weight:500;color:var(--c-dark);margin:0;line-height:1.4;">
      📌 {location if location else "위치 정보 없음"}
    </p>
  </div>

  <div style="display:flex;gap:8px;flex-wrap:wrap;padding:12px 16px 0;">
    <span style="display:inline-flex;align-items:center;padding:6px 10px;border-radius:999px;
                 background:var(--c-primary-light);color:var(--c-primary-dark);font-size:11px;font-weight:700;">
      {supply_key}
    </span>
    <span style="display:inline-flex;align-items:center;padding:6px 10px;border-radius:999px;
                 background:var(--c-bg);color:var(--c-dark);font-size:11px;font-weight:600;">
      입주 {move_in}
    </span>
  </div>

  <!-- 태그 -->
  <div style="padding:11px 16px 9px;flex:1;">
    {tag_items if tag_items else '<span style="font-size:11px;color:var(--c-mid);">-</span>'}
  </div>

  <!-- CTA -->
  <a href="{url}" class="card-cta" onclick="event.stopPropagation()">
    공고 분석 전문 보기 →
  </a>
</article>"""


def build() -> None:
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from shared_ui import (
        FONT_LINK, FONT_FAMILY, PALETTE_CSS,
        PALETTE_INIT_JS, PALETTE_SWITCH_JS, shared_nav,
    )

    posts = load_posts()
    print(f"  포스트 {len(posts)}건 로드")

    # 지역/공급유형 집계
    region_counts: dict[str, int] = {}
    supply_counts: dict[str, int] = {}
    for p in posts:
        r = p.get("region_category", "기타")
        region_counts[r] = region_counts.get(r, 0) + 1
        supply_key = _supply_filter_key(p.get("title", p.get("apt_name", "")), p.get("apt_name", ""))
        supply_counts[supply_key] = supply_counts.get(supply_key, 0) + 1

    _REGION_ORDER = [
        "서울", "경기도", "인천", "부산", "대전", "대구", "광주",
        "세종", "울산", "강원도", "충청북도", "충청남도",
        "전라북도", "전라남도", "경상북도", "경상남도", "제주도",
    ]
    known    = [r for r in _REGION_ORDER if r in region_counts]
    unknown  = sorted(r for r in region_counts if r not in _REGION_ORDER)
    regions  = ["전체"] + known + unknown
    total        = len(posts)
    region_count = len(region_counts)

    region_tabs = "".join(
        _render_filter_btn(r, total if r == "전체" else region_counts.get(r, 0), r, "region")
        for r in regions
    )
    supply_order = ["전체", "민간분양", "공공분양", "재공급"]
    supply_tabs = "".join(
        _render_filter_btn(
            label,
            total if label == "전체" else supply_counts.get(label, 0),
            label,
            "supply",
        )
        for label in supply_order
        if label == "전체" or supply_counts.get(label, 0) > 0
    )
    cards_html  = "".join(_render_card(p, i + 1) for i, p in enumerate(posts))
    nav_html    = shared_nav("/")
    featured_html = _render_featured(posts)
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    # 최근 업데이트 일자 — 항상 오늘 날짜로 표기
    latest_label = f"{today.year}.{today.month:02d}.{today.day:02d} 업데이트"
    upcoming_rank1 = sum(
        1 for p in posts
        if (dt := _parse_date(p.get("rank1_date", ""))) and dt >= today
    )
    seoul_gyeonggi = region_counts.get("서울", 0) + region_counts.get("경기도", 0)
    supply_count = len([k for k, v in supply_counts.items() if v > 0])

    html = f"""<!DOCTYPE html>
<html lang="ko" data-palette="A">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>정과장의 청약노트 — 분양 공고 분석 모음</title>
<meta name="description" content="복잡한 청약 공고문을 쉽게 정리해 드리는 정과장의 청약노트. 전국 아파트 분양 공고 분석 모음.">
<link rel="canonical" href="{SITE_URL}/">
<meta property="og:type" content="website">
<meta property="og:site_name" content="정과장의 청약노트">
<meta property="og:title" content="정과장의 청약노트 — 분양 공고 분석 모음">
<meta property="og:description" content="복잡한 청약 공고문을 쉽게 정리해 드리는 정과장의 청약노트. 전국 아파트 분양 공고 분석 모음.">
<meta property="og:url" content="{SITE_URL}/">
<meta property="og:image" content="{SITE_URL}/og-image.png">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="정과장의 청약노트 — 분양 공고 분석 모음">
<meta name="twitter:description" content="복잡한 청약 공고문을 쉽게 정리해 드리는 정과장의 청약노트.">
<meta name="twitter:image" content="{SITE_URL}/og-image.png">
<meta name="robots" content="index, follow">
<link rel="sitemap" type="application/xml" href="{SITE_URL}/sitemap.xml">
{FONT_LINK}
{PALETTE_INIT_JS}
<style>
{PALETTE_CSS}

*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
html {{ scroll-behavior: smooth; }}
body {{
  font-family: {FONT_FAMILY};
  background: var(--c-bg);
  color: var(--c-dark);
  -webkit-text-size-adjust: 100%;
}}

/* ── 탭 ── */
.tab-btn {{
  flex-shrink: 0;
  padding: 7px 14px;
  border-radius: 6px;
  border: 1.5px solid var(--c-light-gray);
  background: var(--c-surface);
  color: var(--c-dark);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 150ms;
  font-family: inherit;
}}
.tab-count {{ font-weight: 400; color: var(--c-mid); }}
.tab-btn:hover {{ border-color: var(--c-primary); color: var(--c-primary); }}
.tab-btn:hover .tab-count {{ color: var(--c-primary); opacity:0.7; }}
.tab-btn.active {{
  background: var(--c-primary);
  color: #fff;
  border-color: var(--c-primary);
  font-weight: 700;
}}
.tab-btn.active .tab-count {{ color: rgba(255,255,255,0.7); }}

/* ── 그리드 ── */
.cards-grid {{
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 22px;
}}
.intro-grid {{
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(320px, 0.95fr);
  gap: 22px;
}}
@media (max-width: 960px) {{ .cards-grid {{ grid-template-columns: repeat(2, 1fr); }} }}
@media (max-width: 960px) {{ .intro-grid {{ grid-template-columns: 1fr; }} }}
@media (max-width: 580px) {{ .cards-grid {{ grid-template-columns: 1fr; }} }}

/* ── 카드 ── */
.post-card {{
  background: var(--c-surface);
  border-radius: 12px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  cursor: pointer;
  border: 1px solid var(--c-light-gray);
  transition: transform 200ms ease, box-shadow 200ms ease;
}}
.post-card:hover {{
  transform: translateY(-4px);
  box-shadow: 0 12px 32px rgba(0,0,0,0.10);
}}
.post-card.hidden {{ display: none !important; }}

/* ── 카드 헤더 ── */
.card-header {{
  position: relative;
  padding: 16px 16px 18px;
  min-height: 110px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}}

/* ── CTA ── */
.card-cta {{
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 11px 16px;
  background: var(--c-cta-bg);
  color: #fff;
  font-size: 13px;
  font-weight: 700;
  text-decoration: none;
  letter-spacing: 0.2px;
  transition: background 150ms;
  flex-shrink: 0;
}}
.card-cta:hover {{ background: var(--c-cta-hover); }}

/* ── 히어로 줄무늬 ── */
.hero-stripe {{
  position: absolute; inset: 0;
  background-image: repeating-linear-gradient(
    -55deg, transparent, transparent 28px,
    var(--c-primary-stripe) 28px, var(--c-primary-stripe) 29px
  );
  pointer-events: none;
}}

/* ── 검색 ── */
.search-wrap {{
  position: relative;
  flex-shrink: 0;
  margin-right: 4px;
}}
.search-wrap::after {{
  content: '';
  position: absolute;
  right: -8px;
  top: 20%;
  height: 60%;
  width: 1px;
  background: var(--c-light-gray);
}}
#search-input {{
  padding: 7px 12px 7px 30px;
  border-radius: 6px;
  border: 1.5px solid var(--c-light-gray);
  background: var(--c-surface);
  color: var(--c-dark);
  font-size: 13px;
  font-weight: 500;
  font-family: inherit;
  outline: none;
  width: 160px;
  transition: border-color 150ms, width 200ms;
}}
#search-input:focus {{ border-color: var(--c-primary); width: 200px; }}
#search-input::placeholder {{ color: var(--c-mid); }}
.search-icon {{
  position: absolute;
  left: 9px;
  top: 50%;
  transform: translateY(-50%);
  pointer-events: none;
  color: var(--c-mid);
  display: flex;
}}

/* ── 빈 결과 ── */
#no-result {{ display:none; text-align:center; padding:80px 20px; color:var(--c-mid); font-size:15px; }}
#no-result.show {{ display:block; }}

.section-card {{
  background: var(--c-surface);
  border: 1px solid var(--c-light-gray);
  border-radius: 20px;
  box-shadow: 0 18px 40px rgba(36, 32, 28, 0.06);
}}
</style>
</head>
<body>

{nav_html}


<!-- ══ 히어로 ══ -->
<section style="background:var(--c-hero-bg);padding:72px 24px 68px;position:relative;overflow:hidden;">
  <div class="hero-stripe"></div>
  <div style="position:absolute;right:-60px;top:-60px;width:320px;height:320px;
              border-radius:50%;border:1px solid var(--c-primary-stripe);pointer-events:none;"></div>

  <div style="max-width:1160px;margin:0 auto;position:relative;">

    <div style="display:inline-flex;align-items:center;
                background:var(--c-primary-light);border:1px solid rgba(0,0,0,0.08);
                border-radius:6px;padding:6px 16px;margin-bottom:24px;">
      <span style="font-size:16px;font-weight:700;color:var(--c-primary);letter-spacing:0.5px;">
        아파트 청약 공고문 분석 서비스
      </span>
    </div>

    <h1 style="font-size:clamp(28px,4.5vw,52px);font-weight:900;color:var(--c-dark);
               line-height:1.18;margin-bottom:18px;word-break:keep-all;letter-spacing:-1.5px;">
      복잡한 청약 공고문,<br>
      <span style="color:var(--c-primary);">정과장이 쉽게</span> 정리해 드립니다
    </h1>

    <p style="font-size:16px;color:var(--c-dark);opacity:0.65;line-height:1.75;
              max-width:460px;margin-bottom:44px;word-break:keep-all;">
      한국부동산원 청약홈 공개 데이터를 AI로 분석하여<br>
      분양가 · 일정 · 입지 · Q&amp;A를 한 눈에 확인하세요.
    </p>

    <div style="display:flex;flex-wrap:wrap;gap:10px;margin-bottom:24px;">
      <span style="display:inline-flex;align-items:center;padding:10px 14px;border-radius:999px;
                   background:rgba(255,255,255,0.78);border:1px solid rgba(0,0,0,0.06);
                   font-size:13px;font-weight:700;color:var(--c-dark);">
        {latest_label}
      </span>
      <span style="display:inline-flex;align-items:center;padding:10px 14px;border-radius:999px;
                   background:rgba(255,255,255,0.78);border:1px solid rgba(0,0,0,0.06);
                   font-size:13px;font-weight:700;color:var(--c-dark);">
        곧 1순위 접수 {upcoming_rank1}건
      </span>
    </div>

    <!-- 통계 카드 -->
    <div style="display:flex;flex-wrap:wrap;gap:12px;">
      <div style="background:var(--c-surface);border:1px solid var(--c-light-gray);
                  border-radius:10px;padding:18px 32px;text-align:center;">
        <div style="font-size:32px;font-weight:900;color:var(--c-primary);letter-spacing:-1px;">{total}</div>
        <div style="font-size:12px;font-weight:600;color:var(--c-dark);margin-top:4px;letter-spacing:0.3px;">분석 공고</div>
      </div>
      <div style="background:var(--c-surface);border:1px solid var(--c-light-gray);
                  border-radius:10px;padding:18px 32px;text-align:center;">
        <div style="font-size:32px;font-weight:900;color:var(--c-accent);letter-spacing:-1px;">{region_count}</div>
        <div style="font-size:12px;font-weight:600;color:var(--c-dark);margin-top:4px;letter-spacing:0.3px;">커버 지역</div>
      </div>
      <div style="background:var(--c-surface);border:1px solid var(--c-light-gray);
                  border-radius:10px;padding:18px 32px;text-align:center;">
        <div style="font-size:32px;font-weight:900;color:var(--c-green-dark);letter-spacing:-1px;">{seoul_gyeonggi}</div>
        <div style="font-size:12px;font-weight:600;color:var(--c-dark);margin-top:4px;letter-spacing:0.3px;">서울·경기 공고</div>
      </div>
    </div>
  </div>
</section>

<div style="height:3px;background:linear-gradient(90deg,var(--c-primary),var(--c-accent),transparent);"></div>


<!-- ══ 메인 ══ -->
<main style="max-width:1160px;margin:0 auto;padding:44px 24px 100px;">

  <section class="intro-grid" style="margin-bottom:36px;">
    <div class="section-card" style="padding:28px;">
      <p style="font-size:11px;font-weight:800;letter-spacing:2px;color:var(--c-primary);margin-bottom:10px;">START HERE</p>
      <h2 style="font-size:28px;font-weight:900;line-height:1.28;letter-spacing:-0.9px;color:var(--c-dark);margin-bottom:12px;word-break:keep-all;">
        이번 주 청약 흐름을 빠르게 훑고<br>원하는 단지로 바로 들어가세요
      </h2>
      <p style="font-size:15px;line-height:1.8;color:var(--c-mid);margin-bottom:20px;max-width:560px;word-break:keep-all;">
        지역 탭과 공급 유형 필터를 같이 쓰면 재공급 공고, 공공분양 공고, 서울권 신규 공고만 빠르게 압축해서 볼 수 있습니다.
      </p>
      <div style="display:flex;flex-wrap:wrap;gap:10px;">
        <span style="display:inline-flex;align-items:center;padding:10px 14px;border-radius:999px;background:var(--c-bg);font-size:13px;color:var(--c-dark);">
          지역 탐색 {region_count}개 권역
        </span>
        <span style="display:inline-flex;align-items:center;padding:10px 14px;border-radius:999px;background:var(--c-bg);font-size:13px;color:var(--c-dark);">
          공급 유형 {supply_count}개
        </span>
        <span style="display:inline-flex;align-items:center;padding:10px 14px;border-radius:999px;background:var(--c-bg);font-size:13px;color:var(--c-dark);">
          검색으로 단지명 바로 찾기
        </span>
      </div>
    </div>

    <aside class="section-card" style="padding:28px;">
      <div style="display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:8px;">
        <div>
          <p style="font-size:11px;font-weight:800;letter-spacing:2px;color:var(--c-primary);margin-bottom:8px;">LATEST PICKS</p>
          <h3 style="font-size:22px;font-weight:900;letter-spacing:-0.6px;color:var(--c-dark);">최근 분석 공고</h3>
        </div>
        <span style="font-size:12px;font-weight:700;color:var(--c-mid);">TOP 3</span>
      </div>
      {featured_html}
    </aside>
  </section>

  <div style="display:flex;flex-wrap:wrap;align-items:flex-end;
              justify-content:space-between;gap:16px;margin-bottom:22px;">
    <div>
      <p style="font-size:10px;font-weight:700;color:var(--c-mid);
                letter-spacing:2px;margin-bottom:5px;">ANALYSIS REPORTS</p>
      <h2 style="font-size:22px;font-weight:800;color:var(--c-dark);letter-spacing:-0.5px;">
        분양 공고 분석 모음
      </h2>
    </div>
    <p id="result-count" style="font-size:13px;color:var(--c-mid);">
      총 <strong style="color:var(--c-dark);">{total}</strong>건
    </p>
  </div>

  <div style="display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin-bottom:16px;
              padding-bottom:24px;border-bottom:1px solid var(--c-light-gray);">
    <div class="search-wrap">
      <span class="search-icon">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor"
             stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
        </svg>
      </span>
      <input id="search-input" type="text" placeholder="단지명 검색"
             oninput="filterSearch(this.value)" autocomplete="off">
    </div>
    {region_tabs}
  </div>

  <div style="display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin-bottom:32px;">
    <span style="font-size:12px;font-weight:800;letter-spacing:1px;color:var(--c-mid);margin-right:4px;">공급유형</span>
    {supply_tabs}
  </div>

  <div class="cards-grid" id="cards-grid">
    {cards_html}
  </div>
  <p id="no-result">해당 지역의 분석 공고가 없습니다.</p>

  <div id="pagination" style="display:flex;justify-content:center;align-items:center;
       gap:6px;margin-top:48px;flex-wrap:wrap;"></div>

</main>


<!-- ══ 푸터 ══ -->
<footer style="background:var(--c-nav-bg);padding:40px 24px;">
  <div style="max-width:1160px;margin:0 auto;">
    <div style="display:flex;flex-wrap:wrap;justify-content:space-between;gap:32px;
                padding-bottom:28px;border-bottom:1px solid rgba(255,255,255,0.07);">
      <div>
        <div style="display:flex;align-items:center;gap:9px;margin-bottom:12px;">
          <span style="display:inline-flex;align-items:center;justify-content:center;
                       width:28px;height:28px;background:var(--c-primary);border-radius:6px;
                       font-size:14px;flex-shrink:0;">📝</span>
          <span style="color:#fff;font-size:14px;font-weight:800;">정과장의 청약노트</span>
        </div>
        <p style="font-size:13px;color:rgba(255,255,255,0.6);line-height:1.7;max-width:300px;">
          한국부동산원 청약홈 공개 정보를 바탕으로<br>AI가 분석한 분양 공고 리포트입니다.
        </p>
      </div>
      <div style="font-size:12px;color:rgba(255,255,255,0.55);line-height:2.2;">
        <p>📌 데이터 출처: 한국부동산원 청약홈 · 공공데이터포털</p>
        <p>📌 국토교통부 실거래가 공개시스템</p>
        <p>⚠️ 투자 권유가 아닌 정보 제공 목적입니다.</p>
      </div>
    </div>
    <p style="font-size:12px;color:rgba(255,255,255,0.45);margin-top:20px;">
      © 2026 정과장의 청약노트. 실제 청약은 반드시 공식 기관에서 확인하세요.
    </p>
  </div>
</footer>


<script>
{PALETTE_SWITCH_JS}

var POSTS_PER_PAGE = 12;
var _currentPage = 1;
var _activeFilters = {{
  region: '전체',
  supply: '전체'
}};

function _getMatchedCards() {{
  var q = ((document.getElementById('search-input') || {{}}).value || '').toLowerCase().trim();
  var all = Array.from(document.querySelectorAll('.post-card'));
  return all.filter(function(card) {{
    var regionMatch = _activeFilters.region === '전체' || card.dataset.region === _activeFilters.region;
    var supplyMatch = _activeFilters.supply === '전체' || card.dataset.supply === _activeFilters.supply;
    var nameMatch   = !q || (card.dataset.name || '').toLowerCase().includes(q);
    return regionMatch && supplyMatch && nameMatch;
  }});
}}

function _renderPage(matched, page) {{
  var start = (page - 1) * POSTS_PER_PAGE;
  var end   = start + POSTS_PER_PAGE;
  var all   = document.querySelectorAll('.post-card');
  all.forEach(function(c) {{ c.style.display = 'none'; }});
  matched.slice(start, end).forEach(function(c) {{ c.style.display = ''; }});
}}

function _renderPagination(matched) {{
  var box = document.getElementById('pagination');
  if (!box) return;
  var total = matched.length;
  var pages = Math.ceil(total / POSTS_PER_PAGE);
  if (pages <= 1) {{ box.innerHTML = ''; return; }}
  var html = '';
  var btnBase = 'style="min-width:36px;height:36px;border-radius:6px;border:1.5px solid var(--c-light-gray);'
    + 'background:var(--c-surface);color:var(--c-dark);font-size:13px;font-weight:600;'
    + 'cursor:pointer;font-family:inherit;transition:all 150ms;padding:0 10px;"';
  var btnActive = 'style="min-width:36px;height:36px;border-radius:6px;border:1.5px solid var(--c-primary);'
    + 'background:var(--c-primary);color:#fff;font-size:13px;font-weight:700;'
    + 'cursor:pointer;font-family:inherit;padding:0 10px;"';
  for (var i = 1; i <= pages; i++) {{
    if (i === _currentPage) {{
      html += '<button ' + btnActive + '>' + i + '</button>';
    }} else {{
      html += '<button ' + btnBase + ' onclick="goPage(' + i + ')">' + i + '</button>';
    }}
  }}
  box.innerHTML = html;
}}

function _applyFilters() {{
  _currentPage = 1;
  var matched = _getMatchedCards();
  _renderPage(matched, _currentPage);
  _renderPagination(matched);
  document.getElementById('result-count').innerHTML =
    '총 <strong style="color:var(--c-dark);">' + matched.length + '</strong>건';
  document.getElementById('no-result').classList.toggle('show', matched.length === 0);
}}

function goPage(page) {{
  _currentPage = page;
  var matched = _getMatchedCards();
  _renderPage(matched, _currentPage);
  _renderPagination(matched);
  if (window.scrollY > document.getElementById('cards-grid').offsetTop - 120) {{
    window.scrollTo({{top: document.getElementById('cards-grid').offsetTop - 80, behavior: 'smooth'}});
  }}
}}

function filterGroup(btn, group, value) {{
  document.querySelectorAll('.tab-btn[data-group="' + group + '"]').forEach(function(b) {{
    b.classList.remove('active');
  }});
  btn.classList.add('active');
  _activeFilters[group] = value;
  _applyFilters();
}}

function filterSearch(val) {{
  _applyFilters();
}}

document.querySelector('.tab-btn[data-group="region"][data-value="전체"]').classList.add('active');
document.querySelector('.tab-btn[data-group="supply"][data-value="전체"]').classList.add('active');
_applyFilters();
</script>

</body>
</html>"""

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(html, encoding="utf-8")
    print(f"✅ index.html 생성 완료: {OUT_FILE}  ({len(posts)}건)")

    _build_sitemap(posts)
    _build_robots()


def _build_sitemap(posts: list[dict]) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    urls = [
        f'  <url><loc>{SITE_URL}/</loc>'
        f'<changefreq>daily</changefreq><priority>1.0</priority>'
        f'<lastmod>{now}</lastmod></url>'
    ]
    for p in posts:
        loc     = f"{SITE_URL}/{p['post_url']}"
        lastmod = p.get("generated_at", now)[:10]
        urls.append(
            f'  <url><loc>{loc}</loc>'
            f'<changefreq>weekly</changefreq><priority>0.8</priority>'
            f'<lastmod>{lastmod}</lastmod></url>'
        )
    sitemap = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls)
        + "\n</urlset>"
    )
    out = OUTPUT_DIR / "sitemap.xml"
    out.write_text(sitemap, encoding="utf-8")
    print(f"✅ sitemap.xml 생성 완료: {out}  ({len(posts) + 1}개 URL)")


def _build_robots() -> None:
    content = f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n"
    out = OUTPUT_DIR / "robots.txt"
    out.write_text(content, encoding="utf-8")
    print(f"✅ robots.txt 생성 완료: {out}")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    build()
