"""patch_posts_location_v3.py — 포스트의 입지 분석 섹션을 v3 결과로 교체.

흐름
  1) 대상 포스트 식별 (--targets / --all-active / --all-past / --limit)
  2) 각 단지에 v3(단지명·주소만) LLM 호출
  3) markdown body_md → HTML 변환 (5섹션, 디자인 토큰 그대로)
  4) 기존 post.html 의 SECTION 2 (입지 분석) 블록 정규식 패치로 교체

`templates/blog_template.html` / `pipeline/html_renderer.py` 무수정 → UI 보호 정책
미트리거. post.html 자체는 보호 대상 아님.

선택 모드
  --all-active   : winner_date >= today (당첨 발표 미경과)
  --all-past     : winner_date <  today 이면서 location_v3.json 없는 포스트
                   (이미 v3 패치된 포스트는 자동 skip — 재호출 방지)
  --repatch-only : LLM 호출 없이 캐시된 location_v3.json 으로 HTML 만 재생성

사용
  python tools/patch_posts_location_v3.py --all-active
  python tools/patch_posts_location_v3.py --all-past --limit 5    # 안전 테스트
  python tools/patch_posts_location_v3.py --targets 2026000058 ...
  python tools/patch_posts_location_v3.py --all-active --repatch-only  # 비용 0 형식 갱신
"""

from __future__ import annotations

import argparse
import asyncio
import html
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))
sys.path.insert(0, str(ROOT / "tools"))

POSTS_DIR = ROOT / "output" / "posts"


# SECTION 2 — 입지 분석 ~ 다음 구분선까지를 통째로 매치.
SECTION2_RE = re.compile(
    r'(<!--\s*═{10,}\s*\n\s*SECTION 2 — 입지 분석[\s\S]*?<!--\s*구분선\s*-->\s*\n\s*<div style="height: 1px;[^>]*></div>)',
    re.MULTILINE,
)


def _kst_today() -> date:
    from datetime import datetime, timedelta, timezone
    return datetime.now(timezone(timedelta(hours=9))).date()


def _load_meta(notice_id: str) -> dict:
    p = POSTS_DIR / notice_id / "post_meta.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _load_cache(notice_id: str) -> dict:
    p = ROOT / "output" / "data_cache" / "notices" / f"{notice_id}.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def _list_active_posts(today: date) -> list[tuple[str, str, str]]:
    """winner_date >= today 인 (notice_id, apt_name, address) 리스트."""
    return _list_posts_by_winner_date(today, past=False)


def _list_past_posts(today: date) -> list[tuple[str, str, str]]:
    """winner_date < today 이면서 아직 v3 패치되지 않은(location_v3.json 없는) 포스트.

    이미 v3 로 교체된 포스트를 다시 LLM 호출로 덮어쓰지 않도록 skip — 비용·콘텐츠 안정성 보호.
    """
    return _list_posts_by_winner_date(today, past=True, skip_already_patched=True)


def _list_posts_by_winner_date(
    today: date,
    *,
    past: bool,
    skip_already_patched: bool = False,
) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    for meta_path in sorted(POSTS_DIR.glob("*/post_meta.json")):
        meta = _load_meta(meta_path.parent.name)
        raw = (meta.get("winner_date") or "").strip()
        if not raw:
            continue
        try:
            wd = date.fromisoformat(raw[:10])
        except ValueError:
            continue
        if past and wd >= today:
            continue
        if not past and wd < today:
            continue
        nid = meta_path.parent.name
        if skip_already_patched and (POSTS_DIR / nid / "location_v3.json").exists():
            continue
        cache = _load_cache(nid)
        doc = cache.get("document") or {}
        apt_name = doc.get("apt_name") or meta.get("apt_name") or ""
        address = doc.get("supply_location") or doc.get("location") or meta.get("location") or ""
        out.append((nid, apt_name.strip(), address.strip()))
    return out


def _md_inline(text: str) -> str:
    """간단한 markdown inline → HTML (bold 만)."""
    text = html.escape(text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    return text


# Codex P1 — body_md 가 markdown 형식을 안 지키면 _wrap_section_html 이
# outer wrapper 만 만들어 빈 본문으로 SECTION 2 가 덮어쓰일 위험. 최소 섹션
# 수를 강제해 검증 통과 시에만 HTML 생성.
EXPECTED_SECTIONS = 5
MIN_VALID_SECTIONS = 4  # 1개 정도 누락은 허용 (Pro 모델이 가끔 4개만 출력)


def parse_sections(body_md: str) -> list[tuple[str, str]]:
    """body_md 에서 (head, body) 튜플 리스트 추출. 본문이 비어 있는 섹션은 제외."""
    if not body_md:
        return []
    parts = re.split(r"(^###\s+.+$)", body_md, flags=re.MULTILINE)
    out: list[tuple[str, str]] = []
    for i in range(1, len(parts) - 1, 2):
        head = parts[i].lstrip("#").strip()
        body = (parts[i + 1] or "").strip()
        if head and body:  # 헤딩 + 본문 모두 있어야 유효 섹션
            out.append((head, body))
    return out


def md_to_section_html(body_md: str) -> str:
    """v3 body_md (5섹션) 를 사이트 디자인 토큰에 맞춘 HTML 로 변환.

    섹션 수가 MIN_VALID_SECTIONS 미만이면 빈 문자열 반환 — 호출자가 skip 하도록.
    """
    sections = parse_sections(body_md)
    if len(sections) < MIN_VALID_SECTIONS:
        return ""

    # 접근성: OS 폰트 배율 변경 시 텍스트가 따라가도록 font-size·letter-spacing 은 rem.
    # 레이아웃(margin·padding·gap·height) 은 px 유지 — 박스 자체가 함께 커지면 모바일 폭에서 깨짐.
    html_sections: list[str] = []
    for head, body in sections:
        # 본문은 빈 줄로 분리해 단락 만들기
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
        paragraph_html: list[str] = []
        for p in paragraphs:
            # 단락 안 줄바꿈은 그대로 유지
            inline = _md_inline(p).replace("\n", "<br>")
            paragraph_html.append(
                f'<p style="font-size:1rem;color:var(--c-dark, #2C2825);line-height:1.75;margin:0 0 12px 0;">'
                f'{inline}'
                f'</p>'
            )
        html_sections.append(
            f'<div>'
            f'<h3 style="font-size:1.25rem;font-weight:800;color:var(--c-dark, #2C2825);margin:0 0 12px 0;line-height:1.4;">'
            f'{html.escape(head)}'
            f'</h3>'
            f'{"".join(paragraph_html)}'
            f'</div>'
        )

    return (
        '<!-- ══════════════════════════════════════════\n'
        '     SECTION 2 — 입지 분석 (v3-readable)\n'
        '═══════════════════════════════════════════ -->\n'
        '<div style="padding: 0 20px; margin-bottom: 44px;">\n\n'
        '  <div style="font-size: 0.75rem; font-weight: 700; color: var(--c-primary, #CC5F3F); letter-spacing: 0.09375rem; margin-bottom: 10px;">\n'
        '    02 · 입지 분석\n'
        '  </div>\n'
        '  <h2 style="font-size: 1.375rem; font-weight: 800; color: var(--c-dark, #2C2825); margin: 0 0 20px 0; line-height: 1.4;">\n'
        '    이 동네, 어떤 곳인가요?\n'
        '  </h2>\n\n'
        '  <div style="display:flex;flex-direction:column;gap:28px;">\n'
        f'    {"".join(html_sections)}\n'
        '  </div>\n'
        '</div>\n\n'
        '<!-- 구분선 -->\n'
        '<div style="height: 1px; background: #DED9D1; margin: 0 20px 44px;"></div>'
    )


async def _run_v3(apt_name: str, address: str) -> dict:
    from pipeline.agents.location_v3 import generate_v3
    return await generate_v3(apt_name, address)


def _patch_post_html(notice_id: str, new_section_html: str) -> bool:
    p = POSTS_DIR / notice_id / "post.html"
    if not p.exists():
        return False
    html_text = p.read_text(encoding="utf-8")
    if not SECTION2_RE.search(html_text):
        return False
    new_html = SECTION2_RE.sub(lambda _m: new_section_html, html_text, count=1)
    p.write_text(new_html, encoding="utf-8")
    return True


def _load_cached_v3(notice_id: str) -> dict:
    """이전 패치 때 저장해 둔 location_v3.json (LLM 결과) 로드."""
    p = POSTS_DIR / notice_id / "location_v3.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


async def main_async(targets: list[str], dry_run: bool, repatch_only: bool = False) -> int:
    success: list[str] = []
    failed: list[tuple[str, str]] = []
    for nid in targets:
        meta = _load_meta(nid)
        cache = _load_cache(nid)
        doc = cache.get("document") or {}
        apt_name = (doc.get("apt_name") or meta.get("apt_name") or "").strip()
        address = (doc.get("supply_location") or doc.get("location") or meta.get("location") or "").strip()
        if not apt_name or not address:
            failed.append((nid, "단지명·주소 누락"))
            continue
        print(f"\n=== {nid} {apt_name} ===")
        print(f"  주소: {address}")
        if repatch_only:
            # 캐시된 v3 결과 재사용 — LLM 재호출 없이 SECTION 2 HTML 만 재생성.
            result = _load_cached_v3(nid)
            if not result:
                failed.append((nid, "location_v3.json 없음 (이전 패치 기록 없음)"))
                continue
        else:
            try:
                result = await _run_v3(apt_name, address)
            except Exception as exc:
                failed.append((nid, f"v3 호출 실패: {exc}"))
                continue
        if isinstance(result, dict) and result.get("_error"):
            failed.append((nid, str(result["_error"])))
            continue
        body_md = (result or {}).get("body_md", "")
        if not body_md:
            failed.append((nid, "body_md 비어 있음"))
            continue
        # Codex P1 — md_to_section_html 이 빈 문자열 반환 시 (섹션 수 미달)
        # production post.html 을 빈 본문으로 덮어쓰지 않도록 skip.
        sections = parse_sections(body_md)
        if len(sections) < MIN_VALID_SECTIONS:
            failed.append((
                nid,
                f"섹션 수 미달 (기대 {EXPECTED_SECTIONS}, 실제 유효 {len(sections)}) — post.html 보존",
            ))
            # Codex P2 — dry-run 은 작업 트리에 어떤 변경도 만들지 않아야 함.
            # invalid.json 디버그 저장은 실제 적용 모드에서만.
            if not dry_run:
                meta_v3_path = POSTS_DIR / nid / "location_v3.invalid.json"
                meta_v3_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            continue
        new_html = md_to_section_html(body_md)
        if not new_html:
            failed.append((nid, "md_to_section_html 빈 결과 — post.html 보존"))
            continue
        if dry_run:
            print(f"  [dry-run] 생성 HTML 길이: {len(new_html)}자, 섹션 {len(sections)}개")
            success.append(nid)
            continue
        if not _patch_post_html(nid, new_html):
            failed.append((nid, "post.html SECTION 2 매칭 실패"))
            continue
        success.append(nid)
        if not repatch_only:
            # repatch 모드는 캐시 재사용이라 json 재저장 불필요.
            meta_v3_path = POSTS_DIR / nid / "location_v3.json"
            meta_v3_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  ✅ post.html 패치 (섹션 {len(sections)}개)")

    print()
    print(f"성공 {len(success)}건 / 실패 {len(failed)}건")
    for nid, reason in failed[:10]:
        print(f"  - {nid}: {reason}")
    return 0 if not failed else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--targets", nargs="+", default=[])
    parser.add_argument("--all-active", action="store_true", help="winner_date >= today 인 모든 포스트")
    parser.add_argument(
        "--all-past",
        action="store_true",
        help="winner_date < today 이면서 아직 v3 패치되지 않은(location_v3.json 없는) 포스트",
    )
    parser.add_argument("--limit", type=int, default=0, help="최대 처리 건수 (0=제한 없음)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--repatch-only",
        action="store_true",
        help="LLM 재호출 없이 location_v3.json 캐시로 SECTION 2 HTML 만 다시 만듦 (a11y/px→rem 같은 형식 변경용)",
    )
    args = parser.parse_args()

    today = _kst_today()
    if args.targets:
        targets = args.targets
    elif args.all_active:
        targets = [nid for nid, _apt, _addr in _list_active_posts(today)]
    elif args.all_past:
        targets = [nid for nid, _apt, _addr in _list_past_posts(today)]
    else:
        parser.error("--targets 또는 --all-active 또는 --all-past 필요")

    if args.limit:
        targets = targets[: args.limit]
    print(f"[patch] 기준일 {today} / 대상 {len(targets)}건 / dry_run={args.dry_run} / repatch_only={args.repatch_only}")
    return asyncio.run(main_async(targets, args.dry_run, args.repatch_only))


if __name__ == "__main__":
    sys.exit(main())
