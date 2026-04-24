"""
orchestrator_v2.py
────────────────────────────────────────────────────
7-Stage Sequential Pipeline (새로운 구조)

Stage 1: 데이터 추출 (Public Data API)
Stage 2: 청약자격 확인 (Gemini 3.1 Flash Lite + Grounding)
Stage 3: 규제정보 (API + Gemini 3.1 Flash + Grounding)
Stage 4: 단지 소개 (Gemini 3.1 Flash Lite + Grounding)
Stage 5: 입지 분석 (Gemini 3.1 Flash + Grounding)
Stage 6: Q&A 작성 (Gemini 3.1 Flash + Grounding)
Stage 7: 스크립트 평가 (Gemini 3.1 Flash + 자동 검증)

기존 orchestrator.py와는 완전히 독립된 새로운 구조
────────────────────────────────────────────────────
"""

import json
import asyncio
from typing import Optional, Dict, List, Any
from pathlib import Path
from datetime import datetime
import re

try:
    from pipeline.config import (
        ANTHROPIC_API_KEY,
        OPENAI_API_KEY,
        GEMINI_API_KEY,
        BLOG_THEME,
    )
    from pipeline.database import SessionLocal
    from pipeline.models import Apartment, Posting, PostingContent, PostingMeta
    from pipeline.html_renderer import render_blog_post
    from pipeline.index_renderer import build_manifest
except ImportError:
    from config import (
        ANTHROPIC_API_KEY,
        OPENAI_API_KEY,
        GEMINI_API_KEY,
        BLOG_THEME,
    )
    from database import SessionLocal
    from models import Apartment, Posting, PostingContent, PostingMeta
    from html_renderer import render_blog_post
    from index_renderer import build_manifest

# ──────────────────────────────────────────────────
# LLM 클라이언트 초기화
# ──────────────────────────────────────────────────

import google.generativeai as genai
from google.generativeai import caching

genai.configure(api_key=GEMINI_API_KEY)


# ──────────────────────────────────────────────────
# Stage 1: 데이터 추출
# ──────────────────────────────────────────────────

async def stage_1_data_extraction(notice_id: str) -> Dict[str, Any]:
    """
    Stage 1: 공공데이터 API에서 필수 데이터 수집

    입력: notice_id (청약홈 공고번호)
    출력: {
        "data": {...},
        "missing_fields": [],
        "requires_manual_input": bool
    }
    """
    print("  [Stage 1] 데이터 추출 시작...")

    # TODO: Public Data API 호출 구현
    # 현재는 더미 데이터
    apartment_data = {
        "api_notice_id": notice_id,
        "apt_name": "샘플 아파트",
        "supply_address": "서울시 강남구",
        "location": "서울 / 강남구",
        "supply_scale": "30~84평",
        "total_units": 590,
        "unit_types": ["30평", "40평", "60평", "84평"],
        "price_range": "4억~8억",
        "constructor": "샘플건설",
        "notice_url": "https://www.applyhome.co.kr",
        "schedule_dates": {
            "announcement": "2024-05-01",
            "special_supply": "2024-05-15",
            "rank1": "2024-05-20",
            "rank2": "2024-05-25",
            "winner": "2024-06-15",
            "move_in": "2025-01-15",
        }
    }

    # 누락 항목 확인
    required_fields = ["apt_name", "supply_address", "location"]
    missing_fields = [f for f in required_fields if not apartment_data.get(f)]

    result = {
        "data": apartment_data,
        "missing_fields": missing_fields,
        "requires_manual_input": len(missing_fields) > 0
    }

    print(f"  [Stage 1] 완료: {apartment_data['apt_name']}")
    if missing_fields:
        print(f"  ⚠️  누락 필드: {missing_fields}")

    return result


# ──────────────────────────────────────────────────
# Stage 2: 청약자격 확인
# ──────────────────────────────────────────────────

async def stage_2_eligibility(
    supply_type: str,
    is_hot_zone: str,
    is_regulated_zone: str,
    location: str,
    schedule_dates: Dict[str, str]
) -> Dict[str, Any]:
    """
    Stage 2: 정부 정책 기반 청약자격 요건 정리

    모델: Gemini 3.1 Flash Lite + Google Grounding
    """
    print("  [Stage 2] 청약자격 확인 시작...")

    prompt = f"""당신은 대한민국 청약자격 전문가입니다.
최신 정부 정책(2024년)을 기반으로 청약자격 요건을 정리합니다.

【지역 정보】
- 지역: {location}
- 투기과열지구: {is_hot_zone}
- 청약과열지구: {is_regulated_zone}
- 공급유형: {supply_type}

【작업】
아래 정책에 따른 청약자격을 정리하세요.
Google Grounding을 통해 최신 정책 정보를 확인하세요.

각 자격 구분별로 3~5개 핵심 요건을 명확한 문장으로 작성하세요.
개인의 재무 상황이 아닌 정책 기준으로만 작성합니다.

【출력 형식】 (JSON)
{{
    "eligibility_special": ["요건1", "요건2", ...],
    "eligibility_rank1": ["요건1", "요건2", ...],
    "eligibility_rank2": ["요건1", "요건2", ...],
    "notes": "특이사항"
}}"""

    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        # TODO: Google Grounding 설정 추가
        response = await asyncio.to_thread(
            lambda: model.generate_content(prompt)
        )

        # JSON 파싱
        response_text = response.text
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
        else:
            result = {
                "eligibility_special": [],
                "eligibility_rank1": [],
                "eligibility_rank2": [],
                "notes": "파싱 실패"
            }

        result["dates"] = {
            "special_supply_date": schedule_dates.get("special_supply"),
            "rank1_date": schedule_dates.get("rank1"),
            "rank2_date": schedule_dates.get("rank2"),
        }

        print(f"  [Stage 2] 완료: 특별공급, 1순위, 2순위 정보 생성")
        return result

    except Exception as e:
        print(f"  [Stage 2] 오류: {e}")
        return {
            "eligibility_special": [],
            "eligibility_rank1": [],
            "eligibility_rank2": [],
            "notes": f"오류 발생: {str(e)}"
        }


# ──────────────────────────────────────────────────
# Stage 3: 규제정보
# ──────────────────────────────────────────────────

async def stage_3_regulation(location: str, supply_type: str) -> Dict[str, Any]:
    """
    Stage 3: 규제지역 및 제한 정보

    1단계: Public Data API로 규제지역 정보 조회
    2단계: 누락된 정보는 Gemini + Grounding으로 보완
    """
    print("  [Stage 3] 규제정보 확인 시작...")

    # TODO: Public Data API 호출
    regulation_data = {
        "is_hot_zone": "N",
        "is_hot_zone_label": "비해당",
        "regulated_zone": "-",
        "readmission_limit": "4년",
        "live_requirement": "2년",
        "price_cap": "미적용",
        "resale_restriction": "3년",
        "acquisition_tax_rate": "1%"
    }

    # TODO: Gemini + Grounding으로 누락된 정보 보완

    print(f"  [Stage 3] 완료: 규제정보 수집")
    return regulation_data


# ──────────────────────────────────────────────────
# Stage 4: 단지 소개
# ──────────────────────────────────────────────────

async def stage_4_apartment_intro(
    apt_name: str,
    location: str,
    total_units: int,
    unit_types: List[str],
    supply_scale: str,
    schedule_dates: Dict[str, str],
    price_range: str
) -> Dict[str, Any]:
    """
    Stage 4: 아파트 단지의 팩트 기반 소개글

    모델: Gemini 3.1 Flash Lite + Google Grounding
    """
    print("  [Stage 4] 단지 소개 작성 시작...")

    prompt = f"""당신은 아파트 마케팅 담당자입니다.
고객과 친근하게 대화하듯 단지를 소개합니다.

【단지 정보】
- 단지명: {apt_name}
- 위치: {location}
- 공급세대수: {total_units}
- 평형: {', '.join(unit_types)}
- 공급규모: {supply_scale}
- 예상 분양가: {price_range}
- 특별공급: {schedule_dates.get('special_supply', '-')}

【작업】

1. apt_intro (단지 소개글, 150~200자):
   - 마케터 어투로 자연스럽게
   - 단지명, 위치, 규모, 평형 포함

2. post_title (블로그 제목, 15~50자):
   - 형식: "{{단지명}} {{특징}} 분양 분석"

3. unit_type_desc (타입별 분양가):
   - 형식: "30평: 4억~5억\\n40평: ..."

4. schedule_desc (청약 일정):
   - 형식: "특별공급 5/15, 1순위 5/20-22, ..."

【출력 형식】 (JSON)
{{
    "apt_intro": "...",
    "post_title": "...",
    "unit_type_desc": "...",
    "schedule_desc": "..."
}}"""

    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = await asyncio.to_thread(
            lambda: model.generate_content(prompt)
        )

        response_text = response.text
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
        else:
            result = {
                "apt_intro": f"{apt_name} 소개",
                "post_title": f"{apt_name} 분양 분석",
                "unit_type_desc": "정보 없음",
                "schedule_desc": "정보 없음"
            }

        print(f"  [Stage 4] 완료: 소개글, 제목, 일정 생성")
        return result

    except Exception as e:
        print(f"  [Stage 4] 오류: {e}")
        return {
            "apt_intro": f"{apt_name} 소개",
            "post_title": f"{apt_name} 분양 분석",
            "unit_type_desc": "정보 없음",
            "schedule_desc": "정보 없음"
        }


# ──────────────────────────────────────────────────
# Stage 5: 입지 분석
# ──────────────────────────────────────────────────

async def stage_5_location_analysis(
    apt_name: str,
    location: str,
    address: str
) -> Dict[str, Any]:
    """
    Stage 5: 아파트 위치의 지역 특성 및 장점 분석

    모델: Gemini 3.1 Flash + Google Grounding + Google Maps API
    """
    print("  [Stage 5] 입지 분석 시작...")

    prompt = f"""당신은 부동산 입지 분석 전문가입니다.
해당 지역의 장점을 객관적 팩트 기반으로 분석합니다.

【단지 정보】
- 단지명: {apt_name}
- 주소: {address}
- 지역: {location}

【작업】
Google Grounding과 Google Maps API를 이용해 다음을 작성하세요.

1. location_intro (지역 총평, 200~500자):
   - 교통, 교육, 상권 등 핵심 특징
   - 객관적이고 설득력 있게

2. 4개 별점 분석 (subway, school, life, medical):
   - 각 항목별 ★★★★★ 형식 점수
   - 300~2000자 개조식 상세 설명

【출력 형식】 (JSON)
{{
    "location_intro": "...",
    "subway_score": "★★★★★",
    "subway_detail": "• 항목1\\n  - 세부사항",
    "school_score": "★★★★☆",
    "school_detail": "...",
    "life_score": "★★★★★",
    "life_detail": "...",
    "medical_score": "★★★★☆",
    "medical_detail": "..."
}}"""

    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = await asyncio.to_thread(
            lambda: model.generate_content(prompt)
        )

        response_text = response.text
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
        else:
            result = {
                "location_intro": "입지 분석",
                "subway_score": "★★★☆☆",
                "subway_detail": "정보 없음",
                "school_score": "★★★☆☆",
                "school_detail": "정보 없음",
                "life_score": "★★★☆☆",
                "life_detail": "정보 없음",
                "medical_score": "★★★☆☆",
                "medical_detail": "정보 없음"
            }

        print(f"  [Stage 5] 완료: 입지 분석 4개 카테고리")
        return result

    except Exception as e:
        print(f"  [Stage 5] 오류: {e}")
        return {
            "location_intro": "입지 분석",
            "subway_score": "★★★☆☆",
            "subway_detail": "정보 없음",
            "school_score": "★★★☆☆",
            "school_detail": "정보 없음",
            "life_score": "★★★☆☆",
            "life_detail": "정보 없음",
            "medical_score": "★★★☆☆",
            "medical_detail": "정보 없음"
        }


# ──────────────────────────────────────────────────
# Stage 6: Q&A 작성
# ──────────────────────────────────────────────────

async def stage_6_faq_generation(
    apt_name: str,
    supply_type: str,
    eligibility_data: Dict,
    regulation_data: Dict,
    location: str
) -> Dict[str, Any]:
    """
    Stage 6: 청약 제도 + 단지 관련 FAQ 작성

    모델: Gemini 3.1 Flash + Google Grounding
    """
    print("  [Stage 6] Q&A 작성 시작...")

    prompt = f"""당신은 청약 제도 및 주택 금융 전문가입니다.
일반인이 이해하기 쉽게 Q&A를 작성합니다.

【배경 정보】
- 단지명: {apt_name}
- 지역: {location}
- 공급유형: {supply_type}
- 투기과열지구: {regulation_data.get('is_hot_zone', '-')}

【필수 지침】
❌ 금지: 개인의 세대구성, 자산, 소득 기반 조언
✅ 허용: 정책 기준 설명, 일반적 상황

【작업】

1. qa_intro (Q&A 도입부, 60~80자):
   예: "청약 신청 전 꼭 알아야 할 것들..."

2. qa_blocks (3~7개 Q&A):
   - 질문 주제: 자격, 지역특성, 프로세스, 대출, 납부, 이의제기
   - 답변: 300~2000자, 개조식
   - 정책 기반 팩트만 포함

3. financial_intro (자금계획 도입, 80~100자)

4. tax_desc (세금 정보, 300~1000자):
   - 취득세, 재산세, 종부세
   - 개조식 작성

5. 납부 구조:
   - contract_ratio, contract_amount
   - midterm_ratio, midterm_count
   - balance_ratio

6. loan_info (대출 정보, 200~500자):
   - 주택담보대출 LTV
   - 금리, 기간, 조건

【출력 형식】 (JSON)
{{
    "qa_intro": "...",
    "qa_blocks": [
        {{"q": "질문1", "a": "답변1"}},
        ...
    ],
    "financial_intro": "...",
    "tax_desc": "...",
    "contract_ratio": "10%",
    "contract_amount": "...",
    "midterm_ratio": "60%",
    "midterm_count": "6",
    "balance_ratio": "30%",
    "loan_info": "..."
}}"""

    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = await asyncio.to_thread(
            lambda: model.generate_content(prompt)
        )

        response_text = response.text
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
        else:
            result = {
                "qa_intro": "Q&A 정보",
                "qa_blocks": [],
                "financial_intro": "자금계획 정보",
                "tax_desc": "정보 없음",
                "contract_ratio": "10%",
                "contract_amount": "정보 없음",
                "midterm_ratio": "60%",
                "midterm_count": "6",
                "balance_ratio": "30%",
                "loan_info": "정보 없음"
            }

        print(f"  [Stage 6] 완료: Q&A {len(result.get('qa_blocks', []))}개 생성")
        return result

    except Exception as e:
        print(f"  [Stage 6] 오류: {e}")
        return {
            "qa_intro": "Q&A 정보",
            "qa_blocks": [],
            "financial_intro": "자금계획 정보",
            "tax_desc": "정보 없음",
            "contract_ratio": "10%",
            "contract_amount": "정보 없음",
            "midterm_ratio": "60%",
            "midterm_count": "6",
            "balance_ratio": "30%",
            "loan_info": "정보 없음"
        }


# ──────────────────────────────────────────────────
# Stage 7: 스크립트 평가
# ──────────────────────────────────────────────────

async def stage_7_evaluation(
    stage2_result: Dict,
    stage3_result: Dict,
    stage4_result: Dict,
    stage5_result: Dict,
    stage6_result: Dict
) -> Dict[str, Any]:
    """
    Stage 7: 위 Stage 2~6 결과 평가 및 보완

    자동 검증 + LLM 평가
    """
    print("  [Stage 7] 품질 평가 시작...")

    score = 100
    evaluation = {
        "stage2": {"score": 0, "issues": []},
        "stage3": {"score": 0, "issues": []},
        "stage4": {"score": 0, "issues": []},
        "stage5": {"score": 0, "issues": []},
        "stage6": {"score": 0, "issues": []},
    }

    # Stage 2 평가: 청약자격
    s2_score = 100
    if not all(stage2_result.get(k) for k in ["eligibility_special", "eligibility_rank1", "eligibility_rank2"]):
        s2_score -= 20
    if len(stage2_result.get("eligibility_special", [])) < 3:
        s2_score -= 15
    evaluation["stage2"]["score"] = max(s2_score, 0)

    # Stage 3 평가: 규제정보
    s3_score = 100
    required_fields = ["is_hot_zone", "regulated_zone", "readmission_limit",
                      "live_requirement", "price_cap", "resale_restriction", "acquisition_tax_rate"]
    missing = sum(1 for f in required_fields if not stage3_result.get(f))
    s3_score -= missing * 10
    evaluation["stage3"]["score"] = max(s3_score, 0)

    # Stage 4 평가: 단지소개
    s4_score = 100
    intro_len = len(stage4_result.get("apt_intro", ""))
    if intro_len < 150 or intro_len > 200:
        s4_score -= 15
    title_len = len(stage4_result.get("post_title", ""))
    if title_len < 15 or title_len > 50:
        s4_score -= 10
    evaluation["stage4"]["score"] = max(s4_score, 0)

    # Stage 5 평가: 입지분석
    s5_score = 100
    required = ["location_intro", "subway_score", "subway_detail",
                "school_score", "school_detail", "life_score",
                "life_detail", "medical_score", "medical_detail"]
    if not all(stage5_result.get(f) for f in required):
        s5_score -= 20
    intro_len = len(stage5_result.get("location_intro", ""))
    if intro_len < 200 or intro_len > 500:
        s5_score -= 15
    evaluation["stage5"]["score"] = max(s5_score, 0)

    # Stage 6 평가: Q&A
    s6_score = 100
    qa_blocks = stage6_result.get("qa_blocks", [])
    if len(qa_blocks) < 3 or len(qa_blocks) > 7:
        s6_score -= 20
    short_answers = sum(1 for qa in qa_blocks if len(qa.get("a", "")) < 300)
    if short_answers > 0:
        s6_score -= 10
    evaluation["stage6"]["score"] = max(s6_score, 0)

    # 종합 점수
    total_score = sum(e["score"] for e in evaluation.values()) / len(evaluation)

    # 최종 판정
    if total_score >= 80:
        overall_status = "✅ PASS"
    elif total_score >= 70:
        overall_status = "⚠️  WARNING"
    else:
        overall_status = "❌ FAIL"

    result = {
        "quality_score": int(total_score),
        "evaluation": evaluation,
        "overall_status": overall_status,
        "recommendations": []
    }

    print(f"  [Stage 7] 완료: 품질점수 {int(total_score)}점 ({overall_status})")
    return result


# ──────────────────────────────────────────────────
# 메인 파이프라인
# ──────────────────────────────────────────────────

async def run_pipeline_v2(notice_id: str) -> bool:
    """
    7-Stage 순차 파이프라인 실행

    Flow:
    Stage 1 → Stage 2 → Stage 3 → Stage 4 → Stage 5 → Stage 6 → Stage 7
    ↓
    DB 저장 + HTML 렌더링 + manifest.json 업데이트
    """
    print(f"\n🔄 Pipeline V2 시작: {notice_id}")
    print("="*60)

    try:
        # ===== Stage 1: 데이터 추출 =====
        stage1_result = await stage_1_data_extraction(notice_id)
        if stage1_result["requires_manual_input"]:
            print(f"❌ 필수 데이터 누락: {stage1_result['missing_fields']}")
            return False

        apartment_data = stage1_result["data"]

        # ===== Stage 2: 청약자격 =====
        stage2_result = await stage_2_eligibility(
            supply_type="일반공급",
            is_hot_zone=apartment_data.get("is_hot_zone", "N"),
            is_regulated_zone=apartment_data.get("regulated_zone", "-"),
            location=apartment_data["location"],
            schedule_dates=apartment_data["schedule_dates"]
        )

        # ===== Stage 3: 규제정보 =====
        stage3_result = await stage_3_regulation(
            location=apartment_data["location"],
            supply_type="일반공급"
        )

        # ===== Stage 4: 단지소개 =====
        stage4_result = await stage_4_apartment_intro(
            apt_name=apartment_data["apt_name"],
            location=apartment_data["location"],
            total_units=apartment_data["total_units"],
            unit_types=apartment_data["unit_types"],
            supply_scale=apartment_data["supply_scale"],
            schedule_dates=apartment_data["schedule_dates"],
            price_range=apartment_data.get("price_range", "-")
        )

        # ===== Stage 5: 입지분석 =====
        stage5_result = await stage_5_location_analysis(
            apt_name=apartment_data["apt_name"],
            location=apartment_data["location"],
            address=apartment_data["supply_address"]
        )

        # ===== Stage 6: Q&A =====
        stage6_result = await stage_6_faq_generation(
            apt_name=apartment_data["apt_name"],
            supply_type="일반공급",
            eligibility_data=stage2_result,
            regulation_data=stage3_result,
            location=apartment_data["location"]
        )

        # ===== Stage 7: 평가 =====
        stage7_result = await stage_7_evaluation(
            stage2_result, stage3_result, stage4_result,
            stage5_result, stage6_result
        )

        # 평가 결과 확인
        if stage7_result["quality_score"] < 70:
            print(f"❌ 품질점수 부족: {stage7_result['quality_score']}점")
            return False

        print(f"\n✅ 모든 Stage 완료")
        print("="*60)

        # ===== DB 저장 =====
        # TODO: 모든 데이터를 DB에 저장
        # _save_to_database_v2(apartment_data, stage2_result, stage3_result, ...)

        # ===== HTML 렌더링 =====
        # TODO: HTML 템플릿에 데이터 렌더링

        # ===== manifest.json 업데이트 =====
        # TODO: build_manifest() 호출

        return True

    except Exception as e:
        print(f"❌ 파이프라인 오류: {e}")
        import traceback
        traceback.print_exc()
        return False


# ──────────────────────────────────────────────────
# 진입점
# ──────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    notice_id = sys.argv[1] if len(sys.argv) > 1 else "2024-sample-001"

    success = asyncio.run(run_pipeline_v2(notice_id))
    sys.exit(0 if success else 1)
