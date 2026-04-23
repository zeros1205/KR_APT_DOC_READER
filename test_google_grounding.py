#!/usr/bin/env python3
"""
Google Gemini Grounding with Google Search 테스트
단지 분석 정보를 Google Search로 자동 수집하는 테스트
"""

import os
import json
import asyncio
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

async def test_google_grounding():
    """Google Search Grounding 테스트"""

    if not GEMINI_API_KEY:
        print("❌ GEMINI_API_KEY 미설정")
        return

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=GEMINI_API_KEY)

        # 테스트 아파트
        apt_name = "판교역 힐스테이트"
        location = "경기도 성남시 분당구 삼평동"

        print("=" * 70)
        print(f"🔍 Google Search Grounding 테스트")
        print(f"   단지: {apt_name}")
        print(f"   위치: {location}")
        print("=" * 70)

        # Google Search Tool 활성화
        prompt = f"""
당신은 한국 부동산 입지 분석 전문가입니다.
다음 아파트의 입지 정보를 JSON 형식으로 분석해주세요.
Google Search를 통해 실시간 정보를 수집하여 작성하세요.

아파트명: {apt_name}
위치: {location}

다음 정보를 포함하여 JSON으로만 답하세요:
{{
  "subway_detail": "가장 가까운 지하철역과 도보 거리 (예: '신분당선 판교역 도보 5분')",
  "nearby_schools": "인근 학교 (초등학교, 중학교 등) 목록",
  "nearby_facilities": "병원, 백화점, 쇼핑몰 등 주요 시설",
  "transportation": "주요 도로, 버스 노선 정보",
  "commercial_district": "상권 정보",
  "search_results_summary": "Google Search에서 수집된 정보 요약"
}}
"""

        print("\n[1단계] Google Search Grounding 호출...\n")

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction="JSON만 출력하세요. 마크다운 코드블록 없이 순수 JSON만 출력합니다.",
                tools=[
                    types.Tool(
                        google_search=types.GoogleSearch()
                    )
                ]
            ),
        )

        print("[응답 원문]")
        print(response.text)
        print()

        # JSON 파싱
        try:
            result = json.loads(response.text)
            print("[파싱된 JSON]")
            print(json.dumps(result, ensure_ascii=False, indent=2))
        except json.JSONDecodeError as e:
            print(f"⚠️  JSON 파싱 실패: {e}")
            print(f"원문: {response.text[:500]}")

        # 사용된 도구 정보
        print("\n[도구 사용 정보]")
        if hasattr(response, 'candidates') and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                for part in candidate.content.parts:
                    if hasattr(part, 'tool_use'):
                        print(f"✅ Tool: {part.tool_use}")

        print("\n✅ 테스트 완료!")

    except Exception as e:
        print(f"\n❌ 오류 발생:")
        print(f"   {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("\n🚀 Google Gemini Grounding 테스트 시작\n")
    asyncio.run(test_google_grounding())
