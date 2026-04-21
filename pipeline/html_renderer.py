"""
html_renderer.py v2.0
────────────────────────────────────────────────────
스토리텔링 구조 + 테마 시스템 적용

변경 사항 (v2):
  - 스토리텔링 순서: 인사 → 단지 소개 → 입지 → 분양정보 → 자금계획 → Q&A
  - 테마 토큰({{T_*}}) 기반 다크/라이트/색상 일괄 전환
  - 내러티브 산문 필드: apt_intro / location_intro / financial_intro / qa_intro
────────────────────────────────────────────────────
"""

import sys
import re
import json
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))
from image_finder import ImageResult, render_image_html, build_credit_html
from themes import get_theme, THEMES


# ──────────────────────────────────────────────────
# 데이터 구조
# ──────────────────────────────────────────────────

@dataclass
class UnitType:
    type_name: str
    area_sqm: float
    general_units: int
    special_units: int
    price_min: int   # 만원
    price_max: int   # 만원

    @staticmethod
    def _to_manwon(v: int) -> int:
        """원(won) 단위 값을 만원으로 변환. 1000만 만원(1조) 초과 시 원으로 간주."""
        return v // 10000 if v > 10_000_000 else v

    @staticmethod
    def _fmt(won_man: int) -> str:
        if won_man <= 0:
            return "-"
        won_man = UnitType._to_manwon(won_man)
        uk = won_man // 10000
        man = won_man % 10000
        if uk > 0 and man > 0:
            return f"{uk}억 {man:,}만원"
        if uk > 0:
            return f"{uk}억원"
        return f"{man:,}만원"

    @property
    def price_range_str(self) -> str:
        lo, hi = self._fmt(self.price_min), self._fmt(self.price_max)
        return lo if self.price_min == self.price_max else f"{lo} ~ {hi}"

    @property
    def price_per_3_3(self) -> str:
        if self.area_sqm <= 0:
            return "-"
        p_min = self._to_manwon(self.price_min)
        p_max = self._to_manwon(self.price_max)
        avg = (p_min + p_max) / 2
        val = int(avg / (self.area_sqm / 3.3))
        return f"{val:,}만원"


@dataclass
class QABlock:
    question: str
    answer: str       # 인라인 HTML 허용 (<strong> <br> 등)
    image: Optional[ImageResult] = None
    # 추후 CTA 활성화
    cta_url: str = ""
    cta_text: str = ""


@dataclass
class PostData:
    # 식별
    apt_name: str
    post_title: str
    post_subtitle: str
    location: str
    supply_location: str
    supply_scale: str
    total_households: str = ""   # 단지 전체 세대수 (공급세대수와 다를 수 있음)
    price_range: str

    # 유닛 타입
    unit_types: list[UnitType] = field(default_factory=list)

    # 청약 일정
    special_supply_date: str = "-"
    rank1_date: str = "-"
    rank2_date: str = "-"
    winner_date: str = "-"
    move_in_date: str = "-"

    # 금융
    loan_info: str = ""
    resale_restriction: str = ""
    contract_ratio: str = "10"
    contract_amount: str = ""
    midterm_ratio: str = "60"
    midterm_count: str = "6"
    balance_ratio: str = "30"

    # 세금
    acquisition_tax_rate: str = ""
    acquisition_tax_amount: str = "-"
    property_tax_rate: str = "과세표준 × 0.1~0.4%"
    property_tax_amount: str = "-"
    capital_gains_tax_rate: str = "1주택 2년 보유 시 비과세 가능"
    capital_gains_tax_amount: str = "-"

    # 입지 별점
    subway_score: str = "★★★☆☆"
    subway_detail: str = ""
    school_score: str = "★★★☆☆"
    school_detail: str = ""
    life_score: str = "★★★☆☆"
    life_detail: str = ""
    medical_score: str = "★★★☆☆"
    medical_detail: str = ""

    # 내러티브 산문 (LLM 생성) — 섹션 도입부
    apt_intro: str = ""          # 첫인사 + 단지 소개
    location_intro: str = ""     # 입지 설명
    financial_intro: str = ""    # 자금 계획 도입
    qa_intro: str = ""           # Q&A 도입

    # 정보 블록 앞 설명 (LLM 생성) — 표/타임라인 전 맥락 제공
    unit_type_desc: str = ""     # 타입별 분양가 표 앞 설명
    schedule_desc: str = ""      # 청약 일정 타임라인 앞 설명
    tax_desc: str = ""           # 세금 표 앞 설명

    # 청약 신청자격
    eligibility_special: list = field(default_factory=list)  # [{type_name, quota, requirements:[str]}]
    eligibility_rank1: list[str] = field(default_factory=list)
    eligibility_rank2: list[str] = field(default_factory=list)

    # Q&A
    qa_blocks: list[QABlock] = field(default_factory=list)

    # SEO
    seo_tags: list[str] = field(default_factory=list)

    # 이미지
    images: dict[str, ImageResult] = field(default_factory=dict)

    # 메타
    source_date: str = ""
    notice_date: str = ""       # 모집공고일
    read_time: int = 7
    supply_type: str = ""       # API SUBSCRPT_TYCD_NM 원본값

    # 테마
    theme: str = "intercom"

    # 공고문 URL
    notice_url: str = ""


# ──────────────────────────────────────────────────
# 렌더링 헬퍼
# ──────────────────────────────────────────────────

TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "blog_template.html"

_SUPPLY_LABEL_MAP = [
    ("무순위",    "무순위"),
    ("불법행위",  "불법행위재공급"),
    ("임의",      "임의공급"),
    ("취소후",    "취소후재공급"),
    ("잔여",      "잔여세대"),
    ("특별",      "특별공급"),
    ("일반",      "일반공급"),
]

_PUBLIC_APT_KW = ("공공분양", "공공임대", "행복주택", "국민임대", "lh", "sh공사",
                  "경기주택", "인천도시공사", "주공", "공공지원")


def _supply_label(supply_type: str, apt_name: str = "") -> str:
    for kw, label in _SUPPLY_LABEL_MAP:
        if kw in supply_type:
            return label
    combined = (supply_type + " " + apt_name).lower()
    if any(kw in combined for kw in _PUBLIC_APT_KW):
        return "공공분양"
    return "민간분양"

def _render_header_tag(label: str, radius: str) -> str:
    return (
        f'<span style="display:inline-block; background:rgba(255,255,255,0.18);'
        f' color:#FFFFFF; font-size:12px; font-weight:700; letter-spacing:1px;'
        f' padding:5px 14px; border-radius:{radius};'
        f' border:1px solid rgba(255,255,255,0.28);">{label}</span>'
    )


def _notice_doc_btn(notice_url: str, is_lh: bool = False) -> str:
    if not notice_url:
        return ""
    label = "LH청약플러스 바로가기 →" if is_lh else "📄 모집공고문 다운로드"
    return (
        f'<div style="margin-top:24px;text-align:center;">'
        f'<a href="{notice_url}" target="_blank" rel="noopener noreferrer" '
        f'style="display:inline-flex;align-items:center;gap:8px;'
        f'background:var(--c-surface);color:var(--c-dark);'
        f'font-size:15px;font-weight:700;'
        f'padding:14px 28px;border-radius:8px;'
        f'border:2px solid var(--c-primary);'
        f'text-decoration:none;letter-spacing:-0.2px;'
        f'box-shadow:0 2px 6px rgba(0,0,0,0.08);transition:all 200ms;" '
        f'onmouseover="this.style.background=\'var(--c-primary-light)\';this.style.borderColor=\'var(--c-primary-dark)\'" '
        f'onmouseout="this.style.background=\'var(--c-surface)\';this.style.borderColor=\'var(--c-primary)\'">'
        f'{label}'
        f'</a>'
        f'</div>'
    )


def _naver_map_url(address: str) -> str:
    from urllib.parse import quote
    return f"https://map.naver.com/v5/search/{quote(address)}" if address else "https://map.naver.com/"


def _price_range_typed(unit_types: list[UnitType], fallback: str) -> str:
    """최소~최대 분양가 — 금액 큰 글씨, 타입명 16px"""
    valid = [ut for ut in unit_types if ut.price_min > 0]
    if not valid:
        return fallback
    cheapest = min(valid, key=lambda u: u.price_min)
    priciest = max(valid, key=lambda u: u.price_max)

    def _row(price_str: str, type_name: str, prefix: str = "") -> str:
        return (
            f'{prefix}<span style="font-size:22px;font-weight:800;">{price_str}</span>'
            f'<span style="font-size:16px;font-weight:600;opacity:0.85;">({type_name})</span>'
        )

    lo = _row(cheapest._fmt(cheapest.price_min), cheapest.type_name)
    if cheapest is priciest and cheapest.price_min == cheapest.price_max:
        return lo
    hi = _row(priciest._fmt(priciest.price_max), priciest.type_name, prefix="~ ")
    return f"{lo}<br>{hi}"


def _render_unit_rows_intro(unit_types: list[UnitType]) -> str:
    """단지 소개 섹션용 — 5열 (타입/전용/공급세대/분양가/3.3㎡당), 흰색 반투명 스타일"""
    rows = []
    for ut in unit_types:
        total = ut.general_units + ut.special_units
        rows.append(f"""
      <tr style="text-align: center; border-bottom: 1px solid rgba(255,255,255,0.15);">
        <td style="padding: 10px 10px; font-weight: 700; color: #fff; white-space: nowrap;">{ut.type_name}</td>
        <td style="padding: 10px 8px; color: rgba(255,255,255,0.85); letter-spacing: 0.025em;">{round(ut.area_sqm, 1):.1f}</td>
        <td style="padding: 10px 8px; color: rgba(255,255,255,0.85); letter-spacing: 0.025em;">{total:,}세대</td>
        <td style="padding: 10px 10px; font-weight: 700; color: #fff; white-space: nowrap;">{ut.price_range_str}</td>
        <td style="padding: 10px 8px; color: rgba(255,255,255,0.85); letter-spacing: 0.025em;">{ut.price_per_3_3}</td>
      </tr>""")
    return "\n".join(rows)


def _render_unit_rows(unit_types: list[UnitType], t: dict) -> str:
    rows = []
    for i, ut in enumerate(unit_types):
        stripe = f"background: {t['table_stripe']};" if i % 2 == 1 else ""
        rows.append(f"""
      <tr style="text-align: center; border-bottom: 1px solid {t['border']}; {stripe}">
        <td style="padding: 10px 8px; font-weight: 700; color: {t['accent']};">{ut.type_name}</td>
        <td style="padding: 10px 8px; color: {t['text2']};">{round(ut.area_sqm, 1):.1f}</td>
        <td style="padding: 10px 8px; color: {t['text']};">{ut.general_units:,}</td>
        <td style="padding: 10px 8px; color: {t['text']};">{ut.special_units:,}</td>
        <td style="padding: 10px 8px; color: {t['step1']}; font-weight: 700;">{ut.price_range_str}</td>
        <td style="padding: 10px 8px; color: {t['text2']};">{ut.price_per_3_3}</td>
      </tr>""")
    return "\n".join(rows)


def _render_qa_block(qa: QABlock, idx: int, t: dict) -> str:
    img_html = ""
    if qa.image:
        credit = build_credit_html(qa.image)
        img_html = f"""
      <div style="margin: 12px 0; border-radius: {t['radius_sm']}; overflow: hidden;">
        <img src="{qa.image.url}" alt="Q{idx+1} 관련 이미지"
             style="width: 100%; max-height: 200px; object-fit: cover; display: block;" />
        <p style="font-size: 11px; color: {t['muted']}; margin: 4px 8px; font-style: italic;">📷 {credit}</p>
      </div>"""

    return f"""
  <div style="
    border: 1px solid {t['border']}; border-radius: {t['radius_lg']};
    margin-bottom: 16px; overflow: hidden; box-shadow: {t['shadow_sm']};
  ">
    <!-- 질문 -->
    <div style="
      background: {t['q_bg']}; padding: 14px 18px;
      display: flex; align-items: flex-start; gap: 10px;
    ">
      <span style="
        background: {t['q_badge_bg']}; color: {t['q_badge_text']};
        font-weight: 700; font-size: 12px;
        padding: 2px 9px; border-radius: {t['radius_sm']};
        flex-shrink: 0; margin-top: 1px;
      ">Q</span>
      <span style="
        color: {t['q_text']}; font-size: 16px;
        font-weight: 700; line-height: 1.6; word-break: keep-all;
      ">{qa.question}</span>
    </div>
    <!-- 답변 -->
    <div style="padding: 16px 18px; background: {t['bg']};">
      <div style="display: flex; align-items: flex-start; gap: 10px;">
        <span style="
          background: {t['a_badge_bg']}; color: {t['a_badge_text']};
          font-weight: 700; font-size: 12px;
          padding: 2px 9px; border-radius: {t['radius_sm']}; flex-shrink: 0;
        ">A</span>
        <div style="color: {t['text']}; font-size: 16px; line-height: 1.6; word-break: keep-all;">{qa.answer}</div>
      </div>{img_html}
    </div>
  </div>"""


def _render_seo_tags(tags: list[str], t: dict) -> str:
    fixed = ["중도금대출", "주택담보대출", "아파트청약", "청약가점"]
    all_tags = list(dict.fromkeys(tags + fixed))[:10]
    spans = []
    for tag in all_tags:
        clean = tag.lstrip("#")
        spans.append(
            f'<span style="background:{t["tag_bg"]}; color:{t["tag_text"]}; '
            f'font-size:11px; padding:4px 10px; border-radius:{t["radius_pill"]}; '
            f'font-weight:600; display:inline-block;">#{clean}</span>'
        )
    return "\n  ".join(spans)


def _render_eligibility(data: "PostData", t: dict) -> str:
    """04 · 청약 신청자격 섹션 HTML 렌더링"""

    # ── 특별공급 카드들 ──
    sp_cards = ""
    for sp in data.eligibility_special:
        type_name = sp.get("type_name", "")
        quota     = sp.get("quota", "")
        reqs      = sp.get("requirements", [])
        quota_html = (
            f'<span style="font-size:11px;font-weight:600;background:{t["accent_light"]};'
            f'color:{t["accent"]};padding:2px 8px;border-radius:{t["radius_pill"]};'
            f'margin-left:6px;">{quota}</span>'
            if quota else ""
        )
        req_items = "".join(
            f'<li style="font-size:14px;color:{t["text2"]};line-height:1.7;'
            f'padding:2px 0;">{r}</li>'
            for r in reqs
        )
        sp_cards += (
            f'<div style="flex:1 1 calc(50% - 8px);min-width:200px;'
            f'background:{t["surface"]};border:1px solid {t["border"]};'
            f'border-radius:{t["radius_md"]};padding:16px 18px;">'
            f'<div style="font-size:14px;font-weight:800;color:{t["text"]};'
            f'margin-bottom:10px;">{type_name}{quota_html}</div>'
            f'<ul style="list-style:none;padding:0;margin:0;">{req_items}</ul>'
            f'</div>'
        )

    if sp_cards:
        special_block = (
            f'<div style="font-size:13px;font-weight:700;color:{t["accent"]};'
            f'letter-spacing:0.5px;margin-bottom:12px;">특별공급</div>'
            f'<div style="display:flex;flex-wrap:wrap;gap:10px;margin-bottom:28px;">'
            f'{sp_cards}</div>'
        )
    else:
        special_block = (
            f'<div style="background:{t["surface"]};border:1px solid {t["border"]};'
            f'border-radius:{t["radius_md"]};padding:16px 18px;margin-bottom:28px;'
            f'font-size:14px;color:{t["muted"]};">특별공급 자격 정보가 없습니다.</div>'
        )

    # ── 1순위 / 2순위 ──
    def _rank_block(label: str, items: list[str], color: str) -> str:
        if not items:
            items = ["-"]
        li_html = "".join(
            f'<li style="font-size:14px;color:{t["text2"]};line-height:1.8;'
            f'padding:3px 0;border-bottom:1px solid {t["border"]};">'
            f'<span style="color:{color};font-weight:700;margin-right:6px;">·</span>{r}</li>'
            for r in items
        )
        return (
            f'<div style="flex:1 1 calc(50% - 8px);min-width:200px;'
            f'background:{t["surface"]};border:1px solid {t["border"]};'
            f'border-top:3px solid {color};border-radius:{t["radius_md"]};'
            f'padding:16px 18px;">'
            f'<div style="font-size:14px;font-weight:800;color:{color};'
            f'margin-bottom:12px;">{label}</div>'
            f'<ul style="list-style:none;padding:0;margin:0;">{li_html}</ul>'
            f'</div>'
        )

    rank_blocks = (
        f'<div style="display:flex;flex-wrap:wrap;gap:10px;">'
        f'{_rank_block("1순위 자격", data.eligibility_rank1, t["accent"])}'
        f'{_rank_block("2순위 자격", data.eligibility_rank2, t["text2"])}'
        f'</div>'
    )

    notice = (
        f'<p style="font-size:13px;color:{t["muted"]};margin-top:16px;line-height:1.6;">'
        f'※ 자격 요건은 공고문 기준이며, 개인 상황에 따라 다를 수 있습니다. '
        f'반드시 공식 분양사 및 청약홈에서 최종 확인하세요.</p>'
    )

    return special_block + rank_blocks + notice


def _header_meta_rows(data: "PostData", text_color: str, sub_color: str) -> str:
    """헤더 하단 메타 정보 세로 배치. 빈 값 행 자동 숨김."""
    fields = [
        ("모집공고일", data.notice_date),
        ("특별공급", data.special_supply_date),
        ("일반공급(1순위)", data.rank1_date),
        ("일반공급(2순위)", data.rank2_date),
        ("주소", data.supply_location or data.location),
    ]
    rows = []
    for label, value in fields:
        if not value or value in ("-", "", "None", "null"):
            continue
        rows.append(
            f'<div style="margin-bottom:5px;">'
            f'<span style="color:{sub_color};font-size:13px;">{label}: </span>'
            f'<strong style="color:{text_color};font-size:14px;">{value}</strong>'
            f'</div>'
        )
    return "\n    ".join(rows)


def _apply_theme(html: str, t: dict) -> str:
    """{{T_*}} 토큰을 테마 딕셔너리 값으로 치환"""
    mapping = {
        "{{T_NAME}}":             t.get("name", ""),
        "{{T_DESC}}":             t.get("description", ""),
        "{{T_BG}}":               t["bg"],
        "{{T_SURFACE}}":          t["surface"],
        "{{T_SURFACE2}}":         t["surface2"],
        "{{T_BORDER}}":           t["border"],
        "{{T_TEXT}}":             t["text"],
        "{{T_TEXT2}}":            t["text2"],
        "{{T_MUTED}}":            t["muted"],
        "{{T_ACCENT}}":           t["accent"],
        "{{T_ACCENT_DARK}}":      t["accent_dark"],
        "{{T_ACCENT_LIGHT}}":     t["accent_light"],
        "{{T_HEADER_BG}}":        t["header_bg"],
        "{{T_HEADER_TEXT}}":      t["header_text"],
        "{{T_HEADER_SUB}}":       t["header_sub"],
        "{{T_Q_BG}}":             t["q_bg"],
        "{{T_Q_TEXT}}":           t["q_text"],
        "{{T_Q_BADGE_BG}}":       t["q_badge_bg"],
        "{{T_Q_BADGE_TEXT}}":     t["q_badge_text"],
        "{{T_A_BADGE_BG}}":       t["a_badge_bg"],
        "{{T_A_BADGE_TEXT}}":     t["a_badge_text"],
        "{{T_TABLE_HEAD}}":       t["table_head"],
        "{{T_TABLE_HEAD_T}}":     t["table_head_t"],
        "{{T_TABLE_STRIPE}}":     t["table_stripe"],
        "{{T_TAG_BG}}":           t["tag_bg"],
        "{{T_TAG_TEXT}}":         t["tag_text"],
        "{{T_DIVIDER}}":          t["divider"],
        "{{T_TIMELINE}}":         t["timeline"],
        "{{T_CARD1_BG}}":         t["card1_bg"],
        "{{T_CARD1_TEXT}}":       t["card1_text"],
        "{{T_CARD2_BG}}":         t["card2_bg"],
        "{{T_CARD2_TEXT}}":       t["card2_text"],
        "{{T_CARD3_BG}}":         t["card3_bg"],
        "{{T_CARD3_TEXT}}":       t["card3_text"],
        "{{T_CARD4_BG}}":         t["card4_bg"],
        "{{T_CARD4_TEXT}}":       t["card4_text"],
        "{{T_STEP1}}":            t["step1"],
        "{{T_STEP2}}":            t["step2"],
        "{{T_STEP3}}":            t["step3"],
        "{{T_RADIUS_SM}}":        t["radius_sm"],
        "{{T_RADIUS_MD}}":        t["radius_md"],
        "{{T_RADIUS_LG}}":        t["radius_lg"],
        "{{T_RADIUS_PILL}}":      t["radius_pill"],
        "{{T_SHADOW_SM}}":        t["shadow_sm"],
        "{{T_SHADOW_MD}}":        t["shadow_md"],
        "{{T_SHADOW_LG}}":        t["shadow_lg"],
        "{{T_DISCLAIMER_BG}}":    t["disclaimer_bg"],
        "{{T_DISCLAIMER_BORDER}}":t["disclaimer_border"],
    }
    for placeholder, value in mapping.items():
        html = html.replace(placeholder, value)
    return html


# ──────────────────────────────────────────────────
# 메인 렌더러
# ──────────────────────────────────────────────────

class BlogHTMLRenderer:
    def __init__(self, template_path: Path = TEMPLATE_PATH):
        self.template = template_path.read_text(encoding="utf-8")

    def render(self, data: PostData) -> str:
        t = get_theme(data.theme)
        html = self.template

        # Step 1: 테마 토큰 치환
        html = _apply_theme(html, t)

        # Step 2: 데이터 플레이스홀더 치환
        total_general = sum(u.general_units for u in data.unit_types)
        total_special = sum(u.special_units for u in data.unit_types)
        total_units   = total_general + total_special

        from regions import region_name_to_category
        supply_label   = _supply_label(data.supply_type, data.apt_name)
        region_label   = region_name_to_category(data.location)
        pill_r         = t["radius_pill"]

        replacements = {
            # 헤더 태그
            "{{SUPPLY_TYPE_TAG}}": _render_header_tag(supply_label, pill_r),
            "{{REGION_TAG}}":      _render_header_tag(region_label, pill_r),
            "{{HEADER_META_ROWS}}": _header_meta_rows(data, t["header_text"], t["header_sub"]),
            # 포스팅 메타
            "{{POST_TITLE}}":     data.post_title,
            "{{POST_SUBTITLE}}":  data.post_subtitle,
            "{{RANK1_DATE}}":     data.rank1_date,
            "{{LOCATION}}":       data.location,
            "{{READ_TIME}}":      str(data.read_time),
            # 내러티브
            "{{APT_INTRO}}":       data.apt_intro or f"{data.apt_name} 분양 정보를 안내해 드립니다.",
            "{{LOCATION_INTRO}}":  data.location_intro or f"{data.location} 입지를 살펴보겠습니다.",
            "{{FINANCIAL_INTRO}}": data.financial_intro or "자금 계획을 미리 세워두는 것이 중요합니다.",
            "{{QA_INTRO}}":        data.qa_intro or "자주 받는 질문에 답해드릴게요.",
            "{{UNIT_TYPE_DESC}}":  data.unit_type_desc or f"{data.apt_name}은 아래와 같은 타입으로 공급됩니다.",
            "{{SCHEDULE_DESC}}":   data.schedule_desc or "청약 일정을 미리 확인하고 준비하세요.",
            "{{TAX_DESC}}":        data.tax_desc or "취득·보유·양도 단계별로 발생하는 세금을 미리 파악해두세요.",
            # 단지 기본
            "{{APT_NAME}}":         data.apt_name,
            "{{SUPPLY_LOCATION}}":  data.supply_location,
            "{{NAVER_MAP_URL}}":    _naver_map_url(data.supply_location or data.location),
            "{{SUPPLY_SCALE}}":     data.supply_scale,
            "{{PRICE_RANGE}}":      data.price_range,
            "{{PRICE_RANGE_TYPED}}": _price_range_typed(data.unit_types, data.price_range),
            "{{TOTAL_UNITS}}":    f"{total_units:,}",
            "{{MOVE_IN_DATE}}":   data.move_in_date,
            "{{RESALE_RESTRICTION}}": data.resale_restriction,
            # 청약 일정
            "{{SPECIAL_SUPPLY_DATE}}": data.special_supply_date,
            "{{RANK2_DATE}}":     data.rank2_date,
            "{{WINNER_DATE}}":    data.winner_date,
            # 금융
            "{{LOAN_INFO}}":      data.loan_info,
            "{{CONTRACT_RATIO}}": data.contract_ratio,
            "{{CONTRACT_AMOUNT}}":data.contract_amount or "-",
            "{{MIDTERM_RATIO}}":  data.midterm_ratio,
            "{{MIDTERM_COUNT}}":  data.midterm_count,
            "{{BALANCE_RATIO}}":  data.balance_ratio,
            # 세금
            "{{ACQUISITION_TAX_RATE}}":   data.acquisition_tax_rate,
            "{{ACQUISITION_TAX_AMOUNT}}": data.acquisition_tax_amount,
            "{{PROPERTY_TAX_RATE}}":      data.property_tax_rate,
            "{{PROPERTY_TAX_AMOUNT}}":    data.property_tax_amount,
            "{{CAPITAL_GAINS_TAX_RATE}}": data.capital_gains_tax_rate,
            "{{CAPITAL_GAINS_TAX_AMOUNT}}": data.capital_gains_tax_amount,
            # 입지
            "{{SUBWAY_SCORE}}":   data.subway_score,
            "{{SUBWAY_DETAIL}}":  data.subway_detail,
            "{{SCHOOL_SCORE}}":   data.school_score,
            "{{SCHOOL_DETAIL}}":  data.school_detail,
            "{{LIFE_SCORE}}":     data.life_score,
            "{{LIFE_DETAIL}}":    data.life_detail,
            "{{MEDICAL_SCORE}}":  data.medical_score,
            "{{MEDICAL_DETAIL}}": data.medical_detail,
            # 테이블 집계
            "{{TOTAL_GENERAL}}":  f"{total_general:,}",
            "{{TOTAL_SPECIAL}}":  f"{total_special:,}",
            # 메타
            "{{SOURCE_DATE}}":    data.source_date,
            # 공고문 버튼
            "{{NOTICE_DOC_BTN}}": _notice_doc_btn(
                data.notice_url,
                is_lh="apply.lh.or.kr" in data.notice_url,
            ),
        }
        for k, v in replacements.items():
            html = html.replace(k, str(v) if v is not None else "")

        # Step 3: 타입별 행 생성
        html = html.replace(
            "<!-- {{UNIT_TYPE_ROWS}} -->",
            _render_unit_rows(data.unit_types, t),
        )
        html = html.replace(
            "<!-- {{UNIT_TYPE_ROWS_INTRO}} -->",
            _render_unit_rows_intro(data.unit_types),
        )

        # Step 5: Q&A 블록
        qa_html = "\n".join(
            _render_qa_block(qa, i, t)
            for i, qa in enumerate(data.qa_blocks)
        )
        html = html.replace("{{QA_BLOCKS}}", qa_html)

        # Step 5b: 청약 신청자격 섹션
        html = html.replace("{{ELIGIBILITY_SECTION}}", _render_eligibility(data, t))

        # Step 6: SEO 태그
        html = html.replace(
            "<!-- {{SEO_TAG_SPANS}} -->",
            _render_seo_tags(data.seo_tags, t),
        )

        # 미처리 플레이스홀더 확인
        remaining = set(re.findall(r"\{\{[A-Z_0-9]+\}\}", html))
        # 테마 토큰 미처리는 무시 (이미 처리됨), 데이터 토큰만 경고
        data_remaining = {r for r in remaining if not r.startswith("{{T_")}
        if data_remaining:
            print(f"  [경고] 미치환 플레이스홀더: {data_remaining}")

        return html


# ──────────────────────────────────────────────────
# 로컬 저장
# ──────────────────────────────────────────────────

def save_post(data: PostData, html: str, output_root: Path) -> Path:
    date_str = datetime.now().strftime("%Y-%m-%d")
    safe = re.sub(r"[^\w가-힣]", "_", data.apt_name)
    post_dir = output_root / "posts" / f"{date_str}_{safe}"
    post_dir.mkdir(parents=True, exist_ok=True)

    from config import SITE_URL
    from shared_ui import (
        FONT_LINK, FONT_FAMILY, PALETTE_CSS,
        PALETTE_INIT_JS, PALETTE_SWITCH_JS, shared_nav,
    )

    post_slug = f"{date_str}_{safe}"
    post_canonical = f"{SITE_URL}/posts/{post_slug}/post.html"
    desc = f"{data.apt_name} 청약 분양가·일정·입지·자격 한눈에 정리. {data.price_range}"[:120]
    nav_html = shared_nav("../../")

    full_html = f"""<!DOCTYPE html>
<html lang="ko" data-palette="A">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>정과장의 청약노트</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{post_canonical}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="정과장의 청약노트">
<meta property="og:title" content="{data.post_title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{post_canonical}">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="{data.post_title}">
<meta name="twitter:description" content="{desc}">
<meta name="robots" content="index, follow">
{FONT_LINK}
{PALETTE_INIT_JS}
<style>
{PALETTE_CSS}
body {{ font-family: {FONT_FAMILY}; margin: 0; padding: 0; background: var(--c-bg); }}
</style>
</head>
<body>
{nav_html}
<div style="max-width:740px;margin:0 auto;padding:32px 16px 80px;">
{html}
</div>
<script>
{PALETTE_SWITCH_JS}
</script>
</body>
</html>"""
    (post_dir / "post.html").write_text(full_html, encoding="utf-8")

    from regions import region_name_to_category
    region_category = region_name_to_category(data.location)

    meta = {
        "apt_name":        data.apt_name,
        "title":           data.post_title,
        "subtitle":        data.post_subtitle,
        "theme":           data.theme,
        "tags":            data.seo_tags,
        "location":        data.location,
        "region_category": region_category,
        "supply_type":          data.supply_type,
        "price_range":          data.price_range,
        "special_supply_date":  data.special_supply_date,
        "rank1_date":           data.rank1_date,
        "rank2_date":           data.rank2_date,
        "notice_date":          data.notice_date,
        "move_in_date":         data.move_in_date,
        "supply_location":      data.supply_location,
        "total_households":     data.total_households,
        "notice_url":           data.notice_url,
        "generated_at":    datetime.now().isoformat(),
        "naver_blog_guide": {
            "step1": "네이버 블로그 → 글쓰기",
            "step2": "스마트에디터 ONE → [HTML] 버튼",
            "step3": "post.html 전체 붙여넣기",
            "step4": "플레이스홀더 이미지를 건설사 제공 이미지로 교체",
            "step5": f"태그 입력: {', '.join(data.seo_tags[:10])}",
            "step6": "카테고리 설정 후 발행",
        },
    }
    import json
    (post_dir / "post_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"\n{'='*50}")
    print(f"✅ 포스팅 저장 완료: {post_dir}")
    print(f"   📄 HTML  : post.html ({len(html):,}자) | 테마: {data.theme}")
    print(f"   📋 메타  : post_meta.json")
    print(f"{'='*50}")
    print("\n📌 네이버 블로그 등록 방법:")
    for k, v in meta["naver_blog_guide"].items():
        print(f"   {k.upper()}: {v}")
    return post_dir
