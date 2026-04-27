"""
regions.py
────────────────────────────────────────────────────
청약홈 공급지역 코드 ↔ 카테고리 매핑

사용처:
  - 인덱스 페이지 카테고리 필터
  - post_meta.json region_category 태깅
  - API 지역별 수집 (collect_from_api region_code 파라미터)
────────────────────────────────────────────────────
"""

# (카테고리명, 청약홈 SUBSCRPT_AREA_CODE, API 표시명 패턴)
REGIONS: list[tuple[str, str, list[str]]] = [
    ("서울",   "100", ["서울"]),
    ("경기도", "410", ["경기"]),
    ("인천",   "280", ["인천"]),
    ("부산",   "260", ["부산"]),
    ("대전",   "300", ["대전"]),
    ("대구",   "270", ["대구"]),
    ("광주",   "290", ["광주"]),
    ("세종",   "360", ["세종"]),
    ("울산",   "310", ["울산"]),
    ("강원도", "420", ["강원"]),
    ("충청북도","430", ["충북", "충청북"]),
    ("충청남도","440", ["충남", "충청남"]),
    ("전라북도","450", ["전북", "전라북", "전북특별"]),
    ("전라남도","460", ["전남", "전라남"]),
    ("경상북도","470", ["경북", "경상북"]),
    ("경상남도","480", ["경남", "경상남"]),
    ("제주도", "500", ["제주"]),
]

# 빠른 조회용 딕셔너리
CODE_TO_CATEGORY  = {code: name for name, code, _ in REGIONS}
NAME_TO_CODE      = {name: code for name, code, _ in REGIONS}
CATEGORY_ORDER    = [name for name, _, _ in REGIONS]


def region_name_to_category(region_name: str) -> str:
    """API region_name(예: '경기', '서울특별시') → 카테고리명(예: '경기도', '서울')"""
    if not region_name:
        return "기타"
    for cat, _, patterns in REGIONS:
        if any(p in region_name for p in patterns):
            return cat
    return region_name or "기타"


def category_to_code(category: str) -> str:
    """카테고리명 → 청약홈 지역코드"""
    return NAME_TO_CODE.get(category, "")
