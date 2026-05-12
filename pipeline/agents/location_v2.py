"""location_v2.py — 입지 분석 에이전트 v2 (실험용 복사본).

목적
  Phase 1 (A-1 태그 + B-2/3/4 프롬프트 재설계) 의 효과를 production 에 영향을
  주지 않고 측정하기 위한 격리된 v2 에이전트.

production 과의 차이
  1. **A-1 태그 입력**: facts 에 complex_type 7축 태그를 주입 (district_type,
     supply_special, tenure_type, scale_tier, size_profile,
     special_supply_intensity, price_tier).
  2. **B-1 페르소나**: 시행사 세일즈맨/카피라이터 → 부동산 입지 분석가.
  3. **B-2 강조 축 의무**: 4개 후보(교통/학군/생활권/미래가치) 중 단지에 가장
     두드러진 1~2개를 선택해 본문 90% 를 그 축으로 구성.
  4. **B-3 일반어 금지 사전**: 사이트 cliche 26개 명시 금지 + 구체 수치·고유명사
     최소 3개 의무.
  5. **B-4 Few-shot**: 좋은 출력 예시 1쌍 동봉.

production 코드는 일절 수정하지 않음. 같은 facts 입력에 대해 v1·v2 결과를 비교
가능. UI 보호 정책 미트리거.

사용 (라이브러리)
  from pipeline.agents.location_v2 import generate_v2
  result = await generate_v2(facts, payload)  # facts: orchestrator 가 만든 dict
                                                # payload: cache JSON 전체
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT / "pipeline") not in sys.path:
    sys.path.insert(0, str(ROOT / "pipeline"))


# B-3 cliche 사전 — measure_location_diversity.py 와 동일하게 유지.
CLICHE_BLOCKED = [
    "쾌적한", "우수한", "체계적", "원활", "편리한", "다양한", "잘 갖추",
    "주거 환경", "주거 편의", "생활 인프라", "주거 가치", "정주 여건",
    "안정적", "편안한", "안락한", "조화롭게", "조화를 이루",
    "주거지로서", "주거 트렌드", "현대적", "쾌적성", "효율성",
    "프라이버시", "고급 주거", "완성도",
]


# B-2 강조 축 선택 + B-1 페르소나 + B-3 cliche 금지 + B-4 few-shot 을
# 모두 반영한 v2 프롬프트.
LOCATION_ANALYSIS_PROMPT_V2 = """당신은 {region_label} 지역을 다년간 분석해 온 부동산 입지 분석가입니다.
시행사 카피라이터가 아닌, 매수자 입장의 분석 리포트를 작성합니다.

[제공 데이터]
- 단지명·주소·평형 등 기본 facts
- 단지 7축 태그(complex_type): 단지의 본질을 나타냅니다. 강조 축 선택에 반드시 활용하세요.
- 주변 POI(Kakao Local) 가 있으면 거리·이름을 그대로 인용하세요. 없으면 일반화 표현은 금지하고 "해당 항목은 공고문·지도로 확인 권장" 으로만 적습니다.

[B-2 강조 축 의무]
다음 4개 축 중 이 단지에 가장 두드러진 **1~2개만 선택**해 본문의 90% 를 그 축으로 구성하세요.
나머지 축은 짧게 1줄로만 다루거나 생략합니다. 모든 단지가 같은 4축을 균등하게 다루는 패턴을 절대 만들지 마세요.

  ① 교통 — 지하철·간선도로·환승·통근 시간
  ② 학군 — 학교명·진학률·학원가
  ③ 생활권 — 상권·공원·병원·문화시설
  ④ 미래가치 — 정비사업·호재·개발계획·인구 흐름

complex_type 태그 ↔ 강조 축 가이드 (참고):
  - district_type=신도시 → ③생활권 + ④미래가치
  - district_type=재건축·재개발 → ④미래가치 + ①교통
  - price_tier=초고가/고가 → ②학군 + ①교통
  - scale_tier=대단지 → ③생활권 + ④미래가치
  - supply_special=조합원취소분 → ①교통 + ④미래가치 (재공급 메리트)

[B-3 금지 표현 사전]
다음 단어·표현은 본문에 절대 등장하지 마세요. 어겼다면 다른 단어로 즉시 교체.
  {cliche_list}

또한 다음 일반화도 금지:
  - "기본 인프라가 갖춰져 있다"
  - "주거 만족도가 높은 지역"
  - "출퇴근 환경이 양호"
  - "교육 환경이 잘 정비"
  - "주변 편의시설이 풍부"

[B-3 구체 정보 최소 의무]
본문 전체에 다음을 합쳐 **최소 5개 이상** 등장해야 합니다 (facts·지도 데이터에서 검증된 것만):
  - 역명 + 노선번호 (예: "이촌역 4호선·중앙선")
  - 학교명 + 종류 (예: "신용산초등학교", "용강중학교")
  - 도로명·교량명 (예: "강변북로", "반포대교")
  - 공원·시설명 + 거리 (예: "한강시민공원 약 600m")
  - 평형·세대수 (예: "전용 84㎡·86세대")
검증 불가한 수치는 절대 만들어내지 말고 생략하세요.

[B-1 톤·문체]
- 단정하고 설명적인 문장. 감탄사·이모지·CTA 금지.
- 장점만 나열하지 말고 매수자가 알아야 할 제약·맥락(평형 분포·세대수·규제·재공급 사유 등)을 1회 이상 포함.
- 투자수익·시세차익·가격상승·당첨 가능성 예측 금지.

[B-4 few-shot 예시]
좋은 출력 (지하철 강조 + 구체 정보):
  "단지 도보 5분 거리에 신반포역(7호선)이 있어 강남권 환승이 짧습니다.
   동측 700m 지점의 반포한강공원과 경부고속도로 잠원IC 진입로가 가까워
   차량·도보 동선이 모두 수도권 중심부와 직결됩니다."

나쁜 출력 (cliche 가득):
  "단지 인근에 다양한 교통 인프라가 체계적으로 갖춰져 있어 편리한 이동이
   가능합니다. 쾌적한 주거 환경과 안정적인 정주 여건이 어우러져 있습니다."

[출력 형식 — JSON 만]
{{
  "location_intro": "단지·지역의 본질을 1~2문장으로. 무엇이 이 단지의 강조 축인지가 첫 문장에 드러나야 함.",
  "primary_axes": ["교통" 또는 "학군" 또는 "생활권" 또는 "미래가치" — 최대 2개],
  "subway_score": "",
  "subway_detail": "<ul><li>...</li><li>...</li><li>...</li></ul>",
  "school_score": "",
  "school_detail": "<ul><li>...</li><li>...</li><li>...</li></ul>",
  "feature_score": "",
  "feature_detail": "<ul><li>...</li><li>...</li><li>...</li></ul>",
  "medical_score": "",
  "medical_detail": ""
}}

각 <li> 는 2문장 이상, 구체 정보 1개 이상 포함. 비어 있으면 "공고문·지도로 확인 권장" 명시.

[단지 정보 — facts]:
{facts_json}
"""


def _enrich_with_tags(facts: dict, payload: dict) -> dict:
    """A-1 complex_type 7축 태그를 facts 에 주입."""
    try:
        from pipeline.complex_type_tagger import tag_notice
    except ImportError:
        from complex_type_tagger import tag_notice
    tags = tag_notice(payload)
    enriched = dict(facts)
    enriched["complex_type"] = {
        k: v for k, v in tags.items()
        if not k.startswith("_") and k != "size_distribution"
    }
    return enriched


def _region_label(facts: dict) -> str:
    location = (facts.get("location") or facts.get("supply_location") or "").strip()
    # "서울특별시 용산구 이촌동" → "용산구 이촌동", "경기도 오산시 갈곶동" → "오산시 갈곶동"
    parts = re.split(r"\s+", location)
    if len(parts) >= 2:
        return " ".join(parts[1:])
    return location or "해당"


def build_prompt(facts: dict, payload: dict) -> str:
    """v2 프롬프트를 facts·payload 로 채워 반환."""
    enriched = _enrich_with_tags(facts, payload)
    return LOCATION_ANALYSIS_PROMPT_V2.format(
        region_label=_region_label(enriched),
        cliche_list=" · ".join(CLICHE_BLOCKED),
        facts_json=json.dumps(enriched, ensure_ascii=False, indent=2),
    )


async def generate_v2(facts: dict, payload: dict, *, model: str | None = None) -> dict:
    """v2 입지 분석 결과 생성. production 의 `agent_location_analysis_gemini` 와
    동일한 LLM·정규화 단계를 거치되 프롬프트만 v2 로 교체.

    Returns
    -------
    dict with location_intro / subway_detail / school_detail / feature_detail /
    primary_axes / _meta (model · prompt_version).
    """
    import os
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        return {
            "_error": "GEMINI_API_KEY 미설정",
            "_meta": {"model": None, "prompt_version": "v2"},
        }

    # production 의 헬퍼를 그대로 사용 — 정규화·폴백 로직 일치.
    try:
        from pipeline import orchestrator as orch
    except ImportError:
        import orchestrator as orch  # type: ignore[no-redef]

    from google import genai as google_genai
    from google.genai import types as genai_types

    prompt = build_prompt(facts, payload)
    used_model = model or orch.LLM_LOCATION_MODEL

    client = google_genai.Client(api_key=api_key)
    resp = client.models.generate_content(
        model=used_model,
        contents=prompt,
        config=genai_types.GenerateContentConfig(
            system_instruction="JSON만 출력하세요. 마크다운 코드블록 없이 순수 JSON만.",
        ),
    )
    raw = (resp.text or "").strip()
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        result = json.loads(m.group()) if m else {}

    normalized = orch._normalize_location_output(result, facts)
    normalized["primary_axes"] = result.get("primary_axes", [])
    normalized["_meta"] = {
        "model": used_model,
        "prompt_version": "v2",
    }
    return normalized
