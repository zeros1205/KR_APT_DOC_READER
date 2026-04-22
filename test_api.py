#!/usr/bin/env python3
"""공공데이터 API 응답 구조 확인"""

import httpx
import json
import os

API_BASE = "https://api.odcloud.kr/api/ApplyhomeInfoDetailSvc/v1"
API_KEY = os.getenv("PUBLIC_DATA_API_KEY", "")

if not API_KEY or "여기에" in API_KEY:
    print("❌ API 키 필요")
    exit(1)

async def test():
    params = {
        "serviceKey": API_KEY,
        "page": 1,
        "perPage": 1,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{API_BASE}/getAPTLttotPblancDetail",
            params=params
        )
        data = resp.json()

        if data.get("data"):
            item = data["data"][0]
            print("=== API 응답 필드 목록 ===")
            for key in sorted(item.keys()):
                value = item[key]
                if value:
                    print(f"{key}: {value}")

if __name__ == '__main__':
    import asyncio
    asyncio.run(test())
