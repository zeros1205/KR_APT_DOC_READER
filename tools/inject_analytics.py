"""Inject the GA4 (G-D5SCQRYKSM) snippet into every HTML file under output/.

Idempotent: a file that already contains the marker comment is skipped, so the
script can run repeatedly without duplicating the snippet.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

MARKER = "<!-- ga4-injected:G-D5SCQRYKSM -->"

GA_SNIPPET = """<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-D5SCQRYKSM"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());

  gtag('config', 'G-D5SCQRYKSM');
</script>"""

INJECT_BLOCK = MARKER + "\n" + GA_SNIPPET + "\n"


def inject(text: str) -> tuple[str, str]:
    if MARKER in text:
        return text, "skipped"
    if "</head>" not in text:
        return text, "no-head"
    new_text = text.replace("</head>", INJECT_BLOCK + "</head>", 1)
    return new_text, "modified"


def process(root: Path) -> tuple[int, int, int]:
    modified = skipped = no_head = 0
    for path in sorted(root.rglob("*.html")):
        original = path.read_text(encoding="utf-8")
        new_text, status = inject(original)
        if status == "modified":
            path.write_text(new_text, encoding="utf-8")
            modified += 1
            print(f"[modified] {path}")
        elif status == "skipped":
            skipped += 1
        else:
            no_head += 1
            print(f"[no-head]  {path}", file=sys.stderr)
    return modified, skipped, no_head


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        default="output",
        help="Directory to scan recursively for .html files (default: output)",
    )
    args = parser.parse_args()

    root = Path(args.output_dir)
    if not root.is_dir():
        print(f"output dir not found: {root}", file=sys.stderr)
        return 1

    modified, skipped, no_head = process(root)
    print(
        f"\nSummary: modified={modified}, skipped={skipped}, no-head={no_head}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
