"""Helpers for public housing notices that should land on ApplyHome."""

from __future__ import annotations

from typing import Any


_PUBLIC_NAME_KEYWORDS = (
    "공공분양",
    "토지임대부",
    "공공임대",
    "국민임대",
    "행복주택",
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def is_public_notice_data(data: dict[str, Any]) -> bool:
    """Return True for public housing notices handled outside detail posts."""
    apt_name = _text(data.get("apt_name"))
    house_detail_type = _text(data.get("house_detail_type"))
    supply_type = _text(data.get("supply_type"))
    combined = f"{apt_name} {house_detail_type} {supply_type}"

    if house_detail_type and house_detail_type != "민영":
        return True
    return any(keyword in combined for keyword in _PUBLIC_NAME_KEYWORDS)


def is_public_notice_doc(doc: Any) -> bool:
    return is_public_notice_data(
        {
            "apt_name": getattr(doc, "apt_name", ""),
            "house_detail_type": getattr(doc, "house_detail_type", ""),
            "supply_type": getattr(doc, "supply_type", ""),
        }
    )
