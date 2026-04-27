"""
render_policy_pages.py
──────────────────────
Privacy 및 Terms 정책 페이지 렌더링
"""

from pathlib import Path

try:
    from shared_ui import PALETTE_INIT_JS
except ImportError:
    from pipeline.shared_ui import PALETTE_INIT_JS

ROOT = Path(__file__).parent.parent
TEMPLATES_DIR = ROOT / "templates"
OUTPUT_DIR = ROOT / "output"


def render_policy_pages() -> None:
    """Render privacy.html and terms.html from templates."""

    # Privacy page
    privacy_template = (TEMPLATES_DIR / "privacy_template.html").read_text(encoding="utf-8")
    privacy_html = privacy_template.replace("{{PALETTE_INIT_JS}}", PALETTE_INIT_JS)
    privacy_out = OUTPUT_DIR / "privacy.html"
    privacy_out.write_text(privacy_html, encoding="utf-8")
    print(f"✅ privacy.html 생성 완료: {privacy_out}")

    # Terms page
    terms_template = (TEMPLATES_DIR / "terms_template.html").read_text(encoding="utf-8")
    terms_html = terms_template.replace("{{PALETTE_INIT_JS}}", PALETTE_INIT_JS)
    terms_out = OUTPUT_DIR / "terms.html"
    terms_out.write_text(terms_html, encoding="utf-8")
    print(f"✅ terms.html 생성 완료: {terms_out}")


if __name__ == "__main__":
    render_policy_pages()
