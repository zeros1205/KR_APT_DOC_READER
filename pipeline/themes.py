"""
themes.py
────────────────────────────────────────────────────
블로그 포스팅 디자인 테마 정의
awesome-design-md (github.com/VoltAgent/awesome-design-md) 컬렉션 기반

사용법:
  config.py의 BLOG_THEME = "intercom" 으로 설정
  html_renderer.py가 자동으로 해당 테마 토큰을 적용

추가 가능 테마:
  notion / airbnb / intercom / stripe / apple / mintlify
────────────────────────────────────────────────────
"""

THEMES: dict[str, dict[str, str]] = {

    # ──────────────────────────────────────────────
    # CLAUDE — 따뜻한 크림, 에디토리얼 감성, Anthropic 브랜드 톤
    # claude.com/blog 스타일: 크림 배경, 코랄 포인트, 넉넉한 행간
    # ──────────────────────────────────────────────
    "claude": {
        "name": "Claude",
        "description": "따뜻한 크림, 에디토리얼 감성, Anthropic 브랜드 톤",
        # 배경 — 순백 대신 따뜻한 오프화이트
        "bg":           "#FAF9F7",
        "surface":      "#F5F2ED",
        "surface2":     "#ECE8E1",
        "border":       "#DED9D1",
        # 텍스트 — 차가운 검정 대신 따뜻한 차콜
        "text":         "#2C2825",
        "text2":        "#6A635C",
        "muted":        "#A39D96",
        # 강조 — Anthropic 코랄/테라코타
        "accent":       "#CC5F3F",
        "accent_dark":  "#A84830",
        "accent_light": "#FDEEE8",
        # 헤더
        "header_bg":    "linear-gradient(135deg, #CC5F3F 0%, #A84830 60%, #8B3A24 100%)",
        "header_text":  "#FFFFFF",
        "header_sub":   "rgba(255,255,255,0.78)",
        # Q&A
        "q_bg":         "#2C2825",
        "q_text":       "#FFFFFF",
        "q_badge_bg":   "#CC5F3F",
        "q_badge_text": "#FFFFFF",
        "a_badge_bg":   "#4A7C5F",
        "a_badge_text": "#FFFFFF",
        # 테이블
        "table_head":   "#2C2825",
        "table_head_t": "#FFFFFF",
        "table_stripe": "#F5F2ED",
        # 태그
        "tag_bg":       "#FDEEE8",
        "tag_text":     "#A84830",
        # 구분선/타임라인
        "divider":      "#CC5F3F",
        "timeline":     "#DED9D1",
        # 카드 (입지 점수)
        "card1_bg":     "#FDEEE8", "card1_text": "#A84830",
        "card2_bg":     "#EBF5EE", "card2_text": "#2D6349",
        "card3_bg":     "#FEF8EC", "card3_text": "#8B6200",
        "card4_bg":     "#FDEEF0", "card4_text": "#8B1A2A",
        # 납부 단계 색상
        "step1": "#B83C1E", "step2": "#D4820A", "step3": "#CC5F3F",
        # 반응형 & 여백
        "radius_sm":    "6px",
        "radius_md":    "10px",
        "radius_lg":    "16px",
        "radius_pill":  "24px",
        "shadow_sm":    "0 1px 4px rgba(44,40,37,0.07)",
        "shadow_md":    "0 4px 14px rgba(44,40,37,0.10)",
        "shadow_lg":    "0 8px 28px rgba(44,40,37,0.13)",
        # 면책 고지
        "disclaimer_bg":     "#F5F2ED",
        "disclaimer_border": "#DED9D1",
    },

    # ──────────────────────────────────────────────
    # NOTION — 따뜻한 미니멀, 세리프 감성, 가독성 최우선
    # ──────────────────────────────────────────────
    "notion": {
        "name": "Notion",
        "description": "따뜻한 크림 배경, 가독성 최우선, 콘텐츠 블로그 기본",
        # 배경
        "bg":           "#FFFFFF",
        "surface":      "#F7F6F3",
        "surface2":     "#EEECEA",
        "border":       "#E9E8E4",
        # 텍스트
        "text":         "#37352F",
        "text2":        "#6B6B6B",
        "muted":        "#9B9A97",
        # 강조 (브랜드 골드 유지)
        "accent":       "#E8A020",
        "accent_dark":  "#C87D10",
        "accent_light": "#FEF3DC",
        # 헤더
        "header_bg":    "#37352F",
        "header_text":  "#FFFFFF",
        "header_sub":   "rgba(255,255,255,0.65)",
        # Q&A
        "q_bg":         "#37352F",
        "q_text":       "#FFFFFF",
        "q_badge_bg":   "#E8A020",
        "q_badge_text": "#FFFFFF",
        "a_badge_bg":   "#2D6A4F",
        "a_badge_text": "#FFFFFF",
        # 테이블
        "table_head":   "#37352F",
        "table_head_t": "#FFFFFF",
        "table_stripe": "#F7F6F3",
        # 태그
        "tag_bg":       "#EDF2FC",
        "tag_text":     "#37352F",
        # 구분선/타임라인
        "divider":      "#E8A020",
        "timeline":     "#E8A020",
        # 카드 (입지 점수)
        "card1_bg":     "#EBF5FB", "card1_text": "#1B4F72",
        "card2_bg":     "#EAFAF1", "card2_text": "#1E8449",
        "card3_bg":     "#FEF9E7", "card3_text": "#9A6C00",
        "card4_bg":     "#FDEDEC", "card4_text": "#922B21",
        # 납부 단계 색상
        "step1": "#C0392B", "step2": "#E67E22", "step3": "#1B3F6B",
        # 반응형 & 여백
        "radius_sm":    "4px",
        "radius_md":    "6px",
        "radius_lg":    "8px",
        "radius_pill":  "20px",
        "shadow_sm":    "0 1px 3px rgba(0,0,0,0.06)",
        "shadow_md":    "0 2px 8px rgba(0,0,0,0.08)",
        "shadow_lg":    "0 4px 16px rgba(0,0,0,0.10)",
        # 면책 고지
        "disclaimer_bg": "#F7F6F3",
        "disclaimer_border": "#E9E8E4",
    },

    # ──────────────────────────────────────────────
    # INTERCOM — 대화형 블루, 고객 상담원 느낌, 스토리텔링 최적
    # ──────────────────────────────────────────────
    "intercom": {
        "name": "Intercom",
        "description": "대화형 블루, 고객 상담원 느낌, 스토리텔링 최적",
        # 배경
        "bg":           "#FFFFFF",
        "surface":      "#F0F4FF",
        "surface2":     "#E4ECFF",
        "border":       "#C7D7FD",
        # 텍스트
        "text":         "#1F2937",
        "text2":        "#4B5563",
        "muted":        "#9CA3AF",
        # 강조
        "accent":       "#0057FF",
        "accent_dark":  "#0041CC",
        "accent_light": "#EBF0FF",
        # 헤더
        "header_bg":    "linear-gradient(135deg, #0057FF 0%, #0041CC 100%)",
        "header_text":  "#FFFFFF",
        "header_sub":   "rgba(255,255,255,0.75)",
        # Q&A
        "q_bg":         "#0057FF",
        "q_text":       "#FFFFFF",
        "q_badge_bg":   "#FFFFFF",
        "q_badge_text": "#0057FF",
        "a_badge_bg":   "#059669",
        "a_badge_text": "#FFFFFF",
        # 테이블
        "table_head":   "#0057FF",
        "table_head_t": "#FFFFFF",
        "table_stripe": "#F0F4FF",
        # 태그
        "tag_bg":       "#EBF0FF",
        "tag_text":     "#0041CC",
        # 구분선/타임라인
        "divider":      "#0057FF",
        "timeline":     "#0057FF",
        # 카드 (입지 점수)
        "card1_bg":     "#EBF0FF", "card1_text": "#0041CC",
        "card2_bg":     "#ECFDF5", "card2_text": "#065F46",
        "card3_bg":     "#FFFBEB", "card3_text": "#92400E",
        "card4_bg":     "#FFF1F2", "card4_text": "#9F1239",
        # 납부 단계 색상
        "step1": "#DC2626", "step2": "#D97706", "step3": "#0057FF",
        # 반응형 & 여백
        "radius_sm":    "6px",
        "radius_md":    "10px",
        "radius_lg":    "14px",
        "radius_pill":  "24px",
        "shadow_sm":    "0 1px 3px rgba(0,87,255,0.06)",
        "shadow_md":    "0 4px 16px rgba(0,87,255,0.10)",
        "shadow_lg":    "0 8px 24px rgba(0,87,255,0.14)",
        # 면책 고지
        "disclaimer_bg": "#F0F4FF",
        "disclaimer_border": "#C7D7FD",
    },

    # ──────────────────────────────────────────────
    # AIRBNB — 코랄 레드, 라이프스타일 감성, 부동산 플랫폼 느낌
    # ──────────────────────────────────────────────
    "airbnb": {
        "name": "Airbnb",
        "description": "코랄 레드, 라이프스타일 감성, 부동산 플랫폼 느낌",
        "bg":           "#FFFFFF",
        "surface":      "#F7F7F7",
        "surface2":     "#EBEBEB",
        "border":       "#DDDDDD",
        "text":         "#222222",
        "text2":        "#717171",
        "muted":        "#B0B0B0",
        "accent":       "#FF385C",
        "accent_dark":  "#D50027",
        "accent_light": "#FFF0F3",
        "header_bg":    "linear-gradient(135deg, #FF385C 0%, #D50027 100%)",
        "header_text":  "#FFFFFF",
        "header_sub":   "rgba(255,255,255,0.80)",
        "q_bg":         "#FF385C",
        "q_text":       "#FFFFFF",
        "q_badge_bg":   "#FFFFFF",
        "q_badge_text": "#FF385C",
        "a_badge_bg":   "#00A699",
        "a_badge_text": "#FFFFFF",
        "table_head":   "#FF385C",
        "table_head_t": "#FFFFFF",
        "table_stripe": "#FFF8F8",
        "tag_bg":       "#FFF0F3",
        "tag_text":     "#D50027",
        "divider":      "#FF385C",
        "timeline":     "#FF385C",
        "card1_bg":     "#FFF0F3", "card1_text": "#D50027",
        "card2_bg":     "#F0FFF4", "card2_text": "#276749",
        "card3_bg":     "#FFFCF0", "card3_text": "#975A16",
        "card4_bg":     "#FFF5F5", "card4_text": "#C53030",
        "step1": "#C53030", "step2": "#DD6B20", "step3": "#2B6CB0",
        "radius_sm":    "8px",
        "radius_md":    "12px",
        "radius_lg":    "16px",
        "radius_pill":  "24px",
        "shadow_sm":    "0 1px 2px rgba(0,0,0,0.08), 0 4px 12px rgba(0,0,0,0.04)",
        "shadow_md":    "0 6px 16px rgba(0,0,0,0.12)",
        "shadow_lg":    "0 12px 32px rgba(0,0,0,0.14)",
        "disclaimer_bg": "#F7F7F7",
        "disclaimer_border": "#DDDDDD",
    },

    # ──────────────────────────────────────────────
    # STRIPE — 딥 퍼플 그라데이션, 고급스럽고 신뢰감
    # ──────────────────────────────────────────────
    "stripe": {
        "name": "Stripe",
        "description": "딥 퍼플 그라데이션, 고급스럽고 신뢰감, 금융 느낌",
        "bg":           "#FFFFFF",
        "surface":      "#F6F9FC",
        "surface2":     "#EBF0F7",
        "border":       "#E3E8EF",
        "text":         "#0A2540",
        "text2":        "#425466",
        "muted":        "#8898AA",
        "accent":       "#635BFF",
        "accent_dark":  "#4B44CC",
        "accent_light": "#EEF0FF",
        "header_bg":    "linear-gradient(135deg, #635BFF 0%, #0A2540 100%)",
        "header_text":  "#FFFFFF",
        "header_sub":   "rgba(255,255,255,0.70)",
        "q_bg":         "#0A2540",
        "q_text":       "#FFFFFF",
        "q_badge_bg":   "#635BFF",
        "q_badge_text": "#FFFFFF",
        "a_badge_bg":   "#24B47E",
        "a_badge_text": "#FFFFFF",
        "table_head":   "#0A2540",
        "table_head_t": "#FFFFFF",
        "table_stripe": "#F6F9FC",
        "tag_bg":       "#EEF0FF",
        "tag_text":     "#4B44CC",
        "divider":      "#635BFF",
        "timeline":     "#635BFF",
        "card1_bg":     "#EEF0FF", "card1_text": "#4B44CC",
        "card2_bg":     "#F0FFF8", "card2_text": "#145A32",
        "card3_bg":     "#FFF8F0", "card3_text": "#8B4513",
        "card4_bg":     "#FFF0F0", "card4_text": "#8B0000",
        "step1": "#C0392B", "step2": "#E67E22", "step3": "#635BFF",
        "radius_sm":    "5px",
        "radius_md":    "8px",
        "radius_lg":    "12px",
        "radius_pill":  "20px",
        "shadow_sm":    "0 1px 3px rgba(10,37,64,0.08)",
        "shadow_md":    "0 4px 12px rgba(10,37,64,0.12)",
        "shadow_lg":    "0 8px 24px rgba(10,37,64,0.15)",
        "disclaimer_bg": "#F6F9FC",
        "disclaimer_border": "#E3E8EF",
    },

    # ──────────────────────────────────────────────
    # APPLE — 순백 프리미엄, 여백 중심, SF 감성
    # ──────────────────────────────────────────────
    "apple": {
        "name": "Apple",
        "description": "순백 프리미엄, 여백 중심, 신뢰·고급 느낌",
        "bg":           "#FFFFFF",
        "surface":      "#F5F5F7",
        "surface2":     "#EBEBED",
        "border":       "#D2D2D7",
        "text":         "#1D1D1F",
        "text2":        "#515154",
        "muted":        "#86868B",
        "accent":       "#0071E3",
        "accent_dark":  "#0055B3",
        "accent_light": "#E8F2FF",
        "header_bg":    "#1D1D1F",
        "header_text":  "#FFFFFF",
        "header_sub":   "rgba(255,255,255,0.60)",
        "q_bg":         "#1D1D1F",
        "q_text":       "#FFFFFF",
        "q_badge_bg":   "#0071E3",
        "q_badge_text": "#FFFFFF",
        "a_badge_bg":   "#34C759",
        "a_badge_text": "#FFFFFF",
        "table_head":   "#1D1D1F",
        "table_head_t": "#FFFFFF",
        "table_stripe": "#F5F5F7",
        "tag_bg":       "#E8F2FF",
        "tag_text":     "#0055B3",
        "divider":      "#0071E3",
        "timeline":     "#0071E3",
        "card1_bg":     "#E8F2FF", "card1_text": "#0055B3",
        "card2_bg":     "#F0FFF4", "card2_text": "#1A7340",
        "card3_bg":     "#FFF9EC", "card3_text": "#8B5E00",
        "card4_bg":     "#FFF0F0", "card4_text": "#8B0000",
        "step1": "#FF3B30", "step2": "#FF9500", "step3": "#0071E3",
        "radius_sm":    "8px",
        "radius_md":    "12px",
        "radius_lg":    "18px",
        "radius_pill":  "24px",
        "shadow_sm":    "0 1px 4px rgba(0,0,0,0.06)",
        "shadow_md":    "0 4px 12px rgba(0,0,0,0.08)",
        "shadow_lg":    "0 10px 28px rgba(0,0,0,0.10)",
        "disclaimer_bg": "#F5F5F7",
        "disclaimer_border": "#D2D2D7",
    },

    # ──────────────────────────────────────────────
    # MINTLIFY — 그린 포인트, 문서 읽기 최적화, 깔끔한 정보 전달
    # ──────────────────────────────────────────────
    "mintlify": {
        "name": "Mintlify",
        "description": "그린 포인트, 문서 읽기 최적화, 깔끔한 정보 전달",
        "bg":           "#FFFFFF",
        "surface":      "#F4FBF6",
        "surface2":     "#E6F5EB",
        "border":       "#C6E8CF",
        "text":         "#18181B",
        "text2":        "#52525B",
        "muted":        "#A1A1AA",
        "accent":       "#16A34A",
        "accent_dark":  "#15803D",
        "accent_light": "#DCFCE7",
        "header_bg":    "linear-gradient(135deg, #16A34A 0%, #15803D 100%)",
        "header_text":  "#FFFFFF",
        "header_sub":   "rgba(255,255,255,0.75)",
        "q_bg":         "#16A34A",
        "q_text":       "#FFFFFF",
        "q_badge_bg":   "#FFFFFF",
        "q_badge_text": "#15803D",
        "a_badge_bg":   "#2563EB",
        "a_badge_text": "#FFFFFF",
        "table_head":   "#16A34A",
        "table_head_t": "#FFFFFF",
        "table_stripe": "#F4FBF6",
        "tag_bg":       "#DCFCE7",
        "tag_text":     "#15803D",
        "divider":      "#16A34A",
        "timeline":     "#16A34A",
        "card1_bg":     "#DCFCE7", "card1_text": "#15803D",
        "card2_bg":     "#EFF6FF", "card2_text": "#1D4ED8",
        "card3_bg":     "#FEF9C3", "card3_text": "#854D0E",
        "card4_bg":     "#FFE4E6", "card4_text": "#9F1239",
        "step1": "#DC2626", "step2": "#D97706", "step3": "#16A34A",
        "radius_sm":    "6px",
        "radius_md":    "10px",
        "radius_lg":    "14px",
        "radius_pill":  "22px",
        "shadow_sm":    "0 1px 3px rgba(22,163,74,0.06)",
        "shadow_md":    "0 4px 12px rgba(22,163,74,0.10)",
        "shadow_lg":    "0 8px 24px rgba(22,163,74,0.12)",
        "disclaimer_bg": "#F4FBF6",
        "disclaimer_border": "#C6E8CF",
    },

    # ──────────────────────────────────────────────
    # RESUPPLY — 연두 크림, 무순위·임의공급·재공급 전용
    # claude 테마와 동일한 따뜻한 크림 톤 베이스, 포인트만 연두색으로 전환
    # ──────────────────────────────────────────────
    "resupply": {
        "name": "재공급",
        "description": "연두 크림, 무순위·임의공급·재공급 전용",
        # 배경 — claude와 동일한 따뜻한 오프화이트
        "bg":           "#F8FAF5",
        "surface":      "#EFF6E8",
        "surface2":     "#E3EDD9",
        "border":       "#C8DEBC",
        # 텍스트 — claude와 동일한 따뜻한 차콜 계열
        "text":         "#252E1E",
        "text2":        "#556647",
        "muted":        "#8FA47B",
        # 강조 — 연두색 (lime green)
        "accent":       "#6BAF2E",
        "accent_dark":  "#507F21",
        "accent_light": "#E8FAD0",
        # 헤더
        "header_bg":    "linear-gradient(135deg, #6BAF2E 0%, #507F21 60%, #395C17 100%)",
        "header_text":  "#FFFFFF",
        "header_sub":   "rgba(255,255,255,0.78)",
        # Q&A
        "q_bg":         "#252E1E",
        "q_text":       "#FFFFFF",
        "q_badge_bg":   "#6BAF2E",
        "q_badge_text": "#FFFFFF",
        "a_badge_bg":   "#4A7C5F",
        "a_badge_text": "#FFFFFF",
        # 테이블
        "table_head":   "#252E1E",
        "table_head_t": "#FFFFFF",
        "table_stripe": "#EFF6E8",
        # 태그
        "tag_bg":       "#E8FAD0",
        "tag_text":     "#395C17",
        # 구분선/타임라인
        "divider":      "#6BAF2E",
        "timeline":     "#C8DEBC",
        # 카드 (입지 점수)
        "card1_bg":     "#E8FAD0", "card1_text": "#395C17",
        "card2_bg":     "#EBF5EE", "card2_text": "#2D6349",
        "card3_bg":     "#FEFBEC", "card3_text": "#7A6200",
        "card4_bg":     "#FDEEF0", "card4_text": "#8B1A2A",
        # 납부 단계 색상
        "step1": "#395C17", "step2": "#A07A1A", "step3": "#6BAF2E",
        # 반응형 & 여백 — claude와 동일
        "radius_sm":    "6px",
        "radius_md":    "10px",
        "radius_lg":    "16px",
        "radius_pill":  "24px",
        "shadow_sm":    "0 1px 4px rgba(37,46,30,0.07)",
        "shadow_md":    "0 4px 14px rgba(37,46,30,0.10)",
        "shadow_lg":    "0 8px 28px rgba(37,46,30,0.13)",
        # 면책 고지
        "disclaimer_bg":     "#EFF6E8",
        "disclaimer_border": "#C8DEBC",
    },
}


def get_theme(name: str) -> dict[str, str]:
    """테마 이름으로 토큰 딕셔너리 반환 (없으면 claude 기본값)"""
    return THEMES.get(name.lower(), THEMES["claude"])


def list_themes() -> list[dict]:
    """사용 가능한 테마 목록 반환"""
    return [{"id": k, "name": v["name"], "description": v["description"]}
            for k, v in THEMES.items()]
