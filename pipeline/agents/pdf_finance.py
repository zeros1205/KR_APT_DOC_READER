"""
Local PDF finance extraction helpers.

The public ApplyHome API does not expose contract / midterm / balance ratios.
When a local 모집공고문 PDF is available, extract those values from the
"공급금액 및 납부일정" table header without downloading anything.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path

import pdfplumber

SUPPLY_AMOUNT = "\uacf5\uae09\uae08\uc561"
PAYMENT_SCHEDULE = "\ub0a9\ubd80\uc77c\uc815"
CONTRACT = "\uacc4\uc57d\uae08"
MIDTERM = "\uc911\ub3c4\uae08"
BALANCE = "\uc794\uae08"


@dataclass
class FinanceExtraction:
    contract_ratio: str = ""
    midterm_ratio: str = ""
    balance_ratio: str = ""
    midterm_count: str = ""
    source_page: int | None = None
    source_pdf: str = ""
    evidence: list[str] | None = None

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["evidence"] = data["evidence"] or []
        return data

    @property
    def has_core_ratios(self) -> bool:
        return bool(self.contract_ratio and self.midterm_ratio and self.balance_ratio)


def find_local_pdf(pdf_dir: Path, notice_id: str) -> Path | None:
    if not notice_id or not pdf_dir.exists():
        return None
    matches = sorted(pdf_dir.glob(f"{notice_id}*.pdf"))
    return matches[0] if matches else None


def _percent_values(line: str) -> list[int]:
    values: list[int] = []
    for idx, char in enumerate(line):
        if char != "%":
            continue
        cursor = idx - 1
        digits: list[str] = []
        while cursor >= 0 and line[cursor].isdigit():
            digits.append(line[cursor])
            cursor -= 1
        if digits:
            values.append(int("".join(reversed(digits))))
    return values


def _first_percent_after(line: str, keyword: str, width: int = 80) -> int | None:
    idx = line.find(keyword)
    if idx < 0:
        return None
    end = idx + width
    for marker in (CONTRACT, MIDTERM, BALANCE):
        if marker == keyword:
            continue
        marker_idx = line.find(marker, idx + len(keyword))
        if marker_idx >= 0:
            end = min(end, marker_idx)
    values = _percent_values(line[idx:end])
    return values[0] if values else None


def _infer_missing_ratio(result: FinanceExtraction, header_has_balance: bool) -> None:
    try:
        contract = int(result.contract_ratio) if result.contract_ratio else None
        midterm = int(result.midterm_ratio) if result.midterm_ratio else None
        balance = int(result.balance_ratio) if result.balance_ratio else None
    except ValueError:
        return

    if balance is None and header_has_balance and contract is not None and midterm is not None:
        inferred = 100 - contract - midterm
        if 0 <= inferred <= 100:
            result.balance_ratio = str(inferred)
    if midterm is None and contract is not None and balance is not None:
        inferred = 100 - contract - balance
        if 0 <= inferred <= 100:
            result.midterm_ratio = str(inferred)
    if contract is None and midterm is not None and balance is not None:
        inferred = 100 - midterm - balance
        if 0 <= inferred <= 100:
            result.contract_ratio = str(inferred)


def _parse_payment_window(lines: list[str]) -> FinanceExtraction:
    compact = [line.strip() for line in lines if line.strip()]
    result = FinanceExtraction(evidence=[])
    header_has_balance = any(BALANCE in line.replace(" ", "") for line in compact[:8])

    for line in compact:
        no_space = line.replace(" ", "")
        if not result.midterm_ratio and MIDTERM in no_space:
            value = _first_percent_after(no_space, MIDTERM)
            if value is not None:
                result.midterm_ratio = str(value)
                result.evidence.append(line)

        if not result.contract_ratio and CONTRACT in no_space:
            value = _first_percent_after(no_space, CONTRACT)
            if value is not None:
                result.contract_ratio = str(value)
                result.evidence.append(line)

        if not result.balance_ratio and BALANCE in no_space:
            value = _first_percent_after(no_space, BALANCE)
            if value is not None:
                result.balance_ratio = str(value)
                result.evidence.append(line)

    for line in compact:
        no_space = line.replace(" ", "")
        if ("\ud68c\ucc28" in no_space or "\ucc28" in no_space) and len(_percent_values(no_space)) >= 3:
            count = len(_percent_values(no_space))
            if count:
                result.midterm_count = str(count)
                break

    # Header rows often provide contract / midterm directly and omit balance.
    _infer_missing_ratio(result, header_has_balance)

    joined_header = " ".join(compact[:8]).replace(" ", "")
    contract_labels = joined_header.count(CONTRACT)
    midterm_labels = joined_header.count(MIDTERM)
    balance_labels = joined_header.count(BALANCE)
    for line in compact[:8]:
        no_space = line.replace(" ", "")
        if ("\ud68c\ucc28" in no_space or "\ucc28" in no_space) and len(_percent_values(no_space)) >= 3:
            values = _percent_values(no_space)
            if values:
                midterm_values = values
                if header_has_balance and len(set(values)) > 1 and sum(values[:-1]) + values[-1] <= 100:
                    result.balance_ratio = str(values[-1])
                    midterm_values = values[:-1]
                elif header_has_balance and result.contract_ratio:
                    contract_value = int(result.contract_ratio)
                    if contract_value + sum(values[:-1]) + values[-1] == 100:
                        result.balance_ratio = str(values[-1])
                        midterm_values = values[:-1]
                elif result.balance_ratio and str(values[-1]) == result.balance_ratio:
                    midterm_values = values[:-1]
                if not result.midterm_ratio and midterm_values:
                    result.midterm_ratio = str(sum(midterm_values))
                if midterm_values:
                    result.midterm_count = str(len(midterm_values))
                if result.evidence is not None:
                    result.evidence.append(line)
                _infer_missing_ratio(result, header_has_balance)
            continue
        if CONTRACT in no_space or MIDTERM in no_space or BALANCE in no_space:
            continue
        values = _percent_values(no_space)
        if not values:
            continue
        cursor = 0
        if not result.contract_ratio and contract_labels and cursor < len(values):
            result.contract_ratio = str(values[cursor])
            cursor += max(1, contract_labels)
        elif contract_labels:
            cursor += max(1, contract_labels)
        if not result.midterm_ratio and midterm_labels and cursor < len(values):
            take = values[cursor : cursor + max(1, midterm_labels)]
            if take:
                result.midterm_ratio = str(sum(take))
            cursor += max(1, midterm_labels)
        elif midterm_labels:
            cursor += max(1, midterm_labels)
        if not result.balance_ratio and balance_labels and values:
            result.balance_ratio = str(values[-1])
        if result.evidence is not None:
            result.evidence.append(line)
        _infer_missing_ratio(result, header_has_balance)
        if result.has_core_ratios:
            return result

    # Some PDFs split labels and percentages across multiple header rows:
    # "해당 계약금 잔금" followed by "주택형 ... (20%) (20%)".
    for idx, line in enumerate(compact):
        no_space = line.replace(" ", "")
        if CONTRACT in no_space and BALANCE in no_space:
            for next_line in compact[idx + 1 : idx + 6]:
                values = _percent_values(next_line)
                if len(values) == 2:
                    if not result.contract_ratio:
                        result.contract_ratio = str(values[0])
                    if not result.balance_ratio:
                        result.balance_ratio = str(values[1])
                    result.evidence.extend([line, next_line])
                    _infer_missing_ratio(result, header_has_balance)
                    return result

    return result


def _is_payment_table_anchor(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if stripped[0] in "-•※·*":
        return False
    no_space = stripped.replace(" ", "")
    if "\uacf5\uc815" in no_space or "\uaddc\uce59" in no_space or "\uc21c\uc11c\ub85c\ub0a9\ubd80" in no_space:
        return False
    if SUPPLY_AMOUNT not in no_space and PAYMENT_SCHEDULE not in no_space:
        return False
    if stripped.startswith("■") and SUPPLY_AMOUNT in no_space:
        return True
    if PAYMENT_SCHEDULE in no_space:
        return True
    if "\ud45c" in no_space:
        return True
    if CONTRACT in no_space and (MIDTERM in no_space or BALANCE in no_space):
        return True
    return False


def extract_finance_from_pdf(path: Path) -> FinanceExtraction:
    result = FinanceExtraction(source_pdf=path.name, evidence=[])
    try:
        with pdfplumber.open(path) as pdf:
            for page_no, page in enumerate(pdf.pages, 1):
                if page_no > 25:
                    break
                text = page.extract_text() or ""
                if not text:
                    continue
                lines = text.splitlines()
                for idx, line in enumerate(lines):
                    if not _is_payment_table_anchor(line):
                        continue
                    parsed = _parse_payment_window(lines[idx : idx + 16])
                    if parsed.has_core_ratios:
                        parsed.source_page = page_no
                        parsed.source_pdf = path.name
                        return parsed
    except Exception as exc:
        result.evidence = [f"PDF finance extraction failed: {exc}"]
    return result
