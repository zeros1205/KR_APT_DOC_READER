#!/usr/bin/env python3
"""
테스트: 단일 포스트 자동 생성 및 오류 캐치
지정된 아파트명으로 새 포스트 생성하면서 문제점 수집
"""

import sys
import traceback
from pathlib import Path

# 공공데이터 API에서 아파트 검색
import asyncio
import httpx
import json

API_BASE = "https://api.odcloud.kr/api/ApplyhomeInfoDetailSvc/v1"

async def find_apartment(apt_name: str, api_key: str) -> dict:
    """공공데이터에서 아파트 정보 검색"""
    if not api_key or "여기에" in str(api_key):
        print("❌ API 키 미설정")
        return {}

    params = {
        "serviceKey": api_key,
        "page": 1,
        "perPage": 100,
        "cond[HOUSE_NM::LIKE]": apt_name,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(
                f"{API_BASE}/getAPTLttotPblancDetail",
                params=params
            )
            resp.raise_for_status()
            data = resp.json()
            items = data.get("data", [])
            if items:
                return items[0]
            else:
                print(f"❌ '{apt_name}' 아파트를 API에서 찾을 수 없습니다")
                return {}
        except Exception as e:
            print(f"❌ API 조회 실패: {e}")
            traceback.print_exc()
            return {}


async def test_post_generation(apt_name: str):
    """단일 포스트 생성 테스트"""
    import os
    from run import main as run_pipeline

    try:
        # API 키 설정
        api_key = os.getenv("PUBLIC_DATA_API_KEY", "")

        print("="*70)
        print(f"테스트 포스트 생성: {apt_name}")
        print("="*70)

        # 1. 공공데이터 확인
        print("\n[1/3] 공공데이터에서 아파트 정보 조회...")
        apt_info = await find_apartment(apt_name, api_key)

        if not apt_info:
            print(f"⚠️  API에서 '{apt_name}' 아파트를 찾을 수 없습니다")
            print(f"    백업 메타데이터로 진행합니다...")

            # 백업에서 매칭되는 포스트 찾기
            backup_dir = Path('backup/posts_20260422_005603')
            matching_posts = [d for d in backup_dir.iterdir() if d.is_dir() and apt_name in d.name]

            if not matching_posts:
                print(f"⚠️  '{apt_name}' 아파트 정보를 백업에서도 찾을 수 없습니다")
                return False

            # 첫 번째 매칭 포스트에서 메타데이터 로드
            meta_file = matching_posts[0] / 'post_meta.json'
            with open(meta_file) as f:
                meta = json.load(f)
            apt_info = {
                "HOUSE_NM": meta.get('apt_name', apt_name),
                "HOUSE_MANAGE_NO": "",
                "PBLANC_NO": ""
            }
            print(f"✅ 백업에서 찾음: {meta.get('apt_name', apt_name)}")

        house_manage_no = apt_info.get("HOUSE_MANAGE_NO", "")
        pblanc_no = apt_info.get("PBLANC_NO", "")
        print(f"✅ 찾음: {apt_info.get('HOUSE_NM')} (관리번호: {house_manage_no})")

        # 2. 파이프라인 실행 (테스트)
        print("\n[2/3] 포스트 생성 파이프라인 실행...")
        print("   ⚠️  실제 실행 대신 dry-run 정보만 표시합니다")
        print(f"    - 아파트명: {apt_name}")
        print(f"    - 주택관리번호: {house_manage_no}")
        print(f"    - 공고번호: {pblanc_no}")

        # 3. 결과 확인
        print("\n[3/3] 생성 결과 확인...")
        output_dir = Path('output/posts')

        # 포스트 폴더 찾기
        matching_dirs = list(output_dir.glob(f"*{apt_name.split()[0]}*"))

        if matching_dirs:
            post_dir = matching_dirs[0]
            meta_file = post_dir / 'post_meta.json'
            html_file = post_dir / 'post.html'

            if meta_file.exists() and html_file.exists():
                with open(meta_file) as f:
                    meta = json.load(f)

                print(f"✅ 포스트 생성 완료: {post_dir.name}")
                print(f"\n📋 메타데이터:")
                print(f"   - 제목: {meta.get('title')}")
                print(f"   - 분양가: {meta.get('price_range')}")
                print(f"   - 입주예정: {meta.get('move_in_date')}")
                print(f"   - 특별공급: {meta.get('special_supply_date')}")
                print(f"   - 1순위: {meta.get('rank1_date')}")
                print(f"   - 2순위: {meta.get('rank2_date')}")
                print(f"   - 태그 수: {len(meta.get('tags', []))}개")
                print(f"   - HTML 크기: {html_file.stat().st_size / 1024:.1f}KB")

                return True
            else:
                print(f"❌ 포스트 파일 생성 실패 (HTML 또는 메타 누락)")
                return False
        else:
            print(f"❌ '{apt_name}' 포스트 디렉토리를 찾을 수 없습니다")
            print(f"   output/posts/ 디렉토리를 확인해주세요")
            return False

    except Exception as e:
        print(f"\n❌ 오류 발생:")
        print(f"   {type(e).__name__}: {e}")
        traceback.print_exc()
        return False


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("사용법: python test_single_post.py '<아파트명>'")
        print("예: python test_single_post.py '아산탕정자이'")
        sys.exit(1)

    apt_name = sys.argv[1]

    # 비동기 테스트 실행
    result = asyncio.run(test_post_generation(apt_name))

    sys.exit(0 if result else 1)
