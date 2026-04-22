#!/usr/bin/env python3
"""
공공데이터 API 정확한 필드명으로 분양가·일정 검증 및 자동 수정
API 문서: https://infuser.odcloud.kr/api/stages/37000/api-docs
"""

import asyncio
import json
import os
import httpx
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass

API_BASE = "https://api.odcloud.kr/api/ApplyhomeInfoDetailSvc/v1"

# API 키 로드
try:
    from pipeline.config import PUBLIC_DATA_API_KEY
except (ImportError, AttributeError):
    PUBLIC_DATA_API_KEY = os.getenv("PUBLIC_DATA_API_KEY", "")

OUTPUT_DIR = Path('output')
RESULTS_FILE = OUTPUT_DIR / 'price_audit_results.json'


@dataclass
class AuditResult:
    apt_name: str
    found_api: bool = False
    errors: dict = None
    errors_fixed: int = 0

    def __post_init__(self):
        if self.errors is None:
            self.errors = {}


class CheongYakAPI:
    """청약홈 공공데이터 API 클라이언트 - 정확한 필드명 사용"""

    def __init__(self, api_key: str = None):
        self.api_key = api_key

    async def get_detail(self, apt_name: str) -> dict:
        """APT 상세조회 - 일정 정보"""
        if not self.api_key or "여기에" in str(self.api_key):
            return {}

        params = {
            "serviceKey": self.api_key,
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

    async def get_models(self, house_manage_no: str) -> list:
        """주택형별 조회 - 분양가 정보"""
        if not self.api_key or "여기에" in str(self.api_key):
            return []

        params = {
            "serviceKey": self.api_key,
            "page": 1,
            "perPage": 100,
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
                return data.get("data", [])
            except Exception as e:
                print(f"    ⚠️  주택형별 조회 실패: {e}")
                return []

    async def get_price_range(self, house_manage_no: str) -> str:
        """분양가 범위 추출"""
        models = await self.get_models(house_manage_no)
        if not models:
            return ""

        prices = []
        for model in models:
            price = model.get("LTTOT_TOP_AMOUNT")
            if price:
                try:
                    prices.append(int(price))
                except (ValueError, TypeError):
                    pass

        if not prices:
            return ""

        min_price = min(prices)
        max_price = max(prices)

        if min_price == max_price:
            return f"{min_price:,}만원"
        return f"{min_price:,}만원~{max_price:,}만원"


async def audit_post(api: CheongYakAPI, post_folder: Path, auto_fix: bool = True) -> AuditResult:
    """단일 포스트 감사 및 자동 수정"""
    meta_file = post_folder / 'post_meta.json'

    if not meta_file.exists():
        return AuditResult("", False)

    with open(meta_file, 'r', encoding='utf-8') as f:
        meta = json.load(f)

    apt_name = meta.get('apt_name', '')
    result = AuditResult(apt_name=apt_name)

    # API에서 상세 정보 검색
    api_detail = await api.get_detail(apt_name)

    if not api_detail:
        return result

    result.found_api = True
    house_manage_no = api_detail.get("HOUSE_MANAGE_NO", "")
    modified = False

    # 필드 비교 (API 문서 정확한 필드명)
    comparisons = {
        'price_range': {
            'current': meta.get('price_range', ''),
            'api_fn': lambda: asyncio.run(api.get_price_range(house_manage_no)) if house_manage_no else "",
            'api_field': 'LTTOT_TOP_AMOUNT (주택형별)'
        },
        'notice_date': {
            'current': meta.get('notice_date', ''),
            'api_value': api_detail.get('RCRIT_PBLANC_DE', ''),
            'api_field': 'RCRIT_PBLANC_DE'
        },
        'special_supply_date': {
            'current': meta.get('special_supply_date', ''),
            'api_value': api_detail.get('SPSPLY_RCEPT_BGNDE', ''),
            'api_field': 'SPSPLY_RCEPT_BGNDE'
        },
        'rank1_date': {
            'current': meta.get('rank1_date', ''),
            'api_value': api_detail.get('GNRL_RNK1_CRSPAREA_RCPTDE', ''),
            'api_field': 'GNRL_RNK1_CRSPAREA_RCPTDE'
        },
        'rank2_date': {
            'current': meta.get('rank2_date', ''),
            'api_value': api_detail.get('GNRL_RNK2_CRSPAREA_RCPTDE', ''),
            'api_field': 'GNRL_RNK2_CRSPAREA_RCPTDE'
        },
    }

    for field, comp in comparisons.items():
        current = comp['current']

        if 'api_fn' in comp:
            api_value = comp['api_fn']()
        else:
            api_value = comp.get('api_value', '')

        current_clean = str(current).strip()
        api_clean = str(api_value).strip()

        if current_clean and api_clean and current_clean != api_clean:
            result.errors[field] = (current_clean, api_clean)

            if auto_fix and api_clean:
                meta[field] = api_clean
                modified = True

    # 수정사항 저장
    if modified and auto_fix:
        with open(meta_file, 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        result.errors_fixed = len(result.errors)

    return result


async def main():
    """메인 실행"""
    api_key = PUBLIC_DATA_API_KEY

    if not api_key or "여기에" in str(api_key):
        print("❌ PUBLIC_DATA_API_KEY 미설정")
        return

    api = CheongYakAPI(api_key)
    post_dir = OUTPUT_DIR / 'posts'

    print("="*70)
    print("공공데이터 기반 분양가·일정 검증 (정확한 필드명)")
    print("="*70)

    results = []
    post_folders = sorted([d for d in post_dir.iterdir() if d.is_dir()])

    for i, post_folder in enumerate(post_folders, 1):
        meta_file = post_folder / 'post_meta.json'
        if not meta_file.exists():
            continue

        with open(meta_file, 'r', encoding='utf-8') as f:
            meta = json.load(f)

        apt_name = meta.get('apt_name', '')
        print(f"\n[{i}/{len(post_folders)}] {apt_name}...")

        result = await audit_post(api, post_folder, auto_fix=True)
        results.append(result)

        if result.found_api:
            if result.errors:
                print(f"  ⚠️  {len(result.errors)}개 차이 발견 → {result.errors_fixed}개 자동 수정")
                for field, (current, api_val) in result.errors.items():
                    print(f"    - {field}")
                    print(f"      이전: {current}")
                    print(f"      수정: {api_val}")
            else:
                print(f"  ✓ 모든 데이터 일치")
        else:
            print(f"  ❌ API에서 공고 찾기 실패")

    # 결과 저장
    total_fixed = sum(r.errors_fixed for r in results)
    results_data = {
        'timestamp': datetime.now().isoformat(),
        'total': len(results),
        'found_api': sum(1 for r in results if r.found_api),
        'with_errors': sum(1 for r in results if r.errors),
        'auto_fixed': total_fixed,
        'api_fields': {
            'price_range': 'LTTOT_TOP_AMOUNT (getAPTLttotPblancMdl)',
            'notice_date': 'RCRIT_PBLANC_DE',
            'special_supply_date': 'SPSPLY_RCEPT_BGNDE',
            'rank1_date': 'GNRL_RNK1_CRSPAREA_RCPTDE',
            'rank2_date': 'GNRL_RNK2_CRSPAREA_RCPTDE',
        }
    }

    with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(results_data, f, ensure_ascii=False, indent=2)

    print("\n" + "="*70)
    print("검증 및 자동 수정 완료")
    print("="*70)
    print(f"✓ 검사 대상: {results_data['total']}개")
    print(f"✓ API 발견: {results_data['found_api']}개")
    print(f"⚠️  차이 발견: {results_data['with_errors']}개")
    print(f"✅ 자동 수정: {results_data['auto_fixed']}개 항목")


if __name__ == '__main__':
    asyncio.run(main())
