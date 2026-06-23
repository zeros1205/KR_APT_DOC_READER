"""
pdf_policy.py
────────────────────────────────────────────────────
입주자모집공고문 PDF에서 규제 5종 데이터를 추출하는 보조 모듈

추출 대상:
  - regulated_zone: 규제지역 여부
  - readmission_limit: 재당첨 제한
  - resale_restriction: 전매제한
  - live_requirement: 거주의무기간
  - price_cap: 분양가상한제
  - land_type: 택지유형
  - is_hot_zone: 투기과열지구 여부(Y/N)
────────────────────────────────────────────────────
"""

from __future__ import annotations

import re
from pathlib import Path

_POLICY_KEYS = (
    "regulated_zone",
    "readmission_limit",
    "resale_restriction",
    "live_requirement",
    "price_cap",
    "land_type",
    "is_hot_zone",
)

_NULLISH = {"", "-", "null", "none", "None", "공고문 확인 필요", "확인 필요"}


def normalize_pdf_text(text: str) -> str:
    """PDF 추출 텍스트의 공백/개행을 정규화한다."""
    text = (text or "").replace("\u00a0", " ").replace("\ufeff", "")
    text = text.replace("·", "·").replace("–", "-").replace("—", "-")
    lines = []
    for raw in text.splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if line:
            lines.append(line)
    return "\n".join(lines)


def find_local_pdf(pdf_dir: Path, notice_id: str = "", apt_name: str = "") -> Path | None:
    """로컬 PDF 저장소에서 공고문을 찾는다."""
    if not pdf_dir.exists():
        return None

    patterns: list[str] = []
    if notice_id:
        patterns.extend([f"{notice_id}*.pdf", f"*{notice_id}*.pdf"])

    safe_name = re.sub(r"[^\w가-힣]", " ", apt_name).strip()
    if safe_name:
        patterns.extend([f"*{safe_name}*.pdf", f"*{safe_name.replace(' ', '')}*.pdf"])

    for pattern in patterns:
        matches = sorted(pdf_dir.glob(pattern))
        if matches:
            return matches[0]
    return None


def _clean_value(value: str) -> str:
    value = re.sub(r"\s+", " ", value or "").strip(" \t\r\n.·")
    return value


def _clean_policy_period(value: str) -> str:
    value = _clean_value(value)
    if not value:
        return ""
    # 표 머리글을 값으로 잘못 잡은 경우는 폐기한다.
    header_tokens = ("재당첨제한", "전매제한", "거주의무기간", "분양가상한제", "택지유형")
    if any(token in value for token in header_tokens):
        return ""
    valid_patterns = (
        r"^\d+\s*년$",
        r"^\d+\s*개월$",
        r"^없음$",
        r"^해당\s*없음$",
        r"^비해당$",
        r"^소유권\s*이전\s*등기(?:일|시)?(?:까지)?$",
        r"^소유권이전등기(?:일|시)?(?:까지)?$",
    )
    if any(re.search(pattern, value) for pattern in valid_patterns):
        return re.sub(r"\s+", " ", value)
    return ""


def _clean_price_cap(value: str) -> str:
    value = _clean_value(value)
    if value in {"적용", "미적용"}:
        return value
    if value in {"없음", "해당 없음", "비해당"}:
        return "미적용"
    return ""


def _find_first_line(lines: list[str], *needles: str) -> int:
    for idx, line in enumerate(lines):
        if all(needle in line for needle in needles):
            return idx
    return -1


def _pick_value_after_header(lines: list[str], header_needles: tuple[str, ...]) -> str:
    idx = _find_first_line(lines, *header_needles)
    if idx < 0:
        return ""
    for line in lines[idx + 1 : idx + 6]:
        if line and not line.startswith("■"):
            if any(token in line for token in ("없음", "적용", "비규제", "투기과열", "조정대상", "청약과열", "민간택지", "공공택지")):
                return line
    return ""


def _extract_regulated_zone(lines: list[str], normalized: str) -> tuple[str, str]:
    header_idx = _find_first_line(lines, "규제지역여부")
    search_text = "\n".join(lines[header_idx + 1 : header_idx + 6]) if header_idx >= 0 else ""
    if not search_text:
        # 머리글을 찾지 못한 예외 PDF에서만 전체 텍스트를 보조로 사용한다.
        search_text = normalized[:3000]

    compact = search_text.replace(" ", "")
    if "비규제지역" in compact or "비규제지 역" in search_text or "비규제 지역" in search_text:
        return "비규제지역", "N"

    zones: list[str] = []
    if "투기과열지구" in compact:
        zones.append("투기과열지구")
    if "조정대상지역" in compact:
        zones.append("조정대상지역")
    if "청약과열지역" in compact:
        zones.append("청약과열지역")
    if zones:
        return ", ".join(dict.fromkeys(zones)), "Y"

    return "", ""


def _extract_table_tokens(text: str) -> list[str]:
    value_pattern = re.compile(
        r"(?P<readmission>\d+\s*년|없음|해당\s*없음|비해당)\s+"
        r"(?P<resale>\d+\s*년|없음|해당\s*없음|비해당)\s+"
        r"(?P<live>\d+\s*년|없음|해당\s*없음|비해당)\s+"
        r"(?P<price_cap>적용|미적용|해당\s*없음|비해당)"
    )

    inline_match = re.search(
        r"재당첨제한\s+전매제한\s+거주의무기간\s+분양가상한제\s+택지유형(?P<body>.*?)(?=\n구분|\n■|\Z)",
        text,
        re.DOTALL,
    )
    if inline_match:
        body = inline_match.group("body")
        value_match = value_pattern.search(body)
        if value_match:
            land_type = ""
            if "공공택지" in body:
                land_type = "공공택지"
            elif "민간택지" in body:
                land_type = "민간택지"
            return [
                value_match.group("readmission"),
                value_match.group("resale"),
                value_match.group("live"),
                value_match.group("price_cap"),
                land_type,
            ]

    inline_value_match = re.search(
        r"재당첨제한\s*(?P<readmission>\d+\s*년|없음|해당\s*없음|비해당)\s+"
        r"전매제한\s*(?P<resale>\d+\s*년|없음|해당\s*없음|비해당)\s+"
        r"거주의무기간\s*(?P<live>\d+\s*년|없음|해당\s*없음|비해당)\s+"
        r"분양가상한제\s*(?P<price_cap>적용|미적용|해당\s*없음|비해당)\s+"
        r"택지유형\s*(?P<land_type>공공택지|민간택지)?",
        text,
    )
    if inline_value_match:
        return [
            inline_value_match.group("readmission"),
            inline_value_match.group("resale"),
            inline_value_match.group("live"),
            inline_value_match.group("price_cap"),
            inline_value_match.group("land_type") or "",
        ]

    lines = [line for line in text.splitlines() if line.strip()]
    header_idx = _find_first_line(lines, "재당첨제한", "전매제한", "거주의무기간", "분양가상한제", "택지유형")
    if header_idx < 0:
        return []
    window = "\n".join(lines[header_idx + 1 : header_idx + 6])
    value_match = value_pattern.search(window)
    if value_match:
        land_type = ""
        if "공공택지" in window:
            land_type = "공공택지"
        elif "민간택지" in window:
            land_type = "민간택지"
        return [
            value_match.group("readmission"),
            value_match.group("resale"),
            value_match.group("live"),
            value_match.group("price_cap"),
            land_type,
        ]
    return []


def extract_policy_from_pdf_text(pdf_text: str) -> dict[str, str]:
    """PDF 텍스트에서 규제 5종과 택지 유형을 추출한다."""
    normalized = normalize_pdf_text(pdf_text)
    if not normalized.strip():
        return {key: "" for key in _POLICY_KEYS}

    lines = normalized.splitlines()
    result: dict[str, str] = {key: "" for key in _POLICY_KEYS}

    table_tokens = _extract_table_tokens(normalized)
    if len(table_tokens) >= 5:
        result["readmission_limit"] = _clean_policy_period(table_tokens[0])
        result["resale_restriction"] = _clean_policy_period(table_tokens[1])
        result["live_requirement"] = _clean_policy_period(table_tokens[2])
        result["price_cap"] = _clean_price_cap(table_tokens[3])
        result["land_type"] = _clean_value(table_tokens[4])

    # 규제지역 여부: 공고 첫 페이지의 "단지 주요정보" 표를 우선한다.
    zone, is_hot_zone = _extract_regulated_zone(lines, normalized)
    if zone:
        result["regulated_zone"] = zone
        result["is_hot_zone"] = is_hot_zone

    # 재당첨 제한
    readmission_patterns = [
        r"재당첨제한\s*[:：]?\s*([^\n]+)",
        r"재당첨\s*제한\s*[:：]?\s*([^\n]+)",
    ]
    for pat in readmission_patterns:
        m = re.search(pat, normalized)
        if m and not result["readmission_limit"]:
            result["readmission_limit"] = _clean_policy_period(m.group(1))
            break
    if any(phrase in normalized for phrase in ("재당첨 제한을 적용받지", "재당첨제한을 적용받지", "재당첨 제한 없음", "재당첨제한 없음")):
        result["readmission_limit"] = "없음"

    # 전매제한
    resale_patterns = [
        r"전매제한\s*[:：]?\s*([^\n]+)",
        r"전매\s*제한\s*[:：]?\s*([^\n]+)",
        r"전매제한기간\s*[:：]?\s*([^\n]+)",
    ]
    for pat in resale_patterns:
        m = re.search(pat, normalized)
        if m and not result["resale_restriction"]:
            result["resale_restriction"] = _clean_policy_period(m.group(1))
            break
    if any(phrase in normalized for phrase in ("전매제한 없음", "전매 제한 없음", "전매제한기간 전매제한 없음")):
        result["resale_restriction"] = "없음"

    # 거주의무기간
    live_patterns = [
        r"거주의무기간\s*[:：]?\s*([^\n]+)",
        r"실거주\s*의무\s*[:：]?\s*([^\n]+)",
        r"거주\s*의무\s*[:：]?\s*([^\n]+)",
    ]
    for pat in live_patterns:
        m = re.search(pat, normalized)
        if m and not result["live_requirement"]:
            result["live_requirement"] = _clean_policy_period(m.group(1))
            break
    if any(phrase in normalized for phrase in ("거주의무 없음", "실거주 의무 없음", "거주의무기간 없음", "실거주 의무 없음", "거주의무 없음")):
        result["live_requirement"] = "없음"

    # 분양가상한제
    if any(phrase in normalized for phrase in ("분양가상한제 미적용", "미적용 민영주택", "분양가상한제 적용 제외")):
        result["price_cap"] = "미적용"
    elif "분양가상한제 적용" in normalized and result["price_cap"] not in {"미적용"}:
        result["price_cap"] = "적용"

    # 택지 유형
    if not result["land_type"]:
        if "민간택지" in normalized:
            result["land_type"] = "민간택지"
        elif "공공택지" in normalized or "공공주택지구" in normalized:
            result["land_type"] = "공공택지"

    # 비어 있는 항목은 공고문 확인용으로 둔다.
    for key, value in list(result.items()):
        if value in _NULLISH:
            result[key] = ""

    return result


_POLICY_HEADER_MAP = {
    "재당첨제한": "readmission_limit",
    "전매제한": "resale_restriction",
    "거주의무기간": "live_requirement",
    "분양가상한제": "price_cap",
    "택지유형": "land_type",
}


def _norm_cell(cell: str) -> str:
    return re.sub(r"\s+", " ", (cell or "").replace("\n", " ")).strip()


def _value_below(rows: list[list[str]], ri: int, ci: int) -> str:
    """(ri, ci) 머리 셀 바로 아래 행의 같은 열 값을 읽는다."""
    if ri + 1 < len(rows) and ci < len(rows[ri + 1]):
        return rows[ri + 1][ci]
    return ""


def _normalize_zone_value(raw: str) -> tuple[str, str]:
    """규제지역 여부 셀 값을 표준 라벨/(Y·N)으로 정규화한다."""
    compact = (raw or "").replace(" ", "")
    if not compact:
        return "", ""
    if "비규제" in compact:
        return "비규제지역", "N"
    zones: list[str] = []
    if "투기과열지구" in compact:
        zones.append("투기과열지구")
    if "조정대상지역" in compact:
        zones.append("조정대상지역")
    if "청약과열지역" in compact:
        zones.append("청약과열지역")
    if zones:
        return ", ".join(dict.fromkeys(zones)), "Y"
    return "", ""


def extract_policy_from_tables(pages) -> dict[str, str]:
    """pdfplumber 표 추출로 규제 5종 + 규제지역 여부를 읽는다(1순위).

    공고문 1~2페이지 단지정보 표는 머리 셀(재당첨제한/전매제한/거주의무기간/
    분양가상한제/택지유형, 규제지역여부) 바로 아래 행에 값이 위치한다.
    """
    result: dict[str, str] = {key: "" for key in _POLICY_KEYS}
    for page in pages:
        try:
            tables = page.extract_tables()
        except Exception:
            continue
        for table in tables:
            rows = [[_norm_cell(cell) for cell in row] for row in table]
            for ri, row in enumerate(rows):
                for ci, cell in enumerate(row):
                    compact = cell.replace(" ", "")
                    key = _POLICY_HEADER_MAP.get(compact)
                    if key and not result[key]:
                        result[key] = _value_below(rows, ri, ci)
                    if "규제지역여부" in compact and not result["regulated_zone"]:
                        result["regulated_zone"] = _value_below(rows, ri, ci)

    result["readmission_limit"] = _clean_policy_period(result["readmission_limit"])
    result["resale_restriction"] = _clean_policy_period(result["resale_restriction"])
    result["live_requirement"] = _clean_policy_period(result["live_requirement"])
    result["price_cap"] = _clean_price_cap(result["price_cap"])
    result["land_type"] = _clean_value(result["land_type"])
    zone, is_hot = _normalize_zone_value(result["regulated_zone"])
    result["regulated_zone"] = zone
    result["is_hot_zone"] = is_hot
    return result


def extract_policy_from_pdf(pdf_path: Path, *, max_pages: int = 2) -> dict[str, str]:
    """로컬 PDF 파일에서 규제 정보를 직접 추출한다.

    1순위로 표(table) 셀 매핑을, 2순위로 기존 텍스트 정규식 추출을 사용하고
    표 기반 결과가 비어 있는 항목만 텍스트 결과로 보완한다.
    """
    try:
        import pdfplumber
    except Exception:
        return {key: "" for key in _POLICY_KEYS}

    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            pages = pdf.pages[:max(1, max_pages)]
            texts = [page.extract_text() or "" for page in pages]
            table_result = extract_policy_from_tables(pages)
    except Exception:
        return {key: "" for key in _POLICY_KEYS}

    text_result = extract_policy_from_pdf_text("\n".join(texts))

    merged = dict(text_result)
    for key, value in table_result.items():
        if value:
            merged[key] = value

    for key, value in list(merged.items()):
        if value in _NULLISH:
            merged[key] = ""
    return merged
