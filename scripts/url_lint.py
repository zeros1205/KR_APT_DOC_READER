"""url_lint.py — 빌드 후 SEO·광고 위생 회귀 게이트.

검사 항목 (실패 시 exit 1):
  1. output/posts/<id>/post.html 안에서 다른 포스트로 향하는 상대 href 검출
     (`href="posts/..."` 또는 `href="../X/post.html"`) — nested path 누적의 원천.
  2. output/index.html / 404.html 의 카드/네비 href 가 절대경로(`/posts/...`) 인지 확인.
  3. output/sitemap.xml — `//posts` 슬래시 중복, 빈 <loc>, 중복 URL 없음.
  4. output/_redirects — placeholder 문법 오류, 동일 source 중복 검출(경고).

사용:
  python scripts/url_lint.py [--root output]
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "output"

HREF_RE = re.compile(r'href="([^"]+)"')
# 다른 포스트로 향하는 상대 href 패턴 — 절대(/), 외부(http), 앵커(#), 부모홈(../../) 모두 허용.
_BAD_INTERNAL_RE = re.compile(r'^(?:posts/|\./posts/|\.\./[^/]+/post)')


def _href_is_dangerous(href: str) -> bool:
    if not href:
        return False
    if href.startswith(("http://", "https://", "//", "/", "#", "mailto:", "tel:", "../../")):
        return False
    return bool(_BAD_INTERNAL_RE.match(href))


def check_post_pages(output: Path) -> list[str]:
    errors: list[str] = []
    posts_dir = output / "posts"
    if not posts_dir.exists():
        return errors
    for post_html in posts_dir.glob("*/post.html"):
        try:
            text = post_html.read_text(encoding="utf-8")
        except Exception as exc:
            errors.append(f"[read-fail] {post_html}: {exc}")
            continue
        for match in HREF_RE.finditer(text):
            href = match.group(1)
            if _href_is_dangerous(href):
                rel = post_html.relative_to(output)
                errors.append(
                    f"[nested-risk] {rel}: 다른 포스트로 향하는 상대 href 검출 → href=\"{href}\""
                )
    return errors


def check_index_pages(output: Path) -> list[str]:
    errors: list[str] = []
    for name in ("index.html", "404.html"):
        page = output / name
        if not page.exists():
            if name == "404.html":
                errors.append(f"[missing] {name} 없음 — 404 fallback 페이지 필요")
            continue
        text = page.read_text(encoding="utf-8")
        for match in HREF_RE.finditer(text):
            href = match.group(1)
            if href.startswith("posts/"):
                errors.append(
                    f"[index-relative] {name}: 카드 href 가 상대경로 → href=\"{href}\" "
                    f"(절대경로 /posts/... 로 변경 필요)"
                )
    return errors


def check_sitemap(output: Path) -> list[str]:
    errors: list[str] = []
    sitemap = output / "sitemap.xml"
    if not sitemap.exists():
        errors.append("[missing] sitemap.xml 없음")
        return errors
    try:
        tree = ET.parse(sitemap)
    except ET.ParseError as exc:
        errors.append(f"[sitemap-parse] {exc}")
        return errors

    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    locs = [el.text or "" for el in tree.getroot().findall(".//sm:loc", ns)]

    for loc in locs:
        if not loc.strip():
            errors.append("[sitemap-empty-loc] 빈 <loc> 발견")
        if "//posts" in loc.replace("https://", "").replace("http://", ""):
            errors.append(f"[sitemap-double-slash] 슬래시 중복: {loc}")
        if loc.endswith("/post") or "/post," in loc:
            errors.append(f"[sitemap-no-ext] 확장자 없는 URL: {loc}")

    dup = [u for u, c in Counter(locs).items() if c > 1]
    for u in dup:
        errors.append(f"[sitemap-duplicate] 중복 URL: {u}")

    return errors


def check_redirects(output: Path) -> list[str]:
    warnings: list[str] = []
    redirects = output / "_redirects"
    if not redirects.exists():
        return warnings
    sources: Counter[str] = Counter()
    for ln, line in enumerate(redirects.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2:
            warnings.append(f"[redirects:{ln}] 문법 오류(필드 부족): {line}")
            continue
        src = parts[0]
        sources[src] += 1
    for src, count in sources.items():
        if count > 1:
            warnings.append(f"[redirects-dup] 동일 source 중복: {src} ({count}회)")
    return warnings


def check_thin_content(output: Path) -> list[str]:
    """본문 글자수·표 임계치 미달이면서 robots 가 index, follow 로 노출된 페이지 경고."""
    warnings: list[str] = []
    posts_dir = output / "posts"
    if not posts_dir.exists():
        return warnings
    try:
        sys.path.insert(0, str(ROOT / "pipeline"))
        from seo_policy import is_thin_content
    except Exception as exc:
        warnings.append(f"[thin-content] seo_policy import 실패: {exc}")
        return warnings
    robots_re = re.compile(r'<meta name="robots" content="([^"]+)"')
    for post_html in posts_dir.glob("*/post.html"):
        try:
            html = post_html.read_text(encoding="utf-8")
        except Exception:
            continue
        thin, reasons = is_thin_content(html)
        if not thin:
            continue
        m = robots_re.search(html)
        directive = (m.group(1) if m else "").strip().lower().replace(" ", "")
        if "noindex" in directive:
            continue
        rel = post_html.relative_to(output)
        warnings.append(
            f"[thin-content] {rel}: index 인데 thin 임계치 미달 — {','.join(reasons)} "
            f"(patch_posts_noindex.py 실행 권장)"
        )
    return warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(DEFAULT_OUTPUT), help="output dir (default: ./output)")
    parser.add_argument("--strict", action="store_true", help="경고도 실패로 취급")
    args = parser.parse_args()

    output = Path(args.root).resolve()
    if not output.exists():
        print(f"❌ output 디렉터리 없음: {output}", file=sys.stderr)
        return 1

    errors: list[str] = []
    errors += check_post_pages(output)
    errors += check_index_pages(output)
    errors += check_sitemap(output)
    warnings = check_redirects(output)
    warnings += check_thin_content(output)

    if warnings:
        print(f"⚠️  경고 {len(warnings)}건:")
        for w in warnings:
            print(f"   {w}")

    if errors:
        print(f"❌ 검사 실패 — 오류 {len(errors)}건:")
        for e in errors:
            print(f"   {e}")
        return 1

    if args.strict and warnings:
        return 1

    total = sum(1 for _ in output.glob("posts/*/post.html"))
    print(f"✅ URL lint 통과 (포스트 {total}건, 사이트맵 OK, 경고 {len(warnings)}건)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
