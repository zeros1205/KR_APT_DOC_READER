"""generate_app_icons.py — Android Adaptive Icon foreground 만 생성.

기본 소스 경로 (인자 없이 실행):
  Android: mobile-app/assets/icon-only.png

개별 지정 시:
  python3 scripts/generate_app_icons.py [android_src]

생성 대상:
  - Android mipmap ic_launcher_foreground (dpi별)

이 스크립트는 단순 비례 리사이즈만 한다. 알파 채널/모서리 둥글기 없음.
원본은 512 이상 정사각 PNG 권장.

NOTE: iOS AppIcon, 웹 파비콘/PWA/헤더 로고, mobile-app/src/assets/ 의 헤더
이미지는 더 이상 이 스크립트로 생성하지 않는다. Pillow 버전/환경에 따라
같은 소스에서도 다른 PNG 가 나와 회귀를 일으킨 이력이 있고(2026-05-19
`77bdcfb`), 디자이너가 직접 제작한 풀세트를 commit 하는 흐름으로 통일했다.
스크립트가 다시 살아나도 Android Adaptive Icon foreground 만 건드린다.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent

DEFAULT_ANDROID_SRC = ROOT / "mobile-app/assets/icon-only.png"

# (출력 경로, 가로, 세로)
ANDROID_TARGETS: list[tuple[str, int, int]] = [
    # ── Android Adaptive Icon foreground (108dp base, dpi 별 px) ──
    # Android 8+ 에서 시스템이 자동 마스크를 적용. 외곽 ~17% 가 잘리므로
    # source 의 텍스트가 중앙 66% 안에 있어야 함.
    ("mobile-app/android/app/src/main/res/mipmap-mdpi/ic_launcher_foreground.png", 108, 108),
    ("mobile-app/android/app/src/main/res/mipmap-hdpi/ic_launcher_foreground.png", 162, 162),
    ("mobile-app/android/app/src/main/res/mipmap-xhdpi/ic_launcher_foreground.png", 216, 216),
    ("mobile-app/android/app/src/main/res/mipmap-xxhdpi/ic_launcher_foreground.png", 324, 324),
    ("mobile-app/android/app/src/main/res/mipmap-xxxhdpi/ic_launcher_foreground.png", 432, 432),
]


def _process(source: Image.Image, targets: list[tuple[str, int, int]]) -> None:
    for rel_path, width, height in targets:
        out_path = ROOT / rel_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        resized = source.resize((width, height), Image.LANCZOS)
        resized.save(out_path, format="PNG", optimize=True)
        print(f"  {width:4d}x{height:<4d}  {rel_path}")


def main() -> int:
    if len(sys.argv) > 2:
        print(__doc__, file=sys.stderr)
        return 2

    android_src = Path(sys.argv[1]).resolve() if len(sys.argv) == 2 else DEFAULT_ANDROID_SRC

    if not android_src.exists():
        print(f"ERROR: Android source not found: {android_src}", file=sys.stderr)
        return 1

    android_img = Image.open(android_src).convert("RGBA")
    print(f"Android source: {android_src}  ({android_img.size[0]}x{android_img.size[1]})")
    _process(android_img, ANDROID_TARGETS)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
