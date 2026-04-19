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
    def _fmt(won_man: int) -> str:
        if won_man <= 0:
            return "-"
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
        avg = (self.price_min + self.price_max) / 2
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

    # Q&A
    qa_blocks: list[QABlock] = field(default_factory=list)

    # SEO
    seo_tags: list[str] = field(default_factory=list)

    # 이미지
    images: dict[str, ImageResult] = field(default_factory=dict)

    # 메타
    source_date: str = ""
    read_time: int = 7

    # 테마
    theme: str = "intercom"


# ──────────────────────────────────────────────────
# 렌더링 헬퍼
# ──────────────────────────────────────────────────

TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "blog_template.html"


def _price_range_typed(unit_types: list[UnitType], fallback: str) -> str:
    """최소 분양가(타입명) 줄바꿈 ~ 최대 분양가(타입명) 형식 반환"""
    valid = [ut for ut in unit_types if ut.price_min > 0]
    if not valid:
        return fallback
    cheapest = min(valid, key=lambda u: u.price_min)
    priciest = max(valid, key=lambda u: u.price_max)
    lo = f"{cheapest._fmt(cheapest.price_min)}({cheapest.type_name})"
    if cheapest is priciest and cheapest.price_min == cheapest.price_max:
        return lo
    hi = f"~ {priciest._fmt(priciest.price_max)}({priciest.type_name})"
    return f"{lo}<br>{hi}"


def _render_unit_rows_intro(unit_types: list[UnitType]) -> str:
    """단지 소개 섹션용 — 5열 (타입/전용/공급세대/분양가/3.3㎡당), 흰색 반투명 스타일"""
    rows = []
    for ut in unit_types:
        total = ut.general_units + ut.special_units
        rows.append(f"""
      <tr style="text-align: center; border-bottom: 1px solid rgba(255,255,255,0.15);">
        <td style="padding: 10px 10px; font-weight: 700; color: #fff; white-space: nowrap;">{ut.type_name}</td>
        <td style="padding: 10px 8px; color: rgba(255,255,255,0.85); letter-spacing: 0.025em;">{ut.area_sqm:.2f}</td>
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
        <td style="padding: 10px 8px; color: {t['text2']};">{ut.area_sqm:.2f}</td>
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

        replacements = {
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
            "{{CONTRACT_AMOUNT}}":data.contract_amount,
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

        # Step 4: 조감도 이미지 (플레이스홀더)
        hero_img = data.images.get("hero")
        html = html.replace(
            "{{HERO_IMAGE_HTML}}",
            render_image_html(hero_img, "margin-bottom:16px; border-radius:10px; overflow:hidden;")
            if hero_img else "",
        )

        # Step 5: Q&A 블록
        qa_html = "\n".join(
            _render_qa_block(qa, i, t)
            for i, qa in enumerate(data.qa_blocks)
        )
        html = html.replace("{{QA_BLOCKS}}", qa_html)

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

    (post_dir / "post.html").write_text(html, encoding="utf-8")

    meta = {
        "apt_name":    data.apt_name,
        "title":       data.post_title,
        "subtitle":    data.post_subtitle,
        "theme":       data.theme,
        "tags":        data.seo_tags,
        "location":    data.location,
        "rank1_date":  data.rank1_date,
        "generated_at": datetime.now().isoformat(),
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
