"""Sync logo and favicon assets into the static output directory."""

from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCE_DIR = ROOT / "input" / "logo_img"
OUTPUT_DIR = ROOT / "output"

ASSET_MAP = [
    ("favicon.ico", "favicon.ico"),
    ("favicon-16x16.png", "favicon-16x16.png"),
    ("favicon-32x32.png", "favicon-32x32.png"),
    ("apple-touch-icon.png", "apple-touch-icon.png"),
    ("android-chrome-192x192.png", "android-chrome-192x192.png"),
    ("android-chrome-512x512.png", "android-chrome-512x512.png"),
    ("site.webmanifest", "manifest.json"),
    ("site.webmanifest", "site.webmanifest"),
    ("app_logo_80x80_rounded.png", "app_logo_80x80_rounded.png"),
    ("app_logo_1024x1024_rounded.png", "app_logo_1024x1024_rounded.png"),
]

# Backward-compatible output name used by older generated pages.
LEGACY_LOGO_TARGET = "jung_reader_logo.png"


def main() -> None:
    if not SOURCE_DIR.exists():
        raise FileNotFoundError(f"missing brand asset directory: {SOURCE_DIR}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    copied = 0
    for source_name, target_name in ASSET_MAP:
        source = SOURCE_DIR / source_name
        if not source.exists():
            continue
        shutil.copy2(source, OUTPUT_DIR / target_name)
        copied += 1

    logo = SOURCE_DIR / "app_logo_80x80_rounded.png"
    if logo.exists():
        shutil.copy2(logo, OUTPUT_DIR / LEGACY_LOGO_TARGET)
        copied += 1

    print(f"[brand-assets] copied={copied} output={OUTPUT_DIR}")


if __name__ == "__main__":
    main()
