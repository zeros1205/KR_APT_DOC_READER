"""
image_finder.py
────────────────────────────────────────────────────
포스팅 이미지를 두 가지 방식으로 처리합니다.

[A] 단지 전용 이미지 → PLACEHOLDER (직접 삽입)
    - 단지 조감도, 평면도, 위치 지도 등
    - 건설사 제공 이미지라 자동 수집 불가
    - HTML에 눈에 띄는 안내 박스 렌더링

[B] 개념/분위기 이미지 → Unsplash/Pexels 자동 수집
    - 대출/금융, 이사, 인테리어 등 일반 개념 이미지
    - CC0 라이선스 이미지 자동 삽입 + 출처 자동 표기
────────────────────────────────────────────────────
"""

import os
import re
import httpx
import asyncio
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum


# ──────────────────────────────────────────────────
# 이미지 타입 정의
# ──────────────────────────────────────────────────

class ImageType(Enum):
    PLACEHOLDER = "placeholder"   # 직접 삽입 필요
    AUTO        = "auto"          # Unsplash/Pexels 자동 수집


@dataclass
class ImageResult:
    """이미지 처리 결과 단일 객체"""
    image_type: ImageType
    slot_name: str            # 슬롯 식별자 (예: "hero", "finance")
    slot_label: str           # 한글 라벨 (예: "단지 조감도")

    # AUTO 전용 필드
    url: str = ""
    local_path: str | None = None
    source: str = ""
    photographer: str = ""
    photographer_url: str = ""
    credit_text: str = ""

    # PLACEHOLDER 전용 필드
    placeholder_hint: str = ""       # 어떤 이미지를 넣어야 하는지 안내
    placeholder_size: str = "800×450"  # 권장 사이즈


# ──────────────────────────────────────────────────
# [A] 단지 전용 이미지 슬롯 (PLACEHOLDER)
#     → HTML에 안내 박스로 렌더링, 사용자가 직접 교체
# ──────────────────────────────────────────────────

APT_PLACEHOLDER_SLOTS: dict[str, dict] = {
    "hero": {
        "label": "단지 조감도",
        "hint": (
            "건설사 공식 홈페이지 또는 청약홈(applyhome.co.kr) 분양공고 페이지에서\n"
            "단지 조감도(외관 투시도) 이미지를 다운로드하여 삽입하세요."
        ),
        "size": "800×450",
    },
    "floor_plan_59": {
        "label": "59타입 평면도",
        "hint": (
            "청약홈 해당 공고 PDF 또는 건설사 홈페이지에서\n"
            "59타입(또는 가장 작은 타입) 평면도 이미지를 삽입하세요."
        ),
        "size": "600×400",
    },
    "floor_plan_84": {
        "label": "84타입 평면도",
        "hint": (
            "청약홈 해당 공고 PDF 또는 건설사 홈페이지에서\n"
            "84타입(또는 중간 타입) 평면도 이미지를 삽입하세요."
        ),
        "size": "600×400",
    },
}


# ──────────────────────────────────────────────────
# [B] 개념/분위기 이미지 슬롯 (AUTO - Unsplash/Pexels)
#     → 저작권 없는 이미지 자동 수집
# ──────────────────────────────────────────────────

AUTO_IMAGE_SLOTS: dict[str, dict] = {
    "checklist": {
        "label": "입주 준비 (이사/체크리스트)",
        "query_unsplash": "moving boxes apartment new home packing",
        "query_pexels":   "moving house cardboard boxes apartment",
        "orientation": "landscape",
    },
    "interior": {
        "label": "인테리어 개념",
        "query_unsplash": "modern apartment interior living room design",
        "query_pexels":   "modern apartment interior design",
        "orientation": "landscape",
    },
}

# API 키 미설정 시 사용할 기본 이미지 (Unsplash 고정 URL)
FALLBACK_IMAGES: dict[str, str] = {
    "checklist": "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=800",
    "interior":  "https://images.unsplash.com/photo-1586023492125-27b2c045efd7?w=800",
}
FALLBACK_CREDIT = {
    "url": "https://unsplash.com",
    "photographer": "Unsplash",
    "photographer_url": "https://unsplash.com",
    "source": "Unsplash",
    "credit_text": "Photo by Unsplash",
}


# ──────────────────────────────────────────────────
# Unsplash API 호출
# ──────────────────────────────────────────────────

UNSPLASH_API_KEY = os.getenv("UNSPLASH_ACCESS_KEY", "")
UNSPLASH_BASE = "https://api.unsplash.com"


async def _fetch_unsplash(query: str, orientation: str = "landscape") -> dict | None:
    if not UNSPLASH_API_KEY:
        return None
    headers = {"Authorization": f"Client-ID {UNSPLASH_API_KEY}"}
    params = {
        "query": query,
        "orientation": orientation,
        "per_page": 1,
        "content_filter": "high",
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(
                f"{UNSPLASH_BASE}/search/photos",
                headers=headers, params=params,
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])
            return results[0] if results else None
        except Exception as e:
            print(f"    [Unsplash] 실패: {e}")
            return None


# ──────────────────────────────────────────────────
# Pexels API 호출 (폴백)
# ──────────────────────────────────────────────────

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")
PEXELS_BASE = "https://api.pexels.com/v1"


async def _fetch_pexels(query: str, orientation: str = "landscape") -> dict | None:
    if not PEXELS_API_KEY:
        return None
    headers = {"Authorization": PEXELS_API_KEY}
    params = {
        "query": query,
        "orientation": orientation,
        "per_page": 1,
        "size": "large",
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(
                f"{PEXELS_BASE}/search",
                headers=headers, params=params,
            )
            resp.raise_for_status()
            photos = resp.json().get("photos", [])
            return photos[0] if photos else None
        except Exception as e:
            print(f"    [Pexels] 실패: {e}")
            return None


async def _download_image(url: str, save_path: Path) -> bool:
    """이미지를 로컬에 저장 (네이버 블로그 직접 업로드용)"""
    if save_path.exists():
        return True
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            save_path.write_bytes(resp.content)
            size_kb = len(resp.content) // 1024
            print(f"    [저장] {save_path.name} ({size_kb}KB)")
            return True
        except Exception as e:
            print(f"    [저장 실패] {e}")
            return False


async def _fetch_auto_image(
    slot_name: str,
    slot_cfg: dict,
    image_dir: Path,
) -> ImageResult:
    """Unsplash → Pexels → 기본 이미지 순으로 시도"""

    img_url = photographer = photographer_url = source = credit = ""

    # 1순위: Unsplash
    photo = await _fetch_unsplash(slot_cfg["query_unsplash"], slot_cfg["orientation"])
    if photo:
        img_url = photo["urls"]["regular"]
        photographer = photo["user"]["name"]
        photographer_url = photo["user"]["links"]["html"]
        source = "Unsplash"
        credit = f"Photo by {photographer} on Unsplash"

    # 2순위: Pexels
    if not img_url:
        photo = await _fetch_pexels(slot_cfg["query_pexels"], slot_cfg["orientation"])
        if photo:
            img_url = photo["src"]["large"]
            photographer = photo["photographer"]
            photographer_url = photo["photographer_url"]
            source = "Pexels"
            credit = f"Photo by {photographer} on Pexels"

    # 3순위: 고정 기본 이미지 (API 키 없을 때)
    if not img_url:
        img_url = FALLBACK_IMAGES.get(slot_name, FALLBACK_IMAGES["neighborhood"])
        photographer = FALLBACK_CREDIT["photographer"]
        photographer_url = FALLBACK_CREDIT["photographer_url"]
        source = FALLBACK_CREDIT["source"]
        credit = FALLBACK_CREDIT["credit_text"]
        print(f"    [{slot_name}] API 키 없음 → 기본 이미지 사용")

    # 로컬 다운로드
    image_dir.mkdir(parents=True, exist_ok=True)
    safe_slot = re.sub(r"[^\w]", "_", slot_name)
    ext = img_url.split("?")[0].rsplit(".", 1)[-1]
    ext = ext if ext in ("jpg", "jpeg", "png", "webp") else "jpg"
    local_path = image_dir / f"auto_{safe_slot}.{ext}"
    ok = await _download_image(img_url, local_path)

    return ImageResult(
        image_type=ImageType.AUTO,
        slot_name=slot_name,
        slot_label=slot_cfg["label"],
        url=img_url,
        local_path=str(local_path) if ok else None,
        source=source,
        photographer=photographer,
        photographer_url=photographer_url,
        credit_text=credit,
    )


# ──────────────────────────────────────────────────
# 통합 이미지 수집 (메인 진입점)
# ──────────────────────────────────────────────────

async def find_images_for_post(
    apt_name: str,
    output_dir: Path,
) -> dict[str, ImageResult]:
    """
    포스팅에 필요한 전체 이미지를 준비합니다.

    Returns:
        {slot_name: ImageResult}
    """
    image_dir = output_dir / "images"
    results: dict[str, ImageResult] = {}

    # [A] 플레이스홀더 슬롯 (API 호출 없이 즉시 생성)
    for slot_name, cfg in APT_PLACEHOLDER_SLOTS.items():
        results[slot_name] = ImageResult(
            image_type=ImageType.PLACEHOLDER,
            slot_name=slot_name,
            slot_label=cfg["label"],
            placeholder_hint=cfg["hint"],
            placeholder_size=cfg["size"],
        )

    # [B] 자동 이미지 슬롯 (병렬 수집)
    tasks = {
        slot_name: _fetch_auto_image(slot_name, cfg, image_dir)
        for slot_name, cfg in AUTO_IMAGE_SLOTS.items()
    }
    fetched = await asyncio.gather(*tasks.values(), return_exceptions=True)
    for slot_name, result in zip(tasks.keys(), fetched):
        if isinstance(result, Exception):
            print(f"  [이미지] '{slot_name}' 수집 실패: {result}")
        else:
            results[slot_name] = result

    auto_ok = sum(
        1 for k, r in results.items()
        if r.image_type == ImageType.AUTO and r.local_path
    )
    ph_count = sum(1 for r in results.values() if r.image_type == ImageType.PLACEHOLDER)
    print(f"  [이미지] 자동 {auto_ok}/{len(AUTO_IMAGE_SLOTS)}개 | 플레이스홀더 {ph_count}개 (직접 삽입 필요)")
    return results


# ──────────────────────────────────────────────────
# HTML 렌더링 헬퍼
# ──────────────────────────────────────────────────

def render_image_html(img: ImageResult, extra_style: str = "") -> str:
    """ImageResult → 네이버 블로그 호환 HTML"""
    if img.image_type == ImageType.PLACEHOLDER:
        return _render_placeholder_html(img, extra_style)
    return _render_auto_image_html(img, extra_style)


def _render_placeholder_html(img: ImageResult, extra_style: str = "") -> str:
    hint = img.placeholder_hint.replace("\n", "<br>")
    return (
        f'<div style="border:3px dashed #E8A020; border-radius:10px; '
        f'background:#fffbf0; padding:32px 24px; text-align:center; {extra_style}">\n'
        f'  <div style="font-size:36px; margin-bottom:12px;">🖼️</div>\n'
        f'  <div style="font-size:15px; font-weight:700; color:#1B3F6B; margin-bottom:10px;">'
        f'[{img.slot_label}] 이미지를 직접 삽입해주세요</div>\n'
        f'  <div style="font-size:13px; color:#666; line-height:1.7; margin-bottom:14px;">'
        f'{hint}</div>\n'
        f'  <span style="background:#1B3F6B; color:#fff; font-size:11px; '
        f'padding:4px 12px; border-radius:12px; font-weight:600;">'
        f'권장 사이즈: {img.placeholder_size}</span>\n'
        f'</div>'
    )


def _render_auto_image_html(img: ImageResult, extra_style: str = "") -> str:
    credit = build_credit_html(img)
    return (
        f'<div style="{extra_style}">\n'
        f'  <img src="{img.url}" alt="{img.slot_label}"\n'
        f'       style="width:100%; border-radius:8px; display:block;" />\n'
        f'  <p style="font-size:11px; color:#888; margin:4px 0 0 0; '
        f'text-align:right; font-style:italic;">📷 {credit}</p>\n'
        f'</div>'
    )


def build_credit_html(img: ImageResult) -> str:
    """출처 표기 HTML"""
    if img.image_type == ImageType.PLACEHOLDER or not img.source:
        return ""
    platform_url = (
        "https://unsplash.com" if img.source == "Unsplash"
        else "https://www.pexels.com"
    )
    return (
        f'Photo by <a href="{img.photographer_url}" rel="nofollow noopener" '
        f'target="_blank">{img.photographer}</a> on '
        f'<a href="{platform_url}" rel="nofollow noopener" '
        f'target="_blank">{img.source}</a>'
    )
