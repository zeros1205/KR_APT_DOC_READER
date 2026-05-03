"""
index_renderer.py
──────────────────────────────────────────────
최신 프런트 페이지 산출물 구조를 보존하는 index 전용 렌더러.

- 템플릿: templates/front_index_template.html
- 데이터 소스: output/posts/*/post_meta.json
- 산출물: output/index.html / sitemap.xml / robots.txt
"""

from __future__ import annotations

import argparse
import json
import re
from html import escape
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

try:
    from shared_ui import PALETTE_INIT_JS, index_nav
    from public_notices import is_public_notice_data
except ImportError:
    from pipeline.shared_ui import PALETTE_INIT_JS, index_nav
    from pipeline.public_notices import is_public_notice_data

ROOT = Path(__file__).parent.parent
OUTPUT_DIR = ROOT / "output"
POSTS_DIR = OUTPUT_DIR / "posts"
CACHE_DIR = OUTPUT_DIR / "data_cache" / "notices"
OUT_FILE = OUTPUT_DIR / "index.html"
POSTS_INDEX_FILE = OUTPUT_DIR / "posts_index.json"
POSTS_INDEX_JS_FILE = OUTPUT_DIR / "posts_index.js"
TEMPLATE_PATH = ROOT / "templates" / "front_index_template.html"

SITE_URL = "https://apt-note.com"
EXPIRED_GRAD = "linear-gradient(135deg, #6F746F 0%, #555B56 60%, #3F4540 100%)"
SEOUL_TZ = ZoneInfo("Asia/Seoul")
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
  var visibleCards = matched.slice(start, end);
  document.querySelectorAll('.post-card').forEach(function(card) { card.style.display = 'none'; });
  visibleCards.forEach(function(card) { card.style.display = ''; });
  requestAnimationFrame(function() { _bindCardTitleMarquee(visibleCards); });
}

function _showCardLoadError() {
  var grid = document.getElementById('cards-grid');
  if (grid) {
    grid.innerHTML = '<div class="cards-load-error">'
      + '<p>분양 공고 목록을 불러오지 못했어요.<br>잠시 후 새로고침해 주세요.</p>'
      + '<button type="button" onclick="location.reload()">새로고침</button>'
      + '</div>';
  }
  var resultCount = document.getElementById('result-count');
  if (resultCount) {
    resultCount.innerHTML = '총 <strong style="color:var(--c-dark);">0</strong>건';
  }
}

function _loadPostsIndex() {
  function applyPayload(payload) {
    var grid = document.getElementById('cards-grid');
    if (!grid) return;
    var cards = Array.isArray(payload.cards) ? payload.cards : [];
    grid.innerHTML = cards.map(function(card) { return card.html || ''; }).join('');
    _currentPage = 1;
    _applyFilters();
  }
  if (window.__APT_POSTS_INDEX__) {
    applyPayload(window.__APT_POSTS_INDEX__);
    return;
  }
  fetch('posts_index.json', { cache: 'no-store' })
    .then(function(response) {
      if (!response.ok) throw new Error('posts_index.json ' + response.status);
      return response.json();
    })
    .then(applyPayload)
    .catch(function(error) {
      console.error('[posts-index] load failed', error);
      _showCardLoadError();
    });
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
  var html = '';
  var blockSize = 5;
  var startPage = Math.floor((_currentPage - 1) / blockSize) * blockSize + 1;
  var endPage = Math.min(pages, startPage + blockSize - 1);
  if (startPage > 1) {
    html += '<button ' + btnBase + ' aria-label="이전 5페이지" onclick="goPage(' + (startPage - 1) + ')">&lsaquo;</button>';
  }
  for (var i = startPage; i <= endPage; i++) {
    if (i === _currentPage) {
      html += '<button ' + btnActive + '>' + i + '</button>';
    } else {
      html += '<button ' + btnBase + ' onclick="goPage(' + i + ')">' + i + '</button>';
    }
  }
  if (endPage < pages) {
    html += '<button ' + btnBase + ' aria-label="다음 5페이지" onclick="goPage(' + (endPage + 1) + ')">&rsaquo;</button>';
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
  var dock = document.getElementById('filter-dock');
  var stickyOffset = 54 + (dock ? dock.offsetHeight : 0) + 18;
  if (grid && window.scrollY > grid.offsetTop - stickyOffset - 40) {
    window.scrollTo({ top: grid.offsetTop - stickyOffset, behavior: 'smooth' });
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
    var key = name.replace(/\\s+/g, '').toLowerCase();
    if (seen.has(key)) return false;
    var matched = name.toLowerCase().includes(q);
    if (matched) seen.add(key);
    return matched;
  }).slice(0, 10).map(function(card) {
    return {
      name: card.dataset.name || '',
      url: card.dataset.url || '',
      action: card.dataset.action || 'detail',
      applyhomeUrl: card.dataset.applyhomeUrl || '',
      region: card.dataset.region || '',
      supply: card.dataset.supply || ''
    };
  });
}

function openPublicNotice(url) {
  if (!url) return;
  var message = '이 공공분양 공고는 청약Home에서 자세히 확인할 수 있어요.\\n청약Home 공고 페이지로 이동할까요?';
  if (window.confirm(message)) {
    window.open(url, '_blank', 'noopener');
  }
}

function _openSuggestionItem(item) {
  if (!item) return;
  if (item.action === 'applyhome') {
    openPublicNotice(item.applyhomeUrl || item.url);
    return;
  }
  if (item.url) location.href = item.url;
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
    var outlink = item.action === 'applyhome'
      ? '<span class="search-suggestion-outlink" aria-hidden="true" title="청약Home에서 보기">'
        + '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">'
        + '<path d="M15 3h6v6"></path><path d="M10 14 21 3"></path><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>'
        + '</svg></span>'
      : '';
    return '<button type="button" class="search-suggestion" data-index="' + idx + '" data-url="' + item.url + '">'
      + '<span class="search-suggestion-copy">'
      + '<span class="search-suggestion-title">' + item.name + '</span>'
      + '<span class="search-suggestion-meta">' + item.region + ' · ' + item.supply + '</span>'
      + '</span>'
      + outlink
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
    btn.addEventListener('click', function() {
      var state = _searchState.get(input) || { items: [] };
      _openSuggestionItem(state.items[Number(btn.dataset.index)]);
    });
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
          _openSuggestionItem(item);
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

function _bindCardTitleMarquee(cards) {
  var titles = [];
  if (Array.isArray(cards) && cards.length) {
    cards.forEach(function(card) {
      var title = card.querySelector('.card-title');
      if (title) titles.push(title);
    });
  } else {
    titles = Array.from(document.querySelectorAll('.post-card:not([style*="display: none"]) .card-title'));
  }
  titles.forEach(function(title) {
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

function _syncFrontHeaderHeight() {
  var header = document.querySelector('.site-header-v3');
  var headerHeight = header ? Math.ceil(header.getBoundingClientRect().height) : 68;
  document.documentElement.style.setProperty('--front-header-height', headerHeight + 'px');
  return headerHeight;
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
_bindScrollTopButton();
_syncFrontHeaderHeight();
window.addEventListener('resize', _syncFrontHeaderHeight);
window.addEventListener('orientationchange', _syncFrontHeaderHeight);
_loadPostsIndex();
</script>"""


def _notice_id_from_url(url: str) -> str:
    if not url:
        return ""
    try:
        query = parse_qs(urlparse(url).query)
        return (query.get("pblancNo") or query.get("houseManageNo") or [""])[0]
    except Exception:
        return ""


def _post_notice_id(post: dict, fallback: str = "") -> str:
    return str(
        post.get("notice_id")
        or _notice_id_from_url(str(post.get("notice_url") or ""))
        or fallback
    ).strip()


def _fmt_move_in_month(value: object) -> str:
    text = str(value or "").strip()
    if re.fullmatch(r"\d{6}", text):
        return f"{text[:4]}년 {int(text[4:])}월"
    return text


def _fmt_price_range_from_units(units: list[dict]) -> str:
    prices: list[int] = []
    for unit in units or []:
        raw = unit.get("LTTOT_TOP_AMOUNT") or unit.get("price_max") or unit.get("price_min")
        try:
            value = int(str(raw).replace(",", "").strip())
        except Exception:
            continue
        if value > 0:
            prices.append(value)
    if not prices:
        return ""

    def _fmt(manwon: int) -> str:
        uk, man = divmod(manwon, 10000)
        if uk and man:
            return f"{uk}억 {man:,}만원"
        if uk:
            return f"{uk}억원"
        return f"{man:,}만원"

    lo, hi = min(prices), max(prices)
    return _fmt(lo) if lo == hi else f"{_fmt(lo)} ~ {_fmt(hi)}"


def _public_post_from_payload(path: Path) -> dict | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        print(f"  [경고] {path} 파싱 실패: {exc}")
        return None

    doc = payload.get("document") or {}
    if not is_public_notice_data(doc):
        return None

    apt_name = str(doc.get("apt_name") or payload.get("apt_name") or "(단지명 없음)")
    notice_url = str(doc.get("notice_url") or "")
    supply_address = str(doc.get("supply_address") or "")
    location = supply_address or str(doc.get("region_name") or "")

    try:
        from regions import region_name_to_category
    except ImportError:
        from pipeline.regions import region_name_to_category

    notice_id = str(payload.get("notice_id") or doc.get("notice_id") or path.stem)
    return {
        "notice_id": notice_id,
        "apt_name": apt_name,
        "title": apt_name,
        "subtitle": supply_address,
        "theme": "claude",
        "tags": ["공공분양", "청약Home", "입주자모집공고"],
        "location": location,
        "region_category": region_name_to_category(location),
        "supply_type": doc.get("supply_type") or "공공분양",
        "price_range": _fmt_price_range_from_units(payload.get("unit_types") or []),
        "special_supply_date": doc.get("special_supply_start") or doc.get("special_supply_date") or "",
        "rank1_date": doc.get("rank1_local_start") or doc.get("rank1_etc_start") or "",
        "rank2_date": doc.get("rank2_local_start") or doc.get("rank2_etc_start") or "",
        "winner_date": doc.get("winner_date") or "",
        "notice_date": doc.get("notice_date") or "",
        "move_in_date": _fmt_move_in_month(doc.get("move_in_month")),
        "supply_address": supply_address,
        "notice_url": notice_url,
        "post_url": notice_url,
        "index_action": "applyhome",
        "generated_at": payload.get("collected_at") or "",
    }


def load_posts() -> list[dict]:
    posts: list[dict] = []
    for meta_path in POSTS_DIR.glob("*/post_meta.json"):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            post_dir = meta_path.parent.name
            meta["post_url"] = f"posts/{post_dir}/post.html"
            meta["notice_id"] = _post_notice_id(meta, post_dir)
            if not meta.get("region_category"):
                from regions import region_name_to_category
                meta["region_category"] = region_name_to_category(meta.get("location", ""))
            meta.setdefault("price_range", "")
            meta.setdefault("special_supply_date", "")
            posts.append(meta)
        except Exception as exc:
            print(f"  [경고] {meta_path} 파싱 실패: {exc}")

    public_posts: dict[str, dict] = {}
    if CACHE_DIR.exists():
        for cache_path in CACHE_DIR.glob("*.json"):
            public_post = _public_post_from_payload(cache_path)
            if public_post:
                public_posts[_post_notice_id(public_post, cache_path.stem)] = public_post

    if public_posts:
        posts = [
            post for post in posts
            if _post_notice_id(post) not in public_posts
        ]
        posts.extend(public_posts.values())

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


def _fmt_latest_notice_date(posts: list[dict]) -> str:
    latest = max((_parse_date(post.get("notice_date")) for post in posts), default=None)
    if not latest:
        return "최근 업데이트 기준일 확인 필요"
    return f"최근 업데이트 {latest.year}년 {latest.month}월 {latest.day}일"


def _parse_date(value: object) -> date | None:
    text = str(value or "").strip()
    if not text or text in ("-", "null", "None"):
        return None
    text = text.split(" ~ ", 1)[0].strip()
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def _is_expired(post: dict) -> bool:
    winner = _parse_date(post.get("winner_date"))
    today = datetime.now(SEOUL_TZ).date()
    return bool(winner and winner < today)


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
        apt_name = escape(str(post.get("apt_name", "(단지명 없음)")))
        location = escape((post.get("location") or "").strip() or "주소 정보 없음")
        url = escape(str(post.get("post_url") or "#"), quote=True)
        if post.get("index_action") == "applyhome":
            href = "#"
            action_attr = f'onclick="event.preventDefault();openPublicNotice(\'{url}\')"'
        else:
            href = url
            action_attr = ""
        items.append(
            f'''<a href="{href}" class="featured-item" data-name="{apt_name.lower()}" {action_attr} style="display:block;text-decoration:none;">
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
    apt_name = str(post.get("apt_name", "(단지명 없음)"))
    title = str(post.get("title", apt_name))
    location = str(post.get("location", ""))
    region = str(post.get("region_category", "기타"))
    url = str(post["post_url"])
    action = str(post.get("index_action") or "detail")
    applyhome_url = str(post.get("notice_url") or url)
    tags = (post.get("tags") or [])[:4]
    supply_label, header_grad, tag_type = _supply_info(title, apt_name)
    supply_key = _supply_filter_key(title, apt_name)
    if action == "applyhome":
        supply_label = "공공분양"
        supply_key = "공공분양"
        header_grad = "linear-gradient(145deg,#6f9fd1 0%,#477fb9 100%)"
        tag_type = "resupply"
    if _is_expired(post):
        header_grad = EXPIRED_GRAD
    price_range = str(post.get("price_range") or "분양가 확인 필요").replace("약", "").strip()
    sp_month, sp_day = _fmt_date(post.get("special_supply_date", ""))
    r1_month, r1_day = _fmt_date(post.get("rank1_date", ""))
    safe_apt_name = escape(apt_name)
    safe_location = escape(location)
    safe_region = escape(region, quote=True)
    safe_supply_key = escape(supply_key, quote=True)
    safe_url = escape(url, quote=True)
    safe_applyhome_url = escape(applyhome_url, quote=True)
    safe_action = escape(action, quote=True)
    safe_supply_label = escape(supply_label)
    safe_price_range = escape(price_range)
    if action == "applyhome":
        card_click = f"openPublicNotice('{safe_applyhome_url}')"
        cta_href = "#"
        cta_click = f"event.preventDefault();event.stopPropagation();openPublicNotice('{safe_applyhome_url}')"
        cta_text = (
            '청약Home '
            '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" '
            'stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" '
            'aria-hidden="true" style="margin-left:5px;flex-shrink:0;color:#fff;">'
            '<path d="M15 3h6v6"></path><path d="M10 14 21 3"></path>'
            '<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>'
            '</svg>'
        )
    else:
        card_click = f"location.href='{safe_url}'"
        cta_href = safe_url
        cta_click = "event.stopPropagation()"
        cta_text = "분석결과 보기"
    tag_items = "".join(
        f'<span style="display:inline-block;background:var(--c-tag-{tag_type}-bg);color:var(--c-tag-{tag_type}-text);'
        f'font-size:11px;font-weight:700;padding:3px 9px;border-radius:4px;margin:0 4px 5px 0;letter-spacing:0.2px;">#{escape(str(tag))}</span>'
        for tag in tags
    ) or '<span style="font-size:11px;color:var(--c-mid);">-</span>'
    return f"""<article class="post-card" data-region="{safe_region}" data-supply="{safe_supply_key}" data-name="{safe_apt_name}" data-url="{safe_url}" data-action="{safe_action}" data-applyhome-url="{safe_applyhome_url}" onclick="{card_click}">
  <div class="card-header" style="background:{header_grad};">
    <div style="position:absolute;inset:0;background-image:radial-gradient(rgba(255,255,255,0.07) 1.5px,transparent 1.5px);background-size:18px 18px;pointer-events:none;"></div>
    <div style="position:relative;margin-bottom:10px;">
      <span style="font-size:11px;font-weight:900;color:#fff;letter-spacing:1px;text-transform:uppercase;">{safe_supply_label}</span>
    </div>
    <p class="card-title">
      <span class="card-title-track">{safe_apt_name}</span>
    </p>
    <div style="position:relative;margin-top:auto;padding-top:12px;">
      <span style="display:inline-flex;max-width:100%;align-items:center;padding:7px 10px;border-radius:999px;background:rgba(255,255,255,0.14);border:1px solid rgba(255,255,255,0.22);color:#fff;font-size:12px;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
        {safe_price_range}
      </span>
    </div>
  </div>
  <div style="display:flex;border-bottom:1px solid var(--c-light-gray);">
    {_date_cell("특별공급", sp_month, sp_day)}
    <div style="width:1px;background:var(--c-light-gray);flex-shrink:0;margin:10px 0;"></div>
    {_date_cell("1순위", r1_month, r1_day)}
  </div>
  <div style="padding:11px 16px;border-bottom:1px solid var(--c-light-gray);">
    <p style="font-size:12px;font-weight:500;color:var(--c-dark);margin:0;line-height:1.4;">📌 {safe_location if safe_location else "위치 정보 없음"}</p>
  </div>
  <div style="padding:12px 16px 9px;flex:1;">{tag_items}</div>
  <a href="{cta_href}" class="card-cta" onclick="{cta_click}">{cta_text}</a>
</article>"""


def _build_posts_index(posts: list[dict]) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total": len(posts),
        "cards": [
            {
                "apt_name": post.get("apt_name", ""),
                "notice_id": post.get("notice_id", ""),
                "post_url": post.get("post_url", ""),
                "index_action": post.get("index_action", "detail"),
                "notice_url": post.get("notice_url", ""),
                "region": post.get("region_category", "기타"),
                "notice_date": post.get("notice_date", ""),
                "winner_date": post.get("winner_date", ""),
                "html": _render_card(post),
            }
            for post in posts
        ],
    }
    POSTS_INDEX_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    POSTS_INDEX_JS_FILE.write_text(
        "window.__APT_POSTS_INDEX__ = "
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        + ";\n",
        encoding="utf-8",
    )
    print(f"✅ posts_index.json 생성 완료: {POSTS_INDEX_FILE}  ({len(posts)}건)")
    print(f"✅ posts_index.js 생성 완료: {POSTS_INDEX_JS_FILE}  ({len(posts)}건)")


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
    for static_path in ("privacy.html", "terms.html"):
        urls.append(
            f"<url><loc>{SITE_URL}/{static_path}</loc><lastmod>{now}</lastmod>"
            f"<changefreq>monthly</changefreq><priority>0.4</priority></url>"
        )
    for post in posts:
        if post.get("index_action") == "applyhome":
            continue
        urls.append(
            f"<url><loc>{SITE_URL}/{post['post_url']}</loc><lastmod>{now}</lastmod>"
            f"<changefreq>weekly</changefreq><priority>0.8</priority></url>"
        )
    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(urls) + "\n</urlset>"
    out = OUTPUT_DIR / "sitemap.xml"
    out.write_text(sitemap, encoding="utf-8")
    print(f"✅ sitemap.xml 생성 완료: {out}  ({len(urls)}개 URL)")


def _build_robots() -> None:
    out = OUTPUT_DIR / "robots.txt"
    out.write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n", encoding="utf-8")
    print(f"✅ robots.txt 생성 완료: {out}")


def build_front_index(*, render_shell: bool = True) -> None:
    posts = load_posts()
    print(f"  포스트 {len(posts)}건 로드")
    if not render_shell:
        _build_posts_index(posts)
        _build_sitemap(posts)
        _build_robots()
        print("✅ 동적 카드 데이터만 갱신 완료 (index.html 유지)")
        return

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

    html = template
    html = html.replace("{{PALETTE_INIT_JS}}", PALETTE_INIT_JS)
    html = html.replace("{{INDEX_NAV}}", index_nav("/"))
    html = html.replace("{{FEATURED_ITEMS}}", _render_featured_items(posts))
    html = html.replace("{{RESULT_COUNT_HTML}}", f'총 <strong style="color:var(--c-dark);">{total}</strong>건')
    html = html.replace("{{LATEST_NOTICE_DATE}}", _fmt_latest_notice_date(posts))
    html = html.replace("{{LIST_SEARCH_BAR}}", _render_list_search_bar())
    html = html.replace("{{REGION_TABS}}", region_tabs)
    html = html.replace("{{SUPPLY_TABS}}", "")
    html = html.replace("{{CARDS_HTML}}", '<div class="cards-loading">분양 공고 목록을 불러오는 중입니다.</div>')
    html = html.replace("{{INDEX_RUNTIME_SCRIPT}}", INDEX_RUNTIME_SCRIPT)

    OUT_FILE.write_text(html, encoding="utf-8")
    print(f"✅ index.html 생성 완료: {OUT_FILE}  ({len(posts)}건)")
    _build_posts_index(posts)
    _build_sitemap(posts)
    _build_robots()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build front page shell or dynamic post index data")
    parser.add_argument(
        "--data-only",
        action="store_true",
        help="Update posts_index.json/sitemap/robots without regenerating output/index.html",
    )
    args = parser.parse_args()
    build_front_index(render_shell=not args.data_only)
