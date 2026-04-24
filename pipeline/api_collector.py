"""
api_collector.py
────────────────────────────────────────────────────
청약홈 공공데이터 API에서 분양공고 수집

API: https://api.odcloud.kr/api/ApplyhomeInfoDetailSvc/v1/getAPTLttotPblancDetail
────────────────────────────────────────────────────
"""

import asyncio
import sys
from typing import List, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "agents"))

try:
    from agents.collector import CheongYakAPI
except ImportError:
    from pipeline.agents.collector import CheongYakAPI


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

    api = CheongYakAPI()

    if not api.api_key:
        print("❌ PUBLIC_DATA_API_KEY가 설정되지 않았습니다")
        return []

    try:
        # 날짜 범위 계산
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        start_date_str = start_date.strftime("%Y-%m-%d")

        print(f"   조회 기간: {start_date_str} ~ {end_date.strftime('%Y-%m-%d')}")
        print(f"   요청 중...")

        # CheongYakAPI 사용
        items = await api.get_list(
            per_page=limit,
            start_date=start_date_str
        )

        if not items:
            print(f"⚠️  수집된 공고 없음")
            return []

        # 공고 데이터 포맷팅
        notices = []
        for item in items:
            notice = {
                "notice_id": item.get("PBLANC_NO", ""),
                "apt_name": item.get("HOUSE_NM", ""),
                "location": item.get("SUBSCRPT_AREA_CODE_NM", ""),
                "supply_address": item.get("HSSPLY_ADRES", ""),
                "supply_scale": item.get("SUBSCRPT_TYCD_NM", ""),
                "total_units": int(item.get("TOT_SUPLY_HSHLDCO", 0)) or 0,
                "price_range": "",
                "notice_date": item.get("RCRIT_PBLANC_DE", ""),
                "special_supply_date": item.get("SPSPLY_RCEPT_BGNDE", ""),
                "rank1_date": item.get("GNRL_RNK1_CRSPAREA_RCPTDE", ""),
                "rank2_date": item.get("GNRL_RNK2_CRSPAREA_RCPTDE", ""),
                "constructor": item.get("CNSTRCT_ENTRPS_NM", ""),
            }
            notices.append(notice)

        print(f"✅ {len(notices)}개 공고 수집 완료")
        return notices[:limit]

    except Exception as e:
        print(f"❌ API 수집 오류: {e}")
        import traceback
        traceback.print_exc()
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
