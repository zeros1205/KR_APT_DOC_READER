"""location_v2.py — 입지 분석 에이전트 v2 (실험용 복사본, rev 2).

production agent_location_analysis_gemini 와 동일한 LLM·정규화 단계, 다만:
  1. **Grounding(Google Search) 활성화** — Gemini 가 실시간 검색으로 시공사·
     브랜드 전사·재건축 이전 단지명·인근 비교 단지·학교명·시설명 등을
     검증된 외부 정보에서 가져옴. Gemini 앱과 같은 메커니즘.
  2. **모델 업그레이드** — flash-lite → gemini-2.5-flash (Grounding 지원 + 한국어
     품질 ↑). env override 가능.
  3. **A-1 7축 태그** facts 주입 + 본문 첫 문장 명시 의무.
  4. **B-1 페르소나** — 부동산 입지 분석가.
  5. **B-2 강조 축**: 7축 태그를 본문 구조의 1차 근거로, 4축은 시각.
  6. **B-3 cliche 사전 + 회피 문구 사전** 본문 절대 금지. 검증된 내용이 없으면
     해당 li 통째 생략 (회피 문구로 채우지 마라).
  7. **B-4 few-shot** — 좋은 출력(Gemini 앱 결과 발췌) vs 나쁜 출력(현 v1 발췌).
  8. **사실 분리** — 분양가·일정·자격·세대수·평형 같은 단지 고유 사실은 facts
     에서만. 그 외 공개 정보(시공사·브랜드 전사·재건축·학교·랜드마크 등) 는
     LLM 지식 + Google Search 결과 활용 가능. 변동성 큰 수치(가격·경쟁률·진학률
     실시간)는 검색 출처가 명확할 때만 인용.

production 코드는 일절 수정하지 않음. UI 보호 정책 미트리거.
"""

from __future__ import annotations

import json
import os
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

# rev 2 신설 — 회피·면피성 문구 절대 금지 사전. 이 단어가 본문에 등장하면
# 그 li 또는 섹션을 통째로 생략하는 것이 정답.
EVASIVE_BLOCKED = [
    "확인 권장", "확인 필요", "함께 보세요", "함께 살펴", "같이 확인",
    "공고문을 확인", "공고문으로 확인", "지도를 확인", "지도로 확인",
    "교육청에 확인", "교육 자료로 확인", "추가 확인", "구체적으로 확인",
    "꼼꼼히 확인", "직접 확인", "사전에 확인", "검토해야 합니다",
]


LOCATION_ANALYSIS_PROMPT_V2 = """당신은 {region_label} 지역을 다년간 분석해 온 부동산 입지 분석가입니다.
시행사 카피라이터가 아닌, 매수자 입장의 분석 리포트를 작성합니다.
필요하면 Google Search 도구를 적극 활용해 시공사·브랜드 전사·재건축 이전 단지명·
인근 비교 단지·학교·역·랜드마크 같은 공개 정보를 검증한 뒤 인용하세요.

[7축 태그 — complex_type, A-1]
단지의 본질을 나타내는 7개 축이 facts 의 `complex_type` 에 미리 분류되어 있습니다.
location_intro 첫 문장은 반드시 이 7축 중 가장 두드러진 1~2개 항목을 키워드로
시작하세요. 4단지가 같은 첫 문장 패턴을 만들면 실패입니다.

  예시 — supply_special=조합원취소분 + size_profile=중대형:
    "조합원 취소분으로 재공급되는 86세대 중대형 회차로, ..."

  예시 — district_type=재건축·재개발 + tenure_type=분양:
    "구 {{이전단지명}} 자리에 재건축으로 조성되는 정비사업 단지로, ..."

  예시 — price_tier=초고가/고가 + scale_tier=대단지:
    "평당 N억 권역의 ○○ 일대 대단지로, ..."

[B-2 본문 구조의 1차 근거 = 7축, 2차 = 4축 시각]
본문은 7축 태그 중 두드러진 항목을 풀어내는 방식으로 구성하고,
다음 4축은 그 풀이를 담는 그릇으로만 활용하세요. 4단지가 같은 4축 슬롯을
균등하게 채우는 패턴은 실패입니다.

  ① 교통 · ② 학군 · ③ 생활권 · ④ 미래가치

complex_type 별 강조 우선순위 (참고, 절대 규칙 아님):
  district_type=재건축·재개발 → ④미래가치 + 단지 전사(과거 단지명·시공사)
  supply_special=조합원취소분 → ④미래가치 + 청약 메리트(분양가상한제·재공급 사유)
  price_tier=초고가/고가 → ②학군 + 인근 비교 단지(랜드마크와의 차별점)
  scale_tier=대단지 → ③생활권 + 단지 특화 시설
  district_type=신도시 → ③생활권 + ④미래가치(개발계획)

[정보 활용 규칙]
1. **분양가·일정·자격·세대수·평형·규제·재공급 사유** 같은 단지 고유 사실 →
   반드시 facts 에서만 인용. facts 에 없으면 그 항목을 본문에 쓰지 않음.
2. **시공사·브랜드 전사·재건축 이전 단지명·인근 비교 단지·역명·노선번호·
   학교명·도로명·랜드마크** 등 공개 정보 → LLM 지식 + Google Search 활용 가능.
   불확실하면 검색해서 확인 후 인용.
3. **변동성 큰 수치(현재 시세·청약 경쟁률·진학률 실시간)** → 검색 출처가
   명확할 때만 인용. 불명확하면 생략.

[B-3 절대 금지 — cliche 사전]
다음 단어·표현이 본문에 등장하면 즉시 다른 단어로 교체. 어겼다면 작성 실패:
  {cliche_list}

[rev 2 절대 금지 — 회피·면피성 문구]
다음 표현이 본문에 등장하는 것은 작성 실패와 동일합니다. 검증된 내용이 없으면
**그 li 를 통째로 생략하거나 해당 섹션을 비우세요. 회피 문구로 채우지 마세요.**
  {evasive_list}

또한 다음 일반화 표현도 금지:
  - "기본 인프라가 갖춰져 있다"
  - "주거 만족도가 높은 지역"
  - "출퇴근 환경이 양호"
  - "교육 환경이 잘 정비"
  - "주변 편의시설이 풍부"

[B-1 톤·문체]
- 단정하고 설명적인 문장. 감탄사·이모지·CTA 금지.
- 장점만 나열하지 말고 매수자가 알아야 할 제약·맥락(평형 분포·세대수·규제·
  재공급 사유·소규모 단지의 한계 등) 을 본문 어딘가에 1회 이상 포함.
- 투자수익·시세차익·가격상승·당첨 가능성 예측 금지. 단 인근 비교 단지의 객관적
  특성 언급은 가능.

[B-4 few-shot — 좋은 출력 vs 나쁜 출력]
좋은 출력 (7축 활용 + 검증된 외부 정보 + 단지 컨텍스트):
  "구 신반포 21차 자리에 재건축된 251세대 소규모 단지로, 포스코이앤씨가
   하이엔드 브랜드 '오티에르' 를 처음 적용한 케이스이다. 7호선 반포역과
   3·7·9호선 고속터미널역을 도보로 잇는 더블 역세권이고, 반원초·경원중·
   세화고 등 강남 8학군 동선에 있다. 분양가상한제가 적용되어 후분양으로
   진행되며, 청약 당시 약 710:1 의 경쟁률을 기록했다."

나쁜 출력 (cliche + 회피 문구):
  "단지 인근에 다양한 교통 인프라가 체계적으로 갖춰져 있어 편리한 이동이
   가능합니다. 자세한 노선과 시설은 지도를 함께 확인해 주세요. 교육 환경은
   주변 시설과 어우러져 있으며 자녀 교육은 공고문을 추가 확인해야 합니다."

[출력 형식 — JSON 만]
{{
  "location_intro": "7축 태그 1~2개를 키워드로 시작하는 1~3문장. 단지 본질이 드러나야 함.",
  "primary_axes": ["7축 태그 키 이름 중 핵심 1~2개. 예: ['supply_special', 'size_profile']"],
  "subway_score": "",
  "subway_detail": "<ul><li>...</li></ul>  검증된 정보 있는 만큼만 li 작성. 없으면 빈 ul.",
  "school_score": "",
  "school_detail": "<ul><li>...</li></ul>",
  "feature_score": "",
  "feature_detail": "<ul><li>...</li></ul>",
  "medical_score": "",
  "medical_detail": ""
}}

li 수 강제 없음. 1~3개 자유. 회피 문구로 채우느니 비우세요.
각 <li> 는 2문장 이상, 검증된 정보 1개 이상 포함.

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
    parts = re.split(r"\s+", location)
    if len(parts) >= 2:
        return " ".join(parts[1:])
    return location or "해당"


def build_prompt(facts: dict, payload: dict) -> str:
    enriched = _enrich_with_tags(facts, payload)
    return LOCATION_ANALYSIS_PROMPT_V2.format(
        region_label=_region_label(enriched),
        cliche_list=" · ".join(CLICHE_BLOCKED),
        evasive_list=" · ".join(EVASIVE_BLOCKED),
        facts_json=json.dumps(enriched, ensure_ascii=False, indent=2),
    )


# rev 2: env override 가능. 기본은 grounding 지원하는 gemini-2.5-flash.
DEFAULT_MODEL_V2 = os.getenv("LOCATION_V2_MODEL", "gemini-2.5-flash")


async def generate_v2(facts: dict, payload: dict, *, model: str | None = None) -> dict:
    """v2 입지 분석 결과 생성.

    - Grounding(Google Search) 활성화 — Gemini 앱과 동일한 메커니즘.
    - production 의 _normalize_location_output 으로 폴백·정규화 호환.
    """
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        return {
            "_error": "GEMINI_API_KEY 미설정",
            "_meta": {"model": None, "prompt_version": "v2-rev2", "grounding": False},
        }

    try:
        from pipeline import orchestrator as orch
    except ImportError:
        import orchestrator as orch  # type: ignore[no-redef]

    from google import genai as google_genai
    from google.genai import types as genai_types

    prompt = build_prompt(facts, payload)
    used_model = model or DEFAULT_MODEL_V2

    client = google_genai.Client(api_key=api_key)

    # rev 2: Google Search Grounding 활성화. 실패하면 grounding 없이 재시도.
    grounding_used = False
    raw = ""
    try:
        config = genai_types.GenerateContentConfig(
            system_instruction="JSON만 출력하세요. 마크다운 코드블록 없이 순수 JSON만.",
            tools=[genai_types.Tool(google_search=genai_types.GoogleSearch())],
        )
        resp = client.models.generate_content(
            model=used_model,
            contents=prompt,
            config=config,
        )
        raw = (resp.text or "").strip()
        grounding_used = True
    except Exception as exc_grounding:
        # grounding 미지원 모델이면 일반 호출로 폴백
        try:
            config = genai_types.GenerateContentConfig(
                system_instruction="JSON만 출력하세요. 마크다운 코드블록 없이 순수 JSON만.",
            )
            resp = client.models.generate_content(
                model=used_model,
                contents=prompt,
                config=config,
            )
            raw = (resp.text or "").strip()
        except Exception as exc_plain:
            return {
                "_error": f"Gemini 호출 실패: grounding={exc_grounding} / plain={exc_plain}",
                "_meta": {"model": used_model, "prompt_version": "v2-rev2", "grounding": False},
            }

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        result = json.loads(m.group()) if m else {}

    normalized = orch._normalize_location_output(result, facts)
    normalized["primary_axes"] = result.get("primary_axes", [])
    normalized["_meta"] = {
        "model": used_model,
        "prompt_version": "v2-rev2",
        "grounding": grounding_used,
    }
    return normalized
