#!/usr/bin/env python3
"""
공공데이터 API를 통한 분양가·일정 전수 검증 및 수정
모든 포스트의 분양가, 모집공고일, 특별공급, 1순위, 2순위를 공식 데이터와 비교
"""

import asyncio
import json
import re
import httpx
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass

# 설정
API_BASE = "https://api.odcloud.kr/api/ApplyhomeInfoDetailSvc/v1"

# API 키는 config.py에서 자동 로드 (GitHub secret 또는 .env)
try:
    from pipeline.config import PUBLIC_DATA_API_KEY
except ImportError:
    PUBLIC_DATA_API_KEY = None

OUTPUT_DIR = Path('output')
RESULTS_FILE = OUTPUT_DIR / 'price_audit_results.json'


@dataclass
class AuditResult:
    apt_name: str
    house_manage_no: str = ""
    found_api: bool = False
    errors: dict = None  # {field: (expected, actual)}
    errors_fixed: int = 0

    def __post_init__(self):
        if self.errors is None:
            self.errors = {}


class CheongYakAPI:
    """청약홈 공공데이터 API 클라이언트"""

    def __init__(self, api_key: str = None):
        self.api_key = api_key

    async def search_by_name_and_dates(
        self,
        apt_name: str,
        move_in_date: str = None  # "YYYY년 MM월"
    ) -> dict:
        """
        단지명과 입주예정일로 공고 검색
        """
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

                # move_in_date와 매칭하는 항목 찾기
                if move_in_date and items:
                    # "2028년 12월" → "202812"
                    target_ym = move_in_date.replace("년 ", "").replace("월", "")
                    matches = [
                        item for item in items
                        if target_ym in (item.get("MVN_PLN_DE", "") or "")
                    ]
                    if matches:
                        return matches[0]

                # 또는 최신 공고 반환
                return items[0] if items else {}
            except Exception as e:
                print(f"  ⚠️  API 검색 실패: {e}")
                return {}

    async def get_detail(self, house_manage_no: str) -> dict:
        """단일 공고 상세 조회"""
        if not self.api_key or "여기에" in str(self.api_key):
            return {}

        params = {
            "serviceKey": self.api_key,
            "page": 1,
            "perPage": 1,
            "cond[HOUSE_MANAGE_NO::EQ]": house_manage_no,
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
                print(f"  ⚠️  API 조회 실패: {e}")
                return {}


def extract_price_range(api_data: dict) -> str:
    """API 데이터에서 분양가 범위 추출"""
    if not api_data:
        return ""

    # 최소·최대 분양가 필드 찾기
    price_min = api_data.get("LTTOT_BTM_AMOUNT")  # 하한
    price_max = api_data.get("LTTOT_TOP_AMOUNT")  # 상한

    if price_min and price_max:
        # 만원 단위 정수를 억·만원으로 변환
        p_min = int(price_min) if isinstance(price_min, (int, str)) else 0
        p_max = int(price_max) if isinstance(price_max, (int, str)) else 0

        if p_min > 0 and p_max > 0:
            return format_price(min(p_min, p_max), max(p_min, p_max))

    return ""


def format_price(p_min: int, p_max: int) -> str:
    """만원 단위 가격을 "X억 Y만원~A억 B만원" 형식으로"""
    def single_price(manwon):
        if manwon <= 0:
            return ""
        eok = manwon // 10000
        man = manwon % 10000

        if eok == 0:
            return f"{manwon:,}만원"
        elif man == 0:
            return f"{eok}억원"
        else:
            return f"{eok}억 {man:,}만원"

    if p_min == p_max:
        return single_price(p_min)
    return f"{single_price(p_min)}~{single_price(p_max)}"


async def audit_post(api: CheongYakAPI, post_folder: Path, auto_fix: bool = True) -> AuditResult:
    """단일 포스트 감사 및 자동 수정"""
    meta_file = post_folder / 'post_meta.json'

    if not meta_file.exists():
        return AuditResult("", "", False)

    with open(meta_file, 'r', encoding='utf-8') as f:
        meta = json.load(f)

    apt_name = meta.get('apt_name', '')
    move_in_date = meta.get('move_in_date', '')

    result = AuditResult(apt_name=apt_name)

    # API에서 공고 검색
    api_data = await api.search_by_name_and_dates(apt_name, move_in_date)

    if not api_data:
        return result

    result.found_api = True
    result.house_manage_no = api_data.get("HOUSE_MANAGE_NO", "")

    # 필드별 비교 및 수정
    comparisons = {
        'price_range': {
            'current': meta.get('price_range', ''),
            'api_fn': lambda: extract_price_range(api_data),
            'api_field': 'LTTOT_BTM_AMOUNT/TOP_AMOUNT'
        },
        'notice_date': {
            'current': meta.get('notice_date', ''),
            'api_value': api_data.get('RCRIT_PBLANC_DE', ''),
            'api_field': 'RCRIT_PBLANC_DE'
        },
        'special_supply_date': {
            'current': meta.get('special_supply_date', ''),
            'api_value': api_data.get('SPSPLY_RCRIT_DE', ''),
            'api_field': 'SPSPLY_RCRIT_DE'
        },
        'rank1_date': {
            'current': meta.get('rank1_date', ''),
            'api_value': api_data.get('GNRL_RCRIT_DE', ''),
            'api_field': 'GNRL_RCRIT_DE'
        },
        'rank2_date': {
            'current': meta.get('rank2_date', ''),
            'api_value': api_data.get('GNRL_2RCRIT_DE', ''),
            'api_field': 'GNRL_2RCRIT_DE'
        },
    }

    modified = False
    for field, comp in comparisons.items():
        current = comp['current']

        if 'api_fn' in comp:
            api_value = comp['api_fn']()
        else:
            api_value = comp.get('api_value', '')

        # 값 비교 (공백 무시)
        current_clean = str(current).strip()
        api_clean = str(api_value).strip()

        if current_clean and api_clean and current_clean != api_clean:
            result.errors[field] = (current_clean, api_clean)

            # 자동 수정: API 값으로 업데이트
            if auto_fix and api_clean:
                meta[field] = api_clean
                modified = True

    # 수정사항 저장
    if modified and auto_fix:
        with open(meta_file, 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        result.errors_fixed = len(result.errors)  # 수정된 항목 수

    return result


async def main():
    """메인 실행"""

    api_key = PUBLIC_DATA_API_KEY

    if not api_key or "여기에" in str(api_key):
        print("❌ PUBLIC_DATA_API_KEY 미설정")
        print("   GitHub Secrets 또는 .env 파일을 확인하세요")
        return

    api = CheongYakAPI(api_key)
    post_dir = OUTPUT_DIR / 'posts'

    print("="*70)
    print("공공데이터 기반 분양가·일정 전수 감사 시작")
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
                print(f"  ⚠️  {len(result.errors)}개 차이 발견 → {result.errors_fixed}개 자동 수정:")
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
        'details': [
            {
                'apt_name': r.apt_name,
                'found_api': r.found_api,
                'house_manage_no': r.house_manage_no,
                'errors': r.errors,
                'auto_fixed': r.errors_fixed
            }
            for r in results
        ]
    }

    with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(results_data, f, ensure_ascii=False, indent=2)

    print("\n" + "="*70)
    print("감사 및 자동 수정 완료")
    print("="*70)
    print(f"✓ 검사 대상: {results_data['total']}개")
    print(f"✓ API 발견: {results_data['found_api']}개")
    print(f"⚠️  차이 발견: {results_data['with_errors']}개")
    print(f"✅ 자동 수정: {results_data['auto_fixed']}개 항목")
    print(f"📄 결과 저장: {RESULTS_FILE}")


if __name__ == '__main__':
    asyncio.run(main())
