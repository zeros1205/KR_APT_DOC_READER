"""
orchestrator.py
────────────────────────────────────────────────────
멀티에이전트 파이프라인 오케스트레이터

흐름:
  [데이터 수집] → [팩트 추출 Agent] → [콘텐츠 생성 Agent]
               → [CTA 최적화 Agent] → [품질 검수 Agent]
               → [HTML 렌더링] → [로컬 저장]
────────────────────────────────────────────────────
"""

import sys
import asyncio
import json
import re
from pathlib import Path
from openai import AsyncOpenAI

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    OPENAI_API_KEY, GEMINI_API_KEY, KAKAO_API_KEY,
    LLM_CONTENT_MODEL, LLM_EXTRACT_MODEL, LLM_FACTCHECK_MODEL, LLM_LOCATION_MODEL,
    OUTPUT_DIR, MIN_QUALITY_SCORE, MAX_CTA_PER_POST, MIN_CHAR_COUNT,
    CTA_LOAN_COMPARE, CTA_INTERIOR, CTA_MOVING, CTA_TAX, CTA_KAKAO_CHANNEL,
    PREFERRED_IMAGE_SOURCE, BLOG_THEME,
)
from html_renderer import BlogHTMLRenderer, UnitType, build_post_data, save_post
from image_finder import find_images_for_post, ImageResult
from agents.collector import NoticeDocument
from agents.pdf_policy import extract_policy_from_pdf_text
from kakao_local import KakaoLocalClient, merge_places, normalize_places, score_from_distance

openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)


async def _call_openai_json(system: str, user: str, model: str, max_tokens: int = 4096) -> str:
    """OpenAI Responses API 호출 헬퍼 — JSON 객체 출력 전용"""
    resp = await openai_client.responses.create(
        model=model,
        instructions=system,
        input=user,
        max_output_tokens=max_tokens,
        text={"format": {"type": "json_object"}},
    )
    return (resp.output_text or "").strip()


# ──────────────────────────────────────────────────
# Agent 0: 청약규제정보 추출 (별도 전문 에이전트)
# ──────────────────────────────────────────────────
REGULATORY_EXTRACTION_PROMPT = """당신은 청약공고 규제정보 추출 전문가입니다.
아래 [공고 원문]에서 다음 5가지 규제 정보만 정확하게 추출하세요.

추출 대상 (5가지):
1. regulated_zone: 규제지역 여부
   - 투기과열지구 / 청약과열지역 / 조정대상지역 등 해당하는 모든 항목을 쉼표로 나열
   - 예: "투기과열지구, 조정대상지역"
   - 공고에 명시 안 되면 null

2. readmission_limit: 재당첨 제한 (몇 년 동안 청약 불가)
   - "N년" 형식 또는 "없음" / "제한없음"
   - 검색 키워드: "재당첨", "재청약", "재입주" 제한/금지
   - 공고에 명시 안 되면 null

3. resale_restriction: 전매 제한 (매매 가능 시점)
   - "N년" 또는 "입주 후 N년" 또는 "없음" / "제한없음"
   - 검색 키워드: "전매", "매매", "재판매" 제한 관련 항목
   - 예: "입주 후 3년", "소유권이전등기일로부터 2년"
   - 공고에 명시 안 되면 null

4. live_requirement: 거주의무기간 (실거주해야 하는 기간)
   - "N년" 형식 또는 "없음" / "의무없음"
   - 검색 키워드: "거주의무", "실거주", "거주기간" 관련 항목
   - 예: "2년", "의무없음"
   - 공고에 명시 안 되면 null

5. price_cap: 분양가 상한제 (정부가 가격 상한 지정)
   - "적용" 또는 "미적용" 또는 null
   - 검색 키워드: "분양가상한제", "분양가상한" 항목
   - 공고에 명시 안 되면 null

[핵심 규칙]
- 공고문에 명확하게 명시된 정보만 추출
- 추측, 생성, 해석 절대 금지
- null은 따옴표 없이 null로 표기
- JSON만 출력

[공고 원문]:
{notice_text}

JSON 응답:
{{
  "regulated_zone": null,
  "readmission_limit": null,
  "resale_restriction": null,
  "live_requirement": null,
  "price_cap": null
}}"""

# ──────────────────────────────────────────────────
# Agent 1: 팩트 추출
# ──────────────────────────────────────────────────
FACT_EXTRACTION_PROMPT = """
당신은 부동산 분양 공고문 분석 전문가입니다.
아래 [공고 원문]에서 정보를 추출하여 JSON으로만 답하세요.
[공고 원문]에 없는 수치는 절대 추측하거나 생성하지 마세요. 없으면 null로 표기.

추출할 필드 (JSON 키명 고정):
- apt_name: 단지명
- location: 시/구/동 (예: 서울시 강남구 개포동)
- supply_location: 전체 공급위치 (공고문 그대로)
- supply_scale: 공급규모 요약
- unit_types: 배열 (type_name, area_sqm, general_units, special_units, price_min, price_max 키를 가진 객체 목록)
- price_range: "X억~Y억원" 형식 문자열
- total_households: 단지 전체 세대수 정수 (분양 공급 물량과 다를 수 있음. 공고에 명시된 경우만. 없으면 null)
- notice_date: 모집공고일 YYYY-MM-DD (없으면 null)
- special_supply_date: YYYY-MM-DD
- rank1_date: YYYY-MM-DD
- rank2_date: YYYY-MM-DD
- winner_date: YYYY-MM-DD
- move_in_date: YYYY년 MM월
- loan_info: 중도금 대출 가능 여부 및 조건 요약
- resale_restriction: 전매제한 기간 — 공고문의 "제한사항", "전매제한", "계약 조건" 섹션에 기재.
  예: "소유권이전등기일로부터 3년", "입주 후 6개월", "분양가상한제 적용 10년", "없음".
  공고에 없으면 null. 조건별로 다를 경우 가장 긴 기간 기준으로 요약.
- contract_ratio: 계약금 비율 (숫자만, 예: 10)
- contract_amount: 공고문에 실제 납부금액이 명시된 경우에만 계약금 금액 문자열 반환. 비율을 근거로 계산하지 말 것. 없으면 null
- midterm_ratio: 중도금 비율 (숫자만, 예: 60)
- midterm_count: 중도금 납부 횟수 (숫자만, 예: 6), 공고에 없으면 6
- balance_ratio: 잔금 비율 (숫자만, 예: 30)
- acquisition_tax_rate: 취득세율 (예: "1~3%")
- is_hot_zone: 투기과열지구 해당 여부 — 반드시 "Y", "N", "해당없음" 중 하나. 명시 없으면 null.
- regulated_zone: 규제지역 여부 — 해당하는 모든 지역 구분을 쉼표로 나열.
  예: "투기과열지구, 청약과열지역", "청약과열지역", "비규제지역", "해당없음". 공고에 없으면 null.
- readmission_limit: 재당첨 제한 기간 — "재당첨 제한", "재청약 제한" 항목.
  예: "10년", "7년", "없음". 공고에 없으면 null.
- live_requirement: 거주의무기간 — "거주의무", "실거주 의무", "실거주기간" 항목.
  예: "2년", "없음", "해당 없음". 공고에 없으면 null.
- price_cap: 분양가 상한제 적용 여부 — "분양가상한제" 항목.
  반드시 "적용" 또는 "미적용" 중 하나. 공고에 없으면 null.
- land_type: 택지 유형 — "택지유형", "토지 구분" 항목.
  예: "민간택지", "공공택지", "공공주택지구". 공고에 없으면 null.
- is_price_cap: 분양가상한제 여부 (Y/N) — legacy, price_cap과 중복 추출
- eligibility_special: 배열 — 공고에 명시된 특별공급 유형별 신청자격
  각 항목: type_name(예: "생애최초", "신혼부부", "다자녀", "노부모부양", "기관추천"),
           quota(예: "20호" — 없으면 null),
           requirements(핵심 자격 요건 문장 목록, 최대 4개, 공고 원문 기준)
- eligibility_rank1: 배열 — 1순위 신청자격 핵심 요건 문장 목록 (최대 5개, 공고 원문 기준)
- eligibility_rank2: 배열 — 2순위 신청자격 핵심 요건 문장 목록 (최대 3개, 공고 원문 기준)

[공고 원문]:
{notice_text}
"""

ELIGIBILITY_EXTRACTION_PROMPT = """
당신은 한국 청약제도 자격 요건 추출 전문가입니다.
아래 [공고 원문]에서 신청자격만 추출하여 JSON으로만 답하세요.

추출 규칙:
- 공고문에 실제로 적힌 문장만 사용하고, 추측은 금지합니다.
- 특별공급은 타입명(type_name), 세대수(quota, 없으면 null), requirements 배열로 정리하세요.
- 1순위/2순위는 공고문 문장을 최대한 그대로 3~5개씩 정리하세요.
- 정보가 없으면 빈 배열을 반환하세요.

반드시 추출할 키:
- eligibility_special
- eligibility_rank1
- eligibility_rank2

[공고 원문]:
{notice_text}
"""

FINANCIAL_EXTRACTION_PROMPT = """
당신은 한국 부동산 분양 공고문에서 자금계획을 추출하는 전문가입니다.
아래 [공고 원문]에서 자금계획만 추출하여 JSON으로만 답하세요.

추출 규칙:
- 공고문에 실제로 적힌 내용만 사용하고, 추측은 금지합니다.
- 비율은 숫자만 반환하세요. 예: 10, 60, 30
- 계약금 금액은 공고문에 실제 납부금액이 적힌 경우에만 그대로 반환하세요.
- 비율(예: 5%, 10%)만 보고 실제 금액을 계산하지 마세요.
- 중도금 대출이 없거나 조건이 불명확하면 loan_info에 "공고문 확인 필요"를 반환하세요.
- 정보가 없으면 null 또는 기본값을 사용하지 말고 빈 값으로 두세요.

반드시 추출할 키:
- contract_ratio
- contract_amount
- midterm_ratio
- midterm_count
- balance_ratio
- loan_info

[공고 원문]:
{notice_text}
"""


def _has_eligibility_data(facts: dict) -> bool:
    """청약 신청자격 정보가 하나라도 채워졌는지 확인."""
    return any(
        facts.get(key)
        for key in ("eligibility_special", "eligibility_rank1", "eligibility_rank2")
    )


def _has_financial_data(facts: dict) -> bool:
    """자금 계획 정보가 하나라도 채워졌는지 확인."""
    return any(
        facts.get(key)
        for key in ("contract_ratio", "midterm_ratio", "midterm_count", "balance_ratio", "loan_info")
    )


def _derive_price_range(unit_types: list[dict]) -> str:
    """타입별 최저/최고 분양가를 바탕으로 범위를 계산한다."""
    lows: list[int] = []
    highs: list[int] = []

    for ut in unit_types:
        low = _parse_price_manwon(ut.get("price_min", 0))
        high = _parse_price_manwon(ut.get("price_max", 0))
        if low <= 0 and high <= 0:
            continue
        if low <= 0:
            low = high
        if high <= 0:
            high = low
        lows.append(low)
        highs.append(high)

    if not lows or not highs:
        return ""

    lo = min(lows)
    hi = max(highs)
    if lo <= 0 or hi <= 0:
        return ""
    if lo == hi:
        return UnitType._fmt(lo)
    return f"{UnitType._fmt(lo)} ~ {UnitType._fmt(hi)}"


def _extract_pdf_policy_overrides(notice_text: str) -> dict:
    """PDF에서 추출한 규제 정보를 사실 추출 결과보다 우선 적용한다."""
    overrides: dict = {}
    if not notice_text:
        return overrides

    policy_lines: dict[str, str] = {}
    for line in notice_text.splitlines():
        line = line.strip()
        if not line.startswith("[PDF 정책]"):
            continue
        m = re.match(r"\[PDF 정책\]\s*([^:]+):\s*(.+)$", line)
        if not m:
            continue
        key = m.group(1).strip()
        value = m.group(2).strip()
        if key and value:
            policy_lines[key] = value

    key_map = {
        "regulated_zone": "regulated_zone",
        "is_hot_zone": "is_hot_zone",
        "readmission_limit": "readmission_limit",
        "resale_restriction": "resale_restriction",
        "live_requirement": "live_requirement",
        "price_cap": "price_cap",
        "is_price_cap": "is_price_cap",
    }
    for src_key, dst_key in key_map.items():
        value = policy_lines.get(src_key)
        if value:
            overrides[dst_key] = value

    if "regulated_zone" in overrides and "is_hot_zone" not in overrides:
        zone = overrides["regulated_zone"]
        if any(token in zone for token in ("투기과열지구", "청약과열지역", "조정대상지역")):
            overrides["is_hot_zone"] = "Y"
        elif any(token in zone for token in ("비규제지역", "해당없음")):
            overrides["is_hot_zone"] = "N"

    if "price_cap" in overrides and "is_price_cap" not in overrides:
        overrides["is_price_cap"] = "Y" if overrides["price_cap"] == "적용" else "N"

    return overrides


def _extract_bracket_value(text: str, label: str) -> str:
    """[라벨] 값 형태의 문장에서 값을 추출한다."""
    m = re.search(rf"\[{re.escape(label)}\]\s*([^\n]+)", text or "")
    return m.group(1).strip() if m else ""


def _extract_first_match(text: str, patterns: tuple[str, ...], default: str = "") -> str:
    """여러 패턴 중 처음 매칭되는 값을 반환한다."""
    for pat in patterns:
        m = re.search(pat, text or "", re.IGNORECASE | re.DOTALL)
        if m:
            value = m.group(1).strip()
            if value:
                return value
    return default


def _parse_unit_types_from_text(notice_text: str) -> list[dict]:
    """표 형태 또는 요약 문장에서 주택형 정보를 추출한다."""
    unit_types: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for raw_line in (notice_text or "").splitlines():
        line = raw_line.strip()
        if not line or "|" not in line:
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) < 5:
            continue

        type_name = parts[0]
        area_text = parts[1]
        general_text = parts[2]
        special_text = parts[3]
        price_text = parts[4]

        if not re.search(r"\d", type_name):
            continue

        if "전용" in area_text:
            m = re.search(r"([\d.]+)", area_text)
            area_text = m.group(1) if m else area_text
        elif not re.search(r"[\d.]", area_text):
            continue
        if "세대" in general_text:
            m = re.search(r"(\d+)", general_text)
            general_text = m.group(1) if m else general_text
        elif not general_text.isdigit():
            continue
        if "세대" in special_text:
            m = re.search(r"(\d+)", special_text)
            special_text = m.group(1) if m else special_text
        elif not special_text.isdigit():
            continue
        if "분양가" in price_text or "가격" in price_text:
            m = re.search(r"([0-9.,억천백십만~\s]+)", price_text)
            price_text = m.group(1).strip() if m else price_text
        if not re.search(r"\d", price_text):
            continue

        key = (type_name, area_text)
        if key in seen:
            continue
        seen.add(key)

        unit_types.append(
            {
                "type_name": type_name.replace("타입", "타입").strip(),
                "area_sqm": area_text,
                "general_units": general_text,
                "special_units": special_text,
                "price_min": price_text.split("~")[0].strip() if "~" in price_text else price_text,
                "price_max": price_text.split("~")[-1].strip() if "~" in price_text else price_text,
            }
        )

    if unit_types:
        return unit_types

    # 서술형 텍스트에서 1차 추출
    pattern = re.compile(
        r"(?P<type>\d+[A-Z]?(?:타입)?)\s*(?:\(|\[)?\s*(?P<area>[\d.]+)\s*㎡.*?"
        r"(?:일반|공급)\s*(?P<general>\d+)\s*세대.*?"
        r"(?:특별|우선)\s*(?P<special>\d+)\s*세대.*?"
        r"(?:분양가|가격|분양가상한)\s*(?P<price>[0-9.,억천백십만~\s]+)",
        re.IGNORECASE,
    )
    for m in pattern.finditer(notice_text or ""):
        unit_types.append(
            {
                "type_name": m.group("type").replace("타입타입", "타입"),
                "area_sqm": m.group("area"),
                "general_units": m.group("general"),
                "special_units": m.group("special"),
                "price_min": m.group("price").split("~")[0].strip(),
                "price_max": m.group("price").split("~")[-1].strip(),
            }
        )

    return unit_types


def _fallback_fact_extraction(notice_text: str) -> dict:
    """LLM 없이도 샘플/오프라인 실행이 가능한 결정론적 팩트 추출."""
    text = notice_text or ""
    facts: dict = dict(_extract_pdf_policy_overrides(text))

    apt_name = _extract_bracket_value(text, "단지명") or _extract_bracket_value(text, "주택명")
    if not apt_name:
        apt_name = _extract_first_match(
            text,
            (
                r"\[단지 소개\]\s*([^\n]+)",
                r"단지명\s*[:：]\s*([^\n]+)",
                r"주택명\s*[:：]\s*([^\n]+)",
            ),
        )
    location = _extract_bracket_value(text, "공급위치")
    if not location:
        location = _extract_first_match(
            text,
            (
                r"공급위치\s*[:：]\s*([^\n]+)",
                r"위치\s*[:：]\s*([^\n]+)",
            ),
        )

    unit_types = _parse_unit_types_from_text(text)
    price_range = _derive_price_range(unit_types)

    facts.update(
        {
            "apt_name": apt_name,
            "location": location,
            "supply_location": location,
            "supply_scale": _extract_bracket_value(text, "총 공급세대")
            or _extract_first_match(text, (r"총\s*공급세대\s*[:：]\s*([^\n]+)",)),
            "unit_types": unit_types,
            "notice_date": _extract_bracket_value(text, "모집공고일"),
            "special_supply_date": _extract_bracket_value(text, "특별공급")
            or _extract_first_match(text, (r"특별공급\s*[:：]\s*([0-9\-년월일\.~ ]+)",)),
            "rank1_date": _extract_bracket_value(text, "1순위 청약")
            or _extract_first_match(text, (r"1순위\s*청약\s*[:：]\s*([0-9\-년월일\.~ ]+)",)),
            "rank2_date": _extract_bracket_value(text, "2순위 청약")
            or _extract_first_match(text, (r"2순위\s*청약\s*[:：]\s*([0-9\-년월일\.~ ]+)",)),
            "winner_date": _extract_bracket_value(text, "당첨자발표"),
            "move_in_date": _extract_bracket_value(text, "입주예정"),
            "contract_ratio": _extract_first_match(text, (r"계약금[^\d]*(\d+)\s*%", r"계약금\s*(\d+)\s*%"), "10"),
            "contract_amount": "",
            "midterm_ratio": _extract_first_match(text, (r"중도금[^\d]*(\d+)\s*%", r"중도금\s*(\d+)\s*%"), "60"),
            "midterm_count": _extract_first_match(text, (r"(\d+)\s*회\s*분납", r"(\d+)\s*회"), "6"),
            "balance_ratio": _extract_first_match(text, (r"잔금[^\d]*(\d+)\s*%", r"잔금\s*(\d+)\s*%"), "30"),
            "acquisition_tax_rate": "1~3%",
            "is_hot_zone": facts.get("is_hot_zone") or "N",
            "regulated_zone": facts.get("regulated_zone") or ("비규제지역" if facts.get("is_hot_zone") == "N" else "해당없음"),
            "readmission_limit": facts.get("readmission_limit") or "공고문 확인 필요",
            "live_requirement": facts.get("live_requirement") or "공고문 확인 필요",
            "price_cap": facts.get("price_cap") or ("미적용" if facts.get("is_hot_zone") == "N" else "공고문 확인 필요"),
            "is_price_cap": facts.get("is_price_cap") or ("N" if facts.get("price_cap") == "미적용" else "해당없음"),
            "resale_restriction": facts.get("resale_restriction") or "공고문 확인 필요",
            "eligibility_special": [
                {
                    "type_name": "특별공급",
                    "quota": None,
                    "requirements": [
                        "공고문에 명시된 특별공급 자격과 해당 유형별 요건을 모두 충족해야 합니다.",
                        "무주택 세대구성원, 청약통장 가입, 거주지역 요건은 공고문과 청약홈 기준으로 확인합니다.",
                        "세부 가점과 소득·자산 기준은 모집공고 최종본을 기준으로 재확인해야 합니다.",
                    ],
                }
            ],
            "eligibility_rank1": [
                "1순위 자격은 공고문에 적힌 해당지역 거주요건과 청약통장 가입기간을 기준으로 확인합니다.",
                "세대구성원 및 무주택 요건, 예치금 조건은 모집공고와 청약홈 안내를 함께 확인해야 합니다.",
                "지역별 1순위 접수일은 공고문 일정표를 기준으로 준비합니다.",
            ],
            "eligibility_rank2": [
                "2순위 자격은 1순위 미달 시 접수 가능하며, 공고문 기준으로 별도 확인이 필요합니다.",
            ],
        }
    )

    if unit_types:
        facts["price_range"] = price_range
        def _safe_int(value: object) -> int:
            try:
                return int(str(value).strip() or 0)
            except Exception:
                return 0

        facts["supply_total_units"] = sum(
            _safe_int(ut.get("general_units", 0)) + _safe_int(ut.get("special_units", 0))
            for ut in unit_types
        )
        if not facts.get("supply_scale") and facts.get("supply_total_units"):
            facts["supply_scale"] = f"총 {facts['supply_total_units']}세대"
    else:
        facts["price_range"] = price_range or ""
        facts["supply_total_units"] = 0

    return facts


def _extract_section_text(text: str, header: str) -> str:
    """[섹션명]부터 다음 섹션 전까지의 텍스트를 가져온다."""
    pattern = re.compile(
        rf"\[{re.escape(header)}\]\s*(.*?)(?=\n\[[^\]]+\]|\Z)",
        re.DOTALL,
    )
    m = pattern.search(text or "")
    return m.group(1).strip() if m else ""


def _format_distance_label(distance: int) -> str:
    return f"{distance}m" if distance > 0 else "거리 확인 필요"


def _render_place_list_html(items: list, *, empty_text: str, columns: int = 1) -> str:
    if not items:
        return f'<div style="font-size:13px;color:#8A817C;">{empty_text}</div>'

    if columns == 2:
        wrapper_open = '<div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px 10px;">'
    else:
        wrapper_open = '<div style="display:flex;flex-direction:column;gap:8px;">'

    blocks = []
    for item in items:
        source_badge = (
            f'<span style="display:inline-flex;align-items:center;border-radius:999px;padding:2px 8px;'
            f'background:rgba(217,119,87,0.12);color:#B85C38;font-size:11px;font-weight:700;">{item.source}</span>'
        )
        address_html = (
            f'<div style="font-size:12px;color:#8A817C;line-height:1.45;word-break:keep-all;">{item.address}</div>'
            if item.address else ""
        )
        blocks.append(
            f'<div style="border:1px solid rgba(0,0,0,0.06);border-radius:10px;padding:10px 11px;'
            f'background:rgba(255,255,255,0.48);">'
            f'<div style="display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:4px;">'
            f'<strong style="font-size:13px;color:#2C2925;line-height:1.45;">{item.name}</strong>'
            f'<span style="flex-shrink:0;font-size:12px;font-weight:700;color:#B85C38;">{_format_distance_label(item.distance)}</span>'
            f'</div>'
            f'<div style="margin-bottom:4px;">{source_badge}</div>'
            f'{address_html}'
            f'</div>'
        )
    return wrapper_open + "".join(blocks) + "</div>"


def _nearest_distance(items: list) -> int | None:
    distances = [item.distance for item in items if getattr(item, "distance", 0) > 0]
    return min(distances) if distances else None


def _build_sales_location_intro(apt_name: str, location: str, transit: list, schools: list, life: list, medical: list) -> str:
    hooks: list[str] = []
    if transit:
        hooks.append(f"가까운 교통 거점을 걸어서 이용할 수 있다는 점")
    if schools:
        hooks.append(f"반경 500m 안에 학교가 모여 있다는 점")
    if life:
        hooks.append(f"생활편의시설이 촘촘하게 붙어 있다는 점")
    if medical:
        hooks.append(f"의료 인프라까지 생활권 안에서 챙길 수 있다는 점")

    if not hooks:
        return (
            f"{apt_name}는 {location or '공급 위치'} 기준으로 생활권을 다시 확인해볼 필요가 있는 단지입니다. "
            f"시행사 관점에서 보더라도 실제 장점은 교통과 생활 인프라가 얼마나 가까이 붙어 있는지에서 갈리므로, "
            f"카카오 로컬 API 기준 반경 500m 내 시설을 중심으로 장점을 정리했습니다."
        )

    joined = "· ".join(hooks[:3])
    return (
        f"{apt_name}는 {location or '공급 위치'} 기준으로 보면 {joined}이 먼저 눈에 들어오는 단지입니다. "
        f"시행사 세일즈 관점에서 가장 강조할 만한 포인트는, 일상 동선에 필요한 교통·학교·편의시설·의료시설이 "
        f"반경 500m 안에서 얼마나 촘촘하게 붙어 있느냐인데, 이 단지는 그 장점을 비교적 직관적으로 보여주기 좋습니다."
    )


async def _build_kakao_location_analysis(facts: dict) -> dict:
    address = (
        facts.get("supply_location")
        or facts.get("location")
        or ""
    ).strip()
    apt_name = (facts.get("apt_name") or "").strip()
    if not KAKAO_API_KEY.strip() or not address:
        return {}

    client = KakaoLocalClient(KAKAO_API_KEY)
    coords = await client.geocode(address)
    if not coords and apt_name:
        coords = await client.geocode_keyword(apt_name, region_hint=address)
    if not coords:
        return {}
    x, y = coords

    subway_docs = await client.category_search("SW8", x=x, y=y, radius=500)
    bus_docs = await client.keyword_search("버스정류장", x=x, y=y, radius=500)
    train_docs = await client.keyword_search("기차역", x=x, y=y, radius=500)
    airport_docs = await client.keyword_search("공항", x=x, y=y, radius=500)
    school_docs = await client.category_search("SC4", x=x, y=y, radius=500)
    mart_docs = await client.category_search("MT1", x=x, y=y, radius=500)
    park_docs = await client.category_search("PK6", x=x, y=y, radius=500)
    department_docs = await client.keyword_search("백화점", x=x, y=y, radius=500)
    sports_docs = await client.keyword_search("체육시설", x=x, y=y, radius=500)
    hospital_docs = await client.category_search("HP8", x=x, y=y, radius=500)
    health_docs = await client.keyword_search("보건소", x=x, y=y, radius=500)

    transit = merge_places(
        normalize_places(subway_docs, source="지하철역"),
        normalize_places(
            bus_docs,
            source="광역/간선버스",
            include_if=lambda doc: "버스" in (doc.get("category_name") or "") or "정류장" in (doc.get("place_name") or ""),
        ),
        normalize_places(train_docs, source="기차역"),
        normalize_places(airport_docs, source="공항"),
        limit=10,
    )
    schools = merge_places(
        normalize_places(
            school_docs,
            source="학교",
            include_if=lambda doc: (doc.get("place_name") or "").endswith("초등학교") or (doc.get("place_name") or "").endswith("중학교"),
        ),
        limit=10,
    )
    life = merge_places(
        normalize_places(mart_docs, source="대형마트"),
        normalize_places(department_docs, source="백화점"),
        normalize_places(park_docs, source="공원"),
        normalize_places(sports_docs, source="체육시설"),
        limit=10,
    )
    medical = merge_places(
        normalize_places(hospital_docs, source="병원"),
        normalize_places(health_docs, source="보건소"),
        limit=10,
    )

    return {
        "_location_source": "kakao",
        "location_intro": _build_sales_location_intro(apt_name, address, transit, schools, life, medical),
        "subway_score": score_from_distance(_nearest_distance(transit), thresholds=(250, 400, 500, 700)),
        "subway_detail": _render_place_list_html(
            transit,
            empty_text="반경 500m 이내에서 확인된 교통 거점이 없습니다.",
            columns=1,
        ),
        "school_score": score_from_distance(_nearest_distance(schools), thresholds=(200, 350, 500, 700)),
        "school_detail": _render_place_list_html(
            schools,
            empty_text="반경 500m 이내 초등학교·중학교 정보가 확인되지 않았습니다.",
            columns=2,
        ),
        "life_score": score_from_distance(_nearest_distance(life), thresholds=(200, 350, 500, 700)),
        "life_detail": _render_place_list_html(
            life,
            empty_text="반경 500m 이내 주요 생활편의시설 정보가 확인되지 않았습니다.",
            columns=1,
        ),
        "medical_score": score_from_distance(_nearest_distance(medical), thresholds=(200, 350, 500, 700)),
        "medical_detail": _render_place_list_html(
            medical,
            empty_text="반경 500m 이내 의료기관 정보가 확인되지 않았습니다.",
            columns=1,
        ),
    }


def _fallback_location_analysis(facts: dict, notice_text: str) -> dict:
    """입지 분석을 LLM 없이 3개 섹션 HTML로 구성한다."""
    text = notice_text or ""
    apt_name = facts.get("apt_name", "")
    location = facts.get("location", "") or facts.get("supply_location", "")

    location_section = _extract_section_text(text, "입지 정보")
    section_lines = [line.strip() for line in location_section.splitlines() if line.strip()]
    section_text = " ".join(section_lines[:3])

    transit = _extract_first_match(
        text,
        (
            r"(신분당선[^\n]+)",
            r"([가-힣]+역\s*도보\s*\d+분)",
            r"([가-힣]+선\s*[^\n]+)",
        ),
    )
    school = _extract_first_match(
        text,
        (
            r"(배정학교[^\n]+)",
            r"([가-힣]+초등학교[^\n]*)",
            r"([가-힣]+중학교[^\n]*)",
        ),
    )
    life = _extract_first_match(
        text,
        (
            r"(백화점[^\n]+)",
            r"(테크노밸리[^\n]+)",
            r"(마트[^\n]+)",
        ),
    )
    medical = _extract_first_match(text, (r"([가-힣]+병원[^\n]*)",))

    transit_items = [
        transit or f"{location or apt_name} 기준 주요 이동 동선은 공고문과 현장 생활권을 함께 보면서 판단하는 편이 안전합니다.",
        "주요 업무지구 또는 생활권으로 이어지는 도로 접근성이 실거주 만족도를 좌우하는 핵심 포인트입니다.",
        "대중교통 환승 동선과 자차 이동 동선을 함께 확인하면 실제 체감 입지를 더 정확하게 읽을 수 있습니다.",
    ]
    school_items = [
        school or f"{apt_name} 인근 학군과 배정 가능 학교는 교육청 기준 자료를 함께 확인하는 것이 좋습니다.",
        "초등학교 접근성과 중학교 진학 동선을 같이 보면 가족 단위 실거주 수요가 느끼는 장점이 더 선명해집니다.",
        "주변 주거지 성숙도와 생활 인프라 밀도는 자녀 교육 환경의 체감 품질에 직접 연결되는 요소입니다.",
    ]
    life_items = [
        f"{apt_name}는 {facts.get('supply_scale') or '공급 규모'}를 바탕으로 지역 내 새로운 주거 선택지로 읽히는 단지입니다.",
        life or f"{location or apt_name} 생활권의 편의시설 접근성은 실제 거주 편의성을 판단하는 핵심 기준입니다.",
        medical or f"의료·생활 기반시설은 {location or apt_name} 주변 생활권을 기준으로 추가 확인할 만합니다.",
    ]

    location_intro = _limit_sentences(
        f"{apt_name}는 {location or '공고문상 공급위치'}에 들어서는 단지로, "
        f"{section_text or '교통과 교육, 생활 인프라의 균형을 함께 살펴볼 만한 곳입니다.'} "
        f"실거주 관점에서는 출퇴근 동선과 생활권 완성도를 중심으로 장점을 읽어보는 접근이 유효합니다."
    )

    return {
        "location_intro": location_intro,
        "subway_score": "",
        "subway_detail": _html_list(transit_items),
        "school_score": "",
        "school_detail": _html_list(school_items),
        "life_score": "",
        "life_detail": _html_list(life_items),
        "medical_score": "",
        "medical_detail": "",
    }


def _fallback_content_generation(facts: dict, location_data: dict) -> dict:
    """LLM 없이도 렌더링 가능한 기본 콘텐츠를 만든다."""
    apt_name = facts.get("apt_name", "미확인 단지")
    location = facts.get("location", "") or facts.get("supply_location", "")
    supply_type = facts.get("supply_type", "")
    price_range = facts.get("price_range", "")
    unit_types = facts.get("unit_types", []) or []
    rank1_date = facts.get("rank1_date", "-")
    winner_date = facts.get("winner_date", "-")
    contract_ratio = str(facts.get("contract_ratio") or "10")
    midterm_ratio = str(facts.get("midterm_ratio") or "60")
    midterm_count = str(facts.get("midterm_count") or "6")
    balance_ratio = str(facts.get("balance_ratio") or "30")
    regulated_zone = facts.get("regulated_zone") or "공고문 확인 필요"
    readmission_limit = facts.get("readmission_limit") or "공고문 확인 필요"
    live_requirement = facts.get("live_requirement") or "공고문 확인 필요"
    price_cap = facts.get("price_cap") or "공고문 확인 필요"

    unit_names = ", ".join(ut.get("type_name", "") for ut in unit_types[:4] if ut.get("type_name")) or "주요 타입"
    type_summary = (
        f"타입은 {unit_names} 중심으로 구성되어 있으며, 가격대는 {price_range or '공고문 확인 필요'}입니다."
    )

    qa_blocks = [
        {
            "question": "이 단지는 어떤 점을 먼저 봐야 하나요?",
            "answer": (
                f"{apt_name}은(는) {location or '공고문상 공급위치'}에 들어서는 공고로, "
                f"가장 먼저 일정과 규제, 타입별 가격대를 함께 보는 것이 중요합니다. "
                f"현재 확인되는 가격 범위는 {price_range or '공고문 확인 필요'}이고, "
                f"1순위 접수는 {rank1_date or '공고문 확인 필요'}에 진행됩니다. "
                f"단지의 장점은 입지와 공급구성이 맞아떨어질 때 더 선명해지므로, 교통·교육·생활편의 동선을 함께 확인해야 합니다."
            ),
        },
        {
            "question": "규제와 청약 제한은 어떻게 해석하면 되나요?",
            "answer": (
                f"규제 정보는 {regulated_zone}, 전매제한은 {facts.get('resale_restriction') or '공고문 확인 필요'}, "
                f"재당첨 제한은 {readmission_limit}, 거주의무기간은 {live_requirement}, 분양가상한제는 {price_cap}로 정리됩니다. "
                f"실제 청약 가능 여부는 세대원 구성, 거주지역, 청약통장 가입기간, 예치금 조건이 함께 맞아야 판단할 수 있습니다. "
                f"따라서 규제 문구 하나만 보지 말고 공고문 전체와 청약홈 안내를 함께 대조하는 것이 안전합니다."
            ),
        },
        {
            "question": "자금계획은 어떻게 준비해야 하나요?",
            "answer": (
                f"자금계획은 계약금 {contract_ratio}%, 중도금 {midterm_ratio}%({midterm_count}회), 잔금 {balance_ratio}%라는 흐름으로 이해하면 됩니다. "
                f"여기서는 비율과 납부 시점만 먼저 이해하고, 실제 납부금액은 선택 타입과 옵션, 대출 조건을 반영해 공고문 기준으로 다시 확인하는 것이 안전합니다. "
                f"특히 {apt_name}처럼 타입별 분양가 차이가 있는 단지는 동일 단지 안에서도 실제 필요 현금이 달라질 수 있으므로, "
                f"희망 평형을 정한 뒤 분양사 안내와 금융 조건을 함께 대조해야 합니다."
            ),
        },
    ]

    seo_tags = [
        apt_name,
        location.split()[0] if location else "청약",
        supply_type or "분양",
        "청약일정",
        "분양가",
        "규제지역",
        "자금계획",
    ]

    return {
        "post_title": f"{apt_name} 청약 핵심 정리와 체크포인트",
        "post_subtitle": f"{location or '공고문상 공급위치'} 기준으로 꼭 볼 규제와 일정",
        "apt_intro": (
            f"{apt_name}은(는) {location or '공고문상 공급위치'}에 위치한 {supply_type or '분양'} 공고입니다. "
            f"{type_summary} 일정과 규제, 자금 흐름을 한 번에 정리해 두면 청약 판단이 훨씬 쉬워집니다."
        ),
        "location_intro": location_data.get("location_intro")
        or f"{apt_name}의 입지는 {location or '공고문상 공급위치'}를 중심으로 교통과 생활권을 함께 보는 것이 핵심입니다.",
        "financial_intro": (
            f"자금계획은 계약금 {contract_ratio}%, 중도금 {midterm_ratio}%({midterm_count}회), 잔금 {balance_ratio}% 구조로 이해하면 됩니다. "
            f"실제 납부금액은 선택 타입과 옵션, 대출 조건에 따라 달라지므로 비율과 일정부터 먼저 확인하는 편이 안전합니다."
        ),
        "qa_intro": "아래 Q&A에서는 일정, 규제, 자금계획 순서로 실무적으로 필요한 포인트만 다시 정리합니다.",
        "schedule_desc": (
            f"특별공급과 1순위, 2순위 일정은 각각 공고문 일정표를 기준으로 확인해야 합니다. "
            f"대표 청약일은 {rank1_date or '공고문 확인 필요'}이며, 당첨자 발표는 {winner_date or '공고문 확인 필요'}입니다."
        ),
        "unit_type_desc": (
            f"타입별 공급 정보는 {type_summary} 실제 선택은 가격대와 면적, 공급 세대수를 함께 비교해야 합니다."
        ),
        "tax_desc": (
            f"세금 측면에서는 취득세율 {facts.get('acquisition_tax_rate') or '1~3%'}를 기본값으로 보고, "
            f"입주 후 보유세와 양도세는 실거주 계획에 맞춰 별도로 검토해야 합니다."
        ),
        "qa_blocks": qa_blocks,
        "seo_tags": seo_tags,
        "subway_detail": location_data.get("subway_detail", "교통 접근성은 공고문과 지도를 함께 확인해야 합니다."),
        "school_detail": location_data.get("school_detail", "학군 정보는 교육청 자료와 함께 확인해야 합니다."),
        "life_detail": location_data.get("life_detail", "생활편의시설은 지도 기반으로 재확인하는 것이 좋습니다."),
        "medical_detail": location_data.get("medical_detail", "의료 인프라는 실제 생활권 반경을 기준으로 확인해야 합니다."),
    }


_QA_REQUIRED_NOTE = (
    '<br><span style="font-size:13px; color:#999;">'
    '※ 개인 조건(소득·자산·주택 수 등)에 따라 결과가 크게 다를 수 있으므로, '
    '반드시 분양사 및 관련 기관에 직접 확인하세요.</span>'
)

_RISKY_CONTENT_PATTERNS = (
    r"시세차익",
    r"투자\s*가치",
    r"가격이\s*오를",
    r"상승\s*가능성",
    r"수익",
    r"당첨\s*가능",
    r"당첨을\s*노려",
    r"유리합",
    r"추천드",
    r"신청하",
    r"자격이\s*됩니다",
    r"적합합",
)

_FINANCIAL_CONFLICT_PATTERNS = (
    r"명시되지\s*않",
    r"확인되지\s*않",
    r"알\s*수\s*없",
)


def _contains_risky_claim(text: str) -> bool:
    if not text:
        return False
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in _RISKY_CONTENT_PATTERNS)


def _ensure_qa_required_note(answer: str) -> str:
    answer = (answer or "").strip()
    if not answer:
        return _QA_REQUIRED_NOTE.lstrip("<br>")
    if "※ 개인 조건" in answer:
        return answer
    return f"{answer}{_QA_REQUIRED_NOTE}"


def _has_financial_conflict(answer: str, facts: dict) -> bool:
    text = (answer or "").strip()
    if not text:
        return False
    if not any(re.search(pattern, text, re.IGNORECASE) for pattern in _FINANCIAL_CONFLICT_PATTERNS):
        return False
    financial_fields = (
        facts.get("contract_ratio"),
        facts.get("midterm_ratio"),
        facts.get("balance_ratio"),
        facts.get("loan_info"),
    )
    return any(str(value or "").strip() for value in financial_fields)


def _sanitize_generated_content(content: dict, facts: dict, location_data: dict) -> dict:
    """과장·투자성·개인판단이 섞인 생성 결과를 보수적으로 보정한다."""
    fallback = _fallback_content_generation(facts, location_data)
    sanitized = dict(content or {})

    narrative_keys = (
        "apt_intro",
        "location_intro",
        "financial_intro",
        "qa_intro",
        "schedule_desc",
        "unit_type_desc",
        "tax_desc",
    )
    for key in narrative_keys:
        value = str(sanitized.get(key) or "").strip()
        if not value or _contains_risky_claim(value):
            sanitized[key] = fallback.get(key, "")

    qa_blocks = sanitized.get("qa_blocks")
    if not isinstance(qa_blocks, list) or not qa_blocks:
        sanitized["qa_blocks"] = fallback["qa_blocks"]
    else:
        safe_blocks = []
        for qa in qa_blocks:
            question = str((qa or {}).get("question") or "").strip()
            answer = str((qa or {}).get("answer") or "").strip()
            if (
                not question
                or not answer
                or _contains_risky_claim(question)
                or _contains_risky_claim(answer)
                or _has_financial_conflict(answer, facts)
            ):
                safe_blocks = fallback["qa_blocks"]
                break
            safe_blocks.append(
                {
                    "question": question,
                    "answer": _ensure_qa_required_note(answer),
                }
            )
        sanitized["qa_blocks"] = safe_blocks

    for key in ("post_title", "post_subtitle"):
        value = str(sanitized.get(key) or "").strip()
        if not value or _contains_risky_claim(value):
            sanitized[key] = fallback.get(key, "")

    seo_tags = sanitized.get("seo_tags")
    if not isinstance(seo_tags, list) or not seo_tags:
        sanitized["seo_tags"] = fallback["seo_tags"]

    return sanitized
async def agent_regulatory_extraction(notice_text: str) -> dict:
    """Agent 0: 청약규제정보 전문 추출 (GPT-5.4)"""
    print("  [Agent 0] 청약규제정보 추출 시작...")
    try:
        raw = await _call_openai_json(
            system="JSON만 출력하세요. 마크다운 코드블록 없이 순수 JSON만 출력합니다. 추측하지 마세요.",
            user=REGULATORY_EXTRACTION_PROMPT.format(notice_text=notice_text),
            model=LLM_EXTRACT_MODEL,
            max_tokens=1500,
        )
        try:
            regulatory = json.loads(raw)
        except json.JSONDecodeError:
            import re as _re
            m = _re.search(r'\{.*\}', raw, _re.DOTALL)
            regulatory = json.loads(m.group()) if m else {}

        # 추출된 값 로깅
        non_null = {k: v for k, v in regulatory.items() if v is not None}
        if non_null:
            print(f"  [Agent 0] 추출됨: {non_null}")
        else:
            print(f"  [Agent 0] 추출된 규제정보 없음 (공고에 명시 안 됨)")
        return regulatory
    except Exception as e:
        print(f"  [Agent 0] 규제정보 추출 실패 ({e})")
        return {}


async def agent_fact_extraction(notice_text: str) -> dict:
    """Agent 1: 공고문에서 팩트를 추출하여 구조화된 JSON 반환 (GPT-5.4)"""
    print("  [Agent 1] 팩트 추출 시작...")
    if not OPENAI_API_KEY.strip():
        print("  [Agent 1] OPENAI_API_KEY 미설정 → 결정론적 폴백 사용")
        facts = _fallback_fact_extraction(notice_text)
        print(f"  [Agent 1] 완료: {facts.get('apt_name', '미확인')} 추출")
        return facts
    raw = await _call_openai_json(
        system="JSON만 출력하세요. 마크다운 코드블록 없이 순수 JSON만 출력합니다. 추측하지 마세요.",
        user=FACT_EXTRACTION_PROMPT.format(notice_text=notice_text),
        model=LLM_EXTRACT_MODEL,
    )
    try:
        facts = json.loads(raw)
    except json.JSONDecodeError:
        import re
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        facts = json.loads(m.group()) if m else {}
        if not facts:
            print("  [Agent 1] JSON 파싱 실패 → 결정론적 폴백 사용")
            facts = _fallback_fact_extraction(notice_text)

    # 자격 정보가 비어 있으면 전용 재추출을 한 번 더 수행한다.
    if facts and not _has_eligibility_data(facts):
        print("  [Agent 1] 신청자격 누락 감지 → 전용 재추출...")
        try:
            raw_eligibility = await _call_openai_json(
                system="JSON만 출력하세요. 마크다운 코드블록 없이 순수 JSON만 출력합니다. 추측하지 마세요.",
                user=ELIGIBILITY_EXTRACTION_PROMPT.format(notice_text=notice_text),
                model=LLM_EXTRACT_MODEL,
                max_tokens=2500,
            )
            try:
                eligibility = json.loads(raw_eligibility)
            except json.JSONDecodeError:
                import re as _re
                m = _re.search(r'\{.*\}', raw_eligibility, _re.DOTALL)
                eligibility = json.loads(m.group()) if m else {}

            for key in ("eligibility_special", "eligibility_rank1", "eligibility_rank2"):
                if eligibility.get(key):
                    facts[key] = eligibility.get(key)
            if _has_eligibility_data(facts):
                print("  [Agent 1] 신청자격 재추출 완료")
        except Exception as e:
            print(f"  [Agent 1] 신청자격 재추출 실패 ({e})")

    if facts and not _has_eligibility_data(facts):
        print("  [Agent 1] 신청자격 폴백 적용 (기존 보강 데이터)...")
        try:
            from patch_posts4_eligibility import get_eligibility as _get_eligibility

            fallback = _get_eligibility(facts.get("apt_name", ""))
            for key in ("eligibility_special", "eligibility_rank1", "eligibility_rank2"):
                if fallback.get(key):
                    facts[key] = fallback.get(key)
            if _has_eligibility_data(facts):
                print("  [Agent 1] 신청자격 폴백 적용 완료")
        except Exception as e:
            print(f"  [Agent 1] 신청자격 폴백 실패 ({e})")

    if facts and not _has_financial_data(facts):
        print("  [Agent 1] 자금계획 누락 감지 → 전용 재추출...")
        try:
            raw_financial = await _call_openai_json(
                system="JSON만 출력하세요. 마크다운 코드블록 없이 순수 JSON만 출력합니다. 추측하지 마세요.",
                user=FINANCIAL_EXTRACTION_PROMPT.format(notice_text=notice_text),
                model=LLM_EXTRACT_MODEL,
                max_tokens=2000,
            )
            try:
                financial = json.loads(raw_financial)
            except json.JSONDecodeError:
                import re as _re
                m = _re.search(r'\{.*\}', raw_financial, _re.DOTALL)
                financial = json.loads(m.group()) if m else {}

            for key in ("contract_ratio", "contract_amount", "midterm_ratio", "midterm_count", "balance_ratio", "loan_info"):
                if financial.get(key) not in (None, "", []):
                    facts[key] = financial.get(key)
            if _has_financial_data(facts):
                print("  [Agent 1] 자금계획 재추출 완료")
        except Exception as e:
            print(f"  [Agent 1] 자금계획 재추출 실패 ({e})")

    print(f"  [Agent 1] 완료: {facts.get('apt_name', '미확인')} 추출")
    return facts


# ──────────────────────────────────────────────────
# Agent 2: 입지 분석 (Gemini)
# ──────────────────────────────────────────────────

LOCATION_ANALYSIS_PROMPT = """당신은 한국 부동산 입지 분석 전문가입니다.
Google Search Grounding으로 수집한 실제 데이터를 바탕으로, 다음 4가지 항목으로 입지를 분석하세요.

[분석 항목]
1. 총평: 위치·교통·생활 환경의 종합 평가 (1문장~2문장, 핵심 강점만)
2. 교통 및 입지: 지하철·버스 등 대중교통 접근성, 주요 거점까지의 거리/시간
3. 교육 및 주거 환경: 학교 배정, 학군 수준, 주거 인프라 (병원, 은행 등)
4. 단지 특징: 단지 규모, 신축/재개발 특성, 주변 생활권 특성

[작성 기준]
- Google Search에서 수집한 '사실'을 기반으로 분석 관점에서 재작성
- 단순 나열이 아닌 "분석적 평가" 형식
  예: "지하철역까지 도보 5분" → "신분당선과 수도권 주요 거점이 20~30분 이내 접근 가능해, 직장 출근과 지역 이동이 수월합니다"
- 사실에 근거하되, 해석·평가는 긍정적 관점으로 전개
- 고유명사(역명, 학교명, 시설명)는 Google Search 결과에서 확인된 것만 사용
- 과장 금지: "강남급 학군" 같은 표현 X, "학교 수와 위치를 고려할 때" 같은 중립적 표현 O

[출력 구조 - 반드시 JSON]
{{
  "location_summary": "총평: 1~2문장",
  "location_intro": "위치 기본 설명 (1문장)",
  "subway_detail": "<ul><li>교통항목1</li><li>교통항목2</li><li>교통항목3</li></ul>",
  "school_detail": "<ul><li>교육항목1</li><li>교육항목2</li><li>교육항목3</li></ul>",
  "life_detail": "<ul><li>특징항목1</li><li>특징항목2</li><li>특징항목3</li></ul>"
}}

[단지 정보]:
{facts_json}

주의: JSON만 출력하세요. 마크다운 코드블록 없이 순수 JSON만 출력합니다."""

LOCATION_VERIFY_PROMPT = """아래는 AI가 생성한 입지 분석입니다.
사실관계와 문장 구조를 검토하고, 부정확하거나 과한 표현이 있으면 수정하세요.

검증 기준:
1. facts에 없는 고유명사·역명·학교명·시설명을 새로 만들지 않았는가?
2. 투자수익, 시세차익, 가격상승, 당첨 가능성 예측이 들어가 있지 않은가?
3. location_intro는 3문장 이내인가?
4. subway_detail / school_detail / life_detail 은 각각 <ul>...</ul> HTML 목록인가?
5. "교통 및 입지 여건 / 교육 및 주거 환경 / 단지 특징"에 맞는 내용으로 구분되어 있는가?

[단지명]: {apt_name}
[위치]: {location}

[Gemini 생성 입지 분석]:
{location_json}

수정 필요 시 수정된 JSON 반환. 수정 없으면 원본 그대로 반환. JSON만 출력."""

_LOCATION_KEYS = (
    "location_summary", "location_intro", "subway_detail",
    "school_detail", "life_detail",
)


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def _limit_sentences(text: str, max_sentences: int = 3) -> str:
    cleaned = re.sub(r"\s+", " ", _strip_html(text))
    if not cleaned:
        return ""
    parts = [part.strip() for part in re.split(r"(?<=[.!?。！？])\s+", cleaned) if part.strip()]
    if len(parts) <= max_sentences:
        return cleaned
    return " ".join(parts[:max_sentences]).strip()


def _html_list(items: list[str]) -> str:
    normalized = [re.sub(r"\s+", " ", (item or "").strip()) for item in items if (item or "").strip()]
    if not normalized:
        return "<ul><li>공고문 기준으로 추가 확인이 필요한 항목입니다.</li></ul>"
    lis = "".join(f"<li>{item}</li>" for item in normalized[:4])
    return f"<ul>{lis}</ul>"


def _normalize_location_output(result: dict, facts: dict, notice_text: str = "") -> dict:
    apt_name = facts.get("apt_name", "해당 단지")
    location = facts.get("location", "") or facts.get("supply_location", "") or "공급 위치"

    intro = _limit_sentences(result.get("location_intro", ""))
    if not intro:
        intro = _limit_sentences(
            f"{apt_name}는 {location} 생활권을 바탕으로 교통과 주거 편의성을 함께 살펴볼 만한 단지입니다. "
            f"이번 공고에서는 실거주 관점에서 확인해야 할 장점 위주로 핵심만 정리했습니다."
        )

    normalized = {
        "location_intro": intro,
        "subway_score": "",
        "subway_detail": result.get("subway_detail", "") or "",
        "school_score": "",
        "school_detail": result.get("school_detail", "") or "",
        "life_score": "",
        "life_detail": result.get("life_detail", "") or "",
        "medical_score": "",
        "medical_detail": "",
    }

    for key in ("subway_detail", "school_detail", "life_detail"):
        value = (normalized.get(key) or "").strip()
        if not value:
            continue
        if not value.lstrip().startswith("<ul"):
            chunks = [line.strip("-• \t") for line in re.split(r"[\r\n]+", _strip_html(value)) if line.strip()]
            normalized[key] = _html_list(chunks)

    if not normalized["subway_detail"] or normalized["subway_detail"] == "<ul></ul>":
        fallback = _fallback_location_analysis(facts, notice_text)
        normalized["subway_detail"] = fallback["subway_detail"]
    if not normalized["school_detail"] or normalized["school_detail"] == "<ul></ul>":
        fallback = _fallback_location_analysis(facts, notice_text)
        normalized["school_detail"] = fallback["school_detail"]
    if not normalized["life_detail"] or normalized["life_detail"] == "<ul></ul>":
        fallback = _fallback_location_analysis(facts, notice_text)
        normalized["life_detail"] = fallback["life_detail"]

    return normalized


async def agent_location_analysis_gemini(facts: dict) -> dict:
    """Agent 2: Gemini 3.5 Pro 기반 입지 분석 생성."""
    print(f"  [Agent 2] 입지 분석 시작 ({LLM_LOCATION_MODEL})...")
    if not GEMINI_API_KEY:
        print("  [Agent 2] GEMINI_API_KEY 미설정 → 결정론적 폴백 사용")
        return _fallback_location_analysis(facts, "")
    try:
        from google import genai as google_genai
        from google.genai import types as genai_types

        client = google_genai.Client(api_key=GEMINI_API_KEY)
        resp = client.models.generate_content(
            model=LLM_LOCATION_MODEL,
            contents=LOCATION_ANALYSIS_PROMPT.format(
                facts_json=json.dumps(facts, ensure_ascii=False, indent=2)
            ),
            config=genai_types.GenerateContentConfig(
                system_instruction="JSON만 출력하세요. 마크다운 코드블록 없이 순수 JSON만 출력합니다.",
                tools=[
                    genai_types.Tool(
                        google_search=genai_types.GoogleSearch()
                    )
                ]
            ),
        )
        raw = resp.text.strip()
        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            import re as _re
            m = _re.search(r"\{.*\}", raw, _re.DOTALL)
            result = json.loads(m.group()) if m else {}
        result = _normalize_location_output(result, facts)
        print(f"  [Agent 2] 완료: subway_detail={result.get('subway_detail','')[:40]}")
        return result
    except Exception as e:
        print(f"  [Agent 2] Gemini 오류 ({e}) → 결정론적 폴백 사용")
        return _fallback_location_analysis(facts, "")


async def agent_location_analysis_gpt(facts: dict) -> dict:
    """호환성용 래퍼. 입지 분석은 Gemini 경로를 사용한다."""
    return await agent_location_analysis_gemini(facts)


async def agent_location_verify_gemini(location_data: dict, facts: dict) -> dict:
    """Agent 3: Gemini로 입지 분석 검증·교정"""
    print(f"  [Agent 3] 입지 분석 검증 시작 ({LLM_LOCATION_MODEL})...")
    if not location_data:
        return location_data
    if not GEMINI_API_KEY:
        print("  [Agent 3] GEMINI_API_KEY 미설정 → 검증 건너뜀")
        return location_data
    try:
        from google import genai as google_genai
        from google.genai import types as genai_types

        client = google_genai.Client(api_key=GEMINI_API_KEY)
        resp = client.models.generate_content(
            model=LLM_LOCATION_MODEL,
            contents=LOCATION_VERIFY_PROMPT.format(
                apt_name=facts.get("apt_name", ""),
                location=facts.get("location", ""),
                location_json=json.dumps(location_data, ensure_ascii=False, indent=2),
            ),
            config=genai_types.GenerateContentConfig(
                system_instruction="JSON만 출력하세요. 마크다운 코드블록 없이 순수 JSON만 출력합니다.",
            ),
        )
        raw = resp.text.strip()
        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            import re as _re
            m = _re.search(r'\{.*\}', raw, _re.DOTALL)
            result = json.loads(m.group()) if m else location_data
        result = _normalize_location_output(result, facts)
        print(f"  [Agent 3] 검증 완료: subway_detail={result.get('subway_detail','')[:40]}")
        return result
    except Exception as e:
        print(f"  [Agent 3] Gemini 검증 오류 ({e}) → 원본 결과 그대로 사용")
        return location_data


async def agent_location_verify_gpt(location_data: dict, facts: dict) -> dict:
    """Agent 3: GPT-5.4로 입지 분석 검증·교정"""
    print("  [Agent 3] 입지 분석 검증 시작 (GPT-5.4)...")
    if not location_data:
        return location_data
    if location_data.get("_location_source") == "kakao":
        print("  [Agent 3] Kakao 실데이터 경로 → 별도 LLM 검증 생략")
        return location_data
    try:
        raw = await _call_openai_json(
            system=(
                "당신은 한국 지리·부동산 전문가입니다.\n"
                "JSON만 출력하세요. 마크다운 코드블록 없이 순수 JSON만 출력합니다."
            ),
            user=LOCATION_VERIFY_PROMPT.format(
                apt_name=facts.get("apt_name", ""),
                location=facts.get("location", ""),
                location_json=json.dumps(location_data, ensure_ascii=False, indent=2),
            ),
            model=LLM_CONTENT_MODEL,
            max_tokens=2000,
        )
        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            import re as _re
            m = _re.search(r'\{.*\}', raw, _re.DOTALL)
            result = json.loads(m.group()) if m else location_data
        print(f"  [Agent 3] 검증 완료: subway_detail={result.get('subway_detail','')[:40]}")
        return result
    except Exception as e:
        print(f"  [Agent 3] GPT-5.4 검증 오류 ({e}) → Gemini 결과 그대로 사용")
        return location_data


# ──────────────────────────────────────────────────
# Agent 4: 블로그 콘텐츠 생성
# ──────────────────────────────────────────────────
CONTENT_GEN_PROMPT = """
당신은 네이버 블로그 콘텐츠 전문가이자 분양 담당 마케터입니다.
독자는 청약에 관심 있는 20~40대 실수요자입니다.

글쓰기 방식: 마케팅 담당자가 고객을 처음 만나 대화하듯 자연스럽고 친근한 스토리텔링으로 작성하세요.
딱딱한 공문서 스타일이 아닌, 독자가 술술 읽히는 산문체로 작성해야 합니다.

【공급세대수 vs 총세대수 구분 원칙 — 반드시 준수】
- apt_intro에서 "이번 청약 공급 물량(공급세대수)"과 "단지 전체 세대수(total_households)"를 절대 혼용하지 마세요.
- total_households(단지 전체 세대수)가 있는 경우: "총 X세대 규모 단지"라고 언급하되, 이번 공급 물량(공급세대수)은 별도로 "이번 청약 Y세대 모집"처럼 명확히 구분하여 서술.
- total_households가 null인 경우: 단지 규모(총세대수) 추측·언급 절대 금지. 이번 공급세대수만 언급.

【Q&A 작성 절대 원칙 — 반드시 준수】
아래 금지 원칙을 단 하나라도 위반하면 답변 전체가 무효입니다.

① 개인 조건 판단 절대 금지
   - "당신은 자격이 됩니다", "신청하세요", "유리합니다" 등 특정인에게 적합 여부를 판단하는 표현 금지
   - 소득·자산·가점·가족 구성 등 독자의 개인 조건을 전제로 한 결론 도출 금지

② 투자·수익 예측 절대 금지
   - "시세차익 기대", "오를 가능성", "투자 가치 있음" 등 부동산 가격 전망 일체 금지

③ 법령·세금·대출 한도 단정 금지
   - 취득세율·대출한도·DSR 계산값 등을 "확정"처럼 단정하지 말 것
   - 반드시 "공고문 및 관련 기관에서 직접 확인 필요" 문구 포함

④ 답변 말미 필수 문구
   - 모든 Q&A 답변 마지막에 반드시 다음 문구 포함:
     <br><span style="font-size:13px; color:#999;">※ 개인 조건(소득·자산·주택 수 등)에 따라 결과가 크게 다를 수 있으므로, 반드시 분양사 및 관련 기관에 직접 확인하세요.</span>

⑤ 자금 계획 작성 절대 원칙
   - 계약금/중도금/잔금은 비율과 납부 구조만 설명
   - 분양가에 비율을 곱해 실제 납부금액을 계산하지 말 것
   - "약 8,000만원", "약 1.2억원" 같은 계산형 금액 문구 생성 금지
   - 공고문에 실제 납부금액이 명시된 경우에만 그 금액을 그대로 인용 가능
   - 실제 대출 가능 금액, 세금 액수, 실수령액 계산 금지

[단지 정보]:
{facts_json}

다음 JSON 형식으로 출력하세요:
{{
  "post_title": "50자 이내 후킹 제목 (단지명+위치+분양가 또는 핵심 포인트 포함)",
  "post_subtitle": "30자 이내 부제목 (이 글을 읽어야 하는 이유)",
  "seo_tags": ["단지명태그", "지역태그", "청약관련태그", ...최대10개],

  "apt_intro": "150~200자. 반드시 '안녕하세요. 복잡한 청약 공고문을 쉽게 정리해 드리는 정과장입니다. 오늘은 ' 으로 시작. 이어서 단지명과 가장 큰 매력 포인트를 자연스럽게 연결. <strong> 태그 사용 가능.",

  "location_intro": "100~150자. 해당 지역의 분위기와 생활 환경을 친근하게 설명. 지역 특색과 장점 중심. 독자가 그 동네를 떠올릴 수 있도록 묘사.",

  "financial_intro": "80~100자. 자금 계획의 중요성을 공감 가는 방식으로 도입. 단, 실제 납부금액 계산은 하지 말고 비율과 일정 확인이 중요하다는 방향으로만 작성.",

  "qa_intro": "60~80자. '청약 준비하면서 많은 분들이 공통으로 궁금해 하는 내용들을 모았어요' 같은 톤. 댓글 유도·구독 유도·공유 요청 등 일체 금지. 순수하게 정보 안내로만 마무리.",

  "qa_blocks": [
    {{
      "question": "실수요자가 실제로 궁금해하는 질문 (중도금대출/주담대 키워드 포함)",
      "answer": "300~500자. 공고문 팩트 기반 설명. 개인 적합 여부 판단 금지. <strong>강조</strong>, <br> 줄바꿈 사용 가능. 답변 말미에 ※ 개인 조건 확인 필요 문구 필수."
    }},
    {{
      "question": "특별공급/청약 자격 관련 (생애최초/신혼부부 키워드)",
      "answer": "300~500자. 자격 요건 객관적 나열만. '귀하는 해당됩니다' 류 판단 절대 금지. 답변 말미 ※ 문구 필수."
    }},
    {{
      "question": "입지/학군/교통 관련 (역세권/학군 키워드)",
      "answer": "300~500자. 공고문·공개 데이터 기반 사실 서술만. 답변 말미 ※ 문구 필수."
    }},
    {{
      "question": "취득세/세금/자금계획 관련 (취득세/DTI 키워드)",
      "answer": "300~500자. 세율·한도 단정 금지. '일반적인 기준' 수준으로만 안내. 계약금/중도금/잔금을 실제 금액으로 계산하지 말 것. 답변 말미 ※ 문구 필수."
    }},
    {{
      "question": "인테리어/발코니 확장 관련 (아파트인테리어 키워드)",
      "answer": "300~500자. 답변 말미 ※ 문구 필수."
    }},
    {{
      "question": "청약 가점/당첨 전략 관련 (가점제/추첨제 키워드)",
      "answer": "300~500자. 특정 가점 점수로 '당첨 가능' 단정 절대 금지. 경쟁률·제도 구조 설명 수준으로만. 답변 말미 ※ 문구 필수."
    }}
  ],

  "schedule_desc": "청약 일정 타임라인 블록 앞에 들어갈 설명 (80~120자). '특별공급부터 당첨자 발표까지, 날짜별로 정리해드릴게요' 같은 자연스러운 연결. 구체적인 날짜 언급 포함.",

  "unit_type_desc": "타입별 분양가 표 앞에 들어갈 설명 (80~130자). 공급 타입 구성의 특징·포인트를 친근하게 설명. '이 단지는 ~타입으로 구성되는데요, ~가 특히 눈에 띄어요' 같은 톤. <strong> 태그 사용 가능.",

  "tax_desc": "세금 표 앞에 들어갈 설명 (80~120자). 취득세·재산세·양도세를 미리 알아야 하는 이유를 공감 가는 방식으로 설명. '내 집 마련 후에도 세금은 계속 따라와요' 같은 톤.",

  "subway_score": "★★★☆☆",
  "subway_detail": "실제 역 이름과 도보 분수 (★★★★★ 도보5분이내 / ★★★★☆ 도보10분 / ★★★☆☆ 도보15분 / ★★☆☆☆ 버스환승 / ★☆☆☆☆ 지하철없음)",
  "school_score": "★★★★☆",
  "school_detail": "초등학교 배정 + 학군 평가 (★★★★★ 학원가+명문중고 / ★★★★☆ 초등+중학군양호 / ★★★☆☆ 초등+중학군보통 / ★★☆☆☆ 원거리배정 / ★☆☆☆☆ 정보없음)",
  "life_score": "★★★☆☆",
  "life_detail": "가장 가까운 대형마트/백화점 (★★★★★ 대형마트+백화점 도보권 / ★★★★☆ 대형마트 10분 / ★★★☆☆ 슈퍼+편의점 / ★★☆☆☆ 차량필요 / ★☆☆☆☆ 편의시설없음)",
  "medical_score": "★★★☆☆",
  "medical_detail": "가장 가까운 종합병원 (★★★★★ 대학병원 도보권 / ★★★★☆ 종합병원 차량5분 / ★★★☆☆ 차량10분 / ★★☆☆☆ 의원급만 / ★☆☆☆☆ 의료기관없음)"
}}
"""

# CTA URL 매핑 (추후 제휴 링크 등록 후 활성화)


async def agent_content_generation(facts: dict) -> dict:
    """Agent 4: 서술형 콘텐츠 + Q&A 생성 (GPT-5.4)"""
    print("  [Agent 4] 콘텐츠 생성 시작 (GPT-5.4)...")
    if not OPENAI_API_KEY.strip():
        print("  [Agent 4] OPENAI_API_KEY 미설정 → 결정론적 폴백 사용")
        content = _fallback_content_generation(facts, {})
        content = _sanitize_generated_content(content, facts, {})
        print(f"  [Agent 4] 완료: Q&A {len(content.get('qa_blocks', []))}개 생성")
        return content
    raw = await _call_openai_json(
        system=(
            "당신은 친근하고 따뜻한 문체로 글을 쓰는 부동산 블로그 전문가입니다.\n"
            "JSON만 출력하세요. 마크다운 코드블록 없이 순수 JSON만 출력합니다.\n"
            "모든 텍스트는 한국어로 작성하며, 독자에게 직접 말을 걸듯 자연스럽고 따뜻하게 작성하세요."
        ),
        user=CONTENT_GEN_PROMPT.format(
            facts_json=json.dumps(facts, ensure_ascii=False, indent=2)
        ),
        model=LLM_CONTENT_MODEL,
        max_tokens=6000,
    )
    try:
        content = json.loads(raw)
    except json.JSONDecodeError:
        import re
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        content = json.loads(m.group()) if m else {}
        if not content:
            print("  [Agent 4] JSON 파싱 실패 → 결정론적 폴백 사용")
            content = _fallback_content_generation(facts, {})
    content = _sanitize_generated_content(content, facts, {})
    print(f"  [Agent 4] 완료: Q&A {len(content.get('qa_blocks', []))}개 생성")
    return content


# ──────────────────────────────────────────────────
# Agent 5: Q&A 팩트체크 (GPT-5.4 mini)
# ──────────────────────────────────────────────────

FACTCHECK_SYSTEM = """당신은 한국 부동산·청약 분야 전문가입니다.
아래 [단지 팩트]와 [Q&A 목록]을 검토하고, 각 답변의 사실 정확성을 점검하세요.

검토 기준:
1. 단지 팩트(분양가·일정·대출조건·세금)와 답변 내용이 일치하는가?
2. 한국 청약제도(특별공급 자격·가점제·전매제한 등)를 정확히 설명하고 있는가?
3. 과장·오해를 유발하는 표현이 없는가?
4. 【필수 점검】 개인 조건 판단 금지 원칙 위반 여부:
   - "당신은 자격이 됩니다", "신청하세요", "유리합니다" 등 개인 적합 여부 판단 표현 → 즉시 삭제·수정
   - 투자 수익·시세 전망 언급 → 즉시 삭제
   - 세금·대출 한도를 확정적으로 단정한 표현 → "일반적 기준" 수준으로 완화
   - 모든 답변 말미에 ※ 개인 조건 확인 필요 문구가 있는지 확인 → 없으면 추가:
     <br><span style="font-size:13px; color:#999;">※ 개인 조건(소득·자산·주택 수 등)에 따라 결과가 크게 다를 수 있으므로, 반드시 분양사 및 관련 기관에 직접 확인하세요.</span>

출력 형식 (JSON만):
{
  "qa_blocks": [
    {
      "question": "원본 질문 그대로",
      "answer": "수정된 답변 (문제없으면 원본 그대로, 문제있으면 정정된 내용으로 교체)",
      "status": "ok" | "corrected",
      "note": "수정 사유 (status=ok이면 빈 문자열)"
    }
  ],
  "overall": "pass" | "fail",
  "summary": "전체 팩트체크 요약 (1~2문장)"
}"""

FACTCHECK_USER_TPL = """[단지 팩트]
{facts_json}

[Q&A 목록]
{qa_json}

위 Q&A 답변을 팩트체크하고 JSON으로 반환하세요."""


async def agent_factcheck_qa(content: dict, facts: dict) -> dict:
    """Agent 5: GPT-5.4 mini로 Q&A 팩트체크 — 오류 답변 자동 정정"""
    print("  [Agent 5] Q&A 팩트체크 시작 (GPT-5.4 mini)...")

    if not OPENAI_API_KEY:
        print("  [Agent 5] OPENAI_API_KEY 미설정 → 팩트체크 건너뜀")
        return _sanitize_generated_content(content, facts, {})

    try:
        user_msg = FACTCHECK_USER_TPL.format(
            facts_json=json.dumps(facts, ensure_ascii=False, indent=2),
            qa_json=json.dumps(content.get("qa_blocks", []), ensure_ascii=False, indent=2),
        )
        raw = await _call_openai_json(
            system=FACTCHECK_SYSTEM,
            user=user_msg,
            model=LLM_FACTCHECK_MODEL,
            max_tokens=3000,
        )

        # JSON 추출
        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            import re
            m = re.search(r'\{.*\}', raw, re.DOTALL)
            result = json.loads(m.group()) if m else None

        if not result:
            print("  [Agent 5] 팩트체크 JSON 파싱 실패 → 원본 유지")
            return _sanitize_generated_content(content, facts, {})

        corrected = result.get("qa_blocks", [])
        corrected_count = sum(1 for qa in corrected if qa.get("status") == "corrected")
        print(f"  [Agent 5] 팩트체크 완료: {corrected_count}개 답변 수정 / {result.get('overall','?')} — {result.get('summary','')}")

        # 수정된 답변으로 교체
        content["qa_blocks"] = [
            {"question": qa["question"], "answer": qa["answer"]}
            for qa in corrected
        ]

    except Exception as e:
        print(f"  [Agent 5] 팩트체크 오류 ({e}) → 원본 유지")

    return _sanitize_generated_content(content, facts, {})


# ──────────────────────────────────────────────────
# Agent 4: CTA 최적화 (저품질 방어 포함)
# ──────────────────────────────────────────────────

def agent_cta_optimization(content: dict, facts: dict) -> dict:
    """
    Agent 6: 콘텐츠 검수
    (CTA 링크는 추후 활성화 예정, 현재는 데이터 패스스루)
    """
    print("  [Agent 6] 콘텐츠 검수 시작...")
    print(f"  [Agent 6] Q&A {len(content.get('qa_blocks', []))}개 확인 (CTA 링크 비활성)")
    return content


# ──────────────────────────────────────────────────
# Agent 7: 품질 검수
# ──────────────────────────────────────────────────

def compute_quality_score(content: dict, facts: dict) -> tuple[int, list[str]]:
    """품질 점수 계산 (0~100)"""
    score = 100
    issues = []

    # 1. Q&A 답변 길이 검증
    for i, qa in enumerate(content.get("qa_blocks", [])):
        answer_len = len(qa.get("answer", ""))
        if answer_len < 150:
            score -= 15
            issues.append(f"Q{i+1} 답변이 너무 짧음 ({answer_len}자)")

    # 2. 필수 팩트 존재 여부
    required_facts = ["apt_name", "rank1_date", "price_range", "unit_types"]
    for fact_key in required_facts:
        if not facts.get(fact_key):
            score -= 20
            issues.append(f"필수 팩트 누락: {fact_key}")

    # 2-1. 청약 신청자격 정보 여부
    if not _has_eligibility_data(facts):
        score -= 12
        issues.append("청약 신청자격 데이터 누락")

    # 2-2. 자금 계획 정보 여부
    if not _has_financial_data(facts):
        score -= 10
        issues.append("자금 계획 데이터 누락")

    # 3. SEO 태그 수
    tags = content.get("seo_tags", [])
    if len(tags) < 5:
        score -= 10
        issues.append(f"SEO 태그 부족 ({len(tags)}개 / 최소 5개)")

    # 4. 제목 길이
    title_len = len(content.get("post_title", ""))
    if title_len < 10 or title_len > 60:
        score -= 10
        issues.append(f"제목 길이 부적절 ({title_len}자 / 권장 15~50자)")

    # 5. 환각 감지: 답변에 실제 단지명 포함 여부
    apt_name = facts.get("apt_name", "")
    for i, qa in enumerate(content.get("qa_blocks", [])):
        answer = qa.get("answer", "")
        if apt_name and apt_name not in answer and len(answer) > 200:
            # 단지명 미언급 (경미한 감점만)
            score -= 3

    return max(score, 0), issues


async def agent_quality_check(content: dict, facts: dict) -> tuple[int, list[str]]:
    """Agent 7: 품질 검수"""
    print("  [Agent 7] 품질 검수 시작...")
    score, issues = compute_quality_score(content, facts)
    print(f"  [Agent 7] 품질 점수: {score}점 / 이슈: {len(issues)}개")
    for issue in issues:
        print(f"    ⚠️  {issue}")
    return score, issues


# ──────────────────────────────────────────────────
# 오케스트레이터 주석 업데이트
# ──────────────────────────────────────────────────
# 파이프라인 흐름:
#   [Agent 1] 팩트 추출 (Haiku)
#   [Agent 2] 입지 분석 (Gemini) — subway/school/life/medical 별점+설명
#   [Agent 3] 입지 검증 (GPT-5.4) — 역명·학교명·비수도권 지하철 오류 교정
#   [Agent 4] 콘텐츠 생성 (GPT-5.4)
#   [Agent 5] Q&A 팩트체크 (GPT-5.4 mini)
#   [Agent 6] CTA 최적화
#   [Agent 7] 품질 검수
#   [렌더링] HTML 생성 → 저장


# ──────────────────────────────────────────────────
# 메인 오케스트레이터
# ──────────────────────────────────────────────────

_RESUPPLY_KEYWORDS = ("무순위", "잔여", "재공급", "취소후", "불법행위", "임의공급")


def _select_theme(supply_type: str) -> str:
    """공급 유형에 따라 테마 자동 선택.
    신규분양(특별/일반 1·2순위) → config BLOG_THEME (기본 claude)
    무순위·임의공급·불법행위재공급 → resupply (연두 팔레트)
    """
    if any(kw in supply_type for kw in _RESUPPLY_KEYWORDS):
        return "resupply"
    return BLOG_THEME


def _fmt_hot_zone(v: str) -> str:
    """API/LLM raw 값(Y/N/해당없음) → 한국어 표시값 변환"""
    if v in ("Y", "y"):
        return "해당 (투기과열지구)"
    if v in ("N", "n", "해당없음", "아니오", "비해당"):
        return "비해당"
    return v  # 그 외 텍스트 값 그대로 사용


def _parse_price_manwon(value) -> int:
    """분양가 값을 만원 단위 정수로 정규화."""
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


def _merge_pdf_policy(facts: dict, policy_text: str) -> dict:
    """PDF 규제 텍스트를 파싱해 LLM/공공데이터 결과를 덮어쓴다."""
    if not policy_text.strip():
        return facts

    policy = extract_policy_from_pdf_text(policy_text)
    if not policy:
        return facts

    merged = dict(facts)
    for key in ("regulated_zone", "readmission_limit", "resale_restriction", "live_requirement", "price_cap", "land_type", "is_hot_zone"):
        value = policy.get(key)
        if value not in (None, "", [], "공고문 확인 필요"):
            merged[key] = value
    return merged


async def run_pipeline(
    notice_text: str,
    max_retries: int = 2,
    theme: str = "",
    supply_type: str = "",
    notice_url: str = "",
    api_is_hot_zone: str = "",
    *,
    doc: NoticeDocument | None = None,
    pdf_policy_text: str = "",
) -> Path | None:
    """
    단일 공고문 → 블로그 포스팅 생성 파이프라인 실행

    Args:
        notice_text: 분양 공고 원문 (청약홈 API + PDF 파싱 결과 합본)
        max_retries: 품질 미달 시 재생성 최대 횟수

    Returns:
        저장된 포스팅 디렉토리 경로 (실패 시 None)
    """
    print("\n" + "="*55)
    print("🚀 블로그 포스팅 파이프라인 시작")
    print("="*55)

    # Step 0: 청약규제정보 추출 (전문 에이전트)
    regulatory = await agent_regulatory_extraction(notice_text)

    # Step 1: 팩트 추출
    facts = await agent_fact_extraction(notice_text)
    facts = _merge_pdf_policy(facts, pdf_policy_text or (doc.pdf_policy_text if doc else ""))

    # 규제정보를 팩트에 병합 (null이 아닌 값만)
    for key in ("regulated_zone", "readmission_limit", "resale_restriction", "live_requirement", "price_cap"):
        if regulatory.get(key) is not None:
            facts[key] = regulatory[key]

    if not facts.get("apt_name") and doc and doc.apt_name:
        facts["apt_name"] = doc.apt_name
        print(f"  [Agent 1] 단지명 폴백 적용: {doc.apt_name}")
    if not facts.get("apt_name"):
        print("❌ 팩트 추출 실패 - 단지명 없음. 파이프라인 중단.")
        return None

    apt_name = facts["apt_name"]
    post_dir = OUTPUT_DIR / "posts" / f"temp_{apt_name}"

    # Step 2: 이미지 검색 (병렬)
    print(f"\n  [이미지] '{apt_name}' 관련 이미지 검색...")
    images = await find_images_for_post(
        apt_name=apt_name,
        output_dir=OUTPUT_DIR,
    )

    # 타입이 1개뿐이면 84타입 평면도 슬롯 불필요
    if len(facts.get("unit_types", [])) <= 1 and "floor_plan_84" in images:
        del images["floor_plan_84"]
        print("  [이미지] 타입 1개 → floor_plan_84 슬롯 제거")

    # Step 2: 입지 분석 (Gemini → GPT-5.4 검증)
    location_data = await agent_location_analysis_gemini(facts)
    location_data = await agent_location_verify_gpt(location_data, facts)

    # Step 3~5: 콘텐츠 생성 + 팩트체크 + 품질 검수 루프
    for attempt in range(1, max_retries + 2):
        print(f"\n  📝 콘텐츠 생성 시도 {attempt}회...")
        content = await agent_content_generation(facts)
        # Gemini 검증된 입지 데이터로 location 필드 덮어쓰기
        if location_data:
            content.update({k: location_data[k] for k in _LOCATION_KEYS if location_data.get(k)})
        content = await agent_factcheck_qa(content, facts)
        content = agent_cta_optimization(content, facts)
        score, issues = await agent_quality_check(content, facts)

        if score >= MIN_QUALITY_SCORE:
            print(f"\n  ✅ 품질 기준 통과 ({score}점 ≥ {MIN_QUALITY_SCORE}점)")
            break

        if attempt >= max_retries + 1:
            print(f"\n  ⚠️  최대 재시도 횟수 초과. 현재 점수({score})로 진행.")
            break

        print(f"\n  🔄 품질 미달 ({score}점) - 재생성...")

    # Step 5: PostData 조립
    post_data = build_post_data(
        facts=facts,
        content=content,
        doc=doc,
        theme=theme or BLOG_THEME,
        supply_type=supply_type,
        notice_url=notice_url,
        api_is_hot_zone=api_is_hot_zone,
    )
    post_data.images = images

    # Step 6: HTML 렌더링
    print("\n  🎨 HTML 렌더링...")
    renderer = BlogHTMLRenderer()
    html = renderer.render(post_data)

    # Step 7: 로컬 저장
    saved_path = save_post(post_data, html, OUTPUT_DIR)
    return saved_path


# ──────────────────────────────────────────────────
# RAG 연동 파이프라인
# ──────────────────────────────────────────────────

async def run_pipeline_from_doc(doc: NoticeDocument, max_retries: int = 2) -> Path | None:
    """LangGraph 엔트리포인트로 위임한다."""
    from main_langgraph import run_pipeline_from_doc as run_graph_pipeline

    return await run_graph_pipeline(doc, max_retries=max_retries)


# ──────────────────────────────────────────────────
# CLI 진입점
# ──────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("사용법: python orchestrator.py <공고문.txt>")
        print("예시:   python orchestrator.py notice_sample.txt")
        sys.exit(1)

    notice_path = Path(sys.argv[1])
    if not notice_path.exists():
        print(f"파일 없음: {notice_path}")
        sys.exit(1)

    notice_text = notice_path.read_text(encoding="utf-8")
    result = asyncio.run(run_pipeline(notice_text))

    if result:
        print(f"\n🎉 완료! 결과 폴더: {result}")
    else:
        print("\n❌ 파이프라인 실패")
