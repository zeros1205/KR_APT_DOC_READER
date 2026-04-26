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


def _extract_table_tokens(text: str) -> list[str]:
    inline_match = re.search(
        r"재당첨제한\s*(?P<readmission>\S+)\s+전매제한\s*(?P<resale>\S+)\s+거주의무기간\s*(?P<live>\S+)\s+분양가상한제\s*(?P<price_cap>\S+)\s+택지유형\s*(?P<land_type>\S+)",
        text,
    )
    if inline_match:
        return [
            inline_match.group("readmission"),
            inline_match.group("resale"),
            inline_match.group("live"),
            inline_match.group("price_cap"),
            inline_match.group("land_type"),
        ]

    lines = [line for line in text.splitlines() if line.strip()]
    header_idx = _find_first_line(lines, "재당첨제한", "전매제한", "거주의무기간", "분양가상한제", "택지유형")
    if header_idx < 0:
        return []
    collected: list[str] = []
    for line in lines[header_idx + 1 : header_idx + 5]:
        tokens = [
            token
            for token in line.split()
            if token not in {"재당첨제한", "전매제한", "거주의무기간", "분양가상한제", "택지유형"}
        ]
        collected.extend(tokens)
        if len(collected) >= 5:
            return collected[:5]
    return collected[:5]


def extract_policy_from_pdf_text(pdf_text: str) -> dict[str, str]:
    """PDF 텍스트에서 규제 5종과 택지 유형을 추출한다."""
    normalized = normalize_pdf_text(pdf_text)
    if not normalized.strip():
        return {key: "" for key in _POLICY_KEYS}

    lines = normalized.splitlines()
    result: dict[str, str] = {key: "" for key in _POLICY_KEYS}

    table_tokens = _extract_table_tokens(normalized)
    if len(table_tokens) >= 5:
        result["readmission_limit"] = _clean_value(table_tokens[0])
        result["resale_restriction"] = _clean_value(table_tokens[1])
        result["live_requirement"] = _clean_value(table_tokens[2])
        result["price_cap"] = _clean_value(table_tokens[3])
        result["land_type"] = _clean_value(table_tokens[4])

    # 규제지역 여부
    if any(token in normalized for token in ("비규제지역", "비투기과열지구", "비청약과열지역")):
        result["regulated_zone"] = "비규제지역"
        result["is_hot_zone"] = "N"
    else:
        zones: list[str] = []
        if "투기과열지구" in normalized:
            zones.append("투기과열지구")
        if "조정대상지역" in normalized:
            zones.append("조정대상지역")
        if "청약과열지역" in normalized:
            zones.append("청약과열지역")
        if zones:
            result["regulated_zone"] = ", ".join(dict.fromkeys(zones))
            result["is_hot_zone"] = "Y"

    # 재당첨 제한
    readmission_patterns = [
        r"재당첨제한\s*[:：]?\s*([^\n]+)",
        r"재당첨\s*제한\s*[:：]?\s*([^\n]+)",
    ]
    for pat in readmission_patterns:
        m = re.search(pat, normalized)
        if m and not result["readmission_limit"]:
            result["readmission_limit"] = _clean_value(m.group(1))
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
            result["resale_restriction"] = _clean_value(m.group(1))
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
            result["live_requirement"] = _clean_value(m.group(1))
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
