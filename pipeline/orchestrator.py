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
from pathlib import Path
from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    ANTHROPIC_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY,
    LLM_CONTENT_MODEL, LLM_EXTRACT_MODEL, LLM_FACTCHECK_MODEL,
    OUTPUT_DIR, MIN_QUALITY_SCORE, MAX_CTA_PER_POST, MIN_CHAR_COUNT,
    CTA_LOAN_COMPARE, CTA_INTERIOR, CTA_MOVING, CTA_TAX, CTA_KAKAO_CHANNEL,
    PREFERRED_IMAGE_SOURCE, BLOG_THEME,
)
from html_renderer import BlogHTMLRenderer, PostData, QABlock, UnitType, save_post
from image_finder import find_images_for_post, ImageResult
from agents.collector import NoticeDocument

claude  = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)


async def _call_claude(system: str, user: str, model: str, max_tokens: int = 4096) -> str:
    """Claude API 호출 헬퍼 — JSON 순수 출력 전용"""
    resp = await claude.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return resp.content[0].text


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
- resale_restriction: 전매제한 기간
- contract_ratio: 계약금 비율 (숫자만, 예: 10)
- contract_amount: 최저 분양가 기준 계약금 금액 (예: "약 3,000만원"), 공고에 없으면 null
- midterm_ratio: 중도금 비율 (숫자만, 예: 60)
- midterm_count: 중도금 납부 횟수 (숫자만, 예: 6), 공고에 없으면 6
- balance_ratio: 잔금 비율 (숫자만, 예: 30)
- acquisition_tax_rate: 취득세율 (예: "1~3%")
- is_hot_zone: 투기과열지구 여부 (Y/N/해당없음, 없으면 null)
- live_requirement: 실거주 의무 여부 (예: "2년 실거주 의무", "없음", 없으면 null)
- is_price_cap: 분양가상한제 여부 (Y/N)
- eligibility_special: 배열 — 공고에 명시된 특별공급 유형별 신청자격
  각 항목: type_name(예: "생애최초", "신혼부부", "다자녀", "노부모부양", "기관추천"),
           quota(예: "20호" — 없으면 null),
           requirements(핵심 자격 요건 문장 목록, 최대 4개, 공고 원문 기준)
- eligibility_rank1: 배열 — 1순위 신청자격 핵심 요건 문장 목록 (최대 5개, 공고 원문 기준)
- eligibility_rank2: 배열 — 2순위 신청자격 핵심 요건 문장 목록 (최대 3개, 공고 원문 기준)

[공고 원문]:
{notice_text}
"""


async def agent_fact_extraction(notice_text: str) -> dict:
    """Agent 1: 공고문에서 팩트를 추출하여 구조화된 JSON 반환 (Claude Haiku)"""
    print("  [Agent 1] 팩트 추출 시작...")
    raw = await _call_claude(
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
    print(f"  [Agent 1] 완료: {facts.get('apt_name', '미확인')} 추출")
    return facts


# ──────────────────────────────────────────────────
# Agent 2: 입지 분석 (Gemini)
# ──────────────────────────────────────────────────

LOCATION_ANALYSIS_PROMPT = """당신은 한국 부동산 입지 분석 전문가입니다.
아래 단지 정보를 바탕으로 입지 분석을 정확하게 작성하세요.

【필수 준수 원칙】
- 실제로 존재하는 역명·학교명·병원명·상업시설명만 기재. 모르면 "확인 필요" 기재
- 비수도권(강원·충청·전라·경상·제주 등) 지역에서는 지하철/도시철도 언급 절대 금지.
  대신 KTX·버스·도로 접근성·생활권 중심으로 서술
- 지하철 가능 도시: 서울·경기·인천·대전·대구·부산·광주·울산(일부)
- 도보 5분 ≈ 400m, 도보 10분 ≈ 800m, 도보 15분 ≈ 1.2km 기준 준수
- 별점 기준:
  subway: ★★★★★ 도보5분이내 / ★★★★☆ 도보10분 / ★★★☆☆ 도보15분 / ★★☆☆☆ 버스환승 / ★☆☆☆☆ 지하철없음·비수도권
  school: ★★★★★ 학원가+명문중고 / ★★★★☆ 초등+중학군양호 / ★★★☆☆ 보통 / ★★☆☆☆ 원거리 / ★☆☆☆☆ 정보없음
  life:   ★★★★★ 대형마트+백화점 도보권 / ★★★★☆ 대형마트10분 / ★★★☆☆ 슈퍼+편의점 / ★★☆☆☆ 차량필요 / ★☆☆☆☆ 편의시설없음
  medical:★★★★★ 대학병원 도보권 / ★★★★☆ 종합병원 차량5분 / ★★★☆☆ 차량10분 / ★★☆☆☆ 의원급만 / ★☆☆☆☆ 의료기관없음

[단지 정보]:
{facts_json}

JSON만 출력:
{{
  "location_intro": "100~150자. 해당 지역 분위기·생활 환경을 독자에게 친근하게 설명",
  "subway_score":   "★★★☆☆",
  "subway_detail":  "역명과 도보 분수 명시. 비수도권은 KTX/버스/도로 접근성. 지하철 없는 도시에서 지하철 절대 금지",
  "school_score":   "★★★★☆",
  "school_detail":  "배정 초등학교명 + 학군 평가",
  "life_score":     "★★★☆☆",
  "life_detail":    "가장 가까운 대형마트·백화점·상업시설 명칭과 거리",
  "medical_score":  "★★★☆☆",
  "medical_detail": "가장 가까운 종합병원 명칭과 거리"
}}"""

LOCATION_VERIFY_PROMPT = """아래는 AI가 생성한 입지 분석입니다.
사실 정확성을 검증하고 오류가 있으면 수정하세요.

검증 기준:
1. 역명·학교명·병원명·상업시설명이 실제 위치 근처에 존재하는가?
2. 비수도권에서 지하철을 언급하는 오류가 없는가?
3. 도보·차량 거리 수치가 현실적인가?
4. 별점이 설명 내용과 일치하는가?

[단지명]: {apt_name}
[위치]: {location}

[Gemini 생성 입지 분석]:
{location_json}

수정 필요 시 수정된 JSON 반환. 수정 없으면 원본 그대로 반환. JSON만 출력."""

_LOCATION_KEYS = (
    "location_intro", "subway_score", "subway_detail",
    "school_score", "school_detail", "life_score", "life_detail",
    "medical_score", "medical_detail",
)


async def agent_location_analysis_gemini(facts: dict) -> dict:
    """Agent 2: Gemini로 입지 분석 생성"""
    print("  [Agent 2] 입지 분석 시작 (Gemini)...")
    if not GEMINI_API_KEY:
        print("  [Agent 2] GEMINI_API_KEY 미설정 → 건너뜀")
        return {}
    try:
        from google import genai as google_genai
        from google.genai import types as genai_types
        client = google_genai.Client(api_key=GEMINI_API_KEY)
        resp = client.models.generate_content(
            model=LLM_FACTCHECK_MODEL,
            contents=LOCATION_ANALYSIS_PROMPT.format(
                facts_json=json.dumps(facts, ensure_ascii=False, indent=2)
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
            result = json.loads(m.group()) if m else {}
        print(f"  [Agent 2] 완료: subway_detail={result.get('subway_detail','')[:40]}")
        return result
    except Exception as e:
        print(f"  [Agent 2] Gemini 오류 ({e}) → 빈 딕셔너리 반환")
        return {}


async def agent_location_verify_claude(location_data: dict, facts: dict) -> dict:
    """Agent 3: Claude Sonnet으로 입지 분석 검증·교정"""
    print("  [Agent 3] 입지 분석 검증 시작 (Claude)...")
    if not location_data:
        return location_data
    try:
        raw = await _call_claude(
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
        print(f"  [Agent 3] Claude 검증 오류 ({e}) → Gemini 결과 그대로 사용")
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

[단지 정보]:
{facts_json}

다음 JSON 형식으로 출력하세요:
{{
  "post_title": "50자 이내 후킹 제목 (단지명+위치+분양가 또는 핵심 포인트 포함)",
  "post_subtitle": "30자 이내 부제목 (이 글을 읽어야 하는 이유)",
  "seo_tags": ["단지명태그", "지역태그", "청약관련태그", ...최대10개],

  "apt_intro": "150~200자. 반드시 '안녕하세요. 복잡한 청약 공고문을 쉽게 정리해 드리는 정과장입니다. 오늘은 ' 으로 시작. 이어서 단지명과 가장 큰 매력 포인트를 자연스럽게 연결. <strong> 태그 사용 가능.",

  "location_intro": "100~150자. 해당 지역의 분위기와 생활 환경을 친근하게 설명. 지역 특색과 장점 중심. 독자가 그 동네를 떠올릴 수 있도록 묘사.",

  "financial_intro": "80~100자. 자금 계획의 중요성을 공감 가는 방식으로 도입. '청약 당첨만큼 중요한 게 자금 준비인데요~' 같은 톤.",

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
      "answer": "300~500자. 세율·한도 단정 금지. '일반적인 기준' 수준으로만 안내. 답변 말미 ※ 문구 필수."
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
    """Agent 4: 서술형 콘텐츠 + Q&A 생성 (Claude Sonnet — 따뜻한 문체)"""
    print("  [Agent 4] 콘텐츠 생성 시작 (Claude Sonnet)...")
    raw = await _call_claude(
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
    print(f"  [Agent 4] 완료: Q&A {len(content.get('qa_blocks', []))}개 생성")
    return content


# ──────────────────────────────────────────────────
# Agent 5: Q&A 팩트체크 (Gemini)
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
    """Agent 5: Gemini로 Q&A 팩트체크 — 오류 답변 자동 정정"""
    print("  [Agent 5] Q&A 팩트체크 시작 (Gemini)...")

    if not GEMINI_API_KEY:
        print("  [Agent 5] GEMINI_API_KEY 미설정 → 팩트체크 건너뜀")
        return content

    try:
        from google import genai as google_genai
        from google.genai import types as genai_types
        client = google_genai.Client(api_key=GEMINI_API_KEY)
        user_msg = FACTCHECK_USER_TPL.format(
            facts_json=json.dumps(facts, ensure_ascii=False, indent=2),
            qa_json=json.dumps(content.get("qa_blocks", []), ensure_ascii=False, indent=2),
        )
        resp = client.models.generate_content(
            model=LLM_FACTCHECK_MODEL,
            contents=user_msg,
            config=genai_types.GenerateContentConfig(
                system_instruction=FACTCHECK_SYSTEM,
            ),
        )
        raw = resp.text.strip()

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
#   [Agent 3] 입지 검증 (Claude Sonnet) — 역명·학교명·비수도권 지하철 오류 교정
#   [Agent 4] 콘텐츠 생성 (Claude Sonnet)
#   [Agent 5] Q&A 팩트체크 (Gemini)
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


async def run_pipeline(notice_text: str, max_retries: int = 2, theme: str = "", supply_type: str = "", notice_url: str = "") -> Path | None:
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

    # Step 2: 입지 분석 (Gemini → Claude 검증)
    location_data = await agent_location_analysis_gemini(facts)
    location_data = await agent_location_verify_claude(location_data, facts)

    # Step 3~4: 콘텐츠 생성 + 품질 검수 루프
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
    unit_types = [
        UnitType(
            type_name=ut["type_name"],
            area_sqm=float(ut.get("area_sqm", 0)),
            general_units=int(ut.get("general_units", 0)),
            special_units=int(ut.get("special_units", 0)),
            price_min=int(ut.get("price_min", 0)),
            price_max=int(ut.get("price_max", 0)),
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

    post_data = PostData(
        apt_name=apt_name,
        post_title=content.get("post_title", f"{apt_name} 청약 완벽 분석"),
        post_subtitle=content.get("post_subtitle", "청약 전 반드시 확인하세요"),
        location=facts.get("location", ""),
        supply_location=facts.get("supply_location", ""),
        supply_scale=facts.get("supply_scale", ""),
        total_households=str(facts.get("total_households") or ""),
        is_hot_zone=facts.get("is_hot_zone") or "",
        live_requirement=facts.get("live_requirement") or "",
        price_range=facts.get("price_range", ""),
        unit_types=unit_types,
        special_supply_date=facts.get("special_supply_date", "-"),
        rank1_date=facts.get("rank1_date", "-"),
        rank2_date=facts.get("rank2_date", "-"),
        winner_date=facts.get("winner_date", "-"),
        move_in_date=facts.get("move_in_date", "-"),
        loan_info=facts.get("loan_info") or "-",
        resale_restriction=facts.get("resale_restriction") or "-",
        contract_ratio=str(facts.get("contract_ratio") or "10"),
        contract_amount=facts.get("contract_amount") or "",
        midterm_ratio=str(facts.get("midterm_ratio") or "60"),
        midterm_count=str(facts.get("midterm_count") or "6"),
        balance_ratio=str(facts.get("balance_ratio") or "30"),
        acquisition_tax_rate=facts.get("acquisition_tax_rate", "1~3%"),
        acquisition_tax_amount="-",
        property_tax_rate="과세표준 × 0.1~0.4%",
        property_tax_amount="-",
        capital_gains_tax_rate="1주택 2년 보유 시 비과세 가능",
        capital_gains_tax_amount="-",
        subway_score=content.get("subway_score", "★★★☆☆"),
        subway_detail=content.get("subway_detail", ""),
        school_score=content.get("school_score", "★★★☆☆"),
        school_detail=content.get("school_detail", ""),
        life_score=content.get("life_score", "★★★☆☆"),
        life_detail=content.get("life_detail", ""),
        medical_score=content.get("medical_score", "★★★☆☆"),
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
    print(f"\n  [RAG] '{doc.apt_name}' 공고 처리 시작... (공급유형: {doc.supply_type or '신규'} → 테마: {theme})")

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

    return await run_pipeline(notice_text, max_retries=max_retries, theme=theme, supply_type=doc.supply_type, notice_url=doc.notice_url)


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
