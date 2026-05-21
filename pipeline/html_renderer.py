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
from html import escape
from pathlib import Path
from datetime import date, datetime
from dataclasses import dataclass, field
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))
from image_finder import ImageResult, render_image_html, build_credit_html
from themes import get_theme, THEMES


FINANCIAL_INTRO_TEXT = (
    "입주자모집공고문에 명시된 납부 일정에 맞춰 대금을 입금해야 당첨 지위가 유지됩니다. "
    "각 회차별 날짜와 납입 금액을 꼼꼼히 확인하고, 내가 가진 자금과 대출이 실행되는 시점이 서로 어긋나지 않는지 미리 체크해 보세요. "
    "예상치 못한 자금 공백이 생기지 않도록 구체적인 계획을 세우는 것이 무엇보다 중요합니다."
)
CONTRACT_DESC_TEXT = (
    "계약금은 당첨된 권리를 확정 짓는 '확약금'입니다. "
    "아파트 담보대출이 불가능한 단계이고 단기간에 납부해야 하므로, 반드시 본인이 즉시 인출할 수 있는 현금으로 준비해야 합니다. "
    "계약금 납부가 완료되어야만 향후 중도금 대출 신청이나 분양권 승계 같은 후속 절차를 진행할 수 있으니 가장 우선적으로 확보하십시오."
)
MIDTERM_DESC_TEXT = (
    "중도금은 전체 분양대금 중 가장 큰 비중을 차지하며 대개 6회에 걸쳐 분납됩니다. "
    "대부분 집단대출을 통해 조달하지만, 개인의 대출 규제 지역 여부나 DSR(총부채원리금상환비율) 한도에 따라 대출 실행 가능 범위가 달라질 수 있습니다. "
    "무이자와 이자후불제 등 금융 조건에 따른 실질 체감 비용을 사전에 반드시 계산해 보시기 바랍니다."
)
BALANCE_DESC_TEXT = (
    "최종 입주 시점에 납부하는 잔금은 '기존 중도금 대출의 상환'과 '잔금 대출(담보대출)로의 전환'이 동시에 일어나는 핵심 구간입니다. "
    "입주 시점의 KB시세나 감정평가액에 따라 대출 한도가 재산정되므로, 금리 변동성 및 개인의 신용도를 고려한 입체적인 자금 조달 시나리오를 미리 수립해 두는 것이 안전합니다."
)
QA_INTRO_TEXT = "공고문에서 많이 궁금해하시는 부분에 대해서 쉽게 정리해드릴게요."
EXPIRED_HEADER_BG = "linear-gradient(135deg, #6F746F 0%, #555B56 60%, #3F4540 100%)"


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
    is_hot_zone: str = ""        # 투기과열지구 여부 (legacy, IS_HOT_ZONE 토큰으로도 사용)
    regulated_zone: str = ""     # 규제지역 여부 (e.g. "투기과열지구, 청약과열지역", "비규제지역")
    readmission_limit: str = ""  # 재당첨 제한 (e.g. "10년", "없음")
    live_requirement: str = ""   # 거주의무기간 (있음/없음/공고문 확인 필요)
    price_cap: str = ""          # 분양가 상한제 (적용/미적용)
    price_range: str = ""

    # 유닛 타입
    unit_types: list[UnitType] = field(default_factory=list)

    # 청약 일정
    notice_date: str = ""
    special_supply_date: str = "-"
    rank1_date: str = "-"
    rank2_date: str = "-"
    winner_date: str = "-"
    move_in_date: str = "-"

    # 금융
    loan_info: str = ""
    resale_restriction: str = ""
    contract_ratio: str = "0"
    contract_amount: str = ""
    midterm_ratio: str = "0"
    midterm_count: str = ""
    midterm_fixed_amount: str = ""
    balance_ratio: str = "0"

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
    feature_score: str = "★★★☆☆"
    feature_detail: str = ""
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

_DISPLAY_EMPTY_VALUES = {"", "-", "None", "null", "해당없음", "공고문 확인 필요"}


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
        f'<span style="display:inline-flex;align-items:center;justify-content:center;'
        f' padding:5px 14px; border-radius:{radius};'
        f' border:1px solid rgba(255,255,255,0.28); background:rgba(255,255,255,0.18);'
        f' color:#FFFFFF; font-size: 0.75rem; font-weight:700; letter-spacing: 0.0625rem;'
        f' line-height:1;">{label}</span>'
    )


def _stringify(value: object) -> str:
    return str(value).strip() if value is not None else ""


def _display_value(value: object, default: str = "미기재") -> str:
    text = _stringify(value)
    return default if text in _DISPLAY_EMPTY_VALUES else text


def _display_date(value: object) -> str:
    return _display_value(value, default="")


def _has_schedule(value: object) -> bool:
    return _stringify(value) not in _DISPLAY_EMPTY_VALUES


def _parse_date(value: object) -> date | None:
    text = _stringify(value)
    if text in _DISPLAY_EMPTY_VALUES:
        return None
    text = text.split(" ~ ", 1)[0].strip()
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


try:
    from seo_policy import NOINDEX_AFTER_DAYS, is_noindex_eligible as _is_noindex_eligible
except ImportError:
    from pipeline.seo_policy import NOINDEX_AFTER_DAYS, is_noindex_eligible as _is_noindex_eligible

_ = NOINDEX_AFTER_DAYS  # 모듈 사용자가 import 할 수 있도록 re-export 의도 보존


def _is_expired_post(data: "PostData") -> bool:
    winner = _parse_date(data.winner_date)
    return bool(winner and winner < date.today())


def _safe_int(value: object) -> int:
    try:
        return int(str(value).strip() or 0)
    except Exception:
        return 0


def _parse_price_manwon(value: object) -> int:
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(value)

    text = str(value).strip().replace(",", "")
    if not text or text in {"-", "null", "None"}:
        return 0
    if text.isdigit():
        return int(text)

    total = 0
    m = re.search(r"(\d+(?:\.\d+)?)\s*억", text)
    if m:
        total += int(float(m.group(1)) * 10000)
    m = re.search(r"(\d+(?:\.\d+)?)\s*천\s*만원", text)
    if m:
        total += int(float(m.group(1)) * 1000)
    m = re.search(r"(\d+(?:\.\d+)?)\s*백\s*만원", text)
    if m:
        total += int(float(m.group(1)) * 100)
    m = re.search(r"(\d+(?:\.\d+)?)\s*십\s*만원", text)
    if m:
        total += int(float(m.group(1)) * 10)
    if "만원" in text and total == 0:
        m = re.search(r"(\d+(?:\.\d+)?)\s*만원", text)
        if m:
            total += int(float(m.group(1)))
    return total


def _canonical_subtitle(post_subtitle: str, supply_location: str, location: str) -> str:
    return _stringify(supply_location) or _stringify(location) or _stringify(post_subtitle)


def _build_share_text(apt_name: str, region: str, notice_date: str, price_range: str) -> str:
    """앱과 동일한 멀티라인 카드형 공유 텍스트.

    동기화 원본: mobile-app/src/App.tsx buildShareText()
    """
    lines = [f"[{_stringify(apt_name)}] 청약 정보 한눈에 보기", ""]
    region_clean = _stringify(region)
    if region_clean:
        lines.append(f"📍 {region_clean}")
    notice_clean = _stringify(notice_date)
    if notice_clean:
        lines.append(f"🗓 모집공고일 {notice_clean}")
    price_clean = _stringify(price_range)
    if price_clean:
        lines.append(f"💰 {price_clean}")
    if len(lines) > 2:
        lines.append("")
    lines.extend([
        "🏠 분양가·일정·입지·자격 핵심 정리",
        "📋 청약 전 꼭 확인해야 할 정보 모음",
        "✨ 정과장의 청약노트",
    ])
    return "\n".join(lines)


def _canonical_supply_scale(supply_scale: str, total_households: str, unit_types: list["UnitType"]) -> str:
    scale = _stringify(supply_scale)
    if scale:
        return scale
    households = _stringify(total_households)
    if households:
        households_clean = households.replace(",", "")
        if households_clean.isdigit():
            return f"총 {int(households_clean):,}세대"
        return households
    total_units = sum(max(0, _safe_int(ut.general_units)) + max(0, _safe_int(ut.special_units)) for ut in unit_types)
    return f"총 {total_units:,}세대" if total_units > 0 else ""


def _format_date_range(start: object, end: object) -> str:
    start_s = _display_date(start)
    end_s = _display_date(end)
    if start_s in {"-", ""} and end_s in {"-", ""}:
        return "-"
    if end_s in {"-", ""}:
        return start_s
    if start_s in {"-", ""}:
        return end_s
    if start_s == end_s:
        return start_s
    return f"{start_s} ~ {end_s}"


def _rank_area_range(doc, local_start_key: str, etc_start_key: str, fallback: object) -> str:
    local_date = _stringify(getattr(doc, local_start_key, "")) if doc is not None else ""
    etc_date = _stringify(getattr(doc, etc_start_key, "")) if doc is not None else ""
    formatted = _format_date_range(local_date, etc_date)
    if formatted != "-":
        return formatted
    return _display_date(fallback)


def _clean_unit_type_name(type_name: str) -> str:
    text = _stringify(type_name).replace("타입", "").strip()
    m = re.match(r"0*(\d{2,3})(?:\.\d+)?\s*([A-Z])?$", text, re.IGNORECASE)
    if m:
        return f"{int(m.group(1))}{(m.group(2) or '').upper()}"
    m = re.match(r"0*(\d{2,3})(?:\.\d+)?\s*([A-Z])", text, re.IGNORECASE)
    if m:
        return f"{int(m.group(1))}{m.group(2).upper()}"
    return text


def _unit_feature_sentence(unit_types: list["UnitType"]) -> str:
    type_names = []
    for ut in unit_types:
        cleaned = _clean_unit_type_name(_stringify(ut.type_name))
        if cleaned and cleaned not in type_names:
            type_names.append(cleaned)
    if type_names:
        preview = ", ".join(type_names[:8])
        suffix = " 등" if len(type_names) > 8 else ""
        return f"단지 특징으로는 {preview}{suffix} 타입이 공급되는 점을 확인할 수 있습니다."
    return "단지 특징은 공식 공급 정보와 타입별 세부 조건을 기준으로 확인하는 것이 좋습니다."


def _fact_based_apt_intro(
    *,
    apt_name: str,
    supply_location: str,
    supply_units: int,
    unit_types: list["UnitType"],
) -> str:
    units = f"총 {supply_units:,}세대" if supply_units > 0 else "공고문 기준 공급세대"
    location = _stringify(supply_location)
    feature = _unit_feature_sentence(unit_types)
    location_text = f" 공급 위치는 {location}입니다." if location else ""
    return (
        "안녕하세요. 복잡한 청약 공고문을 쉽게 정리해 드리는 정과장입니다. "
        f"오늘은 {units}가 공급되는 <strong>{apt_name}</strong>를 소개해드릴게요."
        f"{location_text} {feature}"
    )


def _normalize_contract_amount(contract_amount: str, contract_ratio: str, unit_types: list["UnitType"]) -> str:
    amount = _stringify(contract_amount)
    if amount and amount not in {"-", "None", "null"}:
        return amount
    return ""


def _is_zero_ratio(value: object) -> bool:
    text = _stringify(value).strip()
    return text in {"", "0", "0%", "0.0", "0.0%"}


def _parse_ratio(value: object) -> int | None:
    text = _stringify(value).strip().replace("%", "")
    if not text:
        return None
    try:
        ratio = float(text)
    except ValueError:
        return None
    if not ratio.is_integer():
        return None
    return int(ratio)


def _finance_uses_non_ratio_display(data: "PostData") -> bool:
    if data.contract_amount or data.midterm_fixed_amount:
        return True
    ratios = [
        _parse_ratio(data.contract_ratio),
        _parse_ratio(data.midterm_ratio),
        _parse_ratio(data.balance_ratio),
    ]
    if any(ratio is None for ratio in ratios):
        return True
    return sum(ratios) != 100


def _remove_no_midterm_from_ratio_bar(html: str) -> str:
    html = re.sub(
        r'\s*<div style="\s*background: #[0-9A-Fa-f]{6};\s*flex: 1;\s*display: flex; align-items: center; justify-content: center;\s*color: #fff; font-size: 1rem; font-weight: 800;\s*">\s*0%\s*</div>',
        "",
        html,
        flags=re.S,
    )
    return re.sub(
        r'\s*<span style="font-size: 0.875rem; letter-spacing: 0.025em; color: #[0-9A-Fa-f]{6}; font-weight: 700;">■ 중도금 (?:0%|없음)</span>',
        "",
        html,
    )


def _remove_no_midterm_timeline_step(html: str) -> str:
    start = html.find("<!-- 2. 중도금 -->")
    end = html.find("<!-- 3. 잔금 -->", start)
    if start != -1 and end != -1:
        html = html[:start] + html[end:]
    html = html.replace("<!-- 3. 잔금 -->", "<!-- 2. 잔금 -->", 1)
    return re.sub(
        r'(<div style="\s*position: absolute; left: -36px; top: 2px;\s*width: 26px; height: 26px;\s*background: #[0-9A-Fa-f]{6}; color: #fff; border-radius: 50%;\s*display: flex; align-items: center; justify-content: center;\s*font-size: 0.8125rem; font-weight: 800;\s*">)3(</div>\s*<div style="font-size: 1.125rem; font-weight: 800; color: #[0-9A-Fa-f]{6}; margin-bottom: 10px;">잔금)',
        r"\g<1>2\2",
        html,
        flags=re.S,
    )


def _remove_finance_ratio_bar(html: str) -> str:
    return re.sub(
        r"\s*<!-- FINANCE_RATIO_BAR_START -->.*?<!-- FINANCE_RATIO_BAR_END -->",
        "",
        html,
        flags=re.S,
    )


def remove_special_finance_ratio_bar_from_html(html: str) -> str:
    """Remove existing ratio bars from generated special-case finance sections."""
    html = _remove_finance_ratio_bar(html)
    html = re.sub(
        r'\s*<!-- 납부 비율 시각화 바 \(CSS 차트\) -->\s*'
        r'<div style="margin-bottom: 32px;">\s*'
        r'<div style="font-size: 0.9375rem; font-weight: 700; color: var\(--c-dark, #[0-9A-Fa-f]{6}\); margin-bottom: 12px;">분양가 납부 비율\(%\)</div>'
        r'.*?</div>\s*</div>',
        "",
        html,
        flags=re.S,
    )
    return html


def adapt_no_midterm_finance_html(html: str) -> str:
    html = _remove_no_midterm_from_ratio_bar(html)
    html = _remove_no_midterm_timeline_step(html)
    html = re.sub(
        r'\s*<p style="font-size: 1.0625rem; font-weight: 800; color: var\(--c-dark, #[0-9A-Fa-f]{6}\); margin: 0;"></p>',
        "",
        html,
    )
    return re.sub(
        r"기본 구조만 보면 계약금 ([0-9.]+)%, 중도금 [^,<>]+, 잔금 ([0-9.]+)% 순서입니다\.",
        r"기본 구조만 보면 계약금 \1%, 중도금 없이 잔금 \2%를 납부하는 흐름입니다.",
        html,
    )

    return re.sub(
        r'\s*<div style="display: flex; gap: 20px; margin-top: 10px; flex-wrap: wrap;">'
        r'.*?</div>\s*</div>(?=\s*<!-- 납부 단계 수직 타임라인 -->)',
        "",
        html,
        flags=re.S,
    )


def build_post_data(
    *,
    facts: dict,
    content: dict,
    doc=None,
    theme: str,
    supply_type: str,
    notice_url: str,
    api_is_hot_zone: str = "",
) -> PostData:
    """상세페이지 기준 샘플 구조에 맞는 PostData를 단일 규칙으로 조립한다."""
    unit_types = [
        UnitType(
            type_name=ut.get("type_name", ""),
            area_sqm=float(ut.get("area_sqm", 0) or 0),
            general_units=_safe_int(ut.get("general_units", 0)),
            special_units=_safe_int(ut.get("special_units", 0)),
            price_min=_parse_price_manwon(ut.get("price_min", 0)),
            price_max=_parse_price_manwon(ut.get("price_max", 0)),
        )
        for ut in facts.get("unit_types", [])
    ]

    qa_blocks = [
        QABlock(question=qa.get("question", ""), answer=qa.get("answer", ""))
        for qa in content.get("qa_blocks", [])
    ]

    apt_name = _stringify(facts.get("apt_name")) or _stringify(getattr(doc, "apt_name", ""))
    location = _stringify(facts.get("location"))
    supply_location = _stringify(facts.get("supply_location")) or _stringify(getattr(doc, "supply_address", ""))
    total_households = _stringify(
        facts.get("total_households")
        or getattr(doc, "total_units", "")
        or facts.get("supply_total_units")
        or ""
    )
    supply_scale = _canonical_supply_scale(_stringify(facts.get("supply_scale")), total_households, unit_types)
    price_range = _stringify(facts.get("price_range"))
    contract_ratio = _stringify(facts.get("contract_ratio") or "0")
    midterm_ratio = _stringify(facts.get("midterm_ratio") or "0")
    midterm_count = _stringify(facts.get("midterm_count") or "")
    balance_ratio = _stringify(facts.get("balance_ratio") or "0")
    midterm_fixed_amount = _stringify(facts.get("midterm_fixed_amount") or "")
    if midterm_ratio == "0":
        midterm_count = ""
    loan_info = MIDTERM_DESC_TEXT
    if midterm_fixed_amount:
        loan_info = MIDTERM_DESC_TEXT
    elif midterm_ratio == "0":
        loan_info = MIDTERM_DESC_TEXT
    supply_units = sum(max(0, _safe_int(ut.general_units)) + max(0, _safe_int(ut.special_units)) for ut in unit_types)
    notice_date = _display_date(facts.get("notice_date"))
    special_supply_date = _display_date(facts.get("special_supply_date"))
    rank1_date = _rank_area_range(doc, "rank1_local_start", "rank1_etc_start", facts.get("rank1_date"))
    rank2_date = _rank_area_range(doc, "rank2_local_start", "rank2_etc_start", facts.get("rank2_date"))

    return PostData(
        apt_name=apt_name,
        post_title=content.get("post_title", f"{apt_name} 청약 완벽 분석"),
        post_subtitle=_canonical_subtitle(
            _stringify(content.get("post_subtitle", "")),
            supply_location,
            location,
        ),
        location=location,
        supply_location=supply_location,
        supply_scale=supply_scale,
        total_households=total_households,
        is_hot_zone=_display_value(_stringify(facts.get("is_hot_zone")) or api_is_hot_zone, default="해당없음"),
        regulated_zone=_display_value(facts.get("regulated_zone"), default="미기재"),
        readmission_limit=_display_value(facts.get("readmission_limit"), default="미기재"),
        live_requirement=_display_value(facts.get("live_requirement"), default="미기재"),
        price_cap=_display_value(facts.get("price_cap"), default="미기재"),
        price_range=price_range,
        unit_types=unit_types,
        notice_date=notice_date,
        special_supply_date=special_supply_date,
        rank1_date=rank1_date,
        rank2_date=rank2_date,
        winner_date=_display_date(facts.get("winner_date")),
        move_in_date=_display_value(facts.get("move_in_date"), default="미정"),
        loan_info=loan_info,
        resale_restriction=_display_value(facts.get("resale_restriction"), default="미기재"),
        contract_ratio=contract_ratio,
        contract_amount=_normalize_contract_amount(_stringify(facts.get("contract_amount")), contract_ratio, unit_types),
        midterm_ratio=midterm_ratio,
        midterm_count=midterm_count,
        midterm_fixed_amount=midterm_fixed_amount,
        balance_ratio=balance_ratio,
        acquisition_tax_rate=_display_value(facts.get("acquisition_tax_rate"), default="1~3%"),
        acquisition_tax_amount="-",
        property_tax_rate="과세표준 × 0.1~0.4%",
        property_tax_amount="-",
        capital_gains_tax_rate="1주택 2년 보유 시 비과세 가능",
        capital_gains_tax_amount="-",
        subway_score=_stringify(content.get("subway_score")) or "★★★☆☆",
        subway_detail=_stringify(content.get("subway_detail")),
        school_score=_stringify(content.get("school_score")) or "★★★☆☆",
        school_detail=_stringify(content.get("school_detail")),
        feature_score=_stringify(content.get("feature_score")) or "★★★☆☆",
        feature_detail=_stringify(content.get("feature_detail") or content.get("life_detail")),
        medical_score=_stringify(content.get("medical_score")) or "★★★☆☆",
        medical_detail=_stringify(content.get("medical_detail")),
        apt_intro=_fact_based_apt_intro(
            apt_name=apt_name,
            supply_location=supply_location,
            supply_units=supply_units,
            unit_types=unit_types,
        ),
        location_intro=_stringify(content.get("location_intro")) or f"{location or apt_name} 입지를 살펴보겠습니다.",
        financial_intro=FINANCIAL_INTRO_TEXT,
        qa_intro=QA_INTRO_TEXT,
        unit_type_desc=_stringify(content.get("unit_type_desc")) or f"{apt_name}은 아래와 같은 타입으로 공급됩니다.",
        schedule_desc=_stringify(content.get("schedule_desc")) or "청약 일정을 미리 확인하고 준비하세요.",
        tax_desc=_stringify(content.get("tax_desc")) or "취득·보유·양도 단계별로 발생하는 세금을 미리 파악해두세요.",
        eligibility_special=(facts.get("eligibility_special") or []) if _has_schedule(special_supply_date) else [],
        eligibility_rank1=facts.get("eligibility_rank1") or [],
        eligibility_rank2=(facts.get("eligibility_rank2") or []) if _has_schedule(rank2_date) else [],
        qa_blocks=qa_blocks,
        seo_tags=content.get("seo_tags", [apt_name, "청약", "분양"]),
        images={},
        source_date=notice_date,
        read_time=max(6, len(str(content)) // 450),
        theme=theme,
        supply_type=supply_type or _stringify(getattr(doc, "supply_type", "")),
        notice_url=notice_url or _stringify(getattr(doc, "notice_url", "")),
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
        f'font-size: 0.9375rem;font-weight:700;'
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
        clean_type = _clean_unit_type_name(type_name)
        return (
            f'{prefix}<span style="font-size: 1.375rem;font-weight:800;">{price_str}</span>'
            f'<span style="font-size: 1rem;font-weight:600;opacity:0.85;">({clean_type})</span>'
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
        type_name = _clean_unit_type_name(ut.type_name)
        rows.append(f"""
      <tr style="text-align: center; border-bottom: 1px solid rgba(255,255,255,0.15);">
        <td style="padding: 10px 10px; font-weight: 700; color: #fff; white-space: nowrap;">{type_name}</td>
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
        type_name = _clean_unit_type_name(ut.type_name)
        rows.append(f"""
      <tr style="text-align: center; border-bottom: 1px solid {t['border']}; {stripe}">
        <td style="padding: 10px 8px; font-weight: 700; color: {t['accent']};">{type_name}</td>
        <td style="padding: 10px 8px; color: {t['text2']};">{round(ut.area_sqm, 1):.1f}</td>
        <td style="padding: 10px 8px; color: {t['text']};">{ut.general_units:,}세대</td>
        <td style="padding: 10px 8px; color: {t['text']};">{ut.special_units:,}세대</td>
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
        <p style="font-size: 0.6875rem; color: {t['muted']}; margin: 4px 8px; font-style: italic;">📷 {credit}</p>
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
        font-weight: 700; font-size: 0.75rem;
        padding: 2px 9px; border-radius: {t['radius_sm']};
        flex-shrink: 0; margin-top: 1px;
      ">Q</span>
      <span style="
        color: {t['q_text']}; font-size: 1rem;
        font-weight: 700; line-height: 1.6; word-break: keep-all;
      ">{qa.question}</span>
    </div>
    <!-- 답변 -->
    <div style="padding: 16px 18px; background: {t['bg']};">
      <div style="display: flex; align-items: flex-start; gap: 10px;">
        <span style="
          background: {t['a_badge_bg']}; color: {t['a_badge_text']};
          font-weight: 700; font-size: 0.75rem;
          padding: 2px 9px; border-radius: {t['radius_sm']}; flex-shrink: 0;
        ">A</span>
        <div style="color: {t['text']}; font-size: 1rem; line-height: 1.6; word-break: keep-all;">{qa.answer}</div>
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
            f'font-size: 0.6875rem; padding:4px 10px; border-radius:{t["radius_pill"]}; '
            f'font-weight:600; display:inline-block;">#{clean}</span>'
        )
    return "\n  ".join(spans)


def _render_eligibility(data: "PostData", t: dict) -> str:
    """04 · 청약 신청자격 섹션 HTML 렌더링"""
    card_color = t["text2"]

    # ── 특별공급 카드들 ──
    sp_cards = ""
    for sp in data.eligibility_special:
        type_name = sp.get("type_name", "")
        reqs      = sp.get("requirements", [])
        req_items = "".join(
            f'<li style="font-size: 0.875rem;color:{t["text2"]};line-height:1.8;'
            f'padding:3px 0;border-bottom:1px solid {t["border"]};">'
            f'<span style="color:{card_color};font-weight:700;margin-right:6px;">·</span>{r}</li>'
            for r in reqs
        )
        sp_cards += (
            f'<div style="flex:1 1 calc(50% - 8px);min-width:200px;'
            f'background:{t["surface"]};border:1px solid {t["border"]};'
            f'border-top:3px solid {card_color};border-radius:{t["radius_md"]};'
            f'padding:16px 18px;">'
            f'<div style="font-size: 0.875rem;font-weight:800;color:{card_color};'
            f'margin-bottom:10px;">{type_name}</div>'
            f'<ul style="list-style:none;padding:0;margin:0;">{req_items}</ul>'
            f'</div>'
        )

    if sp_cards:
        special_block = (
            f'<div style="font-size: 0.8125rem;font-weight:700;color:{t["accent"]};'
            f'letter-spacing: 0.0312rem;margin-bottom:12px;">특별공급</div>'
            f'<div style="display:flex;flex-wrap:wrap;gap:10px;margin-bottom:28px;">'
            f'{sp_cards}</div>'
        )
    else:
        special_block = (
            f'<div style="background:{t["surface"]};border:1px solid {t["border"]};'
            f'border-radius:{t["radius_md"]};padding:16px 18px;margin-bottom:28px;'
            f'font-size: 0.875rem;color:{t["muted"]};">특별공급 관련 정보가 없습니다.  '
            f'입주자모집공고문을 확인하세요.</div>'
        )

    # ── 1순위 / 2순위 ──
    def _rank_block(label: str, items: list[str]) -> str:
        if not items:
            items = [f"{label.replace(' 자격', '')} 일반공급 관련  정보가 없습니다.  입주자모집공고문을 확인하세요."]
        li_html = "".join(
            f'<li style="font-size: 0.875rem;color:{t["text2"]};line-height:1.8;'
            f'padding:3px 0;border-bottom:1px solid {t["border"]};">'
            f'<span style="color:{card_color};font-weight:700;margin-right:6px;">·</span>{r}</li>'
            for r in items
        )
        return (
            f'<div style="flex:1 1 calc(50% - 8px);min-width:200px;'
            f'background:{t["surface"]};border:1px solid {t["border"]};'
            f'border-top:3px solid {card_color};border-radius:{t["radius_md"]};'
            f'padding:16px 18px;">'
            f'<div style="font-size: 0.875rem;font-weight:800;color:{card_color};'
            f'margin-bottom:12px;">{label}</div>'
            f'<ul style="list-style:none;padding:0;margin:0;">{li_html}</ul>'
            f'</div>'
        )

    rank_blocks = (
        f'<div style="font-size: 0.8125rem;font-weight:700;color:{t["accent"]};'
        f'letter-spacing: 0.0312rem;margin-bottom:12px;">일반공급</div>'
        f'<div style="display:flex;flex-wrap:wrap;gap:10px;">'
        f'{_rank_block("1순위 자격", data.eligibility_rank1)}'
        f'{_rank_block("2순위 자격", data.eligibility_rank2)}'
        f'</div>'
    )

    notice = (
        f'<p style="font-size: 0.8125rem;color:{t["muted"]};margin-top:16px;line-height:1.6;">'
        f'※ 자격 요건은 공고문 기준이며, 개인 상황에 따라 다를 수 있습니다. '
        f'반드시 공식 분양사 및 청약홈에서 최종 확인하세요.</p>'
    )

    return special_block + rank_blocks + notice


def _render_schedule_timeline(data: "PostData", t: dict) -> str:
    """Render only schedule steps that have a usable date, with sequential step numbers."""
    items = [
        ("NOTICE", "모집공고일", data.notice_date),
        ("SPECIAL", "특별공급", data.special_supply_date),
        ("1ST PRIORITY", "일반공급 1순위", data.rank1_date),
        ("2ND PRIORITY", "일반공급 2순위", data.rank2_date),
        ("WINNER", "당첨자 발표", data.winner_date),
    ]
    visible = [
        (kicker, label, _stringify(value))
        for kicker, label, value in items
        if _has_schedule(value)
    ]
    if not visible:
        visible = [("NOTICE", "모집공고일", "공고문 확인")]

    rows: list[str] = []
    last_index = len(visible) - 1
    for index, (kicker, label, value) in enumerate(visible, start=1):
        margin = "" if index - 1 == last_index else " margin-bottom: 6px;"
        rows.append(
            f"""
    <div style="display: flex; gap: 18px; align-items: flex-start;{margin}">
      <div style="
        flex-shrink: 0; width: 38px; height: 38px;
        background: var(--c-primary, {t["accent"]}); color: #fff; border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        font-size: 0.9375rem; font-weight: 800;
      ">{index}</div>
      <div style="flex: 1; padding-top: 5px;">
        <div style="font-size: 0.75rem; color: {t["muted"]}; font-weight: 700; letter-spacing: 0.05rem; margin-bottom: 4px;">{kicker}</div>
        <div style="font-size: 1.0625rem; font-weight: 700; color: var(--c-dark, {t["text"]}); margin-bottom: 3px;">{label}</div>
        <div style="font-size: 1.0625rem; color: var(--c-primary, {t["accent"]}); font-weight: 800;">{value}</div>
      </div>
    </div>""".rstrip()
        )
        if index - 1 != last_index:
            rows.append(
                f'<div style="margin-left: 19px; height: 22px; width: 2px; background: {t["border"]};"></div>'
            )

    return (
        f'<div style="background: {t["surface"]}; border: 1px solid {t["border"]};'
        f' border-radius: {t["radius_lg"]}; padding: 26px 22px; margin-bottom: 36px;">'
        + "\n".join(rows)
        + "\n  </div>"
    )


def _header_meta_rows(data: "PostData", text_color: str, sub_color: str) -> str:
    """헤더 하단 메타 정보 세로 배치. 빈 값 행 자동 숨김."""
    def _hero_date(value: str) -> str:
        text = _stringify(value)
        if " ~ " not in text:
            return text
        start, end = [part.strip() for part in text.split(" ~ ", 1)]
        return start if start and start == end else text

    fields = [
        ("모집공고", data.notice_date),
        ("특별공급", data.special_supply_date),
        ("일반공급 1순위", _hero_date(data.rank1_date)),
        ("일반공급 2순위", _hero_date(data.rank2_date)),
    ]
    rows = []
    for label, value in fields:
        if not value or value in ("-", "", "None", "null"):
            continue
        rows.append(
            f'<div style="margin-bottom:5px;">'
            f'<span style="color:{sub_color};font-size: 0.8125rem;">{label}: </span>'
            f'<strong style="color:{text_color};font-size: 0.875rem;">{value}</strong>'
            f'</div>'
        )
    if not rows:
        return ""
    return (
        f'<div style="margin-top:22px;padding-top:22px;">'
        + "\n    ".join(rows)
        + "</div>"
    )


def _header_subtitle(data: "PostData") -> str:
    """상세페이지 히어로 서브타이틀은 주소를 우선 노출."""
    return _canonical_subtitle(data.post_subtitle, data.supply_location, data.location)


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
        if _is_expired_post(data):
            html = html.replace(t["header_bg"], EXPIRED_HEADER_BG)

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
            "{{SCHEDULE_TIMELINE}}": _render_schedule_timeline(data, t),
            # 포스팅 메타
            "{{POST_TITLE}}":     data.post_title,
            "{{POST_SUBTITLE}}":  _header_subtitle(data),
            "{{RANK1_DATE}}":     data.rank1_date,
            "{{LOCATION}}":       data.location,
            "{{READ_TIME}}":      str(data.read_time),
            # 내러티브
            "{{APT_INTRO}}":       data.apt_intro or f"{data.apt_name} 분양 정보를 안내해 드립니다.",
            "{{LOCATION_INTRO}}":  data.location_intro or f"{data.location} 입지를 살펴보겠습니다.",
            "{{FINANCIAL_INTRO}}": data.financial_intro or FINANCIAL_INTRO_TEXT,
            "{{QA_INTRO}}":        data.qa_intro or QA_INTRO_TEXT,
            "{{UNIT_TYPE_DESC}}":  data.unit_type_desc or f"{data.apt_name}은 아래와 같은 타입으로 공급됩니다.",
            "{{SCHEDULE_DESC}}":   data.schedule_desc or "청약 일정을 미리 확인하고 준비하세요.",
            "{{TAX_DESC}}":        data.tax_desc or "취득·보유·양도 단계별로 발생하는 세금을 미리 파악해두세요.",
            # 단지 기본
            "{{APT_NAME}}":         data.apt_name,
            "{{SUPPLY_LOCATION}}":  data.supply_location,
            "{{NAVER_MAP_URL}}":    _naver_map_url(data.supply_location or data.location),
            "{{SUPPLY_SCALE_BLOCK}}": (
                f'<div style="font-size: 0.875rem; letter-spacing: 0.025em; color: var(--c-mid, {t["text2"]}); margin-bottom: 10px;">'
                f'{data.supply_scale}</div>'
                if _stringify(data.supply_scale) else ""
            ),
            "{{PRICE_RANGE}}":      data.price_range,
            "{{PRICE_RANGE_TYPED}}": _price_range_typed(data.unit_types, data.price_range),
            "{{TOTAL_UNITS}}":    f"{total_units:,}",
            "{{MOVE_IN_DATE}}":   data.move_in_date,
            # 공고문 URL
            "{{NOTICE_URL}}":        data.notice_url or "#",
            # 청약 규제 정보
            "{{IS_HOT_ZONE}}":       data.is_hot_zone or "공고문 확인 필요",
            "{{REGULATED_ZONE}}":    data.regulated_zone or data.is_hot_zone or "공고문 확인 필요",
            "{{READMISSION_LIMIT}}": data.readmission_limit or "공고문 확인 필요",
            "{{LIVE_REQUIREMENT}}":  data.live_requirement or "공고문 확인 필요",
            "{{PRICE_CAP}}":         data.price_cap or "공고문 확인 필요",
            "{{RESALE_RESTRICTION_BADGE}}": data.resale_restriction or "공고문 확인 필요",
            "{{RESALE_RESTRICTION}}": data.resale_restriction or "공고문을 통해 전매제한 기간을 반드시 확인하세요.",
            # 청약 일정
            "{{NOTICE_DATE}}": data.notice_date,
            "{{SPECIAL_SUPPLY_DATE}}": data.special_supply_date,
            "{{RANK2_DATE}}":     data.rank2_date,
            "{{WINNER_DATE}}":    data.winner_date,
            # 금융
            "{{LOAN_INFO}}":      data.loan_info,
            "{{CONTRACT_RATIO}}": data.contract_ratio,
            "{{CONTRACT_AMOUNT}}":data.contract_amount or "",
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
            "{{FEATURE_SCORE}}":  data.feature_score,
            "{{FEATURE_DETAIL}}": data.feature_detail,
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

        if data.midterm_fixed_amount:
            html = re.sub(
                r"중도금\s*—\s*\d+%\s*\([^<]*분납\)",
                f"중도금 — {data.midterm_fixed_amount}",
                html,
            )
            html = html.replace("■ 중도금 0%", f"■ 중도금 {data.midterm_fixed_amount}")
        elif str(data.midterm_ratio).strip() == "0":
            html = re.sub(
                r"중도금\s*—\s*0%\s*\([^<]*분납\)",
                "중도금 — 없음",
                html,
            )
            html = html.replace("■ 중도금 0%", "■ 중도금 없음")
            html = adapt_no_midterm_finance_html(html)

        if _finance_uses_non_ratio_display(data):
            html = remove_special_finance_ratio_bar_from_html(html)
            html = re.sub(
                r"계약금\s*—\s*0%",
                f"계약금 — {data.contract_amount}",
                html,
            )
            if data.contract_amount:
                html = re.sub(
                    r'\s*<p style="font-size: 1.0625rem; font-weight: 800; color: var\(--c-dark, #[0-9A-Fa-f]{6}\); margin: 0;">'
                    + re.escape(data.contract_amount)
                    + r"</p>",
                    "",
                    html,
                )
            html = html.replace("■ 계약금 0%", f"■ 계약금 {data.contract_amount}")
            if _is_zero_ratio(data.midterm_ratio):
                html = html.replace("■ 잔금 0%", "■ 잔금 잔여금")
                html = re.sub(
                    r"잔금\s*—\s*0%\s*\(입주 시\)",
                    "잔금 — 잔여금 (입주 시)",
                    html,
                )
                html = html.replace(
                    "최종 입주 시점에 납부하는 잔금은 '기존 중도금 대출의 상환'과 '잔금 대출(담보대출)로의 전환'이 동시에 일어나는 핵심 구간입니다. 입주 시점의 KB시세나 감정평가액에 따라 대출 한도가 재산정되므로, 금리 변동성 및 개인의 신용도를 고려한 입체적인 자금 조달 시나리오를 미리 수립해 두는 것이 안전합니다.",
                    "잔금은 계약금을 제외한 나머지 금액을 공고문에 정해진 시점에 납부하는 구간입니다. 중도금 단계가 없는 구조에서는 잔금 납부 시점의 자금 공백이 생기지 않도록 현금과 금융상품 활용 가능성을 미리 점검해야 합니다. 정확한 금액과 납부일은 입주자모집공고문 및 계약 안내문을 기준으로 확인해 주세요.",
                )
                html = re.sub(
                    r"기본 구조만 보면 계약금[^<]*?순서입니다\.",
                    f"이 공고는 계약금 {data.contract_amount}을 먼저 납부하고, 중도금 없이 잔금은 나머지 금액으로 확인하시면 됩니다.",
                    html,
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
    # SEO 정책: 슬러그는 청약홈 notice_id(숫자)만 허용.
    # notice_url에서 pblancNo/houseManageNo를 추출하지 못하면 빌드를 중단한다.
    # (날짜+단지명 폴백 슬러그는 canonical 중복을 유발해 폐기됨 — GSC 색인 보고서 2026-05-06 참조)
    notice_id_match = re.search(r"(?:pblancNo|houseManageNo)=([0-9]+)", data.notice_url or "")
    if not notice_id_match:
        raise ValueError(
            f"포스트 슬러그 생성 실패: notice_url에서 pblancNo/houseManageNo를 추출할 수 없습니다. "
            f"apt_name={data.apt_name!r}, notice_url={data.notice_url!r}"
        )
    post_slug = notice_id_match.group(1)
    post_dir = output_root / "posts" / post_slug
    post_dir.mkdir(parents=True, exist_ok=True)

    from config import SITE_URL
    from shared_ui import (
        FONT_LINK, FONT_FAMILY, PALETTE_CSS,
        PALETTE_INIT_JS, detail_nav,
    )

    post_canonical = f"{SITE_URL}/posts/{post_slug}/post.html"
    desc = f"{data.apt_name} 청약 분양가·일정·입지·자격 한눈에 정리. {data.price_range}"[:120]
    robots_directive = "noindex, follow" if _is_noindex_eligible(data.winner_date) else "index, follow"
    nav_html = detail_nav("../../")
    compact_title = escape(data.apt_name)
    compact_notice_date = _stringify(data.notice_date)
    compact_subtitle = escape(
        f"모집공고일 {compact_notice_date}" if compact_notice_date else "모집공고일 확인 필요"
    )

    from regions import region_name_to_category
    share_region = region_name_to_category(data.location)
    share_text = _build_share_text(
        apt_name=data.apt_name,
        region=share_region,
        notice_date=data.notice_date,
        price_range=data.price_range,
    )
    share_payload_json = json.dumps(
        {"title": data.post_title, "text": share_text},
        ensure_ascii=False,
    ).replace("</", "<\\/")

    full_html = f"""<!DOCTYPE html>
<html lang="ko" data-palette="A">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<meta name="google-adsense-account" content="ca-pub-8234120897033274">
<title>정과장의 청약노트</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{post_canonical}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="정과장의 청약노트">
<meta property="og:title" content="{data.post_title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{post_canonical}">
<meta property="og:image" content="{SITE_URL}/og-image-v2.jpg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:type" content="image/jpeg">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{data.post_title}">
<meta name="twitter:description" content="{desc}">
<meta name="twitter:image" content="{SITE_URL}/og-image-v2.jpg">
<meta name="robots" content="{robots_directive}">
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "Article",
  "@id": "{post_canonical}#article",
  "headline": "{data.post_title}",
  "description": "{desc}",
  "url": "{post_canonical}",
  "datePublished": "{data.notice_date}",
  "dateModified": "{data.notice_date}",
  "image": {{
    "@type": "ImageObject",
    "url": "{SITE_URL}/og-image-v2.jpg",
    "width": 1200,
    "height": 630
  }},
  "publisher": {{
    "@type": "Organization",
    "@id": "{SITE_URL}/#organization",
    "name": "정과장의 청약노트",
    "url": "{SITE_URL}/",
    "logo": {{
      "@type": "ImageObject",
      "url": "{SITE_URL}/android-chrome-512x512.png",
      "width": 512,
      "height": 512
    }}
  }},
  "author": {{
    "@type": "Person",
    "@id": "{SITE_URL}/about.html#person",
    "name": "정과장",
    "url": "{SITE_URL}/about.html",
    "jobTitle": "청약 분양공고 정보 정리·검수자"
  }},
  "isBasedOn": {{
    "@type": "Dataset",
    "name": "청약홈 분양공고 공공데이터",
    "description": "한국부동산원 청약홈이 공공데이터포털을 통해 공개하는 분양 공고 원본 데이터(분양가·모집 일정·자격·세대수 등)를 본 포스트의 기초 자료로 사용합니다.",
    "url": "{data.notice_url}",
    "license": "https://www.kogl.or.kr/info/license.do#01-tab",
    "creator": {{
      "@type": "Organization",
      "name": "한국부동산원",
      "url": "https://www.applyhome.co.kr/"
    }},
    "provider": {{
      "@type": "Organization",
      "name": "한국부동산원",
      "url": "https://www.applyhome.co.kr/"
    }}
  }},
  "isPartOf": {{
    "@type": "WebSite",
    "@id": "{SITE_URL}/#website",
    "name": "정과장의 청약노트",
    "url": "{SITE_URL}/"
  }}
}}
</script>
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    {{"@type": "ListItem", "position": 1, "name": "홈", "item": "{SITE_URL}/"}},
    {{"@type": "ListItem", "position": 2, "name": "{data.apt_name}", "item": "{post_canonical}"}}
  ]
}}
</script>
<link rel="icon" type="image/x-icon" href="{SITE_URL}/favicon.ico">
<link rel="icon" type="image/png" sizes="16x16" href="{SITE_URL}/favicon-16x16.png">
<link rel="icon" type="image/png" sizes="32x32" href="{SITE_URL}/favicon-32x32.png">
<link rel="icon" type="image/png" sizes="192x192" href="{SITE_URL}/android-chrome-192x192.png">
<link rel="apple-touch-icon" href="{SITE_URL}/apple-touch-icon.png">
<link rel="manifest" href="{SITE_URL}/manifest.json">
{FONT_LINK}
{PALETTE_INIT_JS}
<style>
{PALETTE_CSS}
body {{ font-family: {FONT_FAMILY}; margin: 0; padding: 0; background: #fffaf3; }}
.post-compact-bar {{
  position: fixed;
  left: 0;
  right: 0;
  top: var(--post-header-height, 68px);
  z-index: 45;
  padding: 0 16px;
  pointer-events: none;
  opacity: 0;
  transform: translateY(-10px);
  transition: opacity 180ms ease, transform 180ms ease;
}}
.post-compact-bar.is-visible {{
  opacity: 1;
  transform: translateY(0);
}}
.post-compact-card {{
  max-width: 700px;
  margin: 0 auto;
  padding: 14px 18px 16px;
  border-radius: 0 0 18px 18px;
  background: linear-gradient(135deg, #CC5F3F 0%, #A84830 62%, #8B3A24 100%);
  color: #fff;
  box-shadow: 0 16px 34px rgba(44, 41, 37, 0.18);
  position: relative;
  overflow: hidden;
}}
.post-compact-card::after {{
  content: "";
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  width: 96px;
  background: repeating-linear-gradient(45deg, transparent, transparent 10px, rgba(255,255,255,0.045) 10px, rgba(255,255,255,0.045) 20px);
  pointer-events: none;
}}
.post-compact-title {{
  position: relative;
  margin: 0 0 6px;
  font-size: 1.25rem;
  line-height: 1.25;
  font-weight: 700;
  letter-spacing: -0.04em;
}}
.post-compact-subtitle {{
  position: relative;
  margin: 0;
  color: rgba(255,255,255,0.82);
  font-size: 0.875rem;
  line-height: 1.45;
  font-weight: 600;
}}
@media (max-width: 580px) {{
  .post-compact-bar {{
    top: var(--post-header-height, 56px);
    padding: 0 12px;
  }}
  .post-compact-card {{
    border-radius: 0 0 16px 16px;
    padding: 12px 16px 14px;
  }}
  .post-compact-title {{
    font-size: 1.125rem;
  }}
  .post-compact-subtitle {{
    font-size: 0.8125rem;
  }}
}}
.post-floating-actions {{
  position: fixed;
  right: 24px;
  bottom: 24px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  z-index: 60;
}}
.post-floating-actions button {{
  width: 48px;
  height: 48px;
  border: 1px solid rgba(255,255,255,0.92);
  border-radius: 12px;
  background: rgba(217,119,87,0.7);
  color: #fff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 14px 28px rgba(217,119,87,0.32);
  cursor: pointer;
  padding: 0;
  transition: transform 150ms ease, background 150ms ease, opacity 150ms ease;
}}
.post-floating-actions button:hover {{
  background: rgba(184,92,56,0.78);
  transform: translateY(-2px);
}}
.post-floating-actions button:focus-visible {{
  outline: 2px solid #fff;
  outline-offset: 2px;
}}
#post-share-toast {{
  position: fixed;
  left: 50%;
  bottom: 96px;
  transform: translateX(-50%) translateY(8px);
  background: rgba(30,30,30,0.92);
  color: #fff;
  padding: 10px 16px;
  border-radius: 999px;
  font-size: 0.875rem;
  opacity: 0;
  pointer-events: none;
  transition: opacity 180ms ease, transform 180ms ease;
  z-index: 70;
}}
#post-share-toast.is-visible {{
  opacity: 1;
  transform: translateX(-50%) translateY(0);
}}
</style>
<!-- ga4-injected:G-D5SCQRYKSM -->
<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-D5SCQRYKSM"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());

  gtag('config', 'G-D5SCQRYKSM');
</script>
</head>
<body>
{nav_html}
<div id="post-compact-bar" class="post-compact-bar" aria-hidden="true">
  <div class="post-compact-card">
    <p class="post-compact-title">{compact_title}</p>
    <p class="post-compact-subtitle">{compact_subtitle}</p>
  </div>
</div>
<div id="post-body" style="max-width:740px;margin:0 auto;padding:32px 16px 80px;">
{html}
</div>
<script>
(function() {{
  var bar = document.getElementById('post-compact-bar');
  var body = document.getElementById('post-body');
  if (!bar || !body) return;
  var hero = body.querySelector('div');
  if (!hero) return;

  function setVisible(visible) {{
    bar.classList.toggle('is-visible', visible);
    bar.setAttribute('aria-hidden', visible ? 'false' : 'true');
  }}

  function syncHeaderHeight() {{
    var header = document.querySelector('.site-header-v3');
    var headerHeight = header ? Math.ceil(header.getBoundingClientRect().height) : 68;
    document.documentElement.style.setProperty('--post-header-height', headerHeight + 'px');
    return headerHeight;
  }}

  var ticking = false;
  function onScroll() {{
    if (ticking) return;
    ticking = true;
    window.requestAnimationFrame(function() {{
      var headerHeight = syncHeaderHeight();
      setVisible(hero.getBoundingClientRect().top <= headerHeight);
      ticking = false;
    }});
  }}
  window.addEventListener('scroll', onScroll, {{ passive: true }});
  window.addEventListener('resize', onScroll);
  onScroll();
}})();
</script>
<div class="post-floating-actions" aria-label="페이지 작업">
  <button id="post-share-btn" type="button" aria-label="공유하기">
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <circle cx="18" cy="5" r="3"></circle>
      <circle cx="6" cy="12" r="3"></circle>
      <circle cx="18" cy="19" r="3"></circle>
      <line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line>
      <line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line>
    </svg>
  </button>
  <button id="post-scroll-top-btn" type="button" aria-label="최상단으로 이동">
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <path d="M18 15l-6-6-6 6"></path>
    </svg>
  </button>
</div>
<div id="post-share-toast" role="status" aria-live="polite"></div>
<script id="post-share-data" type="application/json">{share_payload_json}</script>
<script>
(function() {{
  var topBtn = document.getElementById('post-scroll-top-btn');
  if (topBtn) {{
    topBtn.addEventListener('click', function() {{
      window.scrollTo({{ top: 0, behavior: 'smooth' }});
    }});
  }}

  var shareBtn = document.getElementById('post-share-btn');
  var toast = document.getElementById('post-share-toast');
  var toastTimer = null;
  function showToast(msg) {{
    if (!toast) return;
    toast.textContent = msg;
    toast.classList.add('is-visible');
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(function() {{
      toast.classList.remove('is-visible');
    }}, 1800);
  }}

  function getShareData() {{
    var payload = null;
    var payloadEl = document.getElementById('post-share-data');
    if (payloadEl) {{
      try {{ payload = JSON.parse(payloadEl.textContent || '{{}}'); }} catch (_) {{}}
    }}
    var ogTitle = (document.querySelector('meta[property="og:title"]') || {{}}).content || '';
    var ogDesc = (document.querySelector('meta[property="og:description"]') || {{}}).content
      || (document.querySelector('meta[name="description"]') || {{}}).content
      || '';
    var title = (payload && payload.title) || ogTitle || document.title || '정과장의 청약노트';
    var description = (payload && payload.text) || ogDesc || '';
    return {{
      title: title,
      text: description,
      url: location.href
    }};
  }}

  if (shareBtn) {{
    shareBtn.addEventListener('click', async function() {{
      var data = getShareData();
      if (navigator.share) {{
        try {{
          await navigator.share({{text: data.text, url: data.url}});
          return;
        }} catch (err) {{
          if (err && err.name === 'AbortError') return;
        }}
      }}
      if (navigator.clipboard && navigator.clipboard.writeText) {{
        try {{
          await navigator.clipboard.writeText(data.url);
          showToast('링크가 복사되었습니다');
          return;
        }} catch (_) {{}}
      }}
      location.href = 'mailto:?subject=' + encodeURIComponent(data.title)
        + '&body=' + encodeURIComponent(data.url);
    }});
  }}
}})();
</script>
</body>
</html>"""
    (post_dir / "post.html").write_text(full_html, encoding="utf-8")

    region_category = share_region

    meta = {
        "notice_id":       post_slug,
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
        "winner_date":          data.winner_date,
        "move_in_date":         data.move_in_date,
        "supply_location":      data.supply_location,
        "total_households":     data.total_households,
        "is_hot_zone":          data.is_hot_zone,
        "regulated_zone":       data.regulated_zone,
        "readmission_limit":    data.readmission_limit,
        "live_requirement":     data.live_requirement,
        "price_cap":            data.price_cap,
        "resale_restriction":   data.resale_restriction,
        "eligibility_special":   data.eligibility_special,
        "eligibility_rank1":     data.eligibility_rank1,
        "eligibility_rank2":     data.eligibility_rank2,
        "contract_ratio":        data.contract_ratio,
        "contract_amount":       data.contract_amount,
        "midterm_ratio":         data.midterm_ratio,
        "midterm_count":         data.midterm_count,
        "midterm_fixed_amount":  data.midterm_fixed_amount,
        "balance_ratio":         data.balance_ratio,
        "loan_info":             data.loan_info,
        "notice_url":           data.notice_url,
        "generated_at":    datetime.now().isoformat(),
    }
    (post_dir / "post_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"\n{'='*50}")
    print(f"✅ 포스팅 저장 완료: {post_dir}")
    print(f"   📄 HTML  : post.html ({len(html):,}자) | 테마: {data.theme}")
    print(f"   📋 메타  : post_meta.json")
    print(f"{'='*50}")
    return post_dir
