"""generate_app_icons.py — 단일 정사각 소스 PNG에서 iOS·Android·웹 아이콘 일괄 생성.

사용:
  python3 scripts/generate_app_icons.py mobile-app/assets/icon-only.png

생성 대상:
  - iOS Assets.xcassets/AppIcon.appiconset (Universal + 명시적 다중 사이즈)
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

# (출력 경로, 가로, 세로)
TARGETS: list[tuple[str, int, int]] = [
    # ── 웹 파비콘 / PWA ────────────────────────────────────────
    ("output/favicon-16x16.png", 16, 16),
    ("output/favicon-32x32.png", 32, 32),
    ("output/apple-touch-icon.png", 180, 180),
    ("output/android-chrome-192x192.png", 192, 192),
    ("output/android-chrome-512x512.png", 512, 512),

    # ── 웹 헤더 로고 ───────────────────────────────────────────
    ("output/app_logo_80x80_rounded.png", 80, 80),
    ("output/app_logo_1024x1024_rounded.png", 1024, 1024),
    ("output/jung_reader_logo.png", 256, 256),

    # ── 모바일 앱 내부 자산 ────────────────────────────────────
    ("mobile-app/src/assets/app_logo_80x80_rounded.png", 80, 80),

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


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2

    source_path = Path(sys.argv[1]).resolve()
    if not source_path.exists():
        print(f"ERROR: source not found: {source_path}", file=sys.stderr)
        return 1

    source = Image.open(source_path).convert("RGB")
    print(f"source: {source_path}  ({source.size[0]}x{source.size[1]} {source.mode})")

    for rel_path, width, height in TARGETS:
        out_path = ROOT / rel_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        resized = source.resize((width, height), Image.LANCZOS)
        # PNG. apple-touch-icon 같은 일부는 알파 채널 없는 것이 더 안전.
        resized.save(out_path, format="PNG", optimize=True)
        print(f"  {width:4d}x{height:<4d}  {rel_path}")

    # iOS Contents.json 갱신
    contents_path = ROOT / "mobile-app/ios/App/App/Assets.xcassets/AppIcon.appiconset/Contents.json"
    contents_path.write_text(json.dumps(IOS_CONTENTS, indent=2) + "\n", encoding="utf-8")
    print(f"  wrote {contents_path.relative_to(ROOT)}")

    # 기존 universal idiom 파일은 제거 (Contents.json 에서 더이상 참조 안 함)
    legacy_universal = ROOT / "mobile-app/ios/App/App/Assets.xcassets/AppIcon.appiconset/AppIcon-512@2x.png"
    if legacy_universal.exists():
        legacy_universal.unlink()
        print(f"  removed legacy universal idiom: {legacy_universal.relative_to(ROOT)}")

    # ICO 파일은 PIL 로 multi-resolution 생성
    ico_path = ROOT / "output/favicon.ico"
    ico_sizes = [(16, 16), (32, 32), (48, 48)]
    source.resize((48, 48), Image.LANCZOS).save(
        ico_path,
        format="ICO",
        sizes=ico_sizes,
    )
    print(f"  wrote {ico_path.relative_to(ROOT)} ({', '.join(f'{w}x{h}' for w, h in ico_sizes)})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
