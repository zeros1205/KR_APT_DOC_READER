"""
index_renderer.py
──────────────────────────────────────────────
최신 프런트 페이지 산출물 구조를 보존하는 index 전용 렌더러.

- 템플릿: templates/front_index_template.html
- 데이터 소스: output/posts/*/post_meta.json
- 산출물: output/index.html / sitemap.xml / robots.txt
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

try:
    from shared_ui import PALETTE_INIT_JS, index_nav
except ImportError:
    from pipeline.shared_ui import PALETTE_INIT_JS, index_nav

ROOT = Path(__file__).parent.parent
OUTPUT_DIR = ROOT / "output"
POSTS_DIR = OUTPUT_DIR / "posts"
OUT_FILE = OUTPUT_DIR / "index.html"
TEMPLATE_PATH = ROOT / "templates" / "front_index_template.html"

SITE_URL = "https://apt-note.com"
_PUBLIC_KW = (
    "공공분양", "공공임대", "행복주택", "국민임대", "lh", "sh공사",
    "경기주택", "인천도시공사", "주공", "공공지원",
)

INDEX_RUNTIME_SCRIPT = """<script>
var POSTS_PER_PAGE = 12;
var _currentPage = 1;
var _activeFilters = {
  region: '전체',
  supply: '전체'
};
var _searchState = new WeakMap();

function _getMatchedCards() {
  var all = Array.from(document.querySelectorAll('.post-card'));
  return all.filter(function(card) {
    var regionMatch = _activeFilters.region === '전체' || card.dataset.region === _activeFilters.region;
    return regionMatch;
  });
}

function _renderPage(matched, page) {
  var start = (page - 1) * POSTS_PER_PAGE;
  var end = start + POSTS_PER_PAGE;
  document.querySelectorAll('.post-card').forEach(function(card) { card.style.display = 'none'; });
  matched.slice(start, end).forEach(function(card) { card.style.display = ''; });
  requestAnimationFrame(_bindCardTitleMarquee);
}

function _renderPagination(matched) {
  var box = document.getElementById('pagination');
  if (!box) return;
  var pages = Math.ceil(matched.length / POSTS_PER_PAGE);
  if (pages <= 1) {
    box.innerHTML = '';
    return;
  }
  var btnBase = 'style="min-width:36px;height:36px;border-radius:6px;border:1.5px solid var(--c-light-gray);'
    + 'background:var(--c-surface);color:var(--c-dark);font-size:13px;font-weight:600;'
    + 'cursor:pointer;font-family:inherit;transition:all 150ms;padding:0 10px;"';
  var btnActive = 'style="min-width:36px;height:36px;border-radius:6px;border:1.5px solid var(--c-primary);'
    + 'background:var(--c-primary);color:#fff;font-size:13px;font-weight:700;'
    + 'cursor:pointer;font-family:inherit;padding:0 10px;"';
  var BLOCK = 5;
  var block = Math.ceil(_currentPage / BLOCK);
  var totalBlocks = Math.ceil(pages / BLOCK);
  var start = (block - 1) * BLOCK + 1;
  var end = Math.min(block * BLOCK, pages);
  var html = '';
  if (block > 1) {
    html += '<button ' + btnBase + ' aria-label="이전 5페이지" onclick="goPage(' + (start - 1) + ')">‹</button>';
  }
  for (var i = start; i <= end; i++) {
    if (i === _currentPage) {
      html += '<button ' + btnActive + '>' + i + '</button>';
    } else {
      html += '<button ' + btnBase + ' onclick="goPage(' + i + ')">' + i + '</button>';
    }
  }
  if (block < totalBlocks) {
    html += '<button ' + btnBase + ' aria-label="다음 5페이지" onclick="goPage(' + (end + 1) + ')">›</button>';
  }
  box.innerHTML = html;
}

function _applyFilters() {
  _currentPage = 1;
  var matched = _getMatchedCards();
  _renderPage(matched, _currentPage);
  _renderPagination(matched);
  var resultCount = document.getElementById('result-count');
  if (resultCount) {
    resultCount.innerHTML =
      '총 <strong style="color:var(--c-dark);">' + matched.length + '</strong>건';
  }
  document.getElementById('no-result').classList.toggle('show', matched.length === 0);
}

function goPage(page) {
  _currentPage = page;
  var matched = _getMatchedCards();
  _renderPage(matched, _currentPage);
  _renderPagination(matched);
  var grid = document.getElementById('cards-grid');
  if (!grid) return;
  var dock = document.getElementById('filter-dock');
  var stickyTop = dock ? (parseFloat(getComputedStyle(dock).top) || 0) : 0;
  var dockH = dock ? dock.offsetHeight : 0;
  var offset = stickyTop + dockH + 32;
  if (window.scrollY > grid.offsetTop - offset - 40) {
    window.scrollTo({ top: grid.offsetTop - offset, behavior: 'smooth' });
  }
}

function filterGroup(btn, group, value) {
  document.querySelectorAll('.tab-btn[data-group="' + group + '"]').forEach(function(b) {
    b.classList.remove('active');
  });
  btn.classList.add('active');
  _activeFilters[group] = value;
  _applyFilters();
}

function _buildSuggestions(query) {
  var q = (query || '').toLowerCase().trim();
  if (!q) return [];
  var seen = new Set();
  return Array.from(document.querySelectorAll('.post-card')).filter(function(card) {
    var name = (card.dataset.name || '').trim();
    var url = (card.dataset.url || '').trim();
    if (!name || !url) return false;
    var key = name + '|' + url;
    if (seen.has(key)) return false;
    var matched = name.toLowerCase().includes(q);
    if (matched) seen.add(key);
    return matched;
  }).slice(0, 10).map(function(card) {
    return {
      name: card.dataset.name || '',
      url: card.dataset.url || '',
      region: card.dataset.region || '',
      supply: card.dataset.supply || ''
    };
  });
}

function _closeSuggestions(input) {
  var wrap = input.closest('.search-wrap');
  var box = wrap ? wrap.querySelector('.search-suggestions') : null;
  if (!box) return;
  box.classList.remove('show');
  box.innerHTML = '';
  _searchState.set(input, { items: [], activeIndex: -1 });
}

function _renderSuggestions(input) {
  var wrap = input.closest('.search-wrap');
  var box = wrap ? wrap.querySelector('.search-suggestions') : null;
  if (!box) return;
  var items = _buildSuggestions(input.value);
  _searchState.set(input, { items: items, activeIndex: -1 });
  if (!items.length) {
    _closeSuggestions(input);
    return;
  }
  box.innerHTML = items.map(function(item, idx) {
    return '<button type="button" class="search-suggestion" data-index="' + idx + '" data-url="' + item.url + '">'
      + '<span class="search-suggestion-title">' + item.name + '</span>'
      + '<span class="search-suggestion-meta">' + item.region + ' · ' + item.supply + '</span>'
      + '</button>';
  }).join('');
  box.classList.add('show');
  if (!box.dataset.wheelBound) {
    box.addEventListener('wheel', function(e) {
      var delta = e.deltaY;
      if (!delta) return;
      box.scrollTop += delta;
      e.preventDefault();
      e.stopPropagation();
    }, { passive: false });
    box.dataset.wheelBound = 'true';
  }
  box.querySelectorAll('.search-suggestion').forEach(function(btn) {
    btn.addEventListener('click', function() { location.href = btn.dataset.url; });
  });
}

function _syncSearchInputs(source) {
  document.querySelectorAll('.js-apt-search').forEach(function(input) {
    if (input !== source) {
      input.value = source.value;
      _renderSuggestions(input);
    }
  });
}

function _activateSuggestion(input, nextIndex) {
  var wrap = input.closest('.search-wrap');
  var box = wrap ? wrap.querySelector('.search-suggestions') : null;
  var state = _searchState.get(input) || { items: [], activeIndex: -1 };
  if (!box || !state.items.length) return;
  var buttons = Array.from(box.querySelectorAll('.search-suggestion'));
  if (!buttons.length) return;
  var index = nextIndex;
  if (index < 0) index = buttons.length - 1;
  if (index >= buttons.length) index = 0;
  buttons.forEach(function(btn) { btn.classList.remove('active'); });
  buttons[index].classList.add('active');
  _searchState.set(input, { items: state.items, activeIndex: index });
}

function _bindSearchInputs() {
  document.querySelectorAll('.js-apt-search').forEach(function(input) {
    _searchState.set(input, { items: [], activeIndex: -1 });
    input.addEventListener('input', function() {
      _renderSuggestions(input);
      _syncSearchInputs(input);
    });
    input.addEventListener('focus', function() {
      if (input.value.trim()) _renderSuggestions(input);
    });
    input.addEventListener('keydown', function(e) {
      var state = _searchState.get(input) || { items: [], activeIndex: -1 };
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        _activateSuggestion(input, state.activeIndex + 1);
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        _activateSuggestion(input, state.activeIndex - 1);
      } else if (e.key === 'Enter') {
        if (state.items.length) {
          e.preventDefault();
          var item = state.items[state.activeIndex >= 0 ? state.activeIndex : 0];
          if (item && item.url) location.href = item.url;
        }
      } else if (e.key === 'Escape') {
        _closeSuggestions(input);
      }
    });
  });
  document.addEventListener('click', function(e) {
    document.querySelectorAll('.js-apt-search').forEach(function(input) {
      var wrap = input.closest('.search-wrap');
      if (wrap && !wrap.contains(e.target)) _closeSuggestions(input);
    });
  });
}

function _bindCardTitleMarquee() {
  document.querySelectorAll('.card-title').forEach(function(title) {
    var track = title.querySelector('.card-title-track');
    if (!track) return;
    title.classList.remove('is-marquee');
    title.style.removeProperty('--marquee-shift');
    title.style.removeProperty('--marquee-duration');
    var overflow = Math.ceil(track.scrollWidth - title.clientWidth);
    if (overflow > 4) {
      title.classList.add('is-marquee');
      title.style.setProperty('--marquee-shift', '-' + overflow + 'px');
      var duration = Math.min(12, Math.max(4, overflow / 24));
      title.style.setProperty('--marquee-duration', duration + 's');
    }
  });
}

function _bindUserGuideDismiss() {
  var card = document.getElementById('user-guide-card');
  var btn = document.getElementById('dismiss-user-guide');
  if (!card || !btn) return;
  var today = new Date().toISOString().slice(0, 10);
  var key = 'apt-hide-user-guide-until';
  if (localStorage.getItem(key) === today) {
    card.style.display = 'none';
    return;
  }
  btn.addEventListener('click', function() {
    localStorage.setItem(key, today);
    card.style.display = 'none';
  });
}

function _bindFilterDockProgress() {
  var progress = document.getElementById('filter-dock-progress');
  if (!progress) return;
  function updateProgress() {
    var maxScroll = document.documentElement.scrollHeight - window.innerHeight;
    var ratio = maxScroll > 0 ? Math.min(1, Math.max(0, window.scrollY / maxScroll)) : 0;
    progress.style.width = (ratio * 100).toFixed(2) + '%';
  }
  updateProgress();
  window.addEventListener('scroll', updateProgress, { passive: true });
  window.addEventListener('resize', updateProgress);
}

function _bindScrollTopButton() {
  var btn = document.getElementById('scroll-top-btn');
  if (!btn) return;
  btn.addEventListener('click', function() {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });
}

document.querySelector('.tab-btn[data-group="region"][data-value="전체"]').classList.add('active');
var defaultSupplyBtn = document.querySelector('.tab-btn[data-group="supply"][data-value="전체"]');
if (defaultSupplyBtn) defaultSupplyBtn.classList.add('active');
_bindSearchInputs();
_bindFilterDockProgress();
_bindScrollTopButton();
_bindUserGuideDismiss();
_applyFilters();
</script>"""


def load_posts() -> list[dict]:
    posts: list[dict] = []
    for meta_path in POSTS_DIR.glob("*/post_meta.json"):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            post_dir = meta_path.parent.name
            meta["post_url"] = f"posts/{post_dir}/post.html"
            if not meta.get("region_category"):
                from regions import region_name_to_category
                meta["region_category"] = region_name_to_category(meta.get("location", ""))
            meta.setdefault("price_range", "")
            meta.setdefault("special_supply_date", "")
            posts.append(meta)
        except Exception as exc:
            print(f"  [경고] {meta_path} 파싱 실패: {exc}")

    def _sort_key(post: dict) -> tuple[str, str]:
        notice_date = str(post.get("notice_date") or "").strip()
        generated_at = str(post.get("generated_at") or "").strip()
        return (notice_date, generated_at)

    posts.sort(key=_sort_key, reverse=True)
    return posts


def _fmt_date(date_str: str) -> tuple[str, str]:
    if not date_str or date_str in ("-", "null", "None"):
        return ("", "")
    try:
        parsed = datetime.fromisoformat(date_str[:10])
        return (f"{parsed.month}월", f"{parsed.day}일")
    except Exception:
        return ("", "")


def _fmt_notice_date(date_str: str) -> str:
    if not date_str or date_str in ("-", "null", "None"):
        return "모집공고일 확인 필요"
    try:
        parsed = datetime.fromisoformat(date_str[:10])
        return f"모집공고일 {parsed.year}년 {parsed.month}월 {parsed.day}일"
    except Exception:
        return "모집공고일 확인 필요"


def _get_latest_notice_date(posts: list[dict]) -> str:
    """Get the most recent notice_date from all posts and format as Korean string."""
    if not posts:
        return "2026년 4월 22일"
    for post in posts:
        notice_date = post.get("notice_date", "").strip()
        if notice_date and notice_date not in ("-", "null", "None"):
            try:
                parsed = datetime.fromisoformat(notice_date[:10])
                return f"{parsed.year}년 {parsed.month}월 {parsed.day}일"
            except Exception:
                continue
    return "2026년 4월 22일"


def _supply_info(title: str, apt_name: str) -> tuple[str, str, str]:
    combined = title + " " + apt_name
    resupply_map = [
        ("무순위", "무순위"),
        ("불법행위", "불법행위재공급"),
        ("임의", "임의공급"),
        ("취소후", "취소후재공급"),
        ("잔여", "잔여세대"),
    ]
    for keyword, label in resupply_map:
        if keyword in combined:
            return label, "var(--c-card-grad-resupply)", "resupply"

    label = "공공분양" if any(keyword in combined.lower() for keyword in _PUBLIC_KW) else "민간분양"
    return label, "var(--c-card-grad-new)", "new"


def _supply_filter_key(title: str, apt_name: str) -> str:
    label, _, tag_type = _supply_info(title, apt_name)
    return "재공급" if tag_type == "resupply" else label


def _date_cell(label: str, month: str, day: str) -> str:
    if not month:
        return (
            f'<div style="flex:1;padding:12px 14px;text-align:center;">'
            f'<p style="font-size:10px;font-weight:600;color:var(--c-mid);letter-spacing:1px;margin-bottom:5px;">{label}</p>'
            f'<p style="font-size:13px;color:var(--c-mid);">-</p>'
            f'</div>'
        )
    return (
        f'<div style="flex:1;padding:12px 14px;text-align:center;">'
        f'<p style="font-size:10px;font-weight:600;color:var(--c-mid);letter-spacing:1px;margin-bottom:5px;">{label}</p>'
        f'<p style="font-size:16px;font-weight:700;color:var(--c-dark);line-height:1.3;">{month} {day}</p>'
        f'</div>'
    )


def _render_filter_btn(label: str, count: int, js_value: str, group: str, include_count: bool = True) -> str:
    count_html = f'<span class="tab-count"> ({count})</span>' if include_count else ""
    return (
        f'<button class="tab-btn" data-group="{group}" data-value="{js_value}" '
        f'onclick="filterGroup(this,\'{group}\',\'{js_value}\')">'
        f'{label}{count_html}'
        f'</button>'
    )


def _render_featured_items(posts: list[dict]) -> str:
    featured = posts[:6]
    if not featured:
        return ""
    items: list[str] = []
    for post in featured:
        apt_name = post.get("apt_name", "(단지명 없음)")
        location = (post.get("location") or "").strip() or "주소 정보 없음"
        items.append(
            f'''<a href="{post["post_url"]}" class="featured-item" data-name="{apt_name.lower()}" style="display:block;text-decoration:none;">
              <p class="featured-title" style="font-size:17px;font-weight:800;line-height:1.45;color:var(--c-dark);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-bottom:4px;">
                {apt_name}
              </p>
              <p class="featured-meta" style="font-size:12px;color:var(--c-mid);line-height:1.6;">
                {location}
              </p>
            </a>'''
        )
    return "\n".join(items)


def _render_card(post: dict) -> str:
    apt_name = post.get("apt_name", "(단지명 없음)")
    title = post.get("title", apt_name)
    location = post.get("location", "")
    region = post.get("region_category", "기타")
    url = post["post_url"]
    tags = (post.get("tags") or [])[:4]
    supply_label, header_grad, tag_type = _supply_info(title, apt_name)
    supply_key = _supply_filter_key(title, apt_name)
    price_range = (post.get("price_range") or "분양가 확인 필요").replace("약", "").strip()
    move_in = post.get("move_in_date") or "입주 시기 확인 필요"
    sp_month, sp_day = _fmt_date(post.get("special_supply_date", ""))
    r1_month, r1_day = _fmt_date(post.get("rank1_date", ""))
    tag_items = "".join(
        f'<span style="display:inline-block;background:var(--c-tag-{tag_type}-bg);color:var(--c-tag-{tag_type}-text);'
        f'font-size:11px;font-weight:700;padding:3px 9px;border-radius:4px;margin:0 4px 5px 0;letter-spacing:0.2px;">#{tag}</span>'
        for tag in tags
    ) or '<span style="font-size:11px;color:var(--c-mid);">-</span>'
    return f"""<article class="post-card" data-region="{region}" data-supply="{supply_key}" data-name="{apt_name}" data-url="{url}" onclick="location.href='{url}'">
  <div class="card-header" style="background:{header_grad};">
    <div style="position:absolute;inset:0;background-image:radial-gradient(rgba(255,255,255,0.07) 1.5px,transparent 1.5px);background-size:18px 18px;pointer-events:none;"></div>
    <div style="position:relative;margin-bottom:10px;">
      <span style="font-size:11px;font-weight:900;color:#fff;letter-spacing:1px;text-transform:uppercase;">{supply_label}</span>
    </div>
    <p class="card-title">
      <span class="card-title-track">{apt_name}</span>
    </p>
    <div style="position:relative;margin-top:auto;padding-top:12px;">
      <span style="display:inline-flex;max-width:100%;align-items:center;padding:7px 10px;border-radius:999px;background:rgba(255,255,255,0.14);border:1px solid rgba(255,255,255,0.22);color:#fff;font-size:12px;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
        {price_range}
      </span>
    </div>
  </div>
  <div style="display:flex;border-bottom:1px solid var(--c-light-gray);">
    {_date_cell("특별공급", sp_month, sp_day)}
    <div style="width:1px;background:var(--c-light-gray);flex-shrink:0;margin:10px 0;"></div>
    {_date_cell("1순위", r1_month, r1_day)}
  </div>
  <div style="padding:11px 16px;border-bottom:1px solid var(--c-light-gray);">
    <p style="font-size:12px;font-weight:500;color:var(--c-dark);margin:0;line-height:1.4;">📌 {location if location else "위치 정보 없음"}</p>
  </div>
  <div style="padding:12px 16px 9px;flex:1;">{tag_items}</div>
  <a href="{url}" class="card-cta" onclick="event.stopPropagation()">공고 분석 전문 보기 →</a>
</article>"""


def _render_list_search_bar() -> str:
    return """<div class="search-wrap">
      <span class="search-icon">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
        </svg>
      </span>
      <input class="search-input js-apt-search" type="text" placeholder="단지명 검색" autocomplete="off">
      <div class="search-suggestions"></div>
    </div>"""


def _build_sitemap(posts: list[dict]) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    urls = [
        f"<url><loc>{SITE_URL}/</loc><lastmod>{now}</lastmod><changefreq>daily</changefreq><priority>1.0</priority></url>"
    ]
    for post in posts:
        urls.append(
            f"<url><loc>{SITE_URL}/{post['post_url']}</loc><lastmod>{now}</lastmod>"
            f"<changefreq>weekly</changefreq><priority>0.8</priority></url>"
        )
    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(urls) + "\n</urlset>"
    out = OUTPUT_DIR / "sitemap.xml"
    out.write_text(sitemap, encoding="utf-8")
    print(f"✅ sitemap.xml 생성 완료: {out}  ({len(posts) + 1}개 URL)")


def _build_robots() -> None:
    out = OUTPUT_DIR / "robots.txt"
    out.write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n", encoding="utf-8")
    print(f"✅ robots.txt 생성 완료: {out}")


def build_front_index() -> None:
    posts = load_posts()
    print(f"  포스트 {len(posts)}건 로드")
    template = TEMPLATE_PATH.read_text(encoding="utf-8")

    region_counts: dict[str, int] = {}
    supply_counts: dict[str, int] = {}
    for post in posts:
        region = post.get("region_category", "기타")
        region_counts[region] = region_counts.get(region, 0) + 1
        supply = _supply_filter_key(post.get("title", post.get("apt_name", "")), post.get("apt_name", ""))
        supply_counts[supply] = supply_counts.get(supply, 0) + 1

    region_order = [
        "서울", "경기도", "인천", "부산", "대전", "대구", "광주",
        "세종", "울산", "강원도", "충청북도", "충청남도",
        "전라북도", "전라남도", "경상북도", "경상남도", "제주도",
    ]
    region_short_labels = {
        "강원도": "강원",
        "충청북도": "충북",
        "충청남도": "충남",
        "전라북도": "전북",
        "전라남도": "전남",
        "경상북도": "경북",
        "경상남도": "경남",
        "제주도": "제주",
    }
    known = list(region_order)
    unknown = sorted(region for region in region_counts if region not in region_order)
    regions = ["전체"] + known + unknown
    total = len(posts)

    region_tabs = "".join(
        _render_filter_btn(
            region_short_labels.get(region, region),
            total if region == "전체" else region_counts.get(region, 0),
            region,
            "region",
            include_count=False,
        )
        for region in regions
    )

    latest_date = _get_latest_notice_date(posts)

    html = template
    html = html.replace("{{PALETTE_INIT_JS}}", PALETTE_INIT_JS)
    html = html.replace("{{INDEX_NAV}}", index_nav("/"))
    html = html.replace("{{FEATURED_ITEMS}}", _render_featured_items(posts))
    html = html.replace("{{RESULT_COUNT_HTML}}", f'총 <strong style="color:var(--c-dark);">{total}</strong>건')
    html = html.replace("{{LIST_SEARCH_BAR}}", _render_list_search_bar())
    html = html.replace("{{REGION_TABS}}", region_tabs)
    html = html.replace("{{SUPPLY_TABS}}", "")
    html = html.replace("{{CARDS_HTML}}", "\n".join(_render_card(post) for post in posts))
    html = html.replace("{{INDEX_RUNTIME_SCRIPT}}", INDEX_RUNTIME_SCRIPT)
    html = html.replace("최근 업데이트 2026년 4월 22일", f"최근 업데이트 {latest_date}")

    OUT_FILE.write_text(html, encoding="utf-8")
    print(f"✅ index.html 생성 완료: {OUT_FILE}  ({len(posts)}건)")
    _build_sitemap(posts)
    _build_robots()


if __name__ == "__main__":
    build_front_index()
