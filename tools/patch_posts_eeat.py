"""patch_posts_eeat.py — 기존 포스트 일괄 패치 (E-E-A-T 보강).

대상: output/posts/<id>/post.html 의 두 위치
  1. JSON-LD "@type":"Article" 블록에 author + isBasedOn 필드 주입
  2. 면책 고지 블록("📌 데이터 출처" 직전)에 AI 보조·검수 disclosure 단락 삽입

설계 원칙
  - 멱등성: 이미 패치된 페이지는 자동 스킵
  - 색상 무관: 정규식이 테마별 색상값에 의존하지 않음
  - 안전 파싱: JSON-LD 는 정규식 매칭 후 json 모듈로 파싱·재직렬화
  - dry-run: --dry-run 으로 변경량만 카운트

사용:
  python tools/patch_posts_eeat.py [--dry-run] [--limit N]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = ROOT / "output" / "posts"
SITE_URL = "https://apt-note.com"

# 첫 JSON-LD 블록만 매칭. count=1 로 추가 보장.
LD_JSON_RE = re.compile(
    r'(<script type="application/ld\+json">\s*)(\{.*?\})(\s*</script>)',
    re.DOTALL,
)

# 면책 푸터의 "데이터 출처" 라인을 색상 무관하게 식별.
FOOTER_DATA_SOURCE_RE = re.compile(
    r'(<div style="border-top: 1px solid [^"]+; padding-top: 12px;">\s*\n\s*'
    r'<p style="color: [^"]+; font-size: 13px[^"]*"[^>]*>\s*\n\s*'
    r'📌 데이터 출처)',
    re.DOTALL,
)

DISCLOSURE_MARKER = "AI 도구의 보조를 받아"

DISCLOSURE_SNIPPET = (
    '    <p style="color: var(--c-mid, #767370); font-size: 13px; '
    'letter-spacing: 0.025em; line-height: 1.6; margin: 0 0 12px 0;">\n'
    '      이 페이지는 청약홈 공공데이터를 기반으로 AI 도구의 보조를 받아 작성하고 '
    '<a href="/editorial-policy.html" style="color: var(--c-primary, #d97757); '
    'text-decoration: underline;">정과장 팀의 검수</a>를 거쳐 발행되었습니다. '
    '운영자 소개는 <a href="/about.html" style="color: var(--c-primary, #d97757); '
    'text-decoration: underline;">여기</a>에서 확인할 수 있습니다.\n'
    '    </p>\n'
    '    '
)


def _insert_author_and_source(data: dict, notice_url: str) -> bool:
    """Article JSON-LD 에 author·isBasedOn 추가. 변경 여부 반환."""
    if data.get("@type") != "Article":
        return False
    changed = False
    if "author" not in data:
        # publisher 뒤·isPartOf 앞에 끼워 넣으려면 키 순서를 재구성.
        new_data: dict = {}
        for key, value in data.items():
            new_data[key] = value
            if key == "publisher":
                new_data["author"] = {
                    "@type": "Person",
                    "@id": f"{SITE_URL}/about.html#person",
                    "name": "정과장",
                    "url": f"{SITE_URL}/about.html",
                    "jobTitle": "청약 분양공고 정보 정리·검수자",
                }
                if notice_url:
                    new_data["isBasedOn"] = {
                        "@type": "Dataset",
                        "name": "청약홈 분양공고 공공데이터",
                        "url": notice_url,
                        "provider": {
                            "@type": "Organization",
                            "name": "한국부동산원",
                            "url": "https://www.applyhome.co.kr/",
                        },
                    }
        data.clear()
        data.update(new_data)
        changed = True
    elif notice_url and "isBasedOn" not in data:
        data["isBasedOn"] = {
            "@type": "Dataset",
            "name": "청약홈 분양공고 공공데이터",
            "url": notice_url,
            "provider": {
                "@type": "Organization",
                "name": "한국부동산원",
                "url": "https://www.applyhome.co.kr/",
            },
        }
        changed = True
    return changed


def patch_post(post_dir: Path) -> dict:
    meta_path = post_dir / "post_meta.json"
    html_path = post_dir / "post.html"
    if not html_path.exists():
        return {"ok": False, "reason": "no post.html"}
    notice_url = ""
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            notice_url = str(meta.get("notice_url") or "")
        except Exception:
            pass

    html = html_path.read_text(encoding="utf-8")

    json_ld_patched = False
    disclosure_patched = False
    json_ld_skipped = False
    disclosure_skipped = False

    # 1) JSON-LD Article 패치 (첫 블록만)
    def maybe_patch(match: re.Match[str]) -> str:
        nonlocal json_ld_patched, json_ld_skipped
        before, body, after = match.group(1), match.group(2), match.group(3)
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            return match.group(0)
        if data.get("@type") != "Article":
            return match.group(0)
        if "author" in data and "isBasedOn" in data:
            json_ld_skipped = True
            return match.group(0)
        changed = _insert_author_and_source(data, notice_url)
        if not changed:
            return match.group(0)
        new_body = json.dumps(data, ensure_ascii=False, indent=2)
        json_ld_patched = True
        return f"{before}{new_body}{after}"

    html = LD_JSON_RE.sub(maybe_patch, html, count=1)

    # 2) 푸터 disclosure
    if DISCLOSURE_MARKER in html:
        disclosure_skipped = True
    else:
        new_html, n = FOOTER_DATA_SOURCE_RE.subn(DISCLOSURE_SNIPPET + r"\1", html, count=1)
        if n > 0:
            html = new_html
            disclosure_patched = True

    return {
        "ok": True,
        "json_ld_patched": json_ld_patched,
        "json_ld_skipped": json_ld_skipped,
        "disclosure_patched": disclosure_patched,
        "disclosure_skipped": disclosure_skipped,
        "html": html if (json_ld_patched or disclosure_patched) else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="변경 카운트만 출력")
    parser.add_argument("--limit", type=int, default=0, help="처리할 최대 디렉터리 수 (0=전체)")
    args = parser.parse_args()

    if not POSTS_DIR.exists():
        print(f"❌ 포스트 디렉터리 없음: {POSTS_DIR}", file=sys.stderr)
        return 1

    dirs = sorted([d for d in POSTS_DIR.iterdir() if d.is_dir()])
    if args.limit:
        dirs = dirs[: args.limit]

    counts = {
        "total": 0,
        "json_ld_patched": 0,
        "json_ld_skipped": 0,
        "disclosure_patched": 0,
        "disclosure_skipped": 0,
        "no_post": 0,
    }
    failures: list[tuple[str, str]] = []

    for d in dirs:
        result = patch_post(d)
        counts["total"] += 1
        if not result.get("ok"):
            counts["no_post"] += 1
            failures.append((d.name, result.get("reason", "unknown")))
            continue
        if result["json_ld_patched"]:
            counts["json_ld_patched"] += 1
        if result["json_ld_skipped"]:
            counts["json_ld_skipped"] += 1
        if result["disclosure_patched"]:
            counts["disclosure_patched"] += 1
        if result["disclosure_skipped"]:
            counts["disclosure_skipped"] += 1

        if not args.dry_run and result["html"] is not None:
            (d / "post.html").write_text(result["html"], encoding="utf-8")

    mode = "[DRY RUN]" if args.dry_run else "[APPLIED]"
    print(f"{mode} 총 {counts['total']}건 처리")
    print(f"  JSON-LD author/isBasedOn  →  patched {counts['json_ld_patched']} / skipped {counts['json_ld_skipped']}")
    print(f"  Footer disclosure          →  patched {counts['disclosure_patched']} / skipped {counts['disclosure_skipped']}")
    if counts["no_post"]:
        print(f"  post.html 없음: {counts['no_post']}건")
        for name, reason in failures[:5]:
            print(f"    - {name}: {reason}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
