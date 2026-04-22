"""
orchestrator.py
────────────────────────────────────────────────────
멀티에이전트 파이프라인 오케스트레이터

흐름:
  [데이터 수집] → [팩트 추출 Agent] → [콘텐츠 생성 Agent]
               → [품질 검수 Agent]
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
    OPENAI_API_KEY, GEMINI_API_KEY,
    LLM_CONTENT_MODEL, LLM_EXTRACT_MODEL, LLM_FACTCHECK_MODEL, LLM_LOCATION_MODEL,
    OUTPUT_DIR, MIN_QUALITY_SCORE, BLOG_THEME,
)
from html_renderer import BlogHTMLRenderer, PostData, QABlock, UnitType, save_post
from agents.collector import NoticeDocument

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
# Agent 1: 팩트 추출
# ──────────────────────────────────────────────────
FACT_EXTRACTION_PROMPT = """
당신은 부동산 분양 공고문 분석 전문가입니다.
아래 [공고 원문]에서 정보를 추출하여 JSON으로만 답하세요.
[공고 원문]에 없는 수치는 절대 추측하거나 생성하지 마세요. 없으면 null로 표기.
PDF 원문과 API 정보가 함께 있으면 PDF에 적힌 값을 최우선으로 반영하세요.
어떤 필드도 임의의 확인 문구로 채우지 말고, 정보가 없으면 null 또는 빈 값으로 두세요.

추출할 필드 (JSON 키명 고정):
- apt_name: 단지명
- location: 시/구/동 (예: 서울시 강남구 개포동)
- supply_location: 전체 공급위치 (공고문 그대로)
- supply_scale: 공급규모 요약
- unit_types: 배열 (type_name, area_sqm, general_units, special_units, price_min, price_max 키를 가진 객체 목록)
- notice_date: 모집공고일 YYYY-MM-DD (없으면 null)
- special_supply_date: YYYY-MM-DD
- rank1_date: YYYY-MM-DD
- rank2_date: YYYY-MM-DD
- winner_date: YYYY-MM-DD
- move_in_date: YYYY년 MM월
- resale_restriction: 전매제한 기간 — 공고문의 "제한사항", "전매제한", "계약 조건" 섹션에 기재.
  예: "소유권이전등기일로부터 3년", "입주 후 6개월", "분양가상한제 적용 10년", "없음".
  공고에 없으면 null. 조건별로 다를 경우 가장 긴 기간 기준으로 요약.
- contract_ratio: 계약금 비율 (숫자만, 예: 10)
- contract_amount: 최저 분양가 기준 계약금 금액 (예: "약 3,000만원"), 공고에 없으면 null
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
- 계약금 금액은 공고문에 있는 표현을 최대한 그대로 반환하세요.
- 정보가 없으면 null 또는 기본값을 사용하지 말고 빈 값으로 두세요.

반드시 추출할 키:
- contract_ratio
- contract_amount
- midterm_ratio
- midterm_count
- balance_ratio

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
        for key in ("contract_ratio", "contract_amount", "midterm_ratio", "midterm_count", "balance_ratio")
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


async def agent_fact_extraction(notice_text: str) -> dict:
    """Agent 1: 공고문에서 팩트를 추출하여 구조화된 JSON 반환 (GPT-5.4)"""
    print("  [Agent 1] 팩트 추출 시작...")
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
            print("  [Agent 1] JSON 파싱 실패")

    pdf_policy_overrides = _extract_pdf_policy_overrides(notice_text)
    if pdf_policy_overrides:
        facts.update(pdf_policy_overrides)

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

            for key in ("contract_ratio", "contract_amount", "midterm_ratio", "midterm_count", "balance_ratio"):
                if financial.get(key) not in (None, "", []):
                    facts[key] = financial.get(key)
            if _has_financial_data(facts):
                print("  [Agent 1] 자금계획 재추출 완료")
        except Exception as e:
            print(f"  [Agent 1] 자금계획 재추출 실패 ({e})")

    print(f"  [Agent 1] 완료: {facts.get('apt_name', '미확인')} 추출")
    return facts


# ──────────────────────────────────────────────────
# Agent 2: 입지 분석 (GPT-5.4)
# ──────────────────────────────────────────────────

LOCATION_ANALYSIS_PROMPT = """?? ?? ??? ???? ?? ?? ??? ??????.
?, ???? ??, ???, ???, ???? ?? ?? ?? ??? ???? ??? ??? ?????.

?? ??:
- ?? ??? ??? ???? ??, ??? ???? ??? ???? ??? ?????.
- ??? ??? ???, ?? ??, ?????, ???? ????? ??? ?? ??? ?????.
- ??? ??/?? ????? ?? ????? ??? ?? ??? ?????.
- ????? ????, ???, ??, ???? ?? ?? ???? ??? ??? ?????.
- ??? ????, ????, ??? ?? ?? ???? ????? ?????.
- ??? ?? ??, ??? ?? ?? ?????.
- ??? ???? ??? ?? ??? ??? ??, ??? ???? ????? ?????.

[?? ??]:
{facts_json}

JSON? ??:
{{
  "location_intro": "100~150?. ?? ??? ???? ??? ??? ????? ?????.",
  "subway_detail":  "??? ???, ?? ??, ?????, ???? ??? ? ??? ?? ??? ????? ?????.",
  "school_detail":  "??/?? ????? ?? ??? ? ??? ?? ???? ????? ?????.",
  "life_detail":    "????, ???, ??, ???? ? ???? ??? ????? ?????.",
  "medical_detail": "????, ????, ??? ? ?? ???? ????? ?????."
}}"""

LOCATION_VERIFY_PROMPT = """??? AI? ??? ?? ?????.
?? ???? ???? ??? ??? ?????.

?? ??:
1. ???? ????????????????? ?? ?????
2. ?????? ???? ???? ???? ?????
3. ????? ?? ??? ????? ???? ?????
4. ??? ???? ??? ?? ??? ???? ?????

[???]: {apt_name}
[??]: {location}

[GPT ?? ?? ??]:
{location_json}

?? ?? ? ??? JSON ??. ?? ??? ?? ??? ??. JSON? ??."""

_LOCATION_KEYS = (
    "location_intro", "subway_detail",
    "school_detail", "life_detail",
    "medical_detail",
)


async def agent_location_analysis_gpt(facts: dict) -> dict:
    """Agent 2: GPT-5.4로 입지 분석 생성"""
    print("  [Agent 2] 입지 분석 시작 (GPT-5.4)...")
    try:
        raw = await _call_openai_json(
            system=(
                "당신은 한국 부동산 입지 분석 전문가입니다.\n"
                "JSON만 출력하세요. 마크다운 코드블록 없이 순수 JSON만 출력합니다."
            ),
            user=LOCATION_ANALYSIS_PROMPT.format(
                facts_json=json.dumps(facts, ensure_ascii=False, indent=2)
            ),
            model=LLM_CONTENT_MODEL,
            max_tokens=3000,
        )
        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            import re as _re
            m = _re.search(r'\{.*\}', raw, _re.DOTALL)
            result = json.loads(m.group()) if m else {}
        print(f"  [Agent 2] 완료: subway_detail={result.get('subway_detail','')[:40]}")
        return result
    except Exception as e:
        print(f"  [Agent 2] GPT-5.4 오류 ({e}) → 빈 딕셔너리 반환")
        return {}


async def agent_location_verify_gemini(location_data: dict, facts: dict) -> dict:
    """Agent 3: Gemini 3.1 Pro Preview로 입지 분석 검증·교정"""
    print("  [Agent 3] 입지 분석 검증 시작 (Gemini 3.1 Pro Preview)...")
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
        print(f"  [Agent 3] 검증 완료: subway_detail={result.get('subway_detail','')[:40]}")
        return result
    except Exception as e:
        print(f"  [Agent 3] Gemini 검증 오류 ({e}) → 원본 결과 그대로 사용")
        return location_data


# ──────────────────────────────────────────────────
# Agent 4: 블로그 콘텐츠 생성
# ──────────────────────────────────────────────────
CONTENT_GEN_PROMPT = """?? ?? ??? ???? ??? ??? Q&A? ?????.
????, ????, ?? ??? ?? ???? ??? ???? ?????.
???? ?? ???? ?? ?? ??? ?? ???.

?? ??:
- ?? ??? ??? ??? ???? ????.
- ?? ??? ??? ???? ??? ??? ???? ????.
- ?? ??? ???, ???, ??? ???? ????? ??? ?? ??? ??.
- ?? ?? ???? ?? ??? ?? ???.
- ?????????????? ?? ????? ????.
- ??? ??, ???? ?? ??? ????.
- ???? ??? ????? ???? ?? ?????? ??.
- SEO? ????? ?? ???? ???.
- Q&A? ?? 7?, ? ??? 300~500? ??? ??.

?? ??:
- post_title: 50? ??
- post_subtitle: 30? ??
- apt_intro: 150~200?
- location_intro: 100~150?
- financial_intro: 80~100?
- qa_intro: 60~80?
- schedule_desc: 80~120?
- unit_type_desc: 80~130?
- tax_desc: 80~120?
- ? Q&A answer: 300~500?

[?? ??]:
{facts_json}

?? JSON ??:
{{
  "post_title": "50? ?? ??",
  "post_subtitle": "30? ?? ??",
  "seo_tags": ["??1", "??2", "??3", "??4", "??5", "??6", "??7"],
  "apt_intro": "?? ?? ??",
  "location_intro": "?? ?? ??",
  "financial_intro": "?? ?? ??",
  "qa_intro": "Q&A ?? ??",
  "qa_blocks": [
    {{"question": "??", "answer": "??"}}
  ],
  "schedule_desc": "?? ??",
  "unit_type_desc": "??/?? ??",
  "tax_desc": "?? ??",
  "subway_detail": "?? ?? ?? ??",
  "school_detail": "?? ??? ?? ??",
  "life_detail": "???? ?? ??",
  "medical_detail": "?? ??? ?? ??"
}}"""
async def agent_content_generation(facts: dict) -> dict:
    """Agent 4: ??? ??? + Q&A ?? (GPT-5.4)"""
    print("  [Agent 4] ??? ?? ?? (GPT-5.4)...")
    raw = await _call_openai_json(
        system=(
            "??? ?? ??? ?? ??? ???? ???? ??? ??? ?????.\n"
            "????? ????? ????? ????.\n"
            "JSON? ?????. ???? ???? ?? ?? JSON? ????.\n"
            "?? ???? ???? ????, ???? ???? ???? ????? ??."
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
    print(f"  [Agent 4] ??: Q&A {len(content.get('qa_blocks', []))}? ??")
    return content


# ──────────────────────────────────────────────────
# Agent 5: Q&A 팩트체크 (GPT-5.4 mini)
# ──────────────────────────────────────────────────

FACTCHECK_SYSTEM = """??? ?? ?????? ?? ??????.
?? [?? ??]? [Q&A ??]? ????, ? ??? ?? ???? ?????.

?? ??:
1. ?? ??(??????????????)? ?? ??? ??????
2. ?? ????(???? ??????????? ?)? ??? ???? ????
3. ?????? ???? ??? ????
4. ?? ?? ?? ?? ??? ??? ????
   - "??? ??? ???", "?????", "?????" ? ?? ?? ?? ?? ??? ?????.
   - ?? ????? ?? ??? ?????.
   - ????? ??? ????? ??? ??? "??? ??" ???? ?????.
   - ?? ?? ??? ?? ?? ?? ??? ????? ????? ???.

?? ?? (JSON?):
{
  "qa_blocks": [
    {
      "question": "?? ?? ???",
      "answer": "??? ?? (????? ?? ???, ????? ??? ???? ??)",
      "status": "ok" | "corrected",
      "note": "?? ?? (status=ok?? ? ???)"
    }
  ],
  "overall": "pass" | "fail",
  "summary": "?? ???? ?? (1~2??)"
}"""

FACTCHECK_USER_TPL = """[?? ??]
{facts_json}

[Q&A ??]
{qa_json}

? Q&A ??? ?????? JSON?? ?????."""



async def agent_factcheck_qa(content: dict, facts: dict) -> dict:
    """Agent 5: Gemini 3.1 Pro Preview로 Q&A 팩트체크 — 오류 답변 자동 정정"""
    print("  [Agent 5] Q&A 팩트체크 시작 (Gemini 3.1 Pro Preview)...")

    if not GEMINI_API_KEY:
        print("  [Agent 5] GEMINI_API_KEY 미설정 → 팩트체크 건너뜀")
        return content

    try:
        user_msg = FACTCHECK_USER_TPL.format(
            facts_json=json.dumps(facts, ensure_ascii=False, indent=2),
            qa_json=json.dumps(content.get("qa_blocks", []), ensure_ascii=False, indent=2),
        )
        from google import genai as google_genai
        from google.genai import types as genai_types

        client = google_genai.Client(api_key=GEMINI_API_KEY)
        resp = client.models.generate_content(
            model=LLM_FACTCHECK_MODEL,
            contents=user_msg,
            config=genai_types.GenerateContentConfig(
                system_instruction=FACTCHECK_SYSTEM,
            ),
        )
        raw = (resp.text or "").strip()

        # JSON 추출
        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            import re
            m = re.search(r'\{.*\}', raw, re.DOTALL)
            result = json.loads(m.group()) if m else None

        if not result:
            print("  [Agent 5] 팩트체크 JSON 파싱 실패 → 원본 유지")
            return content

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

    return content


# ──────────────────────────────────────────────────
# Agent 6: CTA 검수 (향후 도입 예정)
# ──────────────────────────────────────────────────

def agent_cta_optimization(content: dict, facts: dict) -> dict:
    """
    향후 도입 예정인 CTA 검수용 자리표시자.
    """
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
#   [Agent 2] 입지 분석 (GPT-5.4) — subway/school/life/medical 설명
#   [Agent 3] 입지 검증 (Gemini 3.1 Pro Preview) — 지역 일반 설명 기준으로 과도한 구체화 교정
#   [Agent 4] 콘텐츠 생성 (GPT-5.4)
#   [Agent 5] Q&A 팩트체크 (GPT-5.4 mini)
#   [Agent 6] CTA 검수(향후)
#   [Agent 7] 품질 검수
#   [렌더링] HTML 생성 → 저장


# ──────────────────────────────────────────────────
# 메인 오케스트레이터
# ──────────────────────────────────────────────────

_RESUPPLY_KEYWORDS = ("무순위", "잔여", "재공급", "취소후", "임의공급")


def _is_draft_supply(supply_type: str) -> bool:
    """청약접수 종료 공고는 미지정/드래프트로 분리한다."""
    return "불법행위" in (supply_type or "")


def _select_theme(supply_type: str) -> str:
    """공급 유형에 따라 테마 자동 선택.
    신규분양(특별/일반 1·2순위) → config BLOG_THEME (기본 claude)
    무순위·임의공급·재공급 → resupply (연두 팔레트)
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


def _html_with_breaks(text: str) -> str:
    """개행을 <br>로 바꿔 HTML에서 줄바꿈을 보존."""
    return text.replace("\r\n", "\n").replace("\n", "<br>")


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


async def run_pipeline(notice_text: str, max_retries: int = 2, theme: str = "", supply_type: str = "", notice_url: str = "", api_is_hot_zone: str = "") -> Path | None:
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

    # Step 1: 팩트 추출
    facts = await agent_fact_extraction(notice_text)
    if not facts.get("apt_name"):
        print("❌ 팩트 추출 실패 - 단지명 없음. 파이프라인 중단.")
        return None

    apt_name = facts["apt_name"]
    post_dir = OUTPUT_DIR / "posts" / f"temp_{apt_name}"

    unit_type_dicts = facts.get("unit_types", []) or []
    facts["price_range"] = _derive_price_range(unit_type_dicts) or facts.get("price_range", "")
    facts["supply_total_units"] = sum(
        int(ut.get("general_units", 0) or 0) + int(ut.get("special_units", 0) or 0)
        for ut in unit_type_dicts
    )

    # Step 2: 이미지 검색은 향후 도입 예정이므로 현재 비활성화
    images: dict = {}

    # Step 2: 입지 분석 (GPT-5.4 생성 → Gemini 3.1 Pro Preview 검증)
    location_data = await agent_location_analysis_gpt(facts)
    location_data = await agent_location_verify_gemini(location_data, facts)

    # Step 3~5: 콘텐츠 생성 + 팩트체크 + 품질 검수 루프
    for attempt in range(1, max_retries + 2):
        print(f"\n  📝 콘텐츠 생성 시도 {attempt}회...")
        content = await agent_content_generation(facts)
        # Gemini 검증된 입지 데이터로 location 필드 덮어쓰기
        if location_data:
            content.update({k: location_data[k] for k in _LOCATION_KEYS if location_data.get(k)})
        content = await agent_factcheck_qa(content, facts)
        # CTA 검수는 향후 도입 예정
        # content = agent_cta_optimization(content, facts)
        score, issues = await agent_quality_check(content, facts)

        if score >= MIN_QUALITY_SCORE:
            print(f"\n  ✅ 품질 기준 통과 ({score}점 ≥ {MIN_QUALITY_SCORE}점)")
            break

        if attempt >= max_retries + 1:
            print(f"\n  ⚠️  최대 재시도 횟수 초과. 현재 점수({score})로 진행.")
            break

        print(f"\n  🔄 품질 미달 ({score}점) - 재생성...")

    # Step 5: PostData 조립
    unit_types = [
        UnitType(
            type_name=ut["type_name"],
            area_sqm=float(ut.get("area_sqm", 0)),
            general_units=int(ut.get("general_units", 0)),
            special_units=int(ut.get("special_units", 0)),
            price_min=_parse_price_manwon(ut.get("price_min", 0)),
            price_max=_parse_price_manwon(ut.get("price_max", 0)),
        )
        for ut in facts.get("unit_types", [])
    ]

    qa_blocks = [
        QABlock(
            question=qa["question"],
            answer=qa["answer"],
        )
        for qa in content.get("qa_blocks", [])
    ]

    contract_ratio = str(facts.get("contract_ratio") or "10")
    midterm_ratio = str(facts.get("midterm_ratio") or "60")
    midterm_count = str(facts.get("midterm_count") or "6")
    balance_ratio = str(facts.get("balance_ratio") or "30")
    contract_amount = facts.get("contract_amount") or ""

    publication_status = "draft" if _is_draft_supply(supply_type) else "live"

    post_data = PostData(
        apt_name=apt_name,
        post_title=content.get("post_title", f"{apt_name} 청약 완벽 분석"),
        post_subtitle=content.get("post_subtitle", "청약 전 반드시 확인하세요"),
        location=facts.get("location", ""),
        supply_location=facts.get("supply_location", ""),
        supply_scale=facts.get("supply_scale", ""),
        is_hot_zone=_fmt_hot_zone(facts.get("is_hot_zone") or api_is_hot_zone or ""),
        regulated_zone=facts.get("regulated_zone") or "",
        readmission_limit=facts.get("readmission_limit") or "",
        live_requirement=facts.get("live_requirement") or "",
        price_cap=facts.get("price_cap") or "",
        price_range=facts.get("price_range", ""),
        unit_types=unit_types,
        special_supply_date=facts.get("special_supply_date", "-"),
        rank1_date=facts.get("rank1_date", "-"),
        rank2_date=facts.get("rank2_date", "-"),
        winner_date=facts.get("winner_date", "-"),
        move_in_date=facts.get("move_in_date", "-"),
        resale_restriction=facts.get("resale_restriction") or "-",
        contract_ratio=contract_ratio,
        contract_amount=contract_amount,
        midterm_ratio=midterm_ratio,
        midterm_count=midterm_count,
        balance_ratio=balance_ratio,
        acquisition_tax_rate=facts.get("acquisition_tax_rate", "1~3%"),
        acquisition_tax_amount="-",
        property_tax_rate="과세표준 × 0.1~0.4%",
        property_tax_amount="-",
        capital_gains_tax_rate="1주택 2년 보유 시 비과세 가능",
        capital_gains_tax_amount="-",
        subway_detail=content.get("subway_detail", ""),
        school_detail=content.get("school_detail", ""),
        life_detail=content.get("life_detail", ""),
        medical_detail=content.get("medical_detail", ""),
        # 내러티브 산문 필드
        apt_intro=content.get("apt_intro", ""),
        location_intro=content.get("location_intro", ""),
        financial_intro=content.get("financial_intro", ""),
        qa_intro=content.get("qa_intro", ""),
        # 정보 블록 앞 서술 필드
        unit_type_desc=content.get("unit_type_desc", ""),
        schedule_desc=content.get("schedule_desc", ""),
        tax_desc=content.get("tax_desc", ""),
        qa_blocks=qa_blocks,
        seo_tags=content.get("seo_tags", [apt_name, "청약", "분양"]),
        images=images,
        source_date=facts.get("rank1_date", ""),
        notice_date=facts.get("notice_date", ""),
        read_time=max(6, len(str(content)) // 450),
        theme=theme or BLOG_THEME,
        supply_type=supply_type,
        publication_status=publication_status,
        eligibility_special=facts.get("eligibility_special") or [],
        eligibility_rank1=facts.get("eligibility_rank1") or [],
        eligibility_rank2=facts.get("eligibility_rank2") or [],
        notice_url=notice_url,
    )

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
    """
    NoticeDocument → RAG 저장 → 컨텍스트 조합 → 블로그 포스팅 생성

    RAG 초기화 실패 시 doc.to_rag_text()로 자동 폴백하여
    ChromaDB 없이도 동작 보장.
    """
    theme = _select_theme(doc.supply_type)
    publication_status = "draft" if _is_draft_supply(doc.supply_type) else "live"
    print(
        f"\n  [RAG] '{doc.apt_name}' 공고 처리 시작... "
        f"(공급유형: {doc.supply_type or '신규'} → 테마: {theme}, 상태: {publication_status})"
    )

    try:
        from agents.rag_store import ApartmentRAGStore
        store = ApartmentRAGStore()
        store.add_notice(doc)
        notice_text = store.get_full_context(doc.notice_id)
        if not notice_text.strip():
            raise ValueError("RAG 컨텍스트 비어 있음")
        print(f"  [RAG] 컨텍스트 {len(notice_text):,}자 조합 완료")
    except Exception as e:
        print(f"  [RAG] 초기화/조회 실패 → 원문 폴백: {e}")
        notice_text = doc.to_rag_text()

    return await run_pipeline(
        notice_text,
        max_retries=max_retries,
        theme=theme,
        supply_type=doc.supply_type,
        notice_url=doc.notice_url,
        api_is_hot_zone=doc.is_hot_zone,
    )


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
