#!/usr/bin/env python3
"""
분양가 범위 전수조사 및 수정
주택형별 조회(getAPTLttotPblancMdl)에서 모든 타입의 최소/최고가를 수집하여 범위 계산
"""

import asyncio
import json
import os
import httpx
from pathlib import Path

API_BASE = "https://api.odcloud.kr/api/ApplyhomeInfoDetailSvc/v1"

try:
    from pipeline.config import PUBLIC_DATA_API_KEY
except (ImportError, AttributeError):
    PUBLIC_DATA_API_KEY = os.getenv("PUBLIC_DATA_API_KEY", "")

OUTPUT_DIR = Path('output')


async def get_apt_detail(apt_name: str, api_key: str) -> dict:
    """아파트명으로 상세정보 조회"""
    if not api_key or "여기에" in str(api_key):
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
            return items[0] if items else {}
        except Exception as e:
            print(f"    ⚠️  상세조회 실패: {e}")
            return {}


async def get_price_range_from_models(house_manage_no: str, api_key: str) -> dict:
    """주택형별 조회에서 모든 타입의 가격 수집"""
    if not api_key or "여기에" in str(api_key):
        return {"min": 0, "max": 0, "types": []}

    params = {
        "serviceKey": api_key,
        "page": 1,
        "perPage": 200,
        "cond[HOUSE_MANAGE_NO::EQ]": house_manage_no,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(
                f"{API_BASE}/getAPTLttotPblancMdl",
                params=params
            )
            resp.raise_for_status()
            data = resp.json()
            models = data.get("data", [])

            if not models:
                return {"min": 0, "max": 0, "types": []}

            prices = []
            type_prices = {}

            for model in models:
                house_ty = model.get("HOUSE_TY", "")
                price_str = model.get("LTTOT_TOP_AMOUNT", "")

                if price_str:
                    try:
                        price = int(price_str)
                        prices.append(price)
                        if house_ty:
                            if house_ty not in type_prices:
                                type_prices[house_ty] = []
                            type_prices[house_ty].append(price)
                    except (ValueError, TypeError):
                        pass

            if not prices:
                return {"min": 0, "max": 0, "types": []}

            min_price = min(prices)
            max_price = max(prices)

            return {
                "min": min_price,
                "max": max_price,
                "types": type_prices,
                "all_prices": prices
            }

        except Exception as e:
            print(f"    ⚠️  주택형별 조회 실패: {e}")
            return {"min": 0, "max": 0, "types": []}


def format_price_range(min_price: int, max_price: int) -> str:
    """가격 범위를 문자열로 포맷"""
    if min_price <= 0 or max_price <= 0:
        return ""

    if min_price == max_price:
        return f"{min_price:,}만원"

    return f"{min_price:,}만원~{max_price:,}만원"


async def fix_post_price(post_folder: Path, api_key: str) -> dict:
    """포스트의 가격 정보 확인 및 수정"""
    meta_file = post_folder / 'post_meta.json'

    if not meta_file.exists():
        return {"status": "skip", "reason": "no_meta_file"}

    with open(meta_file, 'r', encoding='utf-8') as f:
        meta = json.load(f)

    apt_name = meta.get('apt_name', '')
    current_price = meta.get('price_range', '')

    # API에서 상세정보 조회
    apt_detail = await get_apt_detail(apt_name, api_key)

    if not apt_detail:
        return {
            "apt_name": apt_name,
            "status": "api_not_found",
            "current_price": current_price
        }

    house_manage_no = apt_detail.get("HOUSE_MANAGE_NO", "")

    if not house_manage_no:
        return {
            "apt_name": apt_name,
            "status": "no_house_manage_no",
            "current_price": current_price
        }

    # 주택형별에서 가격 범위 계산
    price_info = await get_price_range_from_models(house_manage_no, api_key)

    if price_info["min"] == 0 or price_info["max"] == 0:
        return {
            "apt_name": apt_name,
            "status": "no_price_data",
            "current_price": current_price
        }

    new_price = format_price_range(price_info["min"], price_info["max"])

    # 변경 여부 확인
    if current_price == new_price:
        return {
            "apt_name": apt_name,
            "status": "ok",
            "price": new_price,
            "price_count": len(price_info["all_prices"])
        }

    # 가격 수정
    meta['price_range'] = new_price
    with open(meta_file, 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    return {
        "apt_name": apt_name,
        "status": "fixed",
        "old_price": current_price,
        "new_price": new_price,
        "price_count": len(price_info["all_prices"]),
        "min": price_info["min"],
        "max": price_info["max"]
    }


async def main():
    api_key = PUBLIC_DATA_API_KEY

    if not api_key or "여기에" in str(api_key):
        print("❌ PUBLIC_DATA_API_KEY 미설정")
        return

    post_dir = OUTPUT_DIR / 'posts'
    post_folders = sorted([d for d in post_dir.iterdir() if d.is_dir()])

    print("="*80)
    print("분양가 범위 전수조사 및 수정 (주택형별 조회 기반)")
    print("="*80)

    results = []
    fixed_count = 0
    ok_count = 0
    error_count = 0

    for i, post_folder in enumerate(post_folders, 1):
        meta_file = post_folder / 'post_meta.json'
        if not meta_file.exists():
            continue

        with open(meta_file, 'r', encoding='utf-8') as f:
            meta = json.load(f)

        apt_name = meta.get('apt_name', '')
        print(f"\n[{i}/{len(post_folders)}] {apt_name}...", end=" ", flush=True)

        result = await fix_post_price(post_folder, api_key)
        results.append(result)

        if result["status"] == "fixed":
            print(f"✅ 수정됨")
            print(f"    이전: {result['old_price']}")
            print(f"    수정: {result['new_price']} ({result['price_count']}개 타입)")
            fixed_count += 1

        elif result["status"] == "ok":
            print(f"✓ 정상 ({result['price_count']}개 타입)")
            ok_count += 1

        else:
            print(f"⚠️  {result['status']}")
            error_count += 1

    # 결과 요약
    print("\n" + "="*80)
    print("전수조사 완료")
    print("="*80)
    print(f"✅ 수정됨: {fixed_count}개")
    print(f"✓ 정상: {ok_count}개")
    print(f"⚠️  오류/미발견: {error_count}개")
    print(f"총계: {len(results)}개")

    # 결과 저장
    with open(OUTPUT_DIR / 'price_fix_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n📄 결과 저장: {OUTPUT_DIR / 'price_fix_results.json'}")


if __name__ == '__main__':
    asyncio.run(main())
