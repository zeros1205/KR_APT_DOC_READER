"""
Check that frozen UI/layout files match the approved local baseline.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

BASE_DIR = Path(__file__).parent
MANIFEST_FILE = BASE_DIR / "UI_FREEZE_MANIFEST.json"
TEXT_SUFFIXES = {".html", ".py", ".css", ".js", ".json", ".md", ".txt", ".yml", ".yaml"}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    data = path.read_bytes()
    if path.suffix.lower() in TEXT_SUFFIXES:
        data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    h.update(data)
    return h.hexdigest().upper()


def check_ui_freeze() -> list[str]:
    manifest = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
    failures: list[str] = []
    for rel_path, meta in manifest.get("files", {}).items():
        path = BASE_DIR / rel_path
        if not path.exists():
            failures.append(f"{rel_path}: missing")
            continue
        actual = _sha256(path)
        expected = str(meta.get("sha256", "")).upper()
        if actual != expected:
            failures.append(f"{rel_path}: hash mismatch")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Check UI freeze manifest")
    parser.parse_args()

    failures = check_ui_freeze()
    if failures:
        print("[ui-freeze] FAILED")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print("[ui-freeze] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
