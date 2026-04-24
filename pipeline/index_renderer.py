"""
index_renderer.py (수정 버전)
──────────────────────────────────────────────
index.html 고정화 + manifest.json 동적 렌더링

- index.html: 초기 생성 후 절대 변경 안 함
- manifest.json: 매번 업데이트 (포스팅 변경 시)
"""

import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
OUTPUT_DIR = ROOT / "output"
POSTS_DIR = OUTPUT_DIR / "posts"
OUT_FILE = OUTPUT_DIR / "index.html"
MANIFEST_FILE = OUTPUT_DIR / "manifest.json"
TEMPLATE_PATH = ROOT / "templates" / "front_index_template.html"

try:
    from shared_ui import PALETTE_INIT_JS, index_nav
except ImportError:
    from pipeline.shared_ui import PALETTE_INIT_JS, index_nav


def load_posts() -> list[dict]:
    """output/posts에서 post_meta.json 수집"""
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
            with open(meta_file, "r", encoding="utf-8") as f:
                meta = json.load(f)
                meta["post_id"] = post_dir.name
                posts.append(meta)
        except json.JSONDecodeError:
            pass

    return posts


def _extract_region(location_str: str) -> str:
    """location 문자열에서 광역시/도 추출"""
    if not location_str:
        return "기타"
    parts = location_str.split(" / ")
    if parts:
        return parts[0]
    return "기타"


def build_manifest() -> None:
    """
    manifest.json 생성/업데이트
    (포스팅 생성될 때마다 호출 - index.html 수정 없음)
    """
    posts = load_posts()

    # 지역별 그룹화
    region_map = {}
    for post in posts:
        location = post.get("facts", {}).get("location", "")
        region = _extract_region(location)
        if region not in region_map:
            region_map[region] = 0
        region_map[region] += 1

    # regions 배열 생성
    regions = [{"code": "all", "name": "전체", "count": len(posts)}]
    region_order = ["서울", "경기도", "인천", "부산", "대전", "대구", "광주",
                    "세종", "울산", "강원도", "충청북도", "충청남도",
                    "전라북도", "전라남도", "경상북도", "경상남도", "제주도"]

    for region in region_order:
        if region in region_map:
            regions.append({
                "code": region.lower(),
                "name": region,
                "count": region_map[region]
            })

    # posts 배열 생성
    posts_data = []
    for post in posts:
        post_meta = {
            "id": post.get("post_id", ""),
            "apt_name": post.get("facts", {}).get("apt_name", ""),
            "post_title": post.get("content", {}).get("post_title", ""),
            "location": post.get("facts", {}).get("location", ""),
            "quality_score": post.get("quality_score", 0),
            "theme": post.get("theme", "intercom"),
            "created_at": post.get("timestamp", datetime.now().isoformat()),
        }
        posts_data.append(post_meta)

    # manifest.json 생성
    manifest = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "total_posts": len(posts),
            "version": "2.0"
        },
        "regions": regions,
        "posts": posts_data
    }

    MANIFEST_FILE.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ manifest.json 업데이트: {len(posts)}개 포스팅")


def build_front_index_once() -> None:
    """
    index.html 초기 생성 (한 번만 실행)
    이 함수는 필요시에만 수동으로 호출
    """
    if OUT_FILE.exists():
        print(f"⚠️  index.html이 이미 존재합니다. 수정이 필요하면 파일을 직접 편집하세요.")
        return

    template = TEMPLATE_PATH.read_text(encoding="utf-8")

    html = template
    html = html.replace("{{PALETTE_INIT_JS}}", PALETTE_INIT_JS)
    html = html.replace("{{INDEX_NAV}}", index_nav("/"))

    # 나머지 토큰은 JavaScript가 로드하므로 빈 문자열로 설정
    html = html.replace("{{FEATURED_ITEMS}}", "")
    html = html.replace("{{RESULT_COUNT_HTML}}", "")
    html = html.replace("{{LATEST_UPDATE_DATE}}", "")
    html = html.replace("{{LIST_SEARCH_BAR}}", "")

    OUT_FILE.write_text(html, encoding="utf-8")
    print(f"✅ index.html 초기 생성 완료: {OUT_FILE}")

    # 동시에 manifest.json도 생성
    build_manifest()


if __name__ == "__main__":
    # CLI에서 실행 시: manifest.json만 업데이트
    build_manifest()
