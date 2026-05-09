"""
'단지 규모' 위반 문구가 포함된 단락(<li>/<p>)을 통째로 안전한 안내문으로 교체.
다른 콘텐츠는 건드리지 않는다. PDF/LLM 호출 불필요.
"""

import json
import re
from pathlib import Path

POSTS_DIR = Path("output/posts")

GUARD_PATTERNS = (
    r"총\s*[\d,]+\s*세대(?:의|는|로|를)?\s*(?:전체\s*)?(?:단지\s*)?규모",
    r"[\d,]+\s*세대(?:의|로|는)?\s*단지\s*규모",
    r"[\d,]+\s*세대(?:의|로)?\s*단지(?:로|에서|에는)",
    r"[\d,]+\s*세대\s*(?:규모|단지로|구성되어|구성된)",
    r"공급세대수.*(?:단지\s*규모|규모\s*단지)",
    r"총\s*[\d,]+\s*세대(?:의)?\s*공동주택\s*단지",
)
GUARDS = [re.compile(p) for p in GUARD_PATTERNS]
# \b ensures we match <li>/<p> only, not <link>, <pre>, <path>, etc.
BLOCK_RE = re.compile(r"<(li|p)\b([^>]*)>(.*?)</\1>", re.DOTALL)


def violates(text: str) -> bool:
    return any(g.search(text) for g in GUARDS)


def safe_content(tag: str, apt: str) -> str:
    if tag == "li":
        return (
            f"{apt}의 단지 구성과 부대 시설 정보는 모집공고문에 첨부된 단지 배치도, "
            f"평면도 등 공식 자료를 통해 확인하시는 것이 가장 정확합니다. 공급되는 "
            f"타입 구성과 청약 자격 조건은 본문 상단의 분양 일정·공급 정보 섹션에서 "
            f"함께 살펴보세요."
        )
    return (
        f"{apt}의 자세한 단지 구성과 부대 시설 정보는 모집공고문에 첨부된 단지 배치도와 "
        f"평면도 등 공식 자료를 통해 확인해보세요. 공급되는 타입 구성과 청약 자격 조건은 "
        f"본문 상단의 분양 일정·공급 정보 섹션을 함께 참고하시면 도움이 됩니다."
    )


def patch_post(notice_id: str) -> int:
    post_dir = POSTS_DIR / notice_id
    html_path = post_dir / "post.html"
    meta_path = post_dir / "post_meta.json"
    if not html_path.exists() or not meta_path.exists():
        return 0

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    html = html_path.read_text(encoding="utf-8")
    apt = meta.get("apt_name") or "해당 단지"

    replaced = 0

    def repl(match):
        nonlocal replaced
        tag, attrs, content = match.group(1), match.group(2), match.group(3)
        if violates(content):
            replaced += 1
            return f"<{tag}{attrs}>{safe_content(tag, apt)}</{tag}>"
        return match.group(0)

    new_html = BLOCK_RE.sub(repl, html)

    if replaced == 0:
        return 0
    html_path.write_text(new_html, encoding="utf-8")
    return replaced


def main() -> int:
    targets = []
    for post in sorted(POSTS_DIR.glob("*/post.html")):
        text = post.read_text(encoding="utf-8")
        if violates(text):
            targets.append(post.parent.name)

    print(f"violations found in {len(targets)} posts")
    total = 0
    untouched = []
    for nid in targets:
        n = patch_post(nid)
        if n > 0:
            print(f"  [ok] {nid}: {n} block(s) replaced")
            total += n
        else:
            untouched.append(nid)
            print(f"  [miss] {nid}: violation outside <li>/<p> block")

    print(f"\npatched {len(targets) - len(untouched)}/{len(targets)} posts, {total} blocks replaced")
    if untouched:
        print(f"untouched: {untouched}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
