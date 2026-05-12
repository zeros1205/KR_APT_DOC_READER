"""refactor_px_to_rem.py — 접근성을 위해 px 단위를 rem 으로 안전 치환.

폰을 OS 폰트 배율로 키우는 노년·시각약자 사용자가 사이트·앱 UI 가 깨지지
않도록, font-size·line-height 등 텍스트 관련 px 단위를 rem 으로 일괄 변환.
height 는 min-height 로 격상해 박스 overflow 차단.

기본 매핑 (16px = 1rem)
  font-size: 12px → 0.75rem
  font-size: 14px → 0.875rem
  font-size: 16px → 1rem
  font-size: 18px → 1.125rem
  ...

치환 범위
  - font-size: Npx       → rem
  - line-height: Npx     → rem
  - letter-spacing: Npx  → rem
  - gap·padding 의 텍스트 인접 케이스는 사람이 검토 (자동 변환 X)

NOTE: 과거 버전의 `height → min-height` 자동 변환은 정사각형 아이콘·이미지
(예: `.persona-card img { width:64px; height:64px }`) 의 비율을 깨뜨릴 수 있어
제거. height/min-height 결정은 사람이 컨텍스트 보고 직접 변경.

사용
  python tools/refactor_px_to_rem.py path/to/file.css --dry-run
  python tools/refactor_px_to_rem.py mobile-app/src/styles.css
  python tools/refactor_px_to_rem.py --glob "output/about.html"
"""

from __future__ import annotations

import argparse
import glob as globlib
import re
import sys
from pathlib import Path


PX_BASE = 16.0  # 1rem 기준

# font-size·line-height·letter-spacing 옆 Npx 매칭. min/max-font-size 등도 포함.
PX_RE = re.compile(
    r"(font-size|line-height|letter-spacing)\s*:\s*([0-9]+(?:\.[0-9]+)?)\s*px",
    re.IGNORECASE,
)
# 정사각 박스 패턴 — 같은 선언 블록 안에 `width: Npx; height: Npx` 가 있고
# Codex P2: 그 안의 line-height 까지 rem 으로 바꾸면 OS 폰트 배율 변경 시 텍스트가
# 원 밖으로 튀어나옴. 정사각 박스 안의 line-height 는 px 그대로 유지해야 함.
SQUARE_BLOCK_RE = re.compile(
    r"width:\s*(\d+)px;\s*height:\s*(\d+)px",
    re.IGNORECASE,
)


def _to_rem(px: float) -> str:
    value = px / PX_BASE
    # 4자리 소수 → 3자리로 정리 + trailing zero 제거
    s = f"{value:.4f}".rstrip("0").rstrip(".")
    return f"{s}rem"


def _is_in_square_block(text: str, pos: int) -> bool:
    """pos 위치가 정사각 박스 선언({...}) 안에 있는지 판단."""
    # 가장 가까운 { 와 } 위치 찾기
    block_start = text.rfind("{", 0, pos)
    block_end = text.find("}", pos)
    if block_start == -1 or block_end == -1:
        return False
    block = text[block_start:block_end]
    m = SQUARE_BLOCK_RE.search(block)
    if not m:
        return False
    return m.group(1) == m.group(2)  # width == height


def _replace_text_px(text: str) -> tuple[str, int]:
    count = 0
    skipped_in_square = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal count, skipped_in_square
        prop = match.group(1).lower()
        px = float(match.group(2))
        if px == 0:
            return match.group(0)
        # 정사각 박스 안의 line-height 는 px 유지 (Codex P2)
        if prop == "line-height" and _is_in_square_block(text, match.start()):
            skipped_in_square += 1
            return match.group(0)
        count += 1
        return f"{match.group(1)}: {_to_rem(px)}"

    new_text = PX_RE.sub(repl, text)
    return new_text, count


def process_file(path: Path, *, dry_run: bool) -> dict:
    text = path.read_text(encoding="utf-8")
    new_text, text_count = _replace_text_px(text)
    if dry_run:
        return {"file": str(path), "text_px": text_count, "changed": False}
    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
    return {
        "file": str(path),
        "text_px": text_count,
        "changed": new_text != text,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", help="처리할 파일 또는 glob 패턴")
    parser.add_argument("--glob", default="", help="추가 glob 패턴 (큰따옴표로)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    targets: list[Path] = []
    for spec in args.paths:
        for p in globlib.glob(spec, recursive=True):
            path = Path(p)
            if path.is_file():
                targets.append(path)
    if args.glob:
        for p in globlib.glob(args.glob, recursive=True):
            path = Path(p)
            if path.is_file():
                targets.append(path)
    if not targets:
        parser.error("처리할 파일 없음")

    total_text = changed_files = 0
    for t in targets:
        result = process_file(t, dry_run=args.dry_run)
        total_text += result["text_px"]
        if result["changed"]:
            changed_files += 1
        mode = "[dry]" if args.dry_run else "[apply]"
        print(f"{mode} {t}  text-px {result['text_px']:>3}")

    print()
    print(f"총 파일 {len(targets)}건 · 변경 {changed_files}건 · 텍스트 px→rem {total_text}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
