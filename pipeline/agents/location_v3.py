"""location_v3.py — v3 (Gemini 추천 프롬프트, 최소 입력 + 가독성 보강).

v3 rev 2 — 운영자 피드백 반영:
  · v3-minimal 결과 품질은 합격. 다만 문장이 길어 가독성 저하.
  · 모바일 호흡·시각 위계·이모지 마커를 프롬프트 차원에서 보강.

운영자 요청: 단지명·주소만 LLM 에 던지고 나머지는 Gemini Grounding(Google
Search) 의 검색 능력에 맡겨 결과 확인. Gemini 가 직접 추천한 프롬프트 구조
(Role / Analysis Strategy / Tone & Manner / Structure 5섹션) 를 본문 원문 그대로
적용. 사이트 안전 정책(cliche·회피·대장 어휘 금지) 도 의도적으로 비활성 —
Gemini 추천 결과의 baseline 을 그대로 본다.

v2 와 완전 별도. UI 보호 정책 미트리거 — 신규 모듈만 추가.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path


# Gemini 가 추천한 마스터 프롬프트(원문 골격) + 가독성 가이드(rev 2)
# + Hallucination Guard (rev 3, 운영자 피드백 — 계약금/전매 등 정량 정보 hallucinate 사례 발견).
LOCATION_ANALYSIS_PROMPT_V3 = """# Role
당신은 부동산 가치 평가 전문 애널리스트입니다. 주어진 단지에 대해 타 서비스와
차별화되는 깊이 있는 '입지 분석' 리포트를 작성하는 것이 임무입니다.

# Analysis Strategy (Must Apply)
1. **데이터 기반 통찰**: 단순 나열이 아닌, 데이터 간의 상관관계를 분석하십시오.
   (예: "초등학교가 가깝다" → "안심 통학권 확보로 인한 초품아 프리미엄 및
   학령기 자녀 가구의 탄탄한 실수요 확보")
2. **전문 용어의 적절한 사용**: 직주근접·슬세권·하방 경직성·앵커시설·병세권·
   공세권·숲세권·초품아·CBD/YBD/GBD 등 전문 용어를 활용하여 신뢰도를 높이십시오.
3. **입체적 공간 분석**:
   - 교통: 주요 업무지구까지의 소요 시간과 환승 편의성 위주로 서술.
   - 학군: 단순 거리 외에 주변 학원가 형성 수준과 학업 성취도를 추론하여 포함.
   - 환경: 녹지 공간(공세권·숲세권) 이 주거 쾌적성과 자산 가치에 미치는 영향 분석.

# Hallucination Guard (Must Apply — 절대 금지 사항)
입지 분석의 역할은 교통·학군·인프라·환경·미래 가치 등 **입지 본연의 가치**에
집중하는 것. 금융/규제 정보는 별도 섹션에서 다루므로 입지 분석에서는 다음
사항을 절대 작성하지 마십시오. 위반 시 본문 전체가 폐기됩니다.

1. **금액 관련 문구 일체 생성 금지** — *평형(전용면적)·분양가를 제외한* 모든
   금액·금액 비율 표현 절대 금지. 예시(모두 금지):
   - 계약금, 중도금, 잔금 (금액·비율 모두)
   - 무이자, 이자 후불제, 후불제, 대출, DSR, LTV
   - 이주비, 발코니 확장비, 옵션 비용
   - 전세보증금, 월세, 시세, 호가, 매매가, 실거래가
   - "초기 자금 부담 적음" 같은 자금 관련 정성 표현
   허용: 평형(예: 84㎡·전용 84m²·중대형 평형), 분양가(예: 8억원·3.7억원대).

2. **부동산 규제 정보 일체 생성 금지** — 입지 분석 본문에서는 다음 표현을
   언급조차 하지 마십시오. 모두 별도 섹션에서 다룹니다:
   - 전매 제한 (기간·해제·없음 모두 금지)
   - 재당첨 제한
   - 거주 의무
   - 분양가 상한제
   - 규제 지역 (투기과열·조정대상·비규제·해제·지정 모두 금지)
   - 청약 자격(특별 공급·1순위·2순위 등)
   허용: 단지 자체의 신축·재건축·리모델링 같은 건축 형태 언급은 가능.

3. **고유명사 신중 사용** — 역명·학교명·시설명·도로명·노선명은 Grounding 검색
   에서 확인된 것만 인용. 비슷한 이름을 유추해 새로 만들지 말 것.

4. **시점·계획의 단정 금지** — 미확정 노선·미착공 시설은 "검토 중" 또는
   "계획" 으로만 표기. "개통 예정 OO년" 같은 단정은 공식 발표 출처 명시한
   경우에만.

이 가드는 입지 분석의 핵심 가치 — 신뢰도 — 를 지키기 위한 최우선 제약입니다.
정량 수치나 규제 정보가 분석에 필요하다고 느껴져도, 입지 본연의 가치(교통
편의성, 학군, 생활 인프라, 녹지, 미래 가치) 로 우회해서 서술하십시오.

# Tone & Manner
- 정중하고 전문적인 어투를 유지하십시오.
- 모든 섹션은 핵심 결론을 먼저 제시하는 '두괄식' 으로 구성하십시오.
- 감성적인 미사여구보다는 논리적인 근거(Fact-based Logic) 에 집중하십시오.

# Readability — 가독성 (rev 2 신설)
모바일에서 읽기 좋게 다음을 지키십시오. 분석가 톤은 유지.

1. **한 문장 평균 40~60자, 최대 70자**. 길어지면 두 문장으로 분리.
2. **섹션당 2~3 단락**으로 구성. 단락 사이 빈 줄 1개.
   - 1단락: 두괄식 결론 (1~2문장).
   - 2단락: 근거·데이터 (2~3문장).
   - 3단락(선택): 매수자가 알아야 할 제약·맥락 (1~2문장).
3. **핵심 키워드 강조** — 본문 안에서 단지의 핵심 강점·약점 키워드를
   `**굵게**` 표시. 섹션당 1~3개, 본문 전체에서 8개 이내.
4. **이모지** — 다음 규칙으로만 사용. 그 이상은 분석가 톤이 깨져 금지.
   - **섹션 헤딩**에 의미 이모지 1개씩 (총 5개):
       ### 📍 입지 총평
       ### 🚇 교통: 시간적 가치
       ### 🏫 교육: 정주 여건의 핵심
       ### 🛒 인프라: 생활의 완결성
       ### 📈 미래 가치: 자산의 확장성
   - 본문 안에서는 핵심 키워드 옆에 **1~2회만** (단지 전체 기준).
     의미·맥락 이모지만 허용 (예: 직주근접 💼 / 공세권 🌳 / 광역교통망 🚆 /
     학원가 📚 / 한강·공원 🌊 / 신축·재건축 🏗️).
   - 감탄용 이모지(✨🔥💖💎❤️) 절대 금지.

# Structure (markdown body)
다음 5섹션 순서로 본문을 구성하십시오. 각 섹션 헤딩은 위 Readability 의 이모지
포함 형식.

# 출력 형식 — JSON 만
{{
  "headline": "본문의 핵심 결론 한 줄 (제목 형식 X, 평문)",
  "body_md": "...위 5섹션 markdown 본문, 가독성 가이드 적용...",
  "_grounded_facts_used": ["본문에 인용한 검증된 외부 사실 1~3개"]
}}

마크다운 코드블록 없이 순수 JSON 만 출력.

---

# 분석 대상 단지
- 단지명: {apt_name}
- 주소: {address}
"""


def build_prompt_v3(apt_name: str, address: str) -> str:
    return LOCATION_ANALYSIS_PROMPT_V3.format(
        apt_name=apt_name or "(미상)",
        address=address or "(미상)",
    )


DEFAULT_MODEL_V3 = os.getenv("LOCATION_V3_MODEL", "gemini-3.1-pro-preview")
DEFAULT_TEMPERATURE_V3 = float(os.getenv("LOCATION_V3_TEMPERATURE", "0.4"))


def _loads_lenient(raw: str) -> dict:
    """LLM JSON 응답을 관대하게 파싱한다.

    strict=False 로 문자열 내 제어문자를 허용하고, 그래도 실패하면 첫 ``{...}``
    블록만 추출해 재시도하며, 최후에는 제어문자를 공백으로 치환해 복구한다.
    어떤 경우에도 예외를 던지지 않는다(파싱 실패가 구버전 폴백으로 이어지지
    않도록 보장).
    """
    for candidate in (raw, None):
        text = candidate
        if text is None:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            text = match.group() if match else None
        if not text:
            continue
        try:
            return json.loads(text, strict=False)
        except json.JSONDecodeError:
            try:
                return json.loads(re.sub(r"[\x00-\x1f]", " ", text))
            except json.JSONDecodeError:
                continue
    return {}


async def generate_v3(apt_name: str, address: str, *, model: str | None = None) -> dict:
    """단지명·주소만 입력. Gemini Grounding + thinking high 로 5섹션 분석 생성."""
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        return {
            "_error": "GEMINI_API_KEY 미설정",
            "_meta": {"model": None, "prompt_version": "v3-readable", "grounding": False, "thinking": False},
        }

    from google import genai as google_genai
    from google.genai import types as genai_types

    prompt = build_prompt_v3(apt_name, address)
    used_model = model or DEFAULT_MODEL_V3

    try:
        http_options = genai_types.HttpOptions(timeout=600_000)
        client = google_genai.Client(api_key=api_key, http_options=http_options)
    except (AttributeError, TypeError):
        client = google_genai.Client(api_key=api_key)

    def _make_config(*, with_grounding: bool, with_thinking: bool):
        kwargs: dict = {
            "system_instruction": "JSON만 출력하세요. 마크다운 코드블록 없이 순수 JSON만.",
            "temperature": DEFAULT_TEMPERATURE_V3,
        }
        if with_grounding:
            kwargs["tools"] = [genai_types.Tool(google_search=genai_types.GoogleSearch())]
        if with_thinking and hasattr(genai_types, "ThinkingConfig"):
            try:
                kwargs["thinking_config"] = genai_types.ThinkingConfig(thinking_level="high")
            except TypeError:
                try:
                    kwargs["thinking_config"] = genai_types.ThinkingConfig(thinking_budget=-1)
                except Exception:
                    pass
        return genai_types.GenerateContentConfig(**kwargs)

    grounding_used = False
    thinking_used = False
    raw = ""
    last_exc = None
    for with_grounding, with_thinking in (
        (True, True),
        (True, False),
        (False, False),
    ):
        try:
            resp = client.models.generate_content(
                model=used_model,
                contents=prompt,
                config=_make_config(with_grounding=with_grounding, with_thinking=with_thinking),
            )
            raw = (resp.text or "").strip()
            grounding_used = with_grounding
            thinking_used = with_thinking
            break
        except Exception as exc:
            last_exc = exc
            continue
    if not raw:
        return {
            "_error": f"Gemini 호출 실패: {last_exc}",
            "_meta": {"model": used_model, "prompt_version": "v3-readable", "grounding": False, "thinking": False},
        }

    # Gemini 응답 JSON 파싱.
    # 모델이 body_md 안에 원시 제어문자(리터럴 \n·\t 등)를 담아 보내는 경우가 있어
    # strict=False 로 허용한다(기본 strict=True 는 제어문자를 거부 → 'Invalid control
    # character' 예외 → 과거 v3 패치가 실패하고 구버전 본문으로 폴백됨).
    result = _loads_lenient(raw)

    return {
        "headline": (result.get("headline") or "").strip(),
        "body_md": (result.get("body_md") or "").strip(),
        "grounded_facts_used": result.get("_grounded_facts_used") or [],
        "_meta": {
            "model": used_model,
            "prompt_version": "v3-readable",
            "grounding": grounding_used,
            "thinking": thinking_used,
            "input": {"apt_name": apt_name, "address": address},
        },
    }
