"""audit_location_v3_facts.py — v3 입지 분석 본문의 hallucination 의심 표현 색출.

배경
  Gemini v3 가 grounded_facts_used 에 없는 정량/금융 표현(계약금 N만원, 전매
  N년, 무이자 등) 을 만들어 본문에 끼우는 사례 발견. 본 도구는 운영자가
  육안으로 모든 단지를 검토하지 않고도 의심 후보를 색출하도록 본문에서 정량
  표현 정규식 매칭 → cache/meta 와 자동 대조해 의심 후보를 출력.

자동 대조 가능 항목
  - 계약금 금액(만원 단위) → 분양가 × 5% 와 비교
  - 전매 표현 ("전매 제한이 없", "전매 N년") → post_meta.resale_restriction 비교
  - 무이자·후불제·이자 후불 → cache raw_text/pdf_policy_text 미언급 시 의심
  - 이주비·발코니 확장비 정량 → cache 미언급 시 의심

사용
  python tools/audit_location_v3_facts.py
  python tools/audit_location_v3_facts.py --json    # 머신 판독용
  python tools/audit_location_v3_facts.py --target 2026000098  # 단일 단지

출력
  - 의심 후보 단지 목록 (재실행 시 --targets 로 그대로 복사 가능)
  - 단지별 의심 표현 및 사유
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


# 본문에서 정량/금융 표현 추출 정규식.
RE_CONTRACT_AMOUNT = re.compile(r"계약금\s*(\d{2,5})\s*만\s*원")
RE_NO_RESALE = re.compile(r"전매\s*(제한이?\s*)?(없|미적용|해제|면제)")
RE_RESALE_YEARS = re.compile(r"전매\s*제한\s*(\d+)\s*년")
RE_NO_INTEREST = re.compile(r"(중도금\s*)?(무이자|이자\s*후불|이자\s*후불제|후불제)")
RE_RELOC_FUND = re.compile(r"이주비\s*(\d+\s*억|\d+\s*만\s*원)")
RE_BALCONY_FREE = re.compile(r"발코니\s*확장\s*무료")
RE_OPTION_PROMO = re.compile(r"옵션\s*(무료|할인|증정)")


def _load_json(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def _parse_max_price_won(price_range: str) -> int:
    """post_meta.price_range = '7억 400만원 ~ 8억원' → 8_0000_0000 (원)."""
    if not price_range:
        return 0
    # '8억원' / '8억' / '8억 100만원'
    nums = re.findall(r"(\d+)\s*억(?:\s*(\d+)\s*만)?", price_range)
    if not nums:
        return 0
    last = nums[-1]
    eok = int(last[0]) if last[0] else 0
    man = int(last[1]) if last[1] else 0
    return eok * 100_000_000 + man * 10_000


def audit_one(nid: str) -> dict | None:
    """단지 1건 검사. 의심 항목이 있으면 dict 반환, 없으면 None."""
    v3_path = POSTS_DIR / nid / "location_v3.json"
    meta_path = POSTS_DIR / nid / "post_meta.json"
    cache_path = CACHE_DIR / f"{nid}.json"
    if not v3_path.exists():
        return None  # v3 패치되지 않은 단지는 검사 대상 아님.
    v3 = _load_json(v3_path)
    meta = _load_json(meta_path)
    cache = _load_json(cache_path)
    doc = cache.get("document") or {}

    body = (v3.get("body_md") or "")
    if not body:
        return None

    findings: list[str] = []

    # 1. 계약금 금액 — 분양가 5% 와 비교.
    m = RE_CONTRACT_AMOUNT.search(body)
    if m:
        claimed_man = int(m.group(1))  # 만원 단위
        claimed_won = claimed_man * 10_000
        max_price = _parse_max_price_won(meta.get("price_range") or "")
        if max_price:
            expected_5pct = max_price * 0.05
            if claimed_won < expected_5pct * 0.5:
                findings.append(
                    f"계약금 {claimed_man}만원 (분양가 최대 {max_price//100_000_000}억 기준 5%={int(expected_5pct)//10000}만원과 큰 차이)"
                )

    # 2. 전매 제한 표현 — meta.resale_restriction 과 비교.
    resale = (meta.get("resale_restriction") or "").strip()
    if RE_NO_RESALE.search(body):
        if resale and resale not in {"없음", "미적용", "해제"}:
            findings.append(f"본문 '전매 제한 없음' 표현 vs meta.resale_restriction='{resale}'")
    yr = RE_RESALE_YEARS.search(body)
    if yr and resale:
        claimed = f"{yr.group(1)}년"
        if claimed != resale and resale not in {"없음", "미적용"}:
            findings.append(f"본문 전매 제한 '{claimed}' vs meta.resale_restriction='{resale}'")

    # 3. 무이자/후불제 — cache raw_text + pdf_policy_text 에 명시 없으면 의심.
    if RE_NO_INTEREST.search(body):
        src = (doc.get("raw_text") or "") + " " + (doc.get("pdf_policy_text") or "")
        if not re.search(r"무이자|이자\s*후불|후불제", src):
            findings.append("본문 '무이자/이자 후불/후불제' 표현 — cache raw_text 미언급")

    # 4. 이주비 정량 — cache 미언급 시 의심.
    rm = RE_RELOC_FUND.search(body)
    if rm:
        src = (doc.get("raw_text") or "") + " " + (doc.get("pdf_policy_text") or "")
        if "이주비" not in src:
            findings.append(f"본문 이주비 '{rm.group(0)}' — cache 미언급")

    # 5. 발코니 확장 무료 / 옵션 무료 — cache 미언급 시 의심.
    if RE_BALCONY_FREE.search(body):
        src = (doc.get("raw_text") or "") + " " + (doc.get("pdf_policy_text") or "")
        if not re.search(r"발코니\s*확장\s*(무료|0원)", src):
            findings.append("본문 '발코니 확장 무료' — cache 미언급")
    if RE_OPTION_PROMO.search(body):
        src = (doc.get("raw_text") or "") + " " + (doc.get("pdf_policy_text") or "")
        if not re.search(r"옵션\s*(무료|할인|증정)", src):
            findings.append("본문 '옵션 무료/할인/증정' — cache 미언급")

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
