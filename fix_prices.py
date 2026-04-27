#!/usr/bin/env python3
"""
분양가 오류 전수 수정 스크립트
- 소수점 가격(예: 4.3억)을 정수형으로 변환
- 한자 숫자(천, 백, 십)를 올바르게 파싱
- 모든 가격을 "약 X억~Y억원" 형식으로 정규화
"""

import json
import re
from pathlib import Path

def parse_single_price(text: str) -> int:
    """
    개별 가격 텍스트를 만원 단위 정수로 변환
    예: "4.3억" → 43000, "5천2백만" → 5200
    """
    if not text:
        return 0

    text = str(text).strip()
    text = re.sub(r'\s+', '', text)  # 공백 제거
    text = text.replace(',', '')

    if not text or text in {'-', 'null', 'None'}:
        return 0

    total = 0
    remaining = text

    # 억 처리
    m = re.search(r'([\d.]+)\s*억', remaining)
    if m:
        val = float(m.group(1))
        total += int(val * 10000)
        remaining = remaining[:m.start()] + remaining[m.end():]

    # 천만원 처리
    m = re.search(r'([\d.]+)\s*천\s*만원', remaining)
    if m:
        val = float(m.group(1))
        total += int(val * 1000)
        remaining = remaining[:m.start()] + remaining[m.end():]

    # 천만 처리 (만원 없이)
    m = re.search(r'([\d.]+)\s*천\s*만(?!원)', remaining)
    if m:
        val = float(m.group(1))
        total += int(val * 1000)
        remaining = remaining[:m.start()] + remaining[m.end():]

    # 천 처리
    m = re.search(r'([\d.]+)\s*천(?!만)', remaining)
    if m:
        val = float(m.group(1))
        total += int(val * 1000)
        remaining = remaining[:m.start()] + remaining[m.end():]

    # 백만원 처리
    m = re.search(r'([\d.]+)\s*백\s*만원', remaining)
    if m:
        val = float(m.group(1))
        total += int(val * 100)
        remaining = remaining[:m.start()] + remaining[m.end():]

    # 백 처리
    m = re.search(r'([\d.]+)\s*백(?!만)', remaining)
    if m:
        val = float(m.group(1))
        total += int(val * 100)
        remaining = remaining[:m.start()] + remaining[m.end():]

    # 십만원 처리
    m = re.search(r'([\d.]+)\s*십\s*만원', remaining)
    if m:
        val = float(m.group(1))
        total += int(val * 10)
        remaining = remaining[:m.start()] + remaining[m.end():]

    # 십 처리
    m = re.search(r'([\d.]+)\s*십(?!만)', remaining)
    if m:
        val = float(m.group(1))
        total += int(val * 10)
        remaining = remaining[:m.start()] + remaining[m.end():]

    # 만원 처리 (가장 나중에)
    if '만원' in remaining:
        m = re.search(r'([\d.]+)\s*만원', remaining)
        if m:
            val = float(m.group(1))
            if total == 0:  # 억, 천, 백, 십이 없으면
                total = int(val)
            else:  # 있으면 더하기
                total += int(val)
            remaining = remaining[:m.start()] + remaining[m.end():]

    # 단순 숫자만 남음 (만원 단위)
    if total == 0:
        m = re.search(r'([\d.]+)', remaining)
        if m:
            val = float(m.group(1))
            total = int(val)

    return total


def manwon_to_string(manwon: int, use_decimal: bool = False) -> str:
    """
    만원 단위 정수를 "X억 Y만원" 또는 "만원" 형식 문자열로 변환

    Args:
        manwon: 만원 단위 정수
        use_decimal: True면 "4.3억원", False면 "4억 3,000만원"
    """
    if manwon <= 0:
        return ""

    if use_decimal:
        # "4.3억원" 형식
        eok = manwon / 10000
        if eok == int(eok):
            return f"{int(eok)}억원"
        else:
            return f"{eok:.1f}억원"
    else:
        # "4억 3,000만원" 형식, 1억 미만은 "X,XXX만원"
        eok = manwon // 10000
        man = manwon % 10000

        if eok == 0:
            # 1억 미만: "5,326만원"
            return f"{manwon:,}만원"
        elif man == 0:
            # 억 정확히: "4억원"
            return f"{eok}억원"
        else:
            # 억과 만원 혼합: "4억 3,000만원"
            return f"{eok}억 {man:,}만원"


def parse_price_range(price_str: str) -> tuple[int, int]:
    """
    가격대 범위 문자열을 분석하여 최소·최대 만원값 추출
    예: "약 4억 3,000만~6억 5,000만원" → (43000, 65000)
    """
    if not price_str:
        return 0, 0

    # "~" 또는 "-" 기준으로 분리
    parts = re.split(r'~|-', price_str)

    if len(parts) < 2:
        # 범위 없음 (단일 가격)
        val = parse_single_price(price_str)
        return val, val

    # 첫 번째 값과 두 번째 값 파싱
    p_min = parse_single_price(parts[0])
    p_max = parse_single_price(parts[1])

    # min > max인 경우 swap
    if p_min > p_max:
        p_min, p_max = p_max, p_min

    return p_min, p_max


def fix_price_range(price_str: str, apt_name: str = "") -> str:
    """
    분양가 범위 문자열을 정규화
    """
    p_min, p_max = parse_price_range(price_str)

    if p_min == 0 and p_max == 0:
        print(f"  ⚠️  {apt_name}: 가격 파싱 실패 → 원본 유지: {price_str}")
        return price_str

    # 통일된 형식으로 출력
    # 만원 단위 표기
    if p_min == p_max:
        result = manwon_to_string(p_min)
    else:
        result = f"{manwon_to_string(p_min)}~{manwon_to_string(p_max)}"

    # 원본과 다르면 표시
    if result != price_str:
        print(f"  ✓ {apt_name}")
        print(f"    수정 전: {price_str}")
        print(f"    수정 후: {result}")

    return result


def main():
    """모든 포스트의 price_range 수정"""
    post_dir = Path('output/posts')

    if not post_dir.exists():
        print("❌ output/posts 디렉토리 없음")
        return

    print("="*70)
    print("분양가 오류 전수 수정 시작")
    print("="*70)

    fixed_count = 0
    error_count = 0

    for post_folder in sorted(post_dir.iterdir()):
        if not post_folder.is_dir():
            continue

        meta_file = post_folder / 'post_meta.json'

        if not meta_file.exists():
            continue

        try:
            with open(meta_file, 'r', encoding='utf-8') as f:
                meta = json.load(f)

            apt_name = meta.get('apt_name', 'Unknown')
            old_price = meta.get('price_range', '')

            if not old_price:
                continue

            # 가격 수정
            new_price = fix_price_range(old_price, apt_name)

            if new_price != old_price:
                meta['price_range'] = new_price

                # 파일 저장
                with open(meta_file, 'w', encoding='utf-8') as f:
                    json.dump(meta, f, ensure_ascii=False, indent=2)

                fixed_count += 1

        except Exception as e:
            error_count += 1
            print(f"  ❌ {post_folder.name}: {e}")

    print("\n" + "="*70)
    print(f"✅ 수정 완료")
    print(f"  - 수정된 포스트: {fixed_count}개")
    print(f"  - 오류: {error_count}개")
    print("="*70)


if __name__ == '__main__':
    main()
