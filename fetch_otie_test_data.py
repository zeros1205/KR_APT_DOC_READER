"""
fetch_otie_test_data.py
────────────────────────────────────────────────────
'오티에르 반포' 테스트 데이터 수집 및 저장

GitHub Actions 또는 로컬에서 실행:
  python fetch_otie_test_data.py
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent / "pipeline"))
sys.path.insert(0, str(Path(__file__).parent / "pipeline" / "agents"))

from agents.collector import CheongYakAPI, _build_document
from config import OUTPUT_DIR


async def fetch_and_save_otie():
    """오티에르 반포 테스트 데이터 수집 및 저장"""
    print("=" * 60)
    print("오티에르 반포 테스트 데이터 수집 시작")
    print("=" * 60)

    client = CheongYakAPI()

    try:
        # 최대 200개까지 검색해서 '오티에르 반포' 찾기
        print("\n📡 공공데이터 API 검색 중...")
        results = await client.get_list(page=1, per_page=100)

        # '오티에르' 포함 검색
        otie_candidates = [
            r for r in results
            if '오티에르' in (r.get('HOUSE_NM') or '')
        ]

        if not otie_candidates:
            print("❌ '오티에르' 단지 검색 결과 없음")
            print("\n현재 API에서 사용 가능한 샘플 데이터:")
            for i, apt in enumerate(results[:5], 1):
                print(f"  {i}. {apt.get('HOUSE_NM')} - {apt.get('SUPPLY_ADRES')}")
            return False

        # 첫 번째 오티에르 단지
        apt = otie_candidates[0]
        apt_name = apt.get('HOUSE_NM', '오티에르 반포')
        house_manage_no = apt.get('HOUSE_MANAGE_NO')

        print(f"\n✅ 발견: {apt_name}")
        print(f"   주택관리번호: {house_manage_no}")
        print(f"   위치: {apt.get('SUPPLY_ADRES')}")
        print(f"   공고번호: {apt.get('PBLANC_NO')}")
        print(f"   공고일: {apt.get('PBLANC_ANN_DE')}")

        # 상세 정보 조회
        if house_manage_no:
            print(f"\n📄 상세 정보 조회 중...")
            detail = await client.get_detail(house_manage_no)
            if detail:
                print(f"   조회됨: {len(detail)} 필드")
            else:
                detail = apt
                print("   상세 조회 미성공, 목록 정보 사용")
        else:
            detail = apt

        # 유닛 타입 정보 조회
        unit_types = []
        if house_manage_no:
            try:
                print(f"\n🏗️  유닛 타입 정보 조회 중...")
                unit_types = await client.get_unit_types(house_manage_no)
                print(f"   {len(unit_types)} 개 타입 발견")
            except Exception as e:
                print(f"   유닛 타입 조회 실패: {e}")

        # 테스트 데이터 디렉터리 생성
        test_data_dir = OUTPUT_DIR / "test_data" / "otie_banpo"
        test_data_dir.mkdir(parents=True, exist_ok=True)

        # 데이터 저장
        save_data = {
            "timestamp": datetime.now().isoformat(),
            "apt_name": apt_name,
            "house_manage_no": house_manage_no,
            "basic_info": detail,
            "unit_types": unit_types,
        }

        save_path = test_data_dir / "data.json"
        save_path.write_text(json.dumps(save_data, ensure_ascii=False, indent=2), encoding="utf-8")

        print(f"\n✅ 테스트 데이터 저장 완료")
        print(f"   경로: {save_path}")
        print(f"   크기: {save_path.stat().st_size:,} bytes")

        return True

    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(fetch_and_save_otie())
    sys.exit(0 if success else 1)
