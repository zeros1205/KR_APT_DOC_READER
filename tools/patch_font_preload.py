"""기존 포스트 HTML의 동기 폰트 로드를 비동기 preload 방식으로 교체"""
from pathlib import Path

ROOT = Path(__file__).parent.parent
FONT_HREF = (
    "https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9"
    "/dist/web/variable/pretendardvariable-dynamic-subset.min.css"
)
OLD = f'<link rel="stylesheet" href="{FONT_HREF}">'
NEW = (
    f'<link rel="preload" href="{FONT_HREF}" as="style"'
    " onload=\"this.onload=null;this.rel='stylesheet'\">\n"
    f'<noscript><link rel="stylesheet" href="{FONT_HREF}"></noscript>'
)

def main():
    files = list((ROOT / "output" / "posts").glob("*/post.html"))
    patched = skipped = 0
    for f in files:
        html = f.read_text(encoding="utf-8")
        if OLD in html:
            f.write_text(html.replace(OLD, NEW, 1), encoding="utf-8")
            patched += 1
        else:
            skipped += 1
    print(f"패치: {patched}개 / 스킵: {skipped}개")

if __name__ == "__main__":
    main()
