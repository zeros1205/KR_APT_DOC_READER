"""location_v3.py — v3 (Gemini 추천 프롬프트, 최소 입력 실험).

운영자 요청: 단지명·주소만 LLM 에 던지고 나머지는 Gemini Grounding(Google
Search) 의 검색 능력에 맡겨 결과 확인. Gemini 가 직접 추천한 프롬프트 구조
(Role / Analysis Strategy / Tone & Manner / Structure 5섹션) 를 본문 그대로
적용하되, 사이트 안전 정책(cliche 금지·회피 문구 금지·대장주 어휘 금지) 만
얹는다.

v2 와 완전 별도. v2 의 facts.nearby·complex_type 태그·정보 활용 3계층 규칙은
의도적으로 비활성. 출력은 markdown body 한 덩어리 (`body_md`).

UI 보호 정책 미트리거 — 신규 모듈만 추가.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path


CLICHE_BLOCKED = [
    "쾌적한", "우수한", "체계적", "원활", "편리한", "다양한", "잘 갖추",
    "주거 환경", "주거 편의", "생활 인프라", "주거 가치", "정주 여건",
    "안정적", "편안한", "안락한", "조화롭게", "조화를 이루",
    "주거지로서", "주거 트렌드", "현대적", "쾌적성", "효율성",
    "프라이버시", "고급 주거", "완성도",
]

EVASIVE_BLOCKED = [
    "확인 권장", "확인 필요", "함께 보세요", "함께 살펴", "같이 확인",
    "공고문을 확인", "공고문으로 확인", "지도를 확인", "지도로 확인",
    "교육청에 확인", "교육 자료로 확인", "추가 확인", "구체적으로 확인",
    "꼼꼼히 확인", "직접 확인", "사전에 확인", "검토해야 합니다",
]

LANDMARK_BLOCKED = [
    "대장주", "대장 단지", "대장아파트", "대장",
]


# Gemini 가 추천한 마스터 프롬프트(원문 골격 유지) + 사이트 안전장치 추가.
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

# Tone & Manner
- 정중하고 전문적인 어투를 유지하십시오.
- 모든 섹션은 핵심 결론을 먼저 제시하는 '두괄식' 으로 구성하십시오.
- 감성적인 미사여구보다는 논리적인 근거(Fact-based Logic) 에 집중하십시오.

# Structure (markdown body)
다음 5섹션 순서로 본문을 구성하십시오. 각 섹션 헤딩은 `### 섹션명` 형식.
  ### 입지 총평
  ### 교통: 시간적 가치
  ### 교육: 정주 여건의 핵심
  ### 인프라: 생활의 완결성
  ### 미래 가치: 자산의 확장성

# 데이터 정확성 — 절대 위반 금지
- 검색으로 검증 가능한 정보만 인용. 거리·역명·학교명을 추측해 만들지 마세요.
- 변동성 큰 수치(현재 시세·실시간 경쟁률·진학률) 는 검색 출처가 명확할 때만,
  근거를 본문에 자연스럽게 녹여 인용.
- 투자수익·시세차익·가격상승 예측 금지. 대신 "수요 기반·하방 경직성" 같은
  객관 표현.

# 사이트 안전 — 절대 금지 어휘·표현
다음이 본문에 등장하면 작성 실패. 다른 표현으로 즉시 교체.
- cliche 사전: {cliche_list}
- 회피·면피 문구: {evasive_list}
- "대장" 어휘: {landmark_blocked}

# 출력 형식 — JSON 만
{{
  "headline": "본문의 핵심 결론 한 줄 (제목 형식 X, 평문)",
  "body_md": "...위 5섹션 markdown 본문...",
  "_grounded_facts_used": ["본문에 인용한 검증된 외부 사실 1~3개. 출처가 Google Search 라면 검증 가능한 사실만"]
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
        cliche_list=" · ".join(CLICHE_BLOCKED),
        evasive_list=" · ".join(EVASIVE_BLOCKED),
        landmark_blocked=" · ".join(LANDMARK_BLOCKED),
    )


DEFAULT_MODEL_V3 = os.getenv("LOCATION_V3_MODEL", "gemini-3.1-pro-preview")
DEFAULT_TEMPERATURE_V3 = float(os.getenv("LOCATION_V3_TEMPERATURE", "0.4"))


async def generate_v3(apt_name: str, address: str, *, model: str | None = None) -> dict:
    """단지명·주소만 입력. Gemini Grounding + thinking high 로 5섹션 분석 생성."""
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        return {
            "_error": "GEMINI_API_KEY 미설정",
            "_meta": {"model": None, "prompt_version": "v3-minimal", "grounding": False, "thinking": False},
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
            "_meta": {"model": used_model, "prompt_version": "v3-minimal", "grounding": False, "thinking": False},
        }

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        result = json.loads(m.group()) if m else {}

    return {
        "headline": (result.get("headline") or "").strip(),
        "body_md": (result.get("body_md") or "").strip(),
        "grounded_facts_used": result.get("_grounded_facts_used") or [],
        "_meta": {
            "model": used_model,
            "prompt_version": "v3-minimal",
            "grounding": grounding_used,
            "thinking": thinking_used,
            "input": {"apt_name": apt_name, "address": address},
        },
    }
