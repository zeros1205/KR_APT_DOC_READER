#!/usr/bin/env python3
"""모든 포스트의 가격을 통일된 형식(000,000만원)으로 수정"""

import json
import re
from pathlib import Path
from typing import Optional

def parse_amount(s: str) -> int:
    """문자열을 만원 단위 정수로 변환"""
    s = s.strip()

    # 숫자와 단위 분리
    if '억' in s:
        # "X억 Y만원" 또는 "X억Y만원" 형태
        match = re.match(r'([\d.]+)\s*억\s*([\d,]*)\s*만?', s)
        if match:
            eok = float(match.group(1))
            man = match.group(2).replace(',', '')
            man = int(man) if man else 0
            return int(eok * 10000 + man)

    # 만원만 있는 경우
    match = re.match(r'([\d,]+)\s*만', s)
    if match:
        return int(match.group(1).replace(',', ''))

    return 0

def normalize_price(price_str: str) -> str:
    """가격 범위를 통일된 형식으로 변환"""
    if not price_str or not price_str.strip():
        return ""

    # "약" 제거
    price_str = price_str.replace('약', '').strip()

    # 범위 분리 (~ 또는 - 사용)
    if '~' in price_str:
        parts = price_str.split('~')
    elif '-' in price_str:
        parts = price_str.split('-')
    else:
        parts = [price_str]

    result_parts = []
    for part in parts:
        amount = parse_amount(part)
        if amount > 0:
            # 만원 단위로 포맷 (천 단위 구분)
            formatted = f"{amount:,}만원"
            result_parts.append(formatted)

    return '~'.join(result_parts) if result_parts else price_str

def fix_post(post_dir: Path) -> bool:
    """포스트의 가격을 수정"""
    meta_file = post_dir / 'post_meta.json'
    if not meta_file.exists():
        return False

    try:
        with open(meta_file, 'r', encoding='utf-8') as f:
            meta = json.load(f)

        original_price = meta.get('price_range', '')
        if original_price:
            normalized = normalize_price(original_price)
            if normalized and normalized != original_price:
                meta['price_range'] = normalized
                with open(meta_file, 'w', encoding='utf-8') as f:
                    json.dump(meta, f, ensure_ascii=False, indent=2)
                print(f"✓ {post_dir.name}")
                print(f"  Before: {original_price}")
                print(f"  After:  {normalized}")
                return True

        return False
    except Exception as e:
        print(f"✗ {post_dir.name}: {e}")
        return False

def main():
    posts_dir = Path('output/posts')
    if not posts_dir.exists():
        print("❌ output/posts 폴더를 찾을 수 없습니다.")
        return

    fixed_count = 0
    total_count = 0

    for post_dir in sorted(posts_dir.iterdir()):
        if post_dir.is_dir() and post_dir.name != 'posts':
            total_count += 1
            if fix_post(post_dir):
                fixed_count += 1

    print(f"\n✅ 완료: {fixed_count}/{total_count}개 포스트 수정")

if __name__ == '__main__':
    main()
