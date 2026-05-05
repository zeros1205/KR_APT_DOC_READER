"""
patch_seo_structured_data.py
─────────────────────────────
기존 output/posts/*/post.html 파일에:
  1. og:image:width / og:image:height / og:image:type 메타 추가
  2. Article + BreadcrumbList JSON-LD 삽입

이미 패치된 파일은 건너뜀 (idempotent).
"""

import re
import json
from pathlib import Path

SITE_URL = "https://apt-note.com"
POSTS_DIR = Path(__file__).parent.parent / "output" / "posts"

OG_IMAGE_LINE = f'<meta property="og:image" content="{SITE_URL}/og-image.jpg">'
OG_SIZE_BLOCK = (
    f'<meta property="og:image" content="{SITE_URL}/og-image.jpg">\n'
    f'<meta property="og:image:width" content="1200">\n'
    f'<meta property="og:image:height" content="630">\n'
    f'<meta property="og:image:type" content="image/jpeg">'
)

ROBOTS_LINE = '<meta name="robots" content="index, follow">'

def _extract(html: str, pattern: str) -> str:
    m = re.search(pattern, html)
    return m.group(1) if m else ""

def build_jsonld(title: str, description: str, url: str, apt_name: str, notice_date: str) -> str:
    # JSON 내 특수문자 이스케이프
    def esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace('"', '\\"')

    return f"""<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "Article",
  "@id": "{esc(url)}#article",
  "headline": "{esc(title)}",
  "description": "{esc(description)}",
  "url": "{esc(url)}",
  "datePublished": "{esc(notice_date)}",
  "dateModified": "{esc(notice_date)}",
  "image": {{
    "@type": "ImageObject",
    "url": "{SITE_URL}/og-image.jpg",
    "width": 1200,
    "height": 630
  }},
  "publisher": {{
    "@type": "Organization",
    "@id": "{SITE_URL}/#organization",
    "name": "정과장의 청약노트",
    "url": "{SITE_URL}/",
    "logo": {{
      "@type": "ImageObject",
      "url": "{SITE_URL}/android-chrome-512x512.png",
      "width": 512,
      "height": 512
    }}
  }},
  "isPartOf": {{
    "@type": "WebSite",
    "@id": "{SITE_URL}/#website",
    "name": "정과장의 청약노트",
    "url": "{SITE_URL}/"
  }}
}}
</script>
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    {{"@type": "ListItem", "position": 1, "name": "홈", "item": "{SITE_URL}/"}},
    {{"@type": "ListItem", "position": 2, "name": "{esc(apt_name)}", "item": "{esc(url)}"}}
  ]
}}
</script>"""


def patch_file(path: Path) -> str:
    html = path.read_text(encoding="utf-8")

    # 이미 패치됐으면 스킵
    if '"@type": "Article"' in html:
        return "skipped"

    # meta 값 추출
    title = _extract(html, r'<meta property="og:title" content="([^"]+)"')
    description = _extract(html, r'<meta name="description" content="([^"]+)"')
    url = _extract(html, r'<link rel="canonical" href="([^"]+)"')
    apt_name = _extract(html, r'<meta property="og:site_name" content="[^"]*">.*?<meta property="og:title" content="([^"]+)"')

    # apt_name fallback: post_meta.json
    if not apt_name:
        meta_path = path.parent / "post_meta.json"
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                apt_name = meta.get("apt_name", "")
            except Exception:
                pass

    # notice_date: post_meta.json 우선
    notice_date = ""
    meta_path = path.parent / "post_meta.json"
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            notice_date = meta.get("notice_date", "")
        except Exception:
            pass

    if not apt_name:
        apt_name = title  # 최후 fallback

    # 1. og:image 크기 메타 추가 (이미 있으면 스킵)
    if 'og:image:width' not in html:
        html = html.replace(OG_IMAGE_LINE, OG_SIZE_BLOCK, 1)

    # 2. JSON-LD를 <meta name="robots"> 바로 뒤에 삽입
    jsonld = build_jsonld(title, description, url, apt_name, notice_date)
    html = html.replace(
        ROBOTS_LINE,
        ROBOTS_LINE + "\n" + jsonld,
        1
    )

    path.write_text(html, encoding="utf-8")
    return "patched"


def main():
    post_files = sorted(POSTS_DIR.glob("*/post.html"))
    total = len(post_files)
    patched = skipped = error = 0

    for f in post_files:
        try:
            result = patch_file(f)
            if result == "patched":
                patched += 1
            else:
                skipped += 1
        except Exception as e:
            print(f"  ERROR {f.parent.name}: {e}")
            error += 1

    print(f"\n완료: {total}개 중 패치 {patched}개 / 스킵 {skipped}개 / 오류 {error}개")


if __name__ == "__main__":
    main()
