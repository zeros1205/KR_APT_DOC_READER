"""measure_location_diversity.py — 입지분석 섹션 차별성 측정 도구.

목적
  - 같은 사이트 안의 단지 두 개를 골라 02 입지분석 본문의 글자 일치율을 측정.
  - cliche(일반어) 카운트 / 구체 수치·고유명사 카운트를 같이 보여줘
    프롬프트·데이터 개선의 효과를 정량 비교 가능하게 함.

지표
  1) shingling 기반 5-gram 자카드 유사도 (0~1)
  2) cliche 출현 횟수 (운영자 정의 사전)
  3) 구체 수치·고유명사 매치 횟수 (정규식)

사용
  python tools/measure_location_diversity.py [--targets ID1 ID2 ...]
  python tools/measure_location_diversity.py --all              # output/posts/*/post.html 전수
  python tools/measure_location_diversity.py --baseline-dir /tmp/location_baseline   # 사전 캡처된 파일 비교
"""

from __future__ import annotations

import argparse
import re
import sys
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = ROOT / "output" / "posts"

# blog_template 의 입지 섹션 추출 — "02 · 입지" 부터 다음 섹션 전까지
LOCATION_RE = re.compile(
    r'(02\.\s*입지|입지\s*분석|주요\s*입지|위치\s*분석)(.*?)'
    r'(?=03\.|자금\s*계획|타입별\s*분양가|<!--\s*FOOTER|<!--\s*══|🗓|⚠️)',
    re.DOTALL,
)
TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")

# 사이트 전반에 반복 노출되는 cliche — 사용자 피드백 기반.
CLICHE_TERMS = [
    "쾌적한", "우수한", "체계적", "원활", "편리한", "다양한", "잘 갖추",
    "주거 환경", "주거 편의", "생활 인프라", "주거 가치", "정주 여건",
    "안정적", "편안한", "안락한", "조화롭게", "조화를 이루",
    "주거지로서", "주거 트렌드", "현대적", "쾌적성", "효율성",
    "프라이버시", "고급 주거", "완성도",
]

# 구체적 정보 신호 — 수치·고유명사·노선번호 등
SPECIFIC_PATTERNS = [
    re.compile(r"\d+\s*호선"),         # 지하철 노선
    re.compile(r"\d+\s*분"),            # 통학·통근 시간
    re.compile(r"\d{2,4}\s*[mM]"),      # 거리
    re.compile(r"\d+\s*만\s*원"),       # 가격
    re.compile(r"\d+\s*세대"),          # 세대수
    re.compile(r"진학률\s*\d+"),
    re.compile(r"평균\s*\d+"),
    re.compile(r"인구\s*[+\-]\s*\d+"),
    re.compile(r"[가-힣A-Za-z]+(?:역|초등학교|중학교|고등학교|대학교|병원|공원|아파트|단지|상권|타운)"),
]


def extract_location_text(html: str) -> str:
    m = LOCATION_RE.search(html)
    if not m:
        return ""
    text = TAG_RE.sub(" ", m.group(0))
    return WS_RE.sub(" ", text).strip()


def shingles(text: str, n: int = 5) -> set[str]:
    cleaned = re.sub(r"[^\w가-힣]", "", text)
    return {cleaned[i : i + n] for i in range(len(cleaned) - n + 1)} if len(cleaned) >= n else set()


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def count_cliches(text: str) -> int:
    return sum(text.count(c) for c in CLICHE_TERMS)


def count_specifics(text: str) -> int:
    return sum(len(p.findall(text)) for p in SPECIFIC_PATTERNS)


def load_post(notice_id: str) -> tuple[str, str]:
    """Return (label, text) for given notice id from output/posts."""
    p = POSTS_DIR / notice_id / "post.html"
    if not p.exists():
        return notice_id, ""
    return notice_id, extract_location_text(p.read_text(encoding="utf-8"))


def load_baseline_dir(directory: Path) -> dict[str, str]:
    """사전 캡처한 .txt 파일들 로드. 파일명을 ID 로 사용."""
    out: dict[str, str] = {}
    for p in sorted(directory.glob("*.txt")):
        text = p.read_text(encoding="utf-8")
        # 첫 줄 "=== ID | 단지명 ===" 라인 제거하고 본문만
        body = re.sub(r"^===.*?===\s*\n?", "", text, count=1, flags=re.DOTALL).strip()
        out[p.stem] = body
    return out


def report(samples: list[tuple[str, str]]) -> None:
    if not samples:
        print("❌ 비교할 샘플이 없습니다.")
        return

    print(f"=== 입력 샘플 {len(samples)}건 ===")
    for label, text in samples:
        cliche = count_cliches(text)
        specific = count_specifics(text)
        density = (specific / max(len(text), 1)) * 1000  # per 1000 chars
        print(f"  {label}: 본문 {len(text):>5d}자 · cliche {cliche:>2d}회 · 구체 {specific:>2d}회 "
              f"(밀도 {density:.1f}/1000자)")

    print()
    print(f"=== 페어별 글자 일치율 (5-gram Jaccard) ===")
    shingle_map = {label: shingles(text) for label, text in samples}
    pairs = list(combinations(samples, 2))
    scores = []
    for (la, _), (lb, _) in pairs:
        sim = jaccard(shingle_map[la], shingle_map[lb])
        scores.append(sim)
        bar = "█" * int(sim * 40)
        print(f"  {la} ↔ {lb}  {sim*100:>5.1f}%  {bar}")

    if scores:
        avg = sum(scores) / len(scores)
        print()
        print(f"평균 일치율: {avg*100:.1f}%   (목표: 30~40% 이하)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--targets", nargs="*", default=[],
                        help="비교할 notice_id 들 (예: 2026000048 2026000058 ...)")
    parser.add_argument("--all", action="store_true",
                        help="output/posts/*/post.html 전수 비교 (느림)")
    parser.add_argument("--baseline-dir", default="",
                        help="사전 캡처한 .txt 폴더 (예: /tmp/location_baseline)")
    args = parser.parse_args()

    samples: list[tuple[str, str]] = []
    if args.baseline_dir:
        loaded = load_baseline_dir(Path(args.baseline_dir))
        samples = [(k, v) for k, v in loaded.items()]
    elif args.targets:
        for nid in args.targets:
            label, text = load_post(nid)
            if text:
                samples.append((label, text))
            else:
                print(f"⚠️  {nid}: 입지 섹션 추출 실패")
    elif args.all:
        for d in sorted(POSTS_DIR.iterdir()):
            if not d.is_dir():
                continue
            label, text = load_post(d.name)
            if text:
                samples.append((label, text))
    else:
        parser.print_help()
        return 1

    report(samples)
    return 0


if __name__ == "__main__":
    sys.exit(main())
