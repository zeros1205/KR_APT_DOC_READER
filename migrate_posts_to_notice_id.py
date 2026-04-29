"""
Migrate generated post directories to notice_id-based names.

New convention:
  output/posts/{notice_id}/post.html
  output/posts/{notice_id}/post_meta.json

The notice_id is read from post_meta.json when present, otherwise extracted from
notice_url query params. If duplicated legacy folders map to the same notice_id,
the newest generated_at/mtime entry is kept and older duplicates are removed.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parent
POSTS_DIR = ROOT / "output" / "posts"
NOTICE_RE = re.compile(r"(?:pblancNo|houseManageNo)=([0-9]+)")


def _notice_id_from_meta(meta: dict[str, Any]) -> str:
    notice_id = str(meta.get("notice_id") or "").strip()
    if notice_id:
        return notice_id
    match = NOTICE_RE.search(str(meta.get("notice_url") or ""))
    return match.group(1) if match else ""


def _sort_ts(meta_path: Path, meta: dict[str, Any]) -> float:
    generated_at = str(meta.get("generated_at") or "")
    try:
        return datetime.fromisoformat(generated_at).timestamp()
    except Exception:
        return meta_path.stat().st_mtime


def _load_post_dirs() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for meta_path in sorted(POSTS_DIR.glob("*/post_meta.json")):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception as exc:
            rows.append({"dir": meta_path.parent, "notice_id": "", "error": str(exc), "meta": {}})
            continue
        rows.append(
            {
                "dir": meta_path.parent,
                "notice_id": _notice_id_from_meta(meta),
                "meta": meta,
                "ts": _sort_ts(meta_path, meta),
                "error": "",
            }
        )
    return rows


def _write_notice_id(meta_path: Path, notice_id: str) -> None:
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if str(meta.get("notice_id") or "") == notice_id:
        return
    meta["notice_id"] = notice_id
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def migrate(dry_run: bool = False) -> None:
    rows = _load_post_dirs()
    missing = [row for row in rows if not row["notice_id"]]
    if missing:
        print("[migrate] notice_id 추출 실패 폴더:")
        for row in missing:
            print(f"  - {row['dir'].name}: {row['error'] or 'notice_url 없음'}")
        raise SystemExit(1)

    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row["notice_id"], []).append(row)

    moved = 0
    removed = 0
    updated = 0

    for notice_id, items in sorted(grouped.items()):
        items.sort(key=lambda row: row["ts"], reverse=True)
        keep = items[0]
        target = POSTS_DIR / notice_id

        print(f"[migrate] {notice_id}: keep={keep['dir'].name} -> {target.name}")

        if not dry_run:
            if keep["dir"] != target:
                if target.exists():
                    shutil.rmtree(target)
                    removed += 1
                shutil.move(str(keep["dir"]), str(target))
                moved += 1
            _write_notice_id(target / "post_meta.json", notice_id)
            updated += 1

        for duplicate in items[1:]:
            print(f"  remove duplicate: {duplicate['dir'].name}")
            if not dry_run and duplicate["dir"].exists():
                shutil.rmtree(duplicate["dir"])
                removed += 1

    print(
        f"[migrate] done dry_run={dry_run} total={len(rows)} unique={len(grouped)} "
        f"moved={moved} removed={removed} meta_updated={updated}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate output/posts folders to notice_id names")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without changing files")
    args = parser.parse_args()
    migrate(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
