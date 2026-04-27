"""
data_validators.py
────────────────────────────────────────────────────
PostData 필드 검증 모듈
DATA_SPEC.md의 요구사항을 코드로 구현
────────────────────────────────────────────────────
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ValidationResult:
    """검증 결과 데이터 구조"""
    is_valid: bool
    warnings: list[str] = None  # 경고 (감점)
    errors: list[str] = None    # 오류 (불합격)

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
        if self.errors is None:
            self.errors = []


# ──────────────────────────────────────────────────
# 문자 수 제약 정의 (사용자 지시 기준)
# ──────────────────────────────────────────────────

# 전체 콘텐츠 길이 제약만 사용 (사용자 지시)
TOTAL_CONTENT_MIN = 800
TOTAL_CONTENT_MAX = 3000

# 필드별 제약 없음 (사용자가 지시하지 않음)
NARRATIVE_CONSTRAINTS = {}

COUNT_CONSTRAINTS = {
    "qa_blocks": (6, 6, "Q&A 블록 정확히 6개"),
}


# ──────────────────────────────────────────────────
# 개별 필드 검증 함수
# ──────────────────────────────────────────────────

def validate_narrative_field(
    field_name: str,
    value: str,
    strict: bool = False
) -> tuple[bool, list[str]]:
    """
    내러티브 필드 문자 수 검증

    Args:
        field_name: PostData 필드명
        value: 검증할 문자열
        strict: True면 범위 벗어남 = 오류, False면 경고

    Returns:
        (is_valid, messages)
    """
    if field_name not in NARRATIVE_CONSTRAINTS:
        return True, []

    min_char, max_char, description = NARRATIVE_CONSTRAINTS[field_name]
    text_len = len(value) if value else 0
    messages = []

    # 빈 필드 처리: 선택 필드(contract_desc 등)는 0자 허용
    if min_char == 0 and text_len == 0:
        return True, []

    # 최소 문자 수
    if text_len < min_char:
        msg = f"{field_name} 문자 수 부족: {text_len}자 (요구: {min_char}~{max_char}자) - {description}"
        messages.append(msg)

    # 최대 문자 수
    if text_len > max_char:
        msg = f"{field_name} 문자 수 초과: {text_len}자 (요구: {min_char}~{max_char}자) - {description}"
        messages.append(msg)

    # 선택사항은 경고만 반환, 필수는 오류
    if not messages:
        return True, []

    # 선택사항 필드는 경고만 반환
    if min_char == 0:
        return False, messages  # 경고 반환

    # 필수 필드는 범위 벗어나면 오류
    if strict and messages:
        return False, messages

    return True, messages


def validate_count_field(
    field_name: str,
    value: list,
    strict: bool = False
) -> tuple[bool, list[str]]:
    """
    개수 필드 검증

    Args:
        field_name: PostData 필드명 (qa_blocks, seo_tags, unit_types)
        value: 검증할 리스트
        strict: True면 범위 벗어남 = 오류

    Returns:
        (is_valid, messages)
    """
    if field_name not in COUNT_CONSTRAINTS:
        return True, []

    min_count, max_count, description = COUNT_CONSTRAINTS[field_name]
    actual_count = len(value) if value else 0
    messages = []

    # 최소 개수
    if actual_count < min_count:
        msg = f"{field_name} 부족: {actual_count}개 (요구: {min_count}개) - {description}"
        messages.append(msg)

    # 최대 개수
    if actual_count > max_count:
        msg = f"{field_name} 초과: {actual_count}개 (요구: 최대 {max_count}개) - {description}"
        messages.append(msg)

    if strict and messages:
        return False, messages

    return True, messages


# ──────────────────────────────────────────────────
# 종합 검증 함수
# ──────────────────────────────────────────────────

def validate_post_data(data: "PostData" = None, content: dict = None, facts: dict = None, strict: bool = False) -> ValidationResult:
    """
    PostData 전체 검증 (PostData 객체 또는 dict 기반)

    Args:
        data: PostData 인스턴스 (PostData 객체 검증 시)
        content: 콘텐츠 딕셔너리 (dict 검증 시)
        facts: 팩트 딕셔너리 (dict 검증 시)
        strict: True면 모든 요구사항 준수 강제

    Returns:
        ValidationResult (warnings/errors 분리)
    """
    result = ValidationResult(is_valid=True)

    # Dict 입력인 경우 처리
    if content is not None or facts is not None:
        content = content or {}
        facts = facts or {}

        # 1. 전체 콘텐츠 길이 검증 (사용자 지시 기준)
        post_content = content.get("post_content", "") or ""
        total_len = len(post_content)
        if total_len < TOTAL_CONTENT_MIN:
            result.warnings.append(f"전체 콘텐츠 길이 부족: {total_len}자 (요구: {TOTAL_CONTENT_MIN}~{TOTAL_CONTENT_MAX}자)")
        elif total_len > TOTAL_CONTENT_MAX:
            result.warnings.append(f"전체 콘텐츠 길이 초과: {total_len}자 (요구: {TOTAL_CONTENT_MIN}~{TOTAL_CONTENT_MAX}자)")

        # 2. 개수 필드 검증
        for field_name, (min_cnt, max_cnt, desc) in COUNT_CONSTRAINTS.items():
            value = content.get(field_name, []) or facts.get(field_name, [])
            is_valid, messages = validate_count_field(field_name, value, strict=strict)
            if not is_valid:
                result.errors.extend(messages)
            elif messages:
                result.warnings.extend(messages)

        # 3. 필수 필드 존재 여부
        if not facts.get("apt_name"):
            result.errors.append("필수 필드 누락: apt_name (단지명)")
        if not content.get("post_title"):
            result.errors.append("필수 필드 누락: post_title (포스트 제목)")
        if not facts.get("supply_address"):
            result.errors.append("필수 필드 누락: supply_address (공급 위치)")

    # PostData 객체 입력인 경우 처리
    elif data is not None:
        # 1. 전체 콘텐츠 길이 검증 (사용자 지시 기준)
        post_content = getattr(data, "post_content", "") or ""
        total_len = len(post_content)
        if total_len < TOTAL_CONTENT_MIN:
            result.warnings.append(f"전체 콘텐츠 길이 부족: {total_len}자 (요구: {TOTAL_CONTENT_MIN}~{TOTAL_CONTENT_MAX}자)")
        elif total_len > TOTAL_CONTENT_MAX:
            result.warnings.append(f"전체 콘텐츠 길이 초과: {total_len}자 (요구: {TOTAL_CONTENT_MIN}~{TOTAL_CONTENT_MAX}자)")

        # 2. 개수 필드 검증
        for field_name, (min_cnt, max_cnt, desc) in COUNT_CONSTRAINTS.items():
            value = getattr(data, field_name, [])
            is_valid, messages = validate_count_field(field_name, value, strict=strict)
            if not is_valid:
                result.errors.extend(messages)
            elif messages:
                result.warnings.extend(messages)

        # 3. 필수 필드 존재 여부
        required_fields = {
            "apt_name": "단지명",
            "post_title": "포스트 제목",
            "supply_address": "공급 위치",
        }
        for field, label in required_fields.items():
            if not getattr(data, field, ""):
                result.errors.append(f"필수 필드 누락: {field} ({label})")

    # 5. 종합 결과
    result.is_valid = len(result.errors) == 0

    return result


def get_validation_score_penalties(validation_result: ValidationResult) -> tuple[int, list[str]]:
    """
    검증 결과를 품질 점수 패널티로 변환

    Returns:
        (penalty_points, penalty_messages)
    """
    penalties = []
    penalty_points = 0

    # 오류: 20점 감점
    if validation_result.errors:
        penalty_points += 20
        for error in validation_result.errors:
            penalties.append(f"❌ {error}")

    # 경고: 필드당 3~5점 감점
    if validation_result.warnings:
        penalty_points += len(validation_result.warnings) * 3
        for warning in validation_result.warnings:
            penalties.append(f"⚠️  {warning}")

    return penalty_points, penalties
