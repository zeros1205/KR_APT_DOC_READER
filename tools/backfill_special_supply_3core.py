"""
backfill_special_supply_3core.py
────────────────────────────────────────────────────
특별공급 요건을 '유형별 핵심 3가지(대상 / 자격·소득요건 / 당첨자 선정방식)'로
재정리하고 기관추천 세분류를 하나로 묶은 개편(pipeline/orchestrator.py)을,
개편 이전에 생성된 2026 공고 포스트에 소급 적용한다.

동작:
  각 2026 포스트에 대해
    1) 현재 post_meta.json 의 eligibility_special 로 '특별공급 블록' HTML을
       html_renderer._render_eligibility 와 동일하게 재구성한다(= post.html 내
       기존 블록과 바이트 단위로 일치).
    2) _apply_special_supply_2026_guidance 로 최신 요건(3핵심·기관추천 묶음)을
       계산해 새 블록을 만든다.
    3) post.html 에서 기존 블록을 새 블록으로 치환하고 post_meta.json 도 갱신한다.

특별공급 블록만 교체하므로 입지분석 v3 섹션 등 나머지 콘텐츠는 무변경.

사용:
  python tools/backfill_special_supply_3core.py --dry-run
  python tools/backfill_special_supply_3core.py
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
POSTS_DIR = BASE_DIR / "output" / "posts"
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "pipeline"))

from themes import get_theme  # noqa: E402
from pipeline.orchestrator import _apply_special_supply_2026_guidance  # noqa: E402


def _build_special_block(elig: list[dict], t: dict) -> str | None:
    """html_renderer._render_eligibility 의 특별공급 카드 렌더링과 동일한 출력."""
    card_color = t["text2"]
    sp_cards = ""
    for sp in elig:
        type_name = sp.get("type_name", "")
        reqs = sp.get("requirements", [])
        req_items = "".join(
            f'<li style="font-size: 0.875rem;color:{t["text2"]};line-height:1.8;'
            f'padding:3px 0;border-bottom:1px solid {t["border"]};">'
            f'<span style="color:{card_color};font-weight:700;margin-right:6px;">·</span>{r}</li>'
            for r in reqs
        )
        sp_cards += (
            f'<div style="flex:1 1 calc(50% - 8px);min-width:200px;'
            f'background:{t["surface"]};border:1px solid {t["border"]};'
            f'border-top:3px solid {card_color};border-radius:{t["radius_md"]};'
            f'padding:16px 18px;">'
            f'<div style="font-size: 0.875rem;font-weight:800;color:{card_color};'
            f'margin-bottom:10px;">{type_name}</div>'
            f'<ul style="list-style:none;padding:0;margin:0;">{req_items}</ul>'
            f'</div>'
        )
    if not sp_cards:
        return None
    return (
        f'<div style="font-size: 0.8125rem;font-weight:700;color:{t["accent"]};'
        f'letter-spacing: 0.0312rem;margin-bottom:12px;">특별공급</div>'
        f'<div style="display:flex;flex-wrap:wrap;gap:10px;margin-bottom:28px;">'
        f'{sp_cards}</div>'
    )


def _region_replace(html: str, new_block: str) -> str | None:
    """오래된 마크업으로 블록이 바이트 일치하지 않는 포스트용 폴백.

    자격 섹션의 특별공급 라벨(>특별공급</div>) ~ 일반공급 라벨(>일반공급</div>)
    사이(= 특별공급 블록)를 새 블록으로 교체한다. '>일반공급</div>' 는 유일하며,
    자격 섹션 특공 라벨은 그 직전(마지막) '>특별공급</div>' 이다(그 뒤 것은 일정 섹션).
    """
    ilban = html.find(">일반공급</div>")
    if ilban < 0:
        return None
    sp_label = html.rfind(">특별공급</div>", 0, ilban)
    if sp_label < 0:
        return None
    start = html.rfind("<div", 0, sp_label)
    end = html.rfind("<div", 0, ilban)
    if not (0 <= start < sp_label < end <= ilban):
        return None
    return html[:start] + new_block + html[end:]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    changed = 0
    skipped_no_match: list[str] = []
    v3_broken: list[str] = []
    scanned = 0

    for post_dir in sorted(POSTS_DIR.iterdir()):
        if not post_dir.is_dir():
            continue
        meta_path = post_dir / "post_meta.json"
        html_path = post_dir / "post.html"
        if not (meta_path.exists() and html_path.exists()):
            continue

        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if not str(meta.get("notice_date") or "").startswith("2026-"):
            continue  # 2026 개정 표준요건이 적용된 공고만 대상
        old_elig = meta.get("eligibility_special") or []
        if not old_elig:
            continue
        scanned += 1

        t = get_theme(meta.get("theme", "claude"))
        old_block = _build_special_block(old_elig, t)
        if not old_block:
            continue

        html = html_path.read_text(encoding="utf-8")

        new_facts = _apply_special_supply_2026_guidance(
            {"notice_date": meta["notice_date"], "eligibility_special": copy.deepcopy(old_elig)}
        )
        new_elig = new_facts.get("eligibility_special") or old_elig
        new_block = _build_special_block(new_elig, t)
        if not new_block:
            continue

        if old_block in html:
            # 1순위: 바이트 일치 블록을 그대로 치환(가장 안전)
            if new_block == old_block:
                continue
            new_html = html.replace(old_block, new_block, 1)
        else:
            # 2순위: 오래된 마크업 → 라벨 영역 기반 폴백 치환
            new_html = _region_replace(html, new_block)
            if new_html is None or new_html == html:
                skipped_no_match.append(post_dir.name)
                continue

        had_v3 = "v3-readable" in html
        if had_v3 and "v3-readable" not in new_html:
            v3_broken.append(post_dir.name)
        # 안전장치: 자격 섹션 일반공급 라벨이 그대로 유지되는지
        if new_html.count(">일반공급</div>") != html.count(">일반공급</div>"):
            skipped_no_match.append(post_dir.name)
            continue

        changed += 1
        if not args.dry_run:
            html_path.write_text(new_html, encoding="utf-8")
            meta["eligibility_special"] = new_elig
            meta_path.write_text(
                json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
            )

    mode = "[dry-run] " if args.dry_run else ""
    print(f"{mode}2026 대상 스캔 {scanned}건 / 갱신 {changed}건")
    if skipped_no_match:
        print(f"  ⚠ 렌더 불일치로 건너뜀 {len(skipped_no_match)}건: {skipped_no_match}")
    if v3_broken:
        raise SystemExit(f"❌ v3-readable 마커 손실: {v3_broken}")
    print("✅ v3-readable 마커 보존 확인")


if __name__ == "__main__":
    main()
