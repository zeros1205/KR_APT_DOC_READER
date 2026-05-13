"""audit_location_v3_facts.py — v3 입지 분석 본문의 정책 위반 색출.

정책 (location_v3.py 의 Hallucination Guard 반영):
  · 입지 분석 본문에서 *평형·분양가를 제외한* 모든 금액 표현 금지
  · 부동산 규제 정보 (전매·재당첨·거주의무·상한제·규제지역) 일체 금지

본 도구는 v3 패치된 단지의 body_md 를 스캔해 위 두 정책에 걸리는 표현을
색출하고, 재생성용 --targets 문자열을 출력해 워크플로우에 그대로 복붙
가능하도록 함.

사용
  python tools/audit_location_v3_facts.py
  python tools/audit_location_v3_facts.py --json    # 머신 판독용
  python tools/audit_location_v3_facts.py --target 2026000098

출력
  - 의심 후보 단지 목록 (재생성용 --targets 자동 구성)
  - 단지별 위반 표현 인용
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = ROOT / "output" / "posts"
CACHE_DIR = ROOT / "output" / "data_cache" / "notices"


# 정책 1 — 평형·분양가 제외 금액 관련 키워드 (생성 금지).
MONEY_KEYWORDS = (
    "계약금", "중도금", "잔금", "무이자", "이자 후불", "이자후불", "후불제",
    "이주비", "발코니 확장", "발코니확장", "옵션 비용", "옵션비용",
    "전세보증금", "월세", "시세", "호가", "실거래가", "매매가",
    "대출 한도", "DSR", "LTV",
)
# 본문에서 "평형·분양가가 아닌 맥락의 금액 수치" 를 찾기 위한 단순 정규식.
# 분양가/평형 컨텍스트는 따로 분리해 사후 화이트리스트 처리.
RE_MONEY_AMOUNT = re.compile(r"\d[\d,]*\s*(?:만\s*원|억\s*원|억)")
RE_PRICE_CONTEXT = re.compile(r"(분양가|매매가|호가|시세|실거래가)\s*\d")

# 정책 2 — 부동산 규제 정보 (생성 금지).
REGULATION_KEYWORDS = (
    "전매", "재당첨", "거주 의무", "거주의무", "분양가 상한제", "분양가상한제",
    "투기과열", "조정대상", "규제 지역", "규제지역", "비규제지역", "비규제",
    "특별 공급", "특별공급", "1순위", "2순위", "청약 자격", "청약자격",
)


def _load_json(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def _quote_context(body: str, idx: int, span: int = 25) -> str:
    """인덱스 주변 문맥을 짧게 잘라 인용 — 보고용."""
    start = max(0, idx - span)
    end = min(len(body), idx + span)
    snippet = body[start:end].replace("\n", " ").strip()
    return f"…{snippet}…"


def audit_one(nid: str) -> dict | None:
    """단지 1건 검사. 정책 위반 표현이 있으면 dict 반환, 없으면 None.

    정책 1: 평형·분양가 외 모든 금액 표현 금지
    정책 2: 부동산 규제 관련 표현 일체 금지
    """
    v3_path = POSTS_DIR / nid / "location_v3.json"
    meta_path = POSTS_DIR / nid / "post_meta.json"
    cache_path = CACHE_DIR / f"{nid}.json"
    if not v3_path.exists():
        return None
    v3 = _load_json(v3_path)
    meta = _load_json(meta_path)
    cache = _load_json(cache_path)
    doc = cache.get("document") or {}

    body = (v3.get("body_md") or "")
    if not body:
        return None

    findings: list[str] = []

    # 정책 1 — 금액 키워드 직접 출현. 평형·분양가 컨텍스트는 별도 white-list.
    for kw in MONEY_KEYWORDS:
        idx = body.find(kw)
        if idx >= 0:
            findings.append(f"금액 키워드 '{kw}' 출현 — {_quote_context(body, idx)}")
    # 금액 수치 그 자체 — 분양가·시세 같은 합법 컨텍스트가 아니면 의심.
    for m in RE_MONEY_AMOUNT.finditer(body):
        idx = m.start()
        # 분양가/매매가/호가/시세/실거래가 와 함께 등장하는 경우는 정책 1 위반
        # (위에서 이미 키워드로 잡힘 — 중복 보고 방지) 아니면, 그냥 금액 수치만
        # 등장하는 경우 → 평형(㎡·m²) 인접 컨텍스트가 아니라면 의심.
        ctx_before = body[max(0, idx-15):idx]
        ctx_after = body[m.end():m.end()+10]
        ctx = ctx_before + m.group() + ctx_after
        # 평형 인접: "84㎡" "전용 84m²" — 평형 표시 옆 금액은 거의 없음 (분양가 같이 나오면 분양가 컨텍스트)
        # 분양가 컨텍스트면 _허용_ — "분양가 8억" 같은 표현은 OK.
        if "분양가" in ctx or "공급가" in ctx:
            continue
        findings.append(f"금액 수치 '{m.group().strip()}' 비-분양가 컨텍스트 — {_quote_context(body, idx)}")

    # 정책 2 — 규제 키워드 직접 출현.
    for kw in REGULATION_KEYWORDS:
        idx = body.find(kw)
        if idx >= 0:
            findings.append(f"규제 키워드 '{kw}' 출현 — {_quote_context(body, idx)}")

    if not findings:
        return None
    return {
        "notice_id": nid,
        "apt_name": (doc.get("apt_name") or meta.get("apt_name") or "").strip(),
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", default="", help="단일 단지 ID 검사")
    parser.add_argument("--json", action="store_true", help="머신 판독용 JSON 출력")
    args = parser.parse_args()

    if args.target:
        targets = [args.target]
    else:
        targets = sorted(p.parent.name for p in POSTS_DIR.glob("*/location_v3.json"))

    suspects: list[dict] = []
    for nid in targets:
        result = audit_one(nid)
        if result:
            suspects.append(result)

    if args.json:
        print(json.dumps({"total": len(targets), "suspects": suspects}, ensure_ascii=False, indent=2))
        return 0

    print(f"검사한 v3 패치 단지: {len(targets)}건")
    print(f"의심 후보: {len(suspects)}건")
    print()
    for s in suspects:
        print(f"  {s['notice_id']} {s['apt_name']}")
        for f in s["findings"]:
            print(f"    · {f}")
    if suspects:
        print()
        print("재생성용 targets (워크플로우 mode=targets 에 그대로 붙여넣기):")
        print(" ".join(s["notice_id"] for s in suspects))
    return 0


if __name__ == "__main__":
    sys.exit(main())
