"""레거시 폴백 슬러그(YYYY-MM-DD_단지명) 디렉터리 정리 + GSC 폴백 URL → notice_id 301 매핑 생성.

배경:
    pipeline/html_renderer.py가 과거에 notice_url에서 pblancNo/houseManageNo 추출에 실패하면
    `{YYYY-MM-DD}_{apt_name}` 형식의 폴백 슬러그로 포스트를 저장했다.
    Google Search Console 색인 보고서(2026-05-06)에서 이 폴백 URL들이 "적절한 표준 태그가 포함된
    대체 페이지"(276건) / "발견됨 - 현재 색인이 생성되지 않음"(127건)으로 분류되어,
    숫자 notice_id 슬러그 본문과 canonical 중복을 일으키고 있었다.

    SEO 정책:
        - 정본 슬러그: 숫자 notice_id만 허용
        - 폴백 슬러그: 디스크에서 삭제, _redirects에 301 매핑 추가

사용:
    # 1) 디스크에 남은 폴백 슬러그 디렉터리 점검 (dry-run)
    python scripts/cleanup_legacy_slugs.py --dry-run

    # 2) 실제 삭제 (--apply 필요)
    python scripts/cleanup_legacy_slugs.py --apply

    # 3) GSC 폴백 URL CSV/TXT를 입력해 _redirects 매핑 생성
    python scripts/cleanup_legacy_slugs.py --build-redirects \
        seo_audit/gsc_2026-05-06/alternate_canonical_276.txt \
        seo_audit/gsc_2026-05-06/discovered_not_indexed_129.txt \
        seo_audit/gsc_2026-05-06/crawled_not_indexed_8.txt

    # 4) 디스크의 post.html 내부에 박혀있는 폴백 슬러그 self-URL을 정본 notice_id로 치환
    #    (canonical, og:url, JSON-LD url/@id, BreadcrumbList item 등)
    python scripts/cleanup_legacy_slugs.py --rewrite-self-urls
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POSTS_DIR = ROOT / "output" / "posts"
REDIRECTS_FILE = ROOT / "output" / "_redirects"

NUMERIC_SLUG = re.compile(r"^\d+$")
FALLBACK_SLUG = re.compile(r"^\d{4}-\d{2}-\d{2}_")
APT_NAME_SAFE = re.compile(r"[^\w가-힣]")


def _safe_apt_name(apt_name: str) -> str:
    """html_renderer.py가 사용하던 변환과 동일: 영숫자/한글 외는 '_'로 치환."""
    return APT_NAME_SAFE.sub("_", apt_name)


def find_legacy_dirs() -> list[Path]:
    """숫자가 아닌(=폴백) 슬러그 디렉터리 목록."""
    return sorted(p for p in POSTS_DIR.iterdir() if p.is_dir() and not NUMERIC_SLUG.match(p.name))


def cmd_dry_run() -> int:
    legacy = find_legacy_dirs()
    print(f"=== 폴백 슬러그 디렉터리: {len(legacy)}개 ===")
    for p in legacy:
        meta_path = p / "post_meta.json"
        apt_name = "(meta 없음)"
        if meta_path.exists():
            try:
                apt_name = json.loads(meta_path.read_text(encoding="utf-8")).get("apt_name", "(없음)")
            except Exception as exc:
                apt_name = f"(파싱 실패: {exc})"
        print(f"  {p.name}  →  apt_name={apt_name!r}")
    if legacy:
        print("\n실제 삭제하려면 --apply 옵션을 추가하세요.")
    return 0


def cmd_apply() -> int:
    legacy = find_legacy_dirs()
    if not legacy:
        print("삭제할 폴백 슬러그 디렉터리가 없습니다.")
        return 0
    print(f"=== {len(legacy)}개 디렉터리 삭제 ===")
    for p in legacy:
        print(f"  rm -rf {p}")
        shutil.rmtree(p)
    print("✅ 삭제 완료")
    return 0


def _load_apt_name_to_notice_id() -> dict[str, str]:
    """현재 디스크의 숫자 슬러그 디렉터리에서 apt_name → notice_id 맵 구성.

    동일 apt_name이 여러 notice_id를 가질 수 있으므로 첫 매칭만 채택하고 나머지는 경고.
    """
    mapping: dict[str, str] = {}
    collisions: dict[str, list[str]] = {}
    for d in POSTS_DIR.iterdir():
        if not d.is_dir() or not NUMERIC_SLUG.match(d.name):
            continue
        meta = d / "post_meta.json"
        if not meta.exists():
            continue
        try:
            data = json.loads(meta.read_text(encoding="utf-8"))
        except Exception:
            continue
        apt_name = data.get("apt_name") or ""
        if not apt_name:
            continue
        safe = _safe_apt_name(apt_name)
        if safe in mapping and mapping[safe] != d.name:
            collisions.setdefault(safe, [mapping[safe]]).append(d.name)
        else:
            mapping[safe] = d.name
    if collisions:
        print("⚠️ 동일 apt_name에 복수 notice_id 매칭 (첫 번째만 사용):")
        for safe, ids in collisions.items():
            print(f"   {safe}: {ids}")
    return mapping


def _extract_fallback_slugs(input_files: list[Path]) -> list[str]:
    """GSC URL 목록 텍스트 파일에서 폴백 슬러그만 추출."""
    slug_re = re.compile(r"/posts/(\d{4}-\d{2}-\d{2}_[^/]+)/post(?:\.html)?")
    slugs: set[str] = set()
    for f in input_files:
        for line in f.read_text(encoding="utf-8").splitlines():
            m = slug_re.search(line.strip())
            if m:
                slugs.add(m.group(1))
    return sorted(slugs)


def cmd_build_redirects(input_files: list[Path]) -> int:
    apt_to_notice = _load_apt_name_to_notice_id()
    print(f"=== apt_name → notice_id 사전: {len(apt_to_notice)}개 ===")

    fallback_slugs = _extract_fallback_slugs(input_files)
    print(f"=== GSC 폴백 슬러그: {len(fallback_slugs)}개 ===")

    matched: list[tuple[str, str]] = []
    unmatched: list[str] = []
    slug_re = re.compile(r"^\d{4}-\d{2}-\d{2}_(.+)$")
    for slug in fallback_slugs:
        m = slug_re.match(slug)
        if not m:
            unmatched.append(slug)
            continue
        apt_part = m.group(1)
        if apt_part in apt_to_notice:
            matched.append((slug, apt_to_notice[apt_part]))
        else:
            unmatched.append(slug)

    print(f"  매칭 성공: {len(matched)}")
    print(f"  매칭 실패: {len(unmatched)}")

    existing = REDIRECTS_FILE.read_text(encoding="utf-8") if REDIRECTS_FILE.exists() else ""
    lines = [ln for ln in existing.splitlines() if ln.strip()]
    existing_set = set(lines)

    block_header = "# Legacy fallback slug → notice_id (GSC 색인 정리, 2026-05-06)"
    new_lines: list[str] = []
    if block_header not in existing_set:
        new_lines.append(block_header)
    for slug, notice_id in matched:
        rule = f"/posts/{slug}/post.html /posts/{notice_id}/post.html 301"
        if rule not in existing_set:
            new_lines.append(rule)
    for slug in unmatched:
        rule = f"/posts/{slug}/post.html /posts/{slug}/post 410"  # 410 Gone
        if rule not in existing_set:
            # Cloudflare Pages _redirects는 410 상태코드를 그대로 지원하지 않음 → 메인으로 301
            rule = f"/posts/{slug}/post.html / 301"
            if rule not in existing_set:
                new_lines.append(rule)

    if not new_lines:
        print("✅ 추가할 새 리디렉션 규칙이 없습니다.")
        return 0

    final = (existing.rstrip() + "\n\n" + "\n".join(new_lines) + "\n") if existing.strip() else "\n".join(new_lines) + "\n"
    REDIRECTS_FILE.write_text(final, encoding="utf-8")
    print(f"✅ {REDIRECTS_FILE} 업데이트: {len(new_lines)}개 규칙 추가")
    if unmatched:
        print("\n매칭 실패 슬러그(메인으로 301):")
        for slug in unmatched[:20]:
            print(f"  {slug}")
        if len(unmatched) > 20:
            print(f"  ... (총 {len(unmatched)}개)")
    return 0


FALLBACK_SELF_URL = re.compile(
    r'https://apt-note\.com/posts/(\d{4}-\d{2}-\d{2}_[^/"#\s]+)/post\.html'
)


def cmd_rewrite_self_urls() -> int:
    """각 숫자 슬러그 디렉터리의 post.html에 박혀있는 폴백 self-URL을 정본 URL로 치환.

    canonical / og:url / JSON-LD url, @id / BreadcrumbList item 등 5곳이 모두
    `https://apt-note.com/posts/{fallback_slug}/post.html` 형태로 박혀있는 케이스를 처리.
    같은 파일 안의 폴백 URL은 모두 그 포스트의 본인 URL이라 가정하고 일괄 치환.
    """
    rewritten = 0
    untouched = 0
    skipped: list[str] = []
    for d in sorted(POSTS_DIR.iterdir()):
        if not d.is_dir() or not NUMERIC_SLUG.match(d.name):
            continue
        post_html = d / "post.html"
        if not post_html.exists():
            continue
        text = post_html.read_text(encoding="utf-8")
        slugs = set(FALLBACK_SELF_URL.findall(text))
        if not slugs:
            untouched += 1
            continue
        if len(slugs) > 1:
            # 한 페이지에 자기 외 다른 단지 폴백 URL이 섞여 있으면 자동 치환 위험 → 스킵
            skipped.append(f"{d.name}: 복수 폴백 슬러그 {sorted(slugs)}")
            continue
        target = f"https://apt-note.com/posts/{d.name}/post.html"
        new_text = FALLBACK_SELF_URL.sub(target, text)
        post_html.write_text(new_text, encoding="utf-8")
        rewritten += 1
    print(f"✅ self-URL 치환 완료: {rewritten}개 파일")
    print(f"   변경 없음: {untouched}개 파일")
    if skipped:
        print(f"⚠️ 스킵: {len(skipped)}개 (수동 점검 필요)")
        for s in skipped[:10]:
            print(f"   {s}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="삭제 후보만 출력")
    group.add_argument("--apply", action="store_true", help="폴백 슬러그 디렉터리 실삭제")
    group.add_argument("--build-redirects", nargs="+", metavar="GSC_TXT", help="GSC URL 목록 → _redirects 매핑 생성")
    group.add_argument("--rewrite-self-urls", action="store_true", help="post.html의 폴백 self-URL을 정본 notice_id로 치환")
    args = parser.parse_args()

    if not POSTS_DIR.exists():
        print(f"❌ {POSTS_DIR} 가 존재하지 않습니다.")
        return 1

    if args.dry_run:
        return cmd_dry_run()
    if args.apply:
        return cmd_apply()
    if args.build_redirects:
        files = [Path(p) for p in args.build_redirects]
        for f in files:
            if not f.exists():
                print(f"❌ 입력 파일 없음: {f}")
                return 1
        return cmd_build_redirects(files)
    if args.rewrite_self_urls:
        return cmd_rewrite_self_urls()
    return 0


if __name__ == "__main__":
    sys.exit(main())
