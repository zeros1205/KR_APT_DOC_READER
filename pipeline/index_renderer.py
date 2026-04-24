"""
index_renderer.py
──────────────────────────────────────────────────
Dynamic front page with manifest.json approach

- Static index.html template created once
- Dynamic manifest.json updated after each post
- JavaScript loads and renders manifest data
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
MANIFEST_FILE = OUTPUT_DIR / "manifest.json"
TEMPLATE_PATH = ROOT / "templates" / "front_index_template.html"

SITE_URL = "https://apt-note.com"


def load_posts() -> list[dict]:
    """output/posts 디렉토리에서 모든 post_meta.json 로드"""
    posts = []
    if not POSTS_DIR.exists():
        return posts

    for post_dir in sorted(POSTS_DIR.iterdir(), reverse=True):
        if not post_dir.is_dir():
            continue
        meta_file = post_dir / "post_meta.json"
        if not meta_file.exists():
            continue
        try:
            post_data = json.loads(meta_file.read_text(encoding="utf-8"))
            post_data["_dir"] = post_dir.name
            posts.append(post_data)
        except Exception as e:
            print(f"⚠️ 포스트 로드 실패: {post_dir.name} - {e}")
    return posts


def _extract_region(location_str: str) -> str:
    """location 문자열에서 지역 추출"""
    if not location_str:
        return "기타"
    parts = location_str.split(" / ")
    return parts[0] if parts else "기타"


def build_front_index_once() -> None:
    """첫 실행 시에만 index.html 생성 (이후 수정 없음)"""
    if OUT_FILE.exists():
        return

    template = TEMPLATE_PATH.read_text(encoding="utf-8")

    today = datetime.now()
    latest_update_date = f"{today.year}년 {today.month}월 {today.day}일"

    html = template
    html = html.replace("{{PALETTE_INIT_JS}}", PALETTE_INIT_JS)
    html = html.replace("{{INDEX_NAV}}", index_nav("/"))
    html = html.replace("{{LATEST_UPDATE_DATE}}", latest_update_date)
    html = html.replace("{{INDEX_RUNTIME_SCRIPT}}", _render_runtime_script())

    OUT_FILE.write_text(html, encoding="utf-8")
    print(f"✅ index.html 초기 생성 완료: {OUT_FILE}")


def _render_runtime_script() -> str:
    """JavaScript 런타임 스크립트 생성"""
    return r"""<script>
var POSTS_PER_PAGE = 12;
var _currentPage = 1;
var _activeFilters = {
  region: '전체',
};
var _manifestData = { posts: [], regions: [] };

async function initPage() {
  await loadManifest();
  renderRegionTabs();
  renderCards();
}

async function loadManifest() {
  try {
    var response = await fetch('./manifest.json');
    _manifestData = await response.json();
  } catch (e) {
    console.error('manifest.json 로드 실패:', e);
    _manifestData = { posts: [], regions: [] };
  }
}

function renderRegionTabs() {
  var container = document.getElementById('region-tabs-container');
  if (!container) return;

  var regions = _manifestData.regions || [];
  var buttons = regions.map(function(region) {
    var isActive = region.code === '전체' ? 'active' : '';
    return '<button class="tab-btn ' + isActive + '" data-region="' + region.code + '" ' +
           "onclick=\"filterByRegion(this, '" + region.code + "')\">" +
           region.name + ' (' + region.count + ')' +
           '</button>';
  }).join('');
  container.innerHTML = buttons;
}

function filterByRegion(btn, regionCode) {
  document.querySelectorAll('.tab-btn').forEach(function(b) {
    b.classList.remove('active');
  });
  btn.classList.add('active');
  _activeFilters.region = regionCode;
  _currentPage = 1;
  renderCards();
}

function renderCards() {
  var posts = _manifestData.posts || [];
  var filtered = posts.filter(function(post) {
    var regionMatch = _activeFilters.region === '전체' || post.region === _activeFilters.region;
    return regionMatch;
  });

  var grid = document.getElementById('cards-grid');
  if (!grid) return;

  var start = (_currentPage - 1) * POSTS_PER_PAGE;
  var end = start + POSTS_PER_PAGE;
  var page_posts = filtered.slice(start, end);

  grid.innerHTML = page_posts.map(function(post) {
    return '<div class="post-card" data-region="' + post.region + '">' +
           '<a href="/posts/' + post._dir + '/post.html" style="text-decoration:none;color:inherit;">' +
           '<h3 style="margin:0 0 8px;font-size:16px;font-weight:600;">' + post.apt_name + '</h3>' +
           '<p style="margin:0 0 6px;font-size:13px;color:#666;">' + post.location + '</p>' +
           '<p style="margin:0;font-size:12px;color:#999;">생성일: ' + post.created_at + '</p>' +
           '</a>' +
           '</div>';
  }).join('');

  var resultCount = document.getElementById('result-count');
  if (resultCount) {
    resultCount.innerHTML = '총 <strong>' + filtered.length + '</strong>건';
  }

  var noResult = document.getElementById('no-result');
  if (noResult) {
    noResult.style.display = filtered.length === 0 ? 'block' : 'none';
  }
}

document.addEventListener('DOMContentLoaded', initPage);
</script>"""


def build_manifest() -> None:
    """manifest.json 업데이트 (동적으로 호출됨)"""
    posts = load_posts()

    regions_map = {}
    for post in posts:
        location = post.get("location", "")
        region = _extract_region(location)
        if region not in regions_map:
            regions_map[region] = 0
        regions_map[region] += 1

    regions = [{"code": "all", "name": "전체", "count": len(posts)}]
    for region_name in sorted(regions_map.keys()):
        regions.append({
            "code": region_name,
            "name": region_name,
            "count": regions_map[region_name]
        })

    manifest_posts = []
    for post in posts:
        location = post.get("location", "")
        manifest_posts.append({
            "id": post.get("_dir", ""),
            "_dir": post.get("_dir", ""),
            "apt_name": post.get("apt_name", ""),
            "location": location,
            "price_range": post.get("price_range", ""),
            "region": _extract_region(location),
            "post_title": post.get("title", post.get("apt_name", "")),
            "quality_score": post.get("quality_score", 0),
            "theme": post.get("theme", "claude"),
            "created_at": post.get("created_at", datetime.now().isoformat())[:10],
        })

    manifest = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "total_posts": len(posts),
            "version": "2.0"
        },
        "regions": regions,
        "posts": manifest_posts
    }

    MANIFEST_FILE.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ manifest.json 업데이트: {len(posts)}건")


if __name__ == "__main__":
    build_front_index_once()
    build_manifest()
