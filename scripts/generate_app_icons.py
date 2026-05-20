"""generate_app_icons.py — iOS·Android 소스를 분리하여 전체 아이콘 세트 생성.

기본 소스 경로 (인자 없이 실행):
  Android: mobile-app/assets/icon-only.png
  iOS:     input/logo_img/ios_icon_1024.png

개별 지정 시:
  python3 scripts/generate_app_icons.py [android_src] [ios_src]

생성 대상:
  - iOS Assets.xcassets/AppIcon.appiconset (Universal + 명시적 다중 사이즈)
  - Android mipmap ic_launcher_foreground (dpi별)
  - mobile-app/src/assets/ 앱 헤더 이미지
  - output/ 웹 파비콘·헤더 로고·PWA 아이콘 일습

이 스크립트는 단순 비례 리사이즈만 한다. 알파 채널/모서리 둥글기 없음.
원본은 1024 이상 정사각 PNG 권장.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent

DEFAULT_ANDROID_SRC = ROOT / "mobile-app/assets/icon-only.png"
DEFAULT_IOS_SRC = ROOT / "input/logo_img/ios_icon_1024.png"

# (출력 경로, 가로, 세로)
#
# NOTE: 웹 파비콘/PWA/헤더 로고(output/) 와 mobile-app/src/assets/ 의 헤더 로고는
# 더 이상 이 스크립트로 생성하지 않는다. Pillow 버전/환경에 따라 같은 소스에서도
# 다른 PNG 가 나오는 회귀가 있었고(2026-05-19 `77bdcfb`), 디자이너가 직접 제작한
# 자산이 output/ 에 commit 되어 있으므로 스크립트 출력으로 덮어쓰면 안 된다.
# 이 스크립트는 Android Adaptive Icon foreground (네이티브 빌드 필수) 에만 사용.
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

IOS_TARGETS: list[tuple[str, int, int]] = [
    # ── iOS AppIcon.appiconset (Universal 1장 + 명시 사이즈) ──
    ("mobile-app/ios/App/App/Assets.xcassets/AppIcon.appiconset/AppIcon-1024.png", 1024, 1024),
    ("mobile-app/ios/App/App/Assets.xcassets/AppIcon.appiconset/AppIcon-20@2x.png", 40, 40),
    ("mobile-app/ios/App/App/Assets.xcassets/AppIcon.appiconset/AppIcon-20@3x.png", 60, 60),
    ("mobile-app/ios/App/App/Assets.xcassets/AppIcon.appiconset/AppIcon-29@2x.png", 58, 58),
    ("mobile-app/ios/App/App/Assets.xcassets/AppIcon.appiconset/AppIcon-29@3x.png", 87, 87),
    ("mobile-app/ios/App/App/Assets.xcassets/AppIcon.appiconset/AppIcon-40@2x.png", 80, 80),
    ("mobile-app/ios/App/App/Assets.xcassets/AppIcon.appiconset/AppIcon-40@3x.png", 120, 120),
    ("mobile-app/ios/App/App/Assets.xcassets/AppIcon.appiconset/AppIcon-60@2x.png", 120, 120),
    ("mobile-app/ios/App/App/Assets.xcassets/AppIcon.appiconset/AppIcon-60@3x.png", 180, 180),
    ("mobile-app/ios/App/App/Assets.xcassets/AppIcon.appiconset/AppIcon-20.png", 20, 20),
    ("mobile-app/ios/App/App/Assets.xcassets/AppIcon.appiconset/AppIcon-29.png", 29, 29),
    ("mobile-app/ios/App/App/Assets.xcassets/AppIcon.appiconset/AppIcon-40.png", 40, 40),
    ("mobile-app/ios/App/App/Assets.xcassets/AppIcon.appiconset/AppIcon-76@2x.png", 152, 152),
    ("mobile-app/ios/App/App/Assets.xcassets/AppIcon.appiconset/AppIcon-83.5@2x.png", 167, 167),
]

# Contents.json — iOS AppIcon.appiconset 매핑
IOS_CONTENTS = {
    "images": [
        {"size": "20x20", "idiom": "iphone", "filename": "AppIcon-20@2x.png", "scale": "2x"},
        {"size": "20x20", "idiom": "iphone", "filename": "AppIcon-20@3x.png", "scale": "3x"},
        {"size": "29x29", "idiom": "iphone", "filename": "AppIcon-29@2x.png", "scale": "2x"},
        {"size": "29x29", "idiom": "iphone", "filename": "AppIcon-29@3x.png", "scale": "3x"},
        {"size": "40x40", "idiom": "iphone", "filename": "AppIcon-40@2x.png", "scale": "2x"},
        {"size": "40x40", "idiom": "iphone", "filename": "AppIcon-40@3x.png", "scale": "3x"},
        {"size": "60x60", "idiom": "iphone", "filename": "AppIcon-60@2x.png", "scale": "2x"},
        {"size": "60x60", "idiom": "iphone", "filename": "AppIcon-60@3x.png", "scale": "3x"},
        {"size": "20x20", "idiom": "ipad", "filename": "AppIcon-20.png", "scale": "1x"},
        {"size": "20x20", "idiom": "ipad", "filename": "AppIcon-20@2x.png", "scale": "2x"},
        {"size": "29x29", "idiom": "ipad", "filename": "AppIcon-29.png", "scale": "1x"},
        {"size": "29x29", "idiom": "ipad", "filename": "AppIcon-29@2x.png", "scale": "2x"},
        {"size": "40x40", "idiom": "ipad", "filename": "AppIcon-40.png", "scale": "1x"},
        {"size": "40x40", "idiom": "ipad", "filename": "AppIcon-40@2x.png", "scale": "2x"},
        {"size": "76x76", "idiom": "ipad", "filename": "AppIcon-76@2x.png", "scale": "2x"},
        {"size": "83.5x83.5", "idiom": "ipad", "filename": "AppIcon-83.5@2x.png", "scale": "2x"},
        {"size": "1024x1024", "idiom": "ios-marketing", "filename": "AppIcon-1024.png", "scale": "1x"},
    ],
    "info": {"author": "xcode", "version": 1},
}


def _process(source: Image.Image, targets: list[tuple[str, int, int]]) -> None:
    for rel_path, width, height in targets:
        out_path = ROOT / rel_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        resized = source.resize((width, height), Image.LANCZOS)
        if rel_path.endswith("AppIcon-1024.png"):
            resized = resized.convert("RGB")
        resized.save(out_path, format="PNG", optimize=True)
        print(f"  {width:4d}x{height:<4d}  {rel_path}")


def main() -> int:
    if len(sys.argv) > 3:
        print(__doc__, file=sys.stderr)
        return 2

    android_src = Path(sys.argv[1]).resolve() if len(sys.argv) >= 2 else DEFAULT_ANDROID_SRC
    ios_src = Path(sys.argv[2]).resolve() if len(sys.argv) == 3 else DEFAULT_IOS_SRC

    for label, path in [("Android", android_src), ("iOS", ios_src)]:
        if not path.exists():
            print(f"ERROR: {label} source not found: {path}", file=sys.stderr)
            return 1

    android_img = Image.open(android_src).convert("RGBA")
    print(f"Android source: {android_src}  ({android_img.size[0]}x{android_img.size[1]})")
    _process(android_img, ANDROID_TARGETS)

    ios_img = Image.open(ios_src).convert("RGBA")
    print(f"\niOS source: {ios_src}  ({ios_img.size[0]}x{ios_img.size[1]})")
    _process(ios_img, IOS_TARGETS)

    # iOS Contents.json 갱신
    contents_path = ROOT / "mobile-app/ios/App/App/Assets.xcassets/AppIcon.appiconset/Contents.json"
    contents_path.write_text(json.dumps(IOS_CONTENTS, indent=2) + "\n", encoding="utf-8")
    print(f"  wrote {contents_path.relative_to(ROOT)}")

    # 기존 universal idiom 파일 제거
    legacy_universal = ROOT / "mobile-app/ios/App/App/Assets.xcassets/AppIcon.appiconset/AppIcon-512@2x.png"
    if legacy_universal.exists():
        legacy_universal.unlink()
        print(f"  removed legacy: {legacy_universal.relative_to(ROOT)}")

    # ICO (웹 파비콘)
    ico_path = ROOT / "output/favicon.ico"
    ico_sizes = [(16, 16), (32, 32), (48, 48)]
    android_img.resize((48, 48), Image.LANCZOS).save(ico_path, format="ICO", sizes=ico_sizes)
    print(f"  wrote {ico_path.relative_to(ROOT)} ({', '.join(f'{w}x{h}' for w, h in ico_sizes)})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
