"""location_v2.py — 입지 분석 에이전트 v2 (실험용 복사본, rev 3).

production agent_location_analysis_gemini 와 동일한 LLM·정규화 단계, 다만:
  1. **거리 검증된 POI 데이터를 facts.nearby 에 주입** (A-2 핵심) — 강남역
     인근 단지에서 멀리 떨어진 남부터미널역을 언급하던 사고를 차단.
     Kakao Local 의 category_search 로 500m·1000m·2000m 동심원 POI 를
     이름·거리·노선·카테고리와 함께 prompt 에 동봉. LLM 은 역·학교·시설명을
     이 리스트에서만 인용 가능.
  2. **Google Search Grounding** — 거리 무관 정보(시공사·브랜드 전사·재건축
     이전 단지명·인근 비교 단지·청약 메리트 등) 만 활용. 위치 의존 정보는
     절대 Grounding 결과에서 가져오지 않음.
  3. **A-1 7축 태그** 본문 첫 문장 명시 의무.
  4. **회피·면피 문구 사전** 본문 절대 금지. 검증된 내용 없으면 li 통째 생략.
  5. **모델 업그레이드** — gemini-2.5-flash (Grounding 지원 + 한국어 품질).

production 코드는 일절 수정하지 않음. UI 보호 정책 미트리거.
"""

from __future__ import annotations

import asyncio
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

# 회피·면피성 문구 절대 금지 사전.
EVASIVE_BLOCKED = [
    "확인 권장", "확인 필요", "함께 보세요", "함께 살펴", "같이 확인",
    "공고문을 확인", "공고문으로 확인", "지도를 확인", "지도로 확인",
    "교육청에 확인", "교육 자료로 확인", "추가 확인", "구체적으로 확인",
    "꼼꼼히 확인", "직접 확인", "사전에 확인", "검토해야 합니다",
]


LOCATION_ANALYSIS_PROMPT_V2 = """당신은 {region_label} 지역을 다년간 분석해 온 부동산 입지 분석가입니다.
시행사 카피라이터가 아닌, 매수자 입장의 분석 리포트를 작성합니다.

[정보 활용 3계층 규칙 — 반드시 지킬 것]
이 규칙은 과거 사고(강남역 인근 단지에서 멀리 떨어진 남부터미널역을 언급하던 환각)
를 막기 위한 안전장치입니다.

1. **거리 의존 정보 — 역·학교·도로·공원·시설명**: 반드시 `facts.nearby` 에 있는
   항목에서만 인용. 거리(m) 와 카테고리·노선을 그대로 인용. nearby 에 없으면
   해당 내용을 본문에 쓰지 마세요. LLM 일반 지식·Google Search 로 다른 시설을
   추측해 채우면 작성 실패.

2. **단지 고유 사실 — 분양가·일정·자격·세대수·평형·규제·재공급 사유**: 반드시
   `facts` 의 해당 필드에서만 인용. 추정·환각 금지.

3. **거리 무관 공개 정보 — 시공사·브랜드 전사·재건축 이전 단지명·청약 메리트·
   인근 비교 단지·지역 일반 특성**: LLM 지식 + Google Search 활용 가능. 검색
   결과로 검증한 정보만 인용. 변동성 큰 수치(현재 시세·실시간 경쟁률·진학률)
   는 출처가 명확할 때만, 출처를 본문에 자연스럽게 녹여 인용.

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

[B-2 본문 구조 = 7축 1차, 4축 2차]
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

[B-3 절대 금지 — cliche 사전]
다음 단어·표현이 본문에 등장하면 즉시 다른 단어로 교체. 어겼다면 작성 실패:
  {cliche_list}

[절대 금지 — 회피·면피성 문구]
다음 표현이 본문에 등장하는 것은 작성 실패와 동일합니다. 검증된 내용이 없으면
**그 li 를 통째로 생략하거나 해당 섹션을 비우세요. 회피 문구로 채우지 마세요.**
  {evasive_list}

[톤·문체]
- 단정하고 설명적인 문장. 감탄사·이모지·CTA 금지.
- 장점만 나열하지 말고 매수자가 알아야 할 제약·맥락(평형 분포·세대수·규제·
  재공급 사유·소규모 단지의 한계 등) 을 본문 어딘가에 1회 이상 포함.
- 투자수익·시세차익·가격상승·당첨 가능성 예측 금지. 단 인근 비교 단지의
  객관적 특성 언급은 가능.

[B-4 few-shot — 좋은 출력 vs 나쁜 출력]
좋은 출력 (7축 활용 + facts.nearby 인용 + Google Search 로 검증된 컨텍스트):
  "구 신반포 21차 자리에 재건축된 251세대 소규모 단지로, 포스코이앤씨가
   하이엔드 브랜드 '오티에르' 를 처음 적용한 케이스이다. facts.nearby 의
   고속터미널역(3·7·9호선, 약 480m) 과 반포역(7호선, 약 720m) 이 모두
   도보권에 있어 강남권 환승이 짧다. 분양가상한제가 적용되어 후분양으로
   진행되며, 청약 당시 약 710:1 의 경쟁률을 기록했다."

나쁜 출력 1 (회피 문구):
  "단지 인근의 교통 인프라는 지도를 함께 확인해 주세요. 교육 환경은
   교육청 자료로 확인해야 합니다."

나쁜 출력 2 (거리 의존 정보 환각):
  "(facts.nearby 에 없는 역을 임의 추정해 본문에 포함하는 경우)"

[출력 형식 — JSON 만]
{{
  "location_intro": "7축 태그 1~2개를 키워드로 시작하는 1~3문장. 단지 본질이 드러나야 함.",
  "primary_axes": ["7축 태그 키 이름 1~2개. 예: ['supply_special', 'size_profile']"],
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

[단지 정보 — facts (단지 고유 사실)]:
{facts_json}

[facts.nearby — 거리 검증된 인근 POI (역·학교·시설명은 여기서만 인용)]:
{nearby_json}
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


async def _fetch_nearby_pois(facts: dict) -> dict:
    """Kakao Local 로 500m·1000m·2000m 동심원 POI 를 수집해 facts.nearby 용
    dict 를 반환. KAKAO_API_KEY 미설정 시 빈 dict.

    카테고리 코드 (Kakao Local):
      SW8 = 지하철역, SC4 = 학교, HP8 = 병원, MT1 = 대형마트, AT4 = 관광명소
    """
    api_key = os.getenv("KAKAO_API_KEY", "").strip()
    if not api_key:
        return {}
    address = (facts.get("supply_location") or facts.get("location") or "").strip()
    if not address:
        return {}

    try:
        from pipeline.kakao_local import KakaoLocalClient
    except ImportError:
        from kakao_local import KakaoLocalClient  # type: ignore[no-redef]

    client = KakaoLocalClient(api_key)
    coords = await client.geocode(address)
    apt_name = (facts.get("apt_name") or "").strip()
    if not coords and apt_name:
        coords = await client.geocode_keyword(apt_name, region_hint=address)
    if not coords:
        return {}
    x, y = coords

    async def _gather(code: str, radius: int) -> list[dict]:
        try:
            return await client.category_search(code, x=x, y=y, radius=radius)
        except Exception:
            return []

    # 카테고리별로 가장 가까운 것부터 합치되 중복 제거.
    def _flatten(docs_list: list[list[dict]]) -> list[dict]:
        seen: set[str] = set()
        out: list[dict] = []
        for docs in docs_list:
            for d in docs:
                name = d.get("place_name") or ""
                if not name or name in seen:
                    continue
                seen.add(name)
                out.append(d)
        return out

    # 동심원: 500m / 1000m / 2000m
    subway_docs = _flatten(await asyncio.gather(
        _gather("SW8", 500), _gather("SW8", 1000), _gather("SW8", 2000),
    )) if False else _flatten([await _gather("SW8", 2000)])
    school_docs = _flatten([await _gather("SC4", 1000), await _gather("SC4", 2000)])
    hospital_docs = _flatten([await _gather("HP8", 1500)])
    mart_docs = _flatten([await _gather("MT1", 1500)])
    landmark_docs = _flatten([await _gather("AT4", 2000)])

    def _norm(doc: dict, category: str) -> dict:
        try:
            distance = int(doc.get("distance") or 0)
        except (TypeError, ValueError):
            distance = 0
        return {
            "name": doc.get("place_name"),
            "category": category,
            "subcategory": doc.get("category_name", "").split(" > ")[-1] if doc.get("category_name") else "",
            "distance_m": distance,
            "address": doc.get("address_name") or doc.get("road_address_name"),
        }

    def _sort_limit(items: list[dict], n: int) -> list[dict]:
        return sorted(items, key=lambda d: d.get("distance_m") or 999999)[:n]

    nearby = {
        "subway": _sort_limit([_norm(d, "subway") for d in subway_docs], 6),
        "schools": _sort_limit([_norm(d, "school") for d in school_docs], 6),
        "hospitals": _sort_limit([_norm(d, "hospital") for d in hospital_docs], 3),
        "marts": _sort_limit([_norm(d, "mart") for d in mart_docs], 3),
        "landmarks": _sort_limit([_norm(d, "landmark") for d in landmark_docs], 5),
        "_meta": {"coords": {"x": x, "y": y}, "source": "kakao_local"},
    }
    return nearby


async def build_prompt(facts: dict, payload: dict) -> str:
    enriched = _enrich_with_tags(facts, payload)
    nearby = await _fetch_nearby_pois(enriched)
    enriched["nearby"] = nearby
    return LOCATION_ANALYSIS_PROMPT_V2.format(
        region_label=_region_label(enriched),
        cliche_list=" · ".join(CLICHE_BLOCKED),
        evasive_list=" · ".join(EVASIVE_BLOCKED),
        facts_json=json.dumps({k: v for k, v in enriched.items() if k != "nearby"}, ensure_ascii=False, indent=2),
        nearby_json=json.dumps(nearby, ensure_ascii=False, indent=2) if nearby else '{"_note": "KAKAO_API_KEY 미설정 또는 좌표 변환 실패 — 위치 의존 정보는 본문에 쓰지 마세요"}',
    )


# env override 가능. 운영자 지정 — gemini-3.1-pro-preview (Grounding + 한국어 분석 품질).
DEFAULT_MODEL_V2 = os.getenv("LOCATION_V2_MODEL", "gemini-3.1-pro-preview")


async def generate_v2(facts: dict, payload: dict, *, model: str | None = None) -> dict:
    """v2 입지 분석 결과 생성.

    - 거리 의존 정보(역·학교·시설명)는 facts.nearby 에 검증된 POI 만 인용 가능.
    - 거리 무관 컨텍스트(시공사·브랜드·재건축 전사 등)는 Google Search Grounding 활용.
    - production 의 _normalize_location_output 으로 폴백·정규화 호환.
    """
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        return {
            "_error": "GEMINI_API_KEY 미설정",
            "_meta": {"model": None, "prompt_version": "v2-rev3", "grounding": False},
        }

    try:
        from pipeline import orchestrator as orch
    except ImportError:
        import orchestrator as orch  # type: ignore[no-redef]

    from google import genai as google_genai
    from google.genai import types as genai_types

    prompt = await build_prompt(facts, payload)
    used_model = model or DEFAULT_MODEL_V2

    # gemini-3.1-pro-preview + thinking high 는 응답이 길어질 수 있어 SDK timeout
    # 명시적으로 넉넉히 (600초). http_options 미지원 버전이면 기본값 사용.
    try:
        http_options = genai_types.HttpOptions(timeout=600_000)  # ms
        client = google_genai.Client(api_key=api_key, http_options=http_options)
    except (AttributeError, TypeError):
        client = google_genai.Client(api_key=api_key)

    # Grounding + thinking_level=high 활성화. 옵션을 점진 폴백.
    grounding_used = False
    thinking_used = False
    raw = ""

    def _make_config(*, with_grounding: bool, with_thinking: bool):
        kwargs: dict = {
            "system_instruction": "JSON만 출력하세요. 마크다운 코드블록 없이 순수 JSON만.",
        }
        if with_grounding:
            kwargs["tools"] = [genai_types.Tool(google_search=genai_types.GoogleSearch())]
        if with_thinking and hasattr(genai_types, "ThinkingConfig"):
            # gemini-3.1 / 2.5 추론 모델 thinking_config. SDK 버전에 따라
            # thinking_level(신) 또는 thinking_budget(구) 만 지원.
            try:
                kwargs["thinking_config"] = genai_types.ThinkingConfig(thinking_level="high")
            except TypeError:
                try:
                    kwargs["thinking_config"] = genai_types.ThinkingConfig(thinking_budget=-1)
                except Exception:
                    pass
        return genai_types.GenerateContentConfig(**kwargs)

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
            "_meta": {"model": used_model, "prompt_version": "v2-rev3", "grounding": False, "thinking": False},
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
        "prompt_version": "v2-rev3",
        "grounding": grounding_used,
        "thinking": thinking_used,
    }
    return normalized
