from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import httpx
import re


BASE_URL = "https://dapi.kakao.com"
MAX_RADIUS = 500


@dataclass
class NearbyPlace:
    name: str
    distance: int
    address: str
    category: str
    source: str
    place_url: str = ""


class KakaoLocalClient:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key.strip()
        self._headers = {"Authorization": f"KakaoAK {self.api_key}"}

    async def geocode(self, address: str) -> tuple[str, str] | None:
        if not self.api_key or not address.strip():
            return None
        queries = self._build_address_queries(address)
        async with httpx.AsyncClient(timeout=15.0) as client:
            for query in queries:
                for analyze_type in ("exact", "similar"):
                    response = await client.get(
                        f"{BASE_URL}/v2/local/search/address.json",
                        headers=self._headers,
                        params={"query": query, "analyze_type": analyze_type},
                    )
                    response.raise_for_status()
                    data = response.json()
                    documents = data.get("documents") or []
                    if documents:
                        first = self._pick_safe_address_match(address, documents)
                        if first:
                            return first.get("x", ""), first.get("y", "")
        return None

    async def geocode_keyword(self, keyword: str, *, region_hint: str = "") -> tuple[str, str] | None:
        if not self.api_key or not keyword.strip():
            return None
        queries = self._build_keyword_queries(keyword, region_hint)
        async with httpx.AsyncClient(timeout=15.0) as client:
            for query in queries:
                response = await client.get(
                    f"{BASE_URL}/v2/local/search/keyword.json",
                    headers=self._headers,
                    params={"query": query, "page": 1, "size": 10, "sort": "accuracy"},
                )
                response.raise_for_status()
                data = response.json()
                documents = data.get("documents") or []
                if documents:
                    first = self._pick_safe_keyword_match(region_hint, documents)
                    if first:
                        return first.get("x", ""), first.get("y", "")
        return None

    @staticmethod
    def _build_address_queries(address: str) -> list[str]:
        normalized = KakaoLocalClient._normalize_address_query(address)
        tokens = [token for token in normalized.strip().split() if token]
        queries: list[str] = []
        seen: set[str] = set()
        for keep in range(len(tokens), max(len(tokens) - 2, 2), -1):
            query = " ".join(tokens[:keep]).strip()
            if query and query not in seen:
                seen.add(query)
                queries.append(query)
        if normalized and normalized not in seen:
            queries.insert(0, normalized)
        return queries

    @staticmethod
    def _normalize_address_query(address: str) -> str:
        text = address.strip()
        text = re.sub(r"\([^)]*\)", " ", text)
        text = re.sub(r"\b일원\b", " ", text)
        text = re.sub(r"\b일대\b", " ", text)
        text = re.sub(r"\b외\s*\d+필지\b", " ", text)
        text = re.sub(r"\s+", " ", text).strip(" ,")
        return text

    @staticmethod
    def _normalize_keyword(keyword: str) -> str:
        text = keyword.strip()
        text = re.sub(r"\([^)]*\)", " ", text)
        text = re.sub(r"\[[^\]]*\]", " ", text)
        text = re.sub(r"\b(AA|BL|PH)\d+\b", " ", text, flags=re.IGNORECASE)
        text = re.sub(r"\d+단지", " ", text)
        text = re.sub(r"[_\-]+", " ", text)
        text = re.sub(r"\s+", " ", text).strip(" ,")
        return text

    @classmethod
    def _build_keyword_queries(cls, keyword: str, region_hint: str) -> list[str]:
        base = cls._normalize_keyword(keyword)
        region_tokens = cls._region_tokens(region_hint)
        region = " ".join(region_tokens)
        variants = [
            f"{region} {base}".strip(),
            base,
            base.replace("역", "").strip(),
        ]
        queries: list[str] = []
        seen: set[str] = set()
        for item in variants:
            if item and item not in seen:
                seen.add(item)
                queries.append(item)
        return queries

    @staticmethod
    def _region_tokens(address: str) -> list[str]:
        return [token for token in address.strip().split()[:3] if token]

    @staticmethod
    def _normalize_region_token(token: str) -> str:
        replacements = {
            "서울특별시": "서울",
            "부산광역시": "부산",
            "대구광역시": "대구",
            "인천광역시": "인천",
            "광주광역시": "광주",
            "대전광역시": "대전",
            "울산광역시": "울산",
            "세종특별자치시": "세종",
            "경기도": "경기",
            "강원특별자치도": "강원",
            "충청북도": "충북",
            "충청남도": "충남",
            "전북특별자치도": "전북",
            "전라남도": "전남",
            "경상북도": "경북",
            "경상남도": "경남",
            "제주특별자치도": "제주",
        }
        return replacements.get(token, token)

    @classmethod
    def _region_matches(cls, expected_address: str, candidate_address: str) -> bool:
        expected = [cls._normalize_region_token(token) for token in cls._region_tokens(expected_address)]
        candidate = [cls._normalize_region_token(token) for token in cls._region_tokens(candidate_address)]
        if not expected:
            return True
        if len(expected) >= 2 and len(candidate) >= 2:
            return expected[0] == candidate[0] and expected[1] == candidate[1]
        return expected[: len(candidate)] == candidate[: len(expected)]

    @classmethod
    def _pick_safe_address_match(cls, original_address: str, documents: list[dict]) -> dict | None:
        if not cls._region_tokens(original_address):
            return documents[0] if documents else None
        for doc in documents:
            address_name = (doc.get("address_name") or "").strip()
            road_name = (doc.get("road_address", {}) or {}).get("address_name", "").strip()
            candidate = road_name or address_name
            if not candidate:
                continue
            if cls._region_matches(original_address, candidate):
                return doc
        return None

    @classmethod
    def _pick_safe_keyword_match(cls, region_hint: str, documents: list[dict]) -> dict | None:
        for doc in documents:
            address_name = (doc.get("road_address_name") or doc.get("address_name") or "").strip()
            if not address_name:
                continue
            if not cls._region_tokens(region_hint):
                return doc
            if cls._region_matches(region_hint, address_name):
                return doc
        return None

    async def category_search(
        self,
        category_group_code: str,
        *,
        x: str,
        y: str,
        radius: int = MAX_RADIUS,
        page_limit: int = 3,
    ) -> list[dict]:
        if not self.api_key:
            return []
        documents: list[dict] = []
        async with httpx.AsyncClient(timeout=15.0) as client:
            for page in range(1, page_limit + 1):
                response = await client.get(
                    f"{BASE_URL}/v2/local/search/category.json",
                    headers=self._headers,
                    params={
                        "category_group_code": category_group_code,
                        "x": x,
                        "y": y,
                        "radius": radius,
                        "sort": "distance",
                        "page": page,
                        "size": 15,
                    },
                )
                response.raise_for_status()
                data = response.json()
                documents.extend(data.get("documents") or [])
                if data.get("meta", {}).get("is_end", True):
                    break
        return documents

    async def keyword_search(
        self,
        query: str,
        *,
        x: str,
        y: str,
        radius: int = MAX_RADIUS,
        page_limit: int = 2,
    ) -> list[dict]:
        if not self.api_key:
            return []
        documents: list[dict] = []
        async with httpx.AsyncClient(timeout=15.0) as client:
            for page in range(1, page_limit + 1):
                response = await client.get(
                    f"{BASE_URL}/v2/local/search/keyword.json",
                    headers=self._headers,
                    params={
                        "query": query,
                        "x": x,
                        "y": y,
                        "radius": radius,
                        "sort": "distance",
                        "page": page,
                        "size": 15,
                    },
                )
                response.raise_for_status()
                data = response.json()
                documents.extend(data.get("documents") or [])
                if data.get("meta", {}).get("is_end", True):
                    break
        return documents


def normalize_places(
    documents: Iterable[dict],
    *,
    source: str,
    category: str = "",
    include_if=None,
) -> list[NearbyPlace]:
    places: list[NearbyPlace] = []
    seen: set[tuple[str, str]] = set()
    for doc in documents:
        name = (doc.get("place_name") or "").strip()
        address = (doc.get("road_address_name") or doc.get("address_name") or "").strip()
        if not name:
            continue
        if include_if and not include_if(doc):
            continue
        key = (name, address)
        if key in seen:
            continue
        seen.add(key)
        try:
            distance = int(doc.get("distance") or 0)
        except Exception:
            distance = 0
        places.append(
            NearbyPlace(
                name=name,
                distance=distance,
                address=address,
                category=category or (doc.get("category_group_name") or doc.get("category_name") or "").strip(),
                source=source,
                place_url=(doc.get("place_url") or "").strip(),
            )
        )
    return sorted(places, key=lambda item: (item.distance, item.name))


def merge_places(*groups: Iterable[NearbyPlace], limit: int = 10) -> list[NearbyPlace]:
    merged: list[NearbyPlace] = []
    seen: set[tuple[str, str]] = set()
    for group in groups:
        for item in group:
            key = (item.name, item.address)
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)
    merged.sort(key=lambda item: (item.distance, item.name))
    return merged[:limit]


def score_from_distance(distance: int | None, *, thresholds: tuple[int, int, int, int]) -> str:
    if distance is None or distance <= 0:
        return "★☆☆☆☆"
    a, b, c, d = thresholds
    if distance <= a:
        return "★★★★★"
    if distance <= b:
        return "★★★★☆"
    if distance <= c:
        return "★★★☆☆"
    if distance <= d:
        return "★★☆☆☆"
    return "★☆☆☆☆"
