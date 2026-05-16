"""기존 post.html 들에 멀티라인 공유 payload 와 신규 getShareData 를 주입.

웹 공유 메시지를 앱(buildShareText)과 동일한 멀티라인 카드형으로 통일.
앞으로 생성되는 포스트는 pipeline/html_renderer.py 가 자동 주입하지만,
이미 정적으로 출력된 post.html 은 이 스크립트로 일괄 패치한다.

멱등 동작: 이미 'post-share-data' 스크립트가 있으면 payload 만 교체.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POSTS_ROOT = ROOT / "output" / "posts"

# pipeline/html_renderer.py 의 _build_share_text 와 동일 알고리즘
def build_share_text(apt_name: str, region: str, notice_date: str, price_range: str) -> str:
    def s(v) -> str:
        if v is None:
            return ""
        return str(v).strip()
    lines = [f"[{s(apt_name)}] 청약 정보 한눈에 보기", ""]
    if s(region):
        lines.append(f"📍 {s(region)}")
    if s(notice_date):
        lines.append(f"🗓 모집공고일 {s(notice_date)}")
    if s(price_range):
        lines.append(f"💰 {s(price_range)}")
    if len(lines) > 2:
        lines.append("")
    lines.extend([
        "🏠 분양가·일정·입지·자격 핵심 정리",
        "📋 청약 전 꼭 확인해야 할 정보 모음",
        "✨ 정과장의 청약노트",
    ])
    return "\n".join(lines)


NEW_GET_SHARE_DATA = """  function getShareData() {
    var payload = null;
    var payloadEl = document.getElementById('post-share-data');
    if (payloadEl) {
      try { payload = JSON.parse(payloadEl.textContent || '{}'); } catch (_) {}
    }
    var ogTitle = (document.querySelector('meta[property="og:title"]') || {}).content || '';
    var ogDesc = (document.querySelector('meta[property="og:description"]') || {}).content
      || (document.querySelector('meta[name="description"]') || {}).content
      || '';
    var title = (payload && payload.title) || ogTitle || document.title || '정과장의 청약노트';
    var description = (payload && payload.text) || ogDesc || '';
    return {
      title: title,
      text: description,
      url: location.href
    };
  }"""

OLD_GET_SHARE_DATA_PATTERN = re.compile(
    r"  function getShareData\(\) \{\s*\n"
    r"    var title = \(document\.querySelector\('meta\[property=\"og:title\"\]'\) \|\| \{\}\)\.content\s*\n"
    r"      \|\| document\.title\s*\n"
    r"      \|\| '[^']*';\s*\n"
    r"    var description = \(document\.querySelector\('meta\[property=\"og:description\"\]'\) \|\| \{\}\)\.content\s*\n"
    r"      \|\| \(document\.querySelector\('meta\[name=\"description\"\]'\) \|\| \{\}\)\.content\s*\n"
    r"      \|\| '';\s*\n"
    r"    return \{\s*\n"
    r"      title: title,\s*\n"
    r"      text: description,\s*\n"
    r"      url: location\.href\s*\n"
    r"    \};\s*\n"
    r"  \}"
)


def build_payload_script(apt_name: str, post_title: str, region: str,
                         notice_date: str, price_range: str) -> str:
    text = build_share_text(apt_name, region, notice_date, price_range)
    payload = json.dumps({"title": post_title, "text": text}, ensure_ascii=False)
    payload = payload.replace("</", "<\\/")
    return f'<script id="post-share-data" type="application/json">{payload}</script>'


PAYLOAD_TAG_PATTERN = re.compile(
    r'<script id="post-share-data" type="application/json">.*?</script>',
    re.DOTALL,
)
TOAST_ANCHOR = '<div id="post-share-toast" role="status" aria-live="polite"></div>'


def patch_post(notice_id: str, dry_run: bool = False) -> str:
    post_dir = POSTS_ROOT / notice_id
    post_html = post_dir / "post.html"
    post_meta = post_dir / "post_meta.json"
    if not post_html.exists():
        return f"skip (no post.html): {notice_id}"
    if not post_meta.exists():
        return f"skip (no post_meta.json): {notice_id}"

    meta = json.loads(post_meta.read_text(encoding="utf-8"))
    payload_script = build_payload_script(
        apt_name=meta.get("apt_name", ""),
        post_title=meta.get("title", ""),
        region=meta.get("region_category", "") or meta.get("region", ""),
        notice_date=meta.get("notice_date", ""),
        price_range=meta.get("price_range", ""),
    )

    text = post_html.read_text(encoding="utf-8")
    original = text
    changes = []

    # 1) payload script 삽입/교체
    if PAYLOAD_TAG_PATTERN.search(text):
        text = PAYLOAD_TAG_PATTERN.sub(lambda _: payload_script, text, count=1)
        changes.append("payload(replaced)")
    elif TOAST_ANCHOR in text:
        text = text.replace(TOAST_ANCHOR, TOAST_ANCHOR + "\n" + payload_script, 1)
        changes.append("payload(inserted)")
    else:
        return f"skip (anchor missing): {notice_id}"

    # 2) getShareData 본문 교체
    if OLD_GET_SHARE_DATA_PATTERN.search(text):
        text = OLD_GET_SHARE_DATA_PATTERN.sub(lambda _: NEW_GET_SHARE_DATA, text, count=1)
        changes.append("getShareData(updated)")
    elif "var payloadEl = document.getElementById('post-share-data');" in text:
        changes.append("getShareData(already-new)")
    else:
        changes.append("getShareData(pattern-not-found)")

    # 3) navigator.share(data) → navigator.share({text:data.text,url:data.url})
    #    title 필드를 제외해 KakaoTalk 이 "{title} - {text}" 로 붙이는 문제 방지
    OLD_SHARE_CALL = "await navigator.share(data);"
    NEW_SHARE_CALL = "await navigator.share({text: data.text, url: data.url});"
    if OLD_SHARE_CALL in text:
        text = text.replace(OLD_SHARE_CALL, NEW_SHARE_CALL)
        changes.append("navigatorShare(fixed)")
    elif NEW_SHARE_CALL in text:
        changes.append("navigatorShare(already-fixed)")
    else:
        changes.append("navigatorShare(not-found)")

    if text == original:
        return f"noop: {notice_id}"
    if not dry_run:
        post_html.write_text(text, encoding="utf-8")
    return f"{'(dry) ' if dry_run else ''}patched [{', '.join(changes)}]: {notice_id}"


def iter_post_ids() -> list[str]:
    if not POSTS_ROOT.exists():
        return []
    return sorted(p.name for p in POSTS_ROOT.iterdir() if p.is_dir())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("notice_ids", nargs="*",
                        help="대상 notice_id. 비우면 output/posts/* 전체")
    parser.add_argument("--dry-run", action="store_true",
                        help="실제 쓰기 없이 변경 미리보기")
    args = parser.parse_args()

    targets = args.notice_ids or iter_post_ids()
    if not targets:
        print("대상 없음", file=sys.stderr)
        return 1

    summary = {"patched": 0, "noop": 0, "skip": 0}
    for nid in targets:
        result = patch_post(nid, dry_run=args.dry_run)
        print(f"  {result}")
        if result.startswith("skip"):
            summary["skip"] += 1
        elif "noop" in result:
            summary["noop"] += 1
        else:
            summary["patched"] += 1
    print()
    print(f"총 {len(targets)}개 처리. patched={summary['patched']}, "
          f"noop={summary['noop']}, skip={summary['skip']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
