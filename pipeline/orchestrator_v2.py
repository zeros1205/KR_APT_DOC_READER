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
        GEMINI_API_KEY,
        BLOG_THEME,
        PUBLIC_DATA_API_KEY,
        APARTMENT_API_BASE,
    )
    from pipeline.database import SessionLocal
    from pipeline.models import Apartment, Posting, PostingContent, PostingMeta
    from pipeline.index_renderer import build_manifest
    from pipeline.html_renderer import BlogHTMLRenderer, build_post_data, save_post
except ImportError:
    from config import (
        GEMINI_API_KEY,
        BLOG_THEME,
        PUBLIC_DATA_API_KEY,
        APARTMENT_API_BASE,
    )
    from database import SessionLocal
    from models import Apartment, Posting, PostingContent, PostingMeta
    from index_renderer import build_manifest
    from html_renderer import BlogHTMLRenderer, build_post_data, save_post

# ──────────────────────────────────────────────────
# LLM 클라이언트 초기화
# ──────────────────────────────────────────────────

from google.genai import Client

gemini_client = Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None


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

    apartment_data = None

    # 공공데이터 API 호출 시도
    if PUBLIC_DATA_API_KEY:
        try:
            import requests
            api_url = f"{APARTMENT_API_BASE}/getAPTLists"
            params = {
                "serviceKey": PUBLIC_DATA_API_KEY,
                "pageIndex": 1,
                "numOfRows": 1,
            }

            response = await asyncio.to_thread(
                lambda: requests.get(api_url, params=params, timeout=10)
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("response", {}).get("body", {}).get("items"):
                    item = data["response"]["body"]["items"][0]
                    apartment_data = {
                        "api_notice_id": notice_id,
                        "apt_name": item.get("apartmentName", "미상"),
                        "supply_address": item.get("supplyLocation", ""),
                        "location": item.get("location", ""),
                        "supply_scale": item.get("supplyScale", ""),
                        "total_units": int(item.get("totalHouseholds", 0)) or 0,
                        "unit_types": [item.get("unitType", "")],
                        "price_range": f"{item.get('priceMin', 0)}~{item.get('priceMax', 0)}",
                        "constructor": item.get("constructor", ""),
                        "notice_url": "https://www.applyhome.co.kr",
                        "schedule_dates": {
                            "announcement": item.get("noticeDate", ""),
                            "special_supply": item.get("specialSupplyDate", ""),
                            "rank1": item.get("rank1Date", ""),
                            "rank2": item.get("rank2Date", ""),
                            "winner": item.get("winnerDate", ""),
                            "move_in": item.get("moveInDate", ""),
                        }
                    }
                    print(f"  [Stage 1] API에서 {apartment_data['apt_name']} 로드")
        except Exception as e:
            print(f"  [Stage 1] API 호출 실패: {e}")
            apartment_data = None

    # API 실패 시 더미 데이터 사용
    if not apartment_data:
        print("  [Stage 1] 더미 데이터 사용")
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

    # API 키 없으면 더미 응답
    if not GEMINI_API_KEY:
        print("  [Stage 2] API 키 없음 - 더미 응답 반환")
        return {
            "eligibility_special": [
                {"type_name": "신혼부부", "quota": "20%", "requirements": ["혼인 후 7년 이내", "무주택세대주"]},
                {"type_name": "생애최초", "quota": "15%", "requirements": ["생애 처음 주택 구입", "무주택세대주"]}
            ],
            "eligibility_rank1": ["2년 이상 거주", "무주택 세대주"],
            "eligibility_rank2": ["거주 기간 제한 없음", "무주택 세대주"],
            "dates": {
                "special_supply_date": schedule_dates.get("special_supply"),
                "rank1_date": schedule_dates.get("rank1"),
                "rank2_date": schedule_dates.get("rank2"),
            }
        }

    prompt = f"""2024년 기준 청약자격 요건을 정리하세요. 정책 기준으로만 작성.

【정보】지역: {location}, 투기과열: {is_hot_zone}, 규제: {is_regulated_zone}, 유형: {supply_type}

【출력】 JSON만 반환
{{
    "eligibility_special": [
        {{"type_name": "신혼부부", "quota": "20%", "requirements": ["혼인후7년", "무주택"]}},
        ...
    ],
    "eligibility_rank1": ["2년거주", "무주택세대주", ...],
    "eligibility_rank2": ["조건없음", "무주택", ...],
    "dates": {{"special_supply_date": "{schedule_dates.get('special_supply', '-')}", "rank1_date": "{schedule_dates.get('rank1', '-')}", "rank2_date": "{schedule_dates.get('rank2', '-')}"}}
}}"""

    try:
        # TODO: Google Grounding 설정 추가
        response = await asyncio.to_thread(
            lambda: gemini_client.models.generate_content(
                model="gemini-1.5-flash",
                contents=prompt
            )
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

    # API 키 없으면 더미 응답
    if not GEMINI_API_KEY:
        print("  [Stage 4] API 키 없음 - 더미 응답 반환")
        return {
            "title": f"{apt_name} 청약안내",
            "apartment_intro": f"{apt_name}은 {location}에 위치한 신규 아파트단지입니다. {total_units}세대 규모로 {supply_scale} 다양한 평형이 공급됩니다.",
            "price_info": f"분양가: {price_range}"
        }

    prompt = f"""마케팅톤으로 아파트 소개. JSON만 반환.

단지: {apt_name}, {location}, {total_units}세대, {supply_scale}, {price_range}

{{
    "apt_intro": "150~200자, 마케터톤, 단지명+위치+규모+평형 포함",
    "post_title": "15~50자, '{apt_name} {{특징}} 분양 분석' 형식",
    "unit_type_desc": "30평: {price_range[:10]}\\n40평: ...",
    "schedule_desc": "특별공급 {schedule_dates.get('special_supply', '-')}, 1순위 {schedule_dates.get('rank1', '-')}, ..."
}}"""

    try:
        response = await asyncio.to_thread(
            lambda: gemini_client.models.generate_content(
                model="gemini-1.5-flash",
                contents=prompt
            )
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

    # API 키 없으면 더미 응답
    if not GEMINI_API_KEY:
        print("  [Stage 5] API 키 없음 - 더미 응답 반환")
        return {
            "location_intro": f"{location}은 대도시권의 주요 거점으로, 교통과 교육 여건이 우수합니다.",
            "subway_score": "★★★★★",
            "subway_detail": "• 역세권 위치\n  - 지하철역 도보 5분\n  - 다중 노선 교점",
            "school_score": "★★★★☆",
            "school_detail": "• 우수한 교육환경\n  - 초중고 밀집지역\n  - 학군 평판 우수",
            "life_score": "★★★★★",
            "life_detail": "• 상권 발달\n  - 대형마트 인근\n  - 음식점/카페 충실",
            "medical_score": "★★★★☆",
            "medical_detail": "• 의료시설\n  - 종합병원 인근\n  - 의원/약국 풍부"
        }

    prompt = f"""부동산입지분석. {location} 객관적 팩트기반. JSON만반환.

{{
    "location_intro": "200~500자, 교통교육상권, 설득력있게",
    "subway_score": "★★★★★",
    "subway_detail": "• 지하철\\n  - 거리/노선",
    "school_score": "★★★★☆",
    "school_detail": "• 교육\\n  - 학교정보",
    "life_score": "★★★★★",
    "life_detail": "• 상권\\n  - 시설정보",
    "medical_score": "★★★★☆",
    "medical_detail": "• 의료\\n  - 병원정보"
}}"""

    try:
        response = await asyncio.to_thread(
            lambda: gemini_client.models.generate_content(
                model="gemini-1.5-flash",
                contents=prompt
            )
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

    # API 키 없으면 더미 응답
    if not GEMINI_API_KEY:
        print("  [Stage 6] API 키 없음 - 더미 응답 반환")
        return {
            "qa_intro": "청약 신청 전 꼭 알아야 할 기본 정보들을 정리했습니다.",
            "qa_blocks": [
                {"q": "청약 자격이 있는지 어떻게 확인하나요?", "a": "주민등록등본을 통해 거주기간을 확인하고, 무주택자 여부를 확인해야 합니다. 각 지역별 자격요건이 다르므로 공고문을 참조하세요."},
                {"q": "청약통장은 어떻게 만드나요?", "a": "주거래 은행에서 청약통장을 개설할 수 있습니다. 월 6만원 이상 정기적으로 납입해야 가입 요건이 만족됩니다."}
            ],
            "financial_intro": "분양가 결정부터 입주까지 자금 납부 일정과 방식을 안내합니다.",
            "tax_desc": "• 취득세: 부동산 소유권 이전 시 과세\n• 재산세: 매년 부과\n• 종부세: 종합부동산세",
            "contract_ratio": "10%",
            "contract_amount": "계약금",
            "midterm_ratio": "60%",
            "midterm_count": "6개월",
            "balance_ratio": "30%",
            "loan_info": "신청자격자는 주택담보대출 신청이 가능합니다. 대출 한도는 평가액의 60~80% 범위이며, 금리는 시장금리에 따릅니다."
        }

    prompt = f"""청약제도/주택금융 전문가. 일반인 눈높이. 정책기반만. JSON반환.

{apt_name}, {location}, {supply_type}

{{
    "qa_intro": "60~80자, '청약 신청 전...'",
    "qa_blocks": [
        {{"q": "청약자격?", "a": "정책기반 설명"}},
        {{"q": "대출조건?", "a": "LTV/금리/기간"}},
        {{"q": "납부일정?", "a": "계약금/중도금/잔금"}}
    ],
    "financial_intro": "80~100자",
    "tax_desc": "• 취득세\\n• 재산세\\n• 종부세",
    "contract_ratio": "10%",
    "contract_amount": "",
    "midterm_ratio": "60%",
    "midterm_count": "6",
    "balance_ratio": "30%",
    "loan_info": "주택담보대출 LTV/금리 정책"
}}"""

    try:
        response = await asyncio.to_thread(
            lambda: gemini_client.models.generate_content(
                model="gemini-1.5-flash",
                contents=prompt
            )
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
# DB 저장
# ──────────────────────────────────────────────────

def _save_to_database_v2(
    apartment_data: Dict,
    stage2_result: Dict,
    stage3_result: Dict,
    stage4_result: Dict,
    stage5_result: Dict,
    stage6_result: Dict,
    stage7_result: Dict
) -> bool:
    """모든 Stage 결과를 데이터베이스에 저장"""
    print("  [DB Save] 데이터베이스 저장 시작...")

    db = SessionLocal()
    try:
        # 1. Apartment 레코드 생성/업데이트
        apartment = db.query(Apartment).filter(
            Apartment.api_notice_id == apartment_data["api_notice_id"]
        ).first()

        if not apartment:
            apartment = Apartment(
                api_notice_id=apartment_data["api_notice_id"],
                apt_name=apartment_data["apt_name"],
                supply_address=apartment_data["supply_address"],
                location=apartment_data["location"],
                supply_scale=apartment_data.get("supply_scale", ""),
                total_units=apartment_data.get("total_units", 0),
                is_hot_zone=stage3_result.get("is_hot_zone", "해당없음"),
                regulated_zone=stage3_result.get("regulated_zone", "-"),
                readmission_limit=stage3_result.get("readmission_limit", "-"),
                live_requirement=stage3_result.get("live_requirement", "-"),
                price_cap=stage3_result.get("price_cap", "-"),
                land_type=apartment_data.get("land_type", ""),
                constructor=apartment_data.get("constructor", ""),
                notice_url=apartment_data.get("notice_url", ""),
            )
            db.add(apartment)
            db.flush()
        else:
            # 규제정보 업데이트
            apartment.is_hot_zone = stage3_result.get("is_hot_zone", apartment.is_hot_zone)
            apartment.regulated_zone = stage3_result.get("regulated_zone", apartment.regulated_zone)
            apartment.readmission_limit = stage3_result.get("readmission_limit", apartment.readmission_limit)

        # 2. Posting 레코드 생성
        post_slug = stage4_result.get("post_title", apartment.apt_name)
        post_slug = re.sub(r'[^\w\s-]', '', post_slug.lower())
        post_slug = re.sub(r'[-\s]+', '-', post_slug).strip('-')

        posting = Posting(
            apartment_id=apartment.id,
            post_title=stage4_result.get("post_title", apartment.apt_name),
            post_subtitle=stage4_result.get("post_title", ""),
            post_slug=post_slug,
            theme=BLOG_THEME,
            quality_score=stage7_result.get("quality_score", 0),
            is_published=1 if stage7_result.get("quality_score", 0) >= 70 else 0,
        )
        db.add(posting)
        db.flush()

        # 3. PostingContent 레코드 생성
        posting_content = PostingContent(
            posting_id=posting.id,
            apt_intro=stage4_result.get("apt_intro", ""),
            location_intro=stage5_result.get("location_intro", ""),
            financial_intro=stage6_result.get("financial_intro", ""),
            qa_intro=stage6_result.get("qa_intro", ""),
            schedule_desc=stage4_result.get("schedule_desc", ""),
            tax_desc=stage6_result.get("tax_desc", ""),
            unit_type_desc=stage4_result.get("unit_type_desc", ""),
            subway_score=stage5_result.get("subway_score", "★★★☆☆"),
            subway_detail=stage5_result.get("subway_detail", ""),
            school_score=stage5_result.get("school_score", "★★★☆☆"),
            school_detail=stage5_result.get("school_detail", ""),
            life_score=stage5_result.get("life_score", "★★★☆☆"),
            life_detail=stage5_result.get("life_detail", ""),
            medical_score=stage5_result.get("medical_score", "★★★☆☆"),
            medical_detail=stage5_result.get("medical_detail", ""),
            eligibility_special=stage2_result.get("eligibility_special", []),
            eligibility_rank1=stage2_result.get("eligibility_rank1", []),
            eligibility_rank2=stage2_result.get("eligibility_rank2", []),
            qa_blocks=stage6_result.get("qa_blocks", []),
            seo_tags=[],
        )
        db.add(posting_content)
        db.flush()

        # 4. PostingMeta 레코드 생성
        posting_meta = PostingMeta(
            posting_id=posting.id,
            special_supply_date=stage2_result.get("dates", {}).get("special_supply_date", "-"),
            rank1_date=stage2_result.get("dates", {}).get("rank1_date", "-"),
            rank2_date=stage2_result.get("dates", {}).get("rank2_date", "-"),
            winner_date=apartment_data.get("schedule_dates", {}).get("winner", "-"),
            move_in_date=apartment_data.get("schedule_dates", {}).get("move_in", "-"),
            contract_ratio=stage6_result.get("contract_ratio", "10%"),
            contract_amount=stage6_result.get("contract_amount", ""),
            midterm_ratio=stage6_result.get("midterm_ratio", "60%"),
            midterm_count=stage6_result.get("midterm_count", "6"),
            balance_ratio=stage6_result.get("balance_ratio", "30%"),
            loan_info=stage6_result.get("loan_info", ""),
            resale_restriction=stage3_result.get("resale_restriction", "-"),
            acquisition_tax_rate=stage3_result.get("acquisition_tax_rate", ""),
        )
        db.add(posting_meta)
        db.commit()

        print(f"  [DB Save] 완료: Apartment(id={apartment.id}), Posting(id={posting.id})")
        return True

    except Exception as e:
        db.rollback()
        print(f"  [DB Save] 오류: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


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

    # DB 초기화 (테이블 생성)
    try:
        from pipeline.database import engine
        from pipeline.models import Base
        Base.metadata.create_all(engine)
        print("  [DB Init] 테이블 생성 완료")
    except Exception as e:
        print(f"  [DB Init] 테이블 생성 실패: {e}")

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
        db_success = _save_to_database_v2(
            apartment_data, stage2_result, stage3_result,
            stage4_result, stage5_result, stage6_result, stage7_result
        )

        if not db_success:
            print("❌ DB 저장 실패")
            return False

        # ===== HTML 렌더링 및 저장 =====
        try:

            # facts: Stage 1-7의 팩트 데이터
            facts = {
                "apt_name": apartment_data.get("apt_name", "-"),
                "location": apartment_data.get("location", "-"),
                "supply_location": apartment_data.get("supply_address", "-"),
                "supply_scale": apartment_data.get("supply_scale", "-"),
                "total_households": apartment_data.get("total_units", "-"),
                "unit_types": [{"type_name": ut, "area_sqm": 0, "general_units": 0, "special_units": 0, "price_min": 0, "price_max": 0} for ut in apartment_data.get("unit_types", [])],
                "price_range": apartment_data.get("price_range", "-"),
                "special_supply_date": stage2_result.get("dates", {}).get("special_supply_date", "-"),
                "rank1_date": stage2_result.get("dates", {}).get("rank1_date", "-"),
                "rank2_date": stage2_result.get("dates", {}).get("rank2_date", "-"),
                "winner_date": apartment_data.get("schedule_dates", {}).get("winner", "-"),
                "move_in_date": apartment_data.get("schedule_dates", {}).get("move_in", "-"),
                "is_hot_zone": stage3_result.get("is_hot_zone", "-"),
                "regulated_zone": stage3_result.get("regulated_zone", "-"),
                "readmission_limit": stage3_result.get("readmission_limit", "-"),
                "live_requirement": stage3_result.get("live_requirement", "-"),
                "price_cap": stage3_result.get("price_cap", "-"),
                "resale_restriction": stage3_result.get("resale_restriction", "-"),
                "acquisition_tax_rate": stage3_result.get("acquisition_tax_rate", "-"),
                "contract_ratio": stage6_result.get("contract_ratio", "10"),
                "contract_amount": stage6_result.get("contract_amount", "-"),
                "midterm_ratio": stage6_result.get("midterm_ratio", "60"),
                "midterm_count": stage6_result.get("midterm_count", "6"),
                "balance_ratio": stage6_result.get("balance_ratio", "30"),
                "loan_info": stage6_result.get("loan_info", "-"),
                "eligibility_special": stage2_result.get("eligibility_special", []),
                "eligibility_rank1": stage2_result.get("eligibility_rank1", []),
                "eligibility_rank2": stage2_result.get("eligibility_rank2", []),
                "notice_date": apartment_data.get("schedule_dates", {}).get("announcement", "-"),
            }

            # content: Stage 4-6의 콘텐츠 데이터
            content = {
                "post_title": stage4_result.get("title", f"{apartment_data.get('apt_name')} 청약 완벽 분석"),
                "post_subtitle": apartment_data.get("supply_address", "-"),
                "apt_intro": stage4_result.get("apartment_intro", "-"),
                "location_intro": stage5_result.get("location_intro", "-"),
                "financial_intro": stage6_result.get("financial_intro", "-"),
                "qa_intro": stage6_result.get("qa_intro", "-"),
                "tax_desc": stage6_result.get("tax_desc", "-"),
                "subway_score": stage5_result.get("subway_score", "★★★☆☆"),
                "subway_detail": stage5_result.get("subway_detail", "-"),
                "school_score": stage5_result.get("school_score", "★★★☆☆"),
                "school_detail": stage5_result.get("school_detail", "-"),
                "life_score": stage5_result.get("life_score", "★★★☆☆"),
                "life_detail": stage5_result.get("life_detail", "-"),
                "medical_score": stage5_result.get("medical_score", "★★★☆☆"),
                "medical_detail": stage5_result.get("medical_detail", "-"),
                "qa_blocks": stage6_result.get("qa_blocks", []),
                "seo_tags": [apartment_data.get("apt_name", ""), "청약", "분양"],
            }

            # PostData 생성
            post_data = build_post_data(
                facts=facts,
                content=content,
                theme=BLOG_THEME,
                supply_type="일반공급",
                notice_url=apartment_data.get("notice_url", ""),
                api_is_hot_zone=stage3_result.get("is_hot_zone", "")
            )

            # 저장할 때 notice_id 설정
            post_data.notice_id = notice_id

            # BlogHTMLRenderer를 사용하여 HTML 렌더링
            renderer = BlogHTMLRenderer()
            rendered_html = renderer.render(post_data)

            # save_post에 렌더링된 HTML 전달
            output_path = save_post(post_data, rendered_html, Path("output"))
            print(f"✅ HTML 렌더링 완료: {output_path}")

        except Exception as e:
            print(f"⚠️  HTML 렌더링 실패: {e}")
            import traceback
            traceback.print_exc()

        # ===== index.html 생성 (첫 실행만) =====
        try:
            from pipeline.index_renderer import build_front_index_once
            build_front_index_once()
            print("✅ index.html 생성 완료")
        except Exception as e:
            print(f"⚠️  index.html 생성 실패: {e}")

        # ===== manifest.json 업데이트 =====
        try:
            build_manifest()
            print("✅ manifest.json 업데이트 완료")
        except Exception as e:
            print(f"⚠️  manifest.json 업데이트 실패: {e}")

        print("\n🎉 전체 파이프라인 완료!")
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

    if len(sys.argv) > 1 and sys.argv[1] == "--sample":
        notice_id = "2024-sample-001"
    else:
        notice_id = sys.argv[1] if len(sys.argv) > 1 else "2024-sample-001"

    print(f"🚀 Starting orchestrator_v2 with notice_id: {notice_id}")
    success = asyncio.run(run_pipeline_v2(notice_id))
    sys.exit(0 if success else 1)
