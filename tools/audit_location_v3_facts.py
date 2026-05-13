"""audit_location_v3_facts.py — 입지 분석 본문의 정책 위반 색출.

정책 (location_v3.py 의 Hallucination Guard 반영):
  · 입지 분석 본문에서 *평형·분양가를 제외한* 모든 금액 표현 금지
  · 부동산 규제 정보 (전매·재당첨·거주의무·상한제·규제지역) 일체 금지

검사 대상
  · 기본: location_v3.json 이 있는 단지 (v3 패치 완료)
  · --include-non-v3: post.html SECTION 2 텍스트도 함께 (v3 미패치 단지 포함)

사용
  python tools/audit_location_v3_facts.py
  python tools/audit_location_v3_facts.py --include-non-v3        # 전체 포스트
  python tools/audit_location_v3_facts.py --include-non-v3 --ids-only
                                                                  # 위반 ID 만 공백 구분
  python tools/audit_location_v3_facts.py --json
  python tools/audit_location_v3_facts.py --target 2026000098
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

# post.html 의 SECTION 2 (입지 분석) 블록 추출용.
SECTION2_HTML_RE = re.compile(
    r'<!--\s*═{10,}\s*\n\s*SECTION 2 — 입지 분석[\s\S]*?<!--\s*구분선\s*-->',
    re.MULTILINE,
)


def _load_json(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def _strip_html(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _quote_context(body: str, idx: int, span: int = 25) -> str:
    """인덱스 주변 문맥을 짧게 잘라 인용 — 보고용."""
    start = max(0, idx - span)
    end = min(len(body), idx + span)
    snippet = body[start:end].replace("\n", " ").strip()
    return f"…{snippet}…"


def _extract_body(nid: str, include_non_v3: bool) -> tuple[str, str]:
    """단지 1건의 입지 분석 본문 추출. (body_text, source) 반환.

    source: 'v3' (location_v3.json) | 'html' (post.html SECTION 2) | '' (없음)
    """
    v3_path = POSTS_DIR / nid / "location_v3.json"
    if v3_path.exists():
        body = (_load_json(v3_path).get("body_md") or "")
        return body, "v3"
    if not include_non_v3:
        return "", ""
    post_html = POSTS_DIR / nid / "post.html"
    if not post_html.exists():
        return "", ""
    m = SECTION2_HTML_RE.search(post_html.read_text(encoding="utf-8"))
    if not m:
        return "", ""
    return _strip_html(m.group()), "html"


def audit_one(nid: str, *, include_non_v3: bool = False) -> dict | None:
    """단지 1건 검사. 정책 위반 표현이 있으면 dict 반환, 없으면 None."""
    body, source = _extract_body(nid, include_non_v3=include_non_v3)
    if not body:
        return None

    meta = _load_json(POSTS_DIR / nid / "post_meta.json")
    cache = _load_json(CACHE_DIR / f"{nid}.json")
    doc = cache.get("document") or {}

    findings: list[str] = []

    # 정책 1 — 금액 키워드 직접 출현. 평형·분양가 컨텍스트는 별도 white-list.
    for kw in MONEY_KEYWORDS:
        idx = body.find(kw)
        if idx >= 0:
            findings.append(f"금액 키워드 '{kw}' 출현 — {_quote_context(body, idx)}")
    # 금액 수치 그 자체 — 분양가·시세 같은 합법 컨텍스트가 아니면 의심.
    for m in RE_MONEY_AMOUNT.finditer(body):
        idx = m.start()
        ctx_before = body[max(0, idx-15):idx]
        ctx_after = body[m.end():m.end()+10]
        ctx = ctx_before + m.group() + ctx_after
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
        "source": source,
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", default="", help="단일 단지 ID 검사")
    parser.add_argument(
        "--include-non-v3",
        action="store_true",
        help="v3 패치 안 된 단지의 post.html SECTION 2 텍스트도 함께 검사",
    )
    parser.add_argument(
        "--ids-only",
        action="store_true",
        help="위반 단지 ID 만 공백 구분으로 출력 (스크립트 파이프용)",
    )
    parser.add_argument("--json", action="store_true", help="머신 판독용 JSON 출력")
    args = parser.parse_args()

    if args.target:
        targets = [args.target]
    elif args.include_non_v3:
        # 모든 단지 (v3 패치 여부 무관)
        targets = sorted(p.parent.name for p in POSTS_DIR.glob("*/post_meta.json"))
    else:
        targets = sorted(p.parent.name for p in POSTS_DIR.glob("*/location_v3.json"))

    suspects: list[dict] = []
    for nid in targets:
        result = audit_one(nid, include_non_v3=args.include_non_v3)
        if result:
            suspects.append(result)

    if args.ids_only:
        print(" ".join(s["notice_id"] for s in suspects))
        return 0
    if args.json:
        print(json.dumps({"total": len(targets), "suspects": suspects}, ensure_ascii=False, indent=2))
        return 0

    scope = "전체 (v3+html)" if args.include_non_v3 else "v3 패치 단지"
    print(f"검사 범위: {scope} / 검사 단지: {len(targets)}건")
    print(f"위반 후보: {len(suspects)}건")
    print()
    for s in suspects:
        print(f"  [{s['source']}] {s['notice_id']} {s['apt_name']}")
        for f in s["findings"]:
            print(f"    · {f}")
    if suspects:
        print()
        print("재생성용 targets:")
        print(" ".join(s["notice_id"] for s in suspects))
    return 0


if __name__ == "__main__":
    sys.exit(main())
