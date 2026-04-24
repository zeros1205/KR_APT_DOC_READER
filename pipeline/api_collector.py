"""
api_collector.py
────────────────────────────────────────────────
청약홈 공공데이터 API에서 분양공고 수집

API: https://api.odcloud.kr/api/ApplyhomeInfoDetailSvc/v1/getAPTLists
────────────────────────────────────────────────
"""

import asyncio
import requests
from typing import List, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path

try:
    from pipeline.config import PUBLIC_DATA_API_KEY, APARTMENT_API_BASE
except ImportError:
    from config import PUBLIC_DATA_API_KEY, APARTMENT_API_BASE


async def collect_recent_notices(
    days: int = 7,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    최근 N일의 분양공고 수집

    Args:
        days: 수집 기간 (일)
        limit: 최대 수집 건수

    Returns:
        공고 리스트 [{"notice_id": "...", "apt_name": "...", ...}, ...]
    """
    print(f"\n📡 공공API 데이터 수집 시작")
    print(f"   수집 기간: 최근 {days}일")
    print(f"   최대 건수: {limit}개")

    if not PUBLIC_DATA_API_KEY:
        print("❌ PUBLIC_DATA_API_KEY가 설정되지 않았습니다")
        return []

    try:
        api_url = f"{APARTMENT_API_BASE}/getAPTLists"

        # 날짜 범위 계산
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        params = {
            "serviceKey": PUBLIC_DATA_API_KEY,
            "pageIndex": 1,
            "numOfRows": limit,
            "noticeDate": start_date.strftime("%Y-%m-%d"),
        }

        print(f"   API URL: {api_url}")
        print(f"   요청 중...")

        response = await asyncio.to_thread(
            lambda: requests.get(api_url, params=params, timeout=30)
        )

        if response.status_code != 200:
            print(f"❌ API 요청 실패: {response.status_code}")
            return []

        data = response.json()
        items = data.get("response", {}).get("body", {}).get("items", [])

        if not items:
            print(f"⚠️  수집된 공고 없음")
            return []

        # 공고 데이터 포맷팅
        notices = []
        for item in items:
            notice = {
                "notice_id": f"{item.get('noticeDate', '').replace('-', '')}-{item.get('apartmentName', 'unknown')[:10]}",
                "apt_name": item.get("apartmentName", ""),
                "location": item.get("location", ""),
                "supply_address": item.get("supplyLocation", ""),
                "supply_scale": item.get("supplyScale", ""),
                "total_units": int(item.get("totalHouseholds", 0)) or 0,
                "price_range": f"{item.get('priceMin', 0)}~{item.get('priceMax', 0)}",
                "notice_date": item.get("noticeDate", ""),
                "special_supply_date": item.get("specialSupplyDate", ""),
                "rank1_date": item.get("rank1Date", ""),
                "rank2_date": item.get("rank2Date", ""),
                "constructor": item.get("constructor", ""),
            }
            notices.append(notice)

        print(f"✅ {len(notices)}개 공고 수집 완료")
        return notices[:limit]

    except requests.exceptions.Timeout:
        print("❌ API 요청 시간 초과")
        return []
    except requests.exceptions.ConnectionError:
        print("❌ 네트워크 연결 실패")
        return []
    except Exception as e:
        print(f"❌ API 수집 오류: {e}")
        return []


async def save_collected_notices(notices: List[Dict], output_path: Path = None) -> bool:
    """
    수집한 공고를 JSON 파일로 저장

    Args:
        notices: 공고 리스트
        output_path: 저장 경로

    Returns:
        성공 여부
    """
    if output_path is None:
        output_path = Path(__file__).parent.parent / "output" / "collected_notices.json"

    try:
        import json
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(notices, f, ensure_ascii=False, indent=2)

        print(f"✅ {len(notices)}개 공고 저장: {output_path}")
        return True
    except Exception as e:
        print(f"❌ 저장 실패: {e}")
        return False


async def get_notice_ids(
    days: int = 7,
    limit: int = 10,
    save_to_file: bool = True
) -> List[str]:
    """
    최근 공고의 notice_id 리스트 반환

    Args:
        days: 수집 기간 (일)
        limit: 최대 건수
        save_to_file: 파일로 저장할지 여부

    Returns:
        공고 ID 리스트 ["2024-04-24-xxx", ...]
    """
    notices = await collect_recent_notices(days=days, limit=limit)

    if save_to_file:
        await save_collected_notices(notices)

    return [notice["notice_id"] for notice in notices]


# 테스트 코드
if __name__ == "__main__":
    import sys

    days = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 3

    notice_ids = asyncio.run(get_notice_ids(days=days, limit=limit))

    print(f"\n📋 수집된 공고 ID:")
    for notice_id in notice_ids:
        print(f"   • {notice_id}")
