"""
image_finder.py
────────────────────────────────────────────────
Unsplash/Pexels API를 통한 이미지 자동 수집
────────────────────────────────────────────────
"""

import asyncio
import requests
from typing import List, Dict, Optional
from pathlib import Path

try:
    from pipeline.config import UNSPLASH_ACCESS_KEY, PEXELS_API_KEY
    from pipeline.logger import logger
except ImportError:
    from config import UNSPLASH_ACCESS_KEY, PEXELS_API_KEY
    logger = None


async def search_unsplash(query: str, count: int = 3) -> List[Dict[str, str]]:
    """
    Unsplash에서 이미지 검색

    Args:
        query: 검색어 (예: "apartment city")
        count: 검색 이미지 수

    Returns:
        이미지 리스트 [{"url": "...", "credit": "...", "alt": "..."}, ...]
    """
    if not UNSPLASH_ACCESS_KEY:
        if logger:
            logger.debug("UNSPLASH_ACCESS_KEY not set")
        return []

    try:
        api_url = "https://api.unsplash.com/search/photos"
        params = {
            "query": query,
            "per_page": count,
            "client_id": UNSPLASH_ACCESS_KEY
        }

        response = await asyncio.to_thread(
            lambda: requests.get(api_url, params=params, timeout=10)
        )

        if response.status_code != 200:
            return []

        data = response.json()
        results = data.get("results", [])

        images = []
        for item in results:
            image = {
                "url": item.get("urls", {}).get("regular", ""),
                "alt": item.get("alt_description", "apartment image"),
                "credit": f"Photo by {item.get('user', {}).get('name', 'Unknown')} on Unsplash"
            }
            if image["url"]:
                images.append(image)

        if logger:
            logger.debug(f"Unsplash: {len(images)} 이미지 검색됨")
        return images

    except Exception as e:
        if logger:
            logger.debug(f"Unsplash API 에러: {e}")
        return []


async def search_pexels(query: str, count: int = 3) -> List[Dict[str, str]]:
    """
    Pexels에서 이미지 검색

    Args:
        query: 검색어
        count: 검색 이미지 수

    Returns:
        이미지 리스트
    """
    if not PEXELS_API_KEY:
        if logger:
            logger.debug("PEXELS_API_KEY not set")
        return []

    try:
        api_url = "https://api.pexels.com/v1/search"
        headers = {"Authorization": PEXELS_API_KEY}
        params = {
            "query": query,
            "per_page": count
        }

        response = await asyncio.to_thread(
            lambda: requests.get(api_url, headers=headers, params=params, timeout=10)
        )

        if response.status_code != 200:
            return []

        data = response.json()
        results = data.get("photos", [])

        images = []
        for item in results:
            src = item.get("src", {})
            image = {
                "url": src.get("large", ""),
                "alt": item.get("alt", "apartment image"),
                "credit": f"Photo by {item.get('photographer', 'Unknown')} on Pexels"
            }
            if image["url"]:
                images.append(image)

        if logger:
            logger.debug(f"Pexels: {len(images)} 이미지 검색됨")
        return images

    except Exception as e:
        if logger:
            logger.debug(f"Pexels API 에러: {e}")
        return []


async def find_images(
    apt_name: str,
    location: str,
    max_images: int = 3
) -> Dict[str, List[Dict[str, str]]]:
    """
    아파트 관련 이미지 수집 (Unsplash + Pexels)

    Args:
        apt_name: 아파트명
        location: 위치
        max_images: 최대 이미지 수

    Returns:
        이미지 딕셔너리
        {
            "apt": [...],           # 아파트 관련
            "location": [...],      # 지역 관련
            "cityscape": [...]      # 도시 경관
        }
    """
    results = {
        "apt": [],
        "location": [],
        "cityscape": []
    }

    try:
        # 병렬로 이미지 검색
        apt_query = f"{apt_name} apartment"
        location_query = f"{location} korea"
        cityscape_query = "city buildings modern"

        apt_images, location_images, cityscape_images = await asyncio.gather(
            _search_both_apis(apt_query, max_images),
            _search_both_apis(location_query, max_images),
            _search_both_apis(cityscape_query, max_images),
            return_exceptions=False
        )

        results["apt"] = apt_images
        results["location"] = location_images
        results["cityscape"] = cityscape_images

        if logger:
            total = sum(len(v) for v in results.values())
            logger.info(f"이미지 수집 완료: {total}개")

        return results

    except Exception as e:
        if logger:
            logger.warning(f"이미지 수집 실패: {e}")
        return results


async def _search_both_apis(query: str, count: int) -> List[Dict[str, str]]:
    """Unsplash + Pexels 병렬 검색"""
    unsplash_imgs, pexels_imgs = await asyncio.gather(
        search_unsplash(query, count),
        search_pexels(query, count),
        return_exceptions=False
    )
    return unsplash_imgs + pexels_imgs


def generate_image_html(images: Dict[str, List[Dict[str, str]]]) -> str:
    """
    이미지 HTML 생성

    Args:
        images: 이미지 딕셔너리

    Returns:
        HTML 문자열
    """
    html = ""

    if images.get("apt"):
        html += '<div style="margin: 20px 0;">\n'
        html += '<h4>단지 이미지</h4>\n'
        for img in images["apt"][:1]:  # 첫 번째만
            html += f'<img src="{img["url"]}" alt="{img["alt"]}" style="max-width:100%; border-radius:8px; margin-bottom:10px;">\n'
            html += f'<p style="font-size:12px; color:#999;">{img["credit"]}</p>\n'
        html += '</div>\n'

    if images.get("location"):
        html += '<div style="margin: 20px 0;">\n'
        html += '<h4>입지 이미지</h4>\n'
        for img in images["location"][:1]:
            html += f'<img src="{img["url"]}" alt="{img["alt"]}" style="max-width:100%; border-radius:8px; margin-bottom:10px;">\n'
            html += f'<p style="font-size:12px; color:#999;">{img["credit"]}</p>\n'
        html += '</div>\n'

    return html


# 테스트 코드
if __name__ == "__main__":
    import sys
    apt_name = sys.argv[1] if len(sys.argv) > 1 else "샘플 아파트"
    location = sys.argv[2] if len(sys.argv) > 2 else "서울 강남구"

    images = asyncio.run(find_images(apt_name, location))
    print(f"\n수집된 이미지:")
    for category, imgs in images.items():
        print(f"  {category}: {len(imgs)}개")
