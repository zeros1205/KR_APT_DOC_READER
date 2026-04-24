"""
build_index.py
──────────────────────────────────────────────
프런트 페이지 생성 엔트리포인트.

최신 index 레이아웃은 templates/front_index_template.html을 기준으로 유지하고,
이 파일은 index 전용 렌더러만 호출한다.
"""

try:
    from index_renderer import build_front_index
except ImportError:
    from pipeline.index_renderer import build_front_index


if __name__ == "__main__":
    build_front_index()
