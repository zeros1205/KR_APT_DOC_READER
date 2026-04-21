"""
rewrite_location.py — 기존 11개 포스트 입지 분석 재작성

흐름:
  1. 각 post.html에서 apt_name·location·supply_location 추출
  2. Gemini → 입지 분석 생성 (교통·학군·생활·의료)
  3. Claude Sonnet → 검증·교정
  4. post.html 패치 (location_intro + 4개 카드 텍스트 교체)

실행:
  python rewrite_location.py [--dry-run]
"""
import asyncio
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "pipeline"))

from config import ANTHROPIC_API_KEY, GEMINI_API_KEY, LLM_CONTENT_MODEL, LLM_FACTCHECK_MODEL
from anthropic import AsyncAnthropic

claude_client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

POSTS_DIR = ROOT / "output" / "posts"

# ── 프롬프트 (orchestrator.py와 동일) ──────────────────
LOCATION_ANALYSIS_PROMPT = """당신은 한국 부동산 입지 분석 전문가입니다.
아래 단지 정보를 바탕으로 입지 분석을 정확하게 작성하세요.

【필수 준수 원칙】
- 실제로 존재하는 역명·학교명·병원명·상업시설명만 기재. 모르면 "확인 필요" 기재
- 비수도권(강원·충청·전라·경상·제주 등) 지역에서는 지하철/도시철도 언급 절대 금지.
  대신 KTX·버스·도로 접근성·생활권 중심으로 서술
- 지하철 가능 도시: 서울·경기·인천·대전·대구·부산·광주·울산(일부)
- 도보 5분 ≈ 400m, 도보 10분 ≈ 800m, 도보 15분 ≈ 1.2km 기준 준수
- 별점 기준:
  subway: ★★★★★ 도보5분이내 / ★★★★☆ 도보10분 / ★★★☆☆ 도보15분 / ★★☆☆☆ 버스환승 / ★☆☆☆☆ 지하철없음·비수도권
  school: ★★★★★ 학원가+명문중고 / ★★★★☆ 초등+중학군양호 / ★★★☆☆ 보통 / ★★☆☆☆ 원거리 / ★☆☆☆☆ 정보없음
  life:   ★★★★★ 대형마트+백화점 도보권 / ★★★★☆ 대형마트10분 / ★★★☆☆ 슈퍼+편의점 / ★★☆☆☆ 차량필요 / ★☆☆☆☆ 편의시설없음
  medical:★★★★★ 대학병원 도보권 / ★★★★☆ 종합병원 차량5분 / ★★★☆☆ 차량10분 / ★★☆☆☆ 의원급만 / ★☆☆☆☆ 의료기관없음

[단지 정보]:
{facts_json}

JSON만 출력:
{{
  "location_intro": "100~150자. 해당 지역 분위기·생활 환경을 독자에게 친근하게 설명",
  "subway_score":   "★★★☆☆",
  "subway_detail":  "역명과 도보 분수 명시. 비수도권은 KTX/버스/도로 접근성 언급. 지하철 없는 도시에서 지하철 절대 금지",
  "school_score":   "★★★★☆",
  "school_detail":  "배정 초등학교명 + 학군 평가",
  "life_score":     "★★★☆☆",
  "life_detail":    "가장 가까운 대형마트·백화점·상업시설 명칭과 거리",
  "medical_score":  "★★★☆☆",
  "medical_detail": "가장 가까운 종합병원 명칭과 거리"
}}"""

LOCATION_VERIFY_PROMPT = """아래는 AI가 생성한 입지 분석입니다.
사실 정확성을 검증하고 오류가 있으면 수정하세요.

검증 기준:
1. 역명·학교명·병원명·상업시설명이 실제 위치 근처에 존재하는가?
2. 비수도권에서 지하철을 언급하는 오류가 없는가?
3. 도보·차량 거리 수치가 현실적인가?
4. 별점이 설명 내용과 일치하는가?

[단지명]: {apt_name}
[위치]: {location}

[Gemini 생성 입지 분석]:
{location_json}

수정 필요 시 수정된 JSON 반환. 수정 없으면 원본 그대로 반환. JSON만 출력."""


# ── 메타데이터 추출 ─────────────────────────────────────
def extract_facts_from_html(html: str) -> dict:
    facts = {}

    # apt_name
    m = re.search(r'<h1[^>]*>\s*([\s\S]*?)(?:<br|</h1>)', html)
    facts["apt_name"] = re.sub(r'\s+', ' ', m.group(1).strip()) if m else ""

    # supply_location (상세 주소)
    m = re.search(
        r'공급 위치</div>.*?<div[^>]*font-size: 16px[^>]*>([^<]+)</div>',
        html, re.DOTALL,
    )
    facts["supply_location"] = m.group(1).strip() if m else ""
    facts["location"] = facts["supply_location"]

    # supply_scale
    m = re.search(r'총\s*([0-9,]+세대)', html)
    facts["supply_scale"] = m.group(1) if m else ""

    return facts


# ── Gemini 입지 분석 생성 ───────────────────────────────
def call_gemini_location(facts: dict) -> dict:
    if not GEMINI_API_KEY:
        print("  GEMINI_API_KEY 미설정 → 건너뜀")
        return {}
    try:
        from google import genai as google_genai
        from google.genai import types as genai_types
        client = google_genai.Client(api_key=GEMINI_API_KEY)
        resp = client.models.generate_content(
            model=LLM_FACTCHECK_MODEL,
            contents=LOCATION_ANALYSIS_PROMPT.format(
                facts_json=json.dumps(facts, ensure_ascii=False, indent=2)
            ),
            config=genai_types.GenerateContentConfig(
                system_instruction="JSON만 출력하세요. 마크다운 코드블록 없이 순수 JSON만 출력합니다.",
            ),
        )
        raw = resp.text.strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            m = re.search(r'\{.*\}', raw, re.DOTALL)
            return json.loads(m.group()) if m else {}
    except Exception as e:
        print(f"  Gemini 오류: {e}")
        return {}


# ── Claude 검증 ────────────────────────────────────────
async def call_claude_verify(location_data: dict, facts: dict) -> dict:
    if not location_data:
        return location_data
    try:
        resp = await claude_client.messages.create(
            model=LLM_CONTENT_MODEL,
            max_tokens=2000,
            system=(
                "당신은 한국 지리·부동산 전문가입니다.\n"
                "JSON만 출력하세요. 마크다운 코드블록 없이 순수 JSON만 출력합니다."
            ),
            messages=[{
                "role": "user",
                "content": LOCATION_VERIFY_PROMPT.format(
                    apt_name=facts.get("apt_name", ""),
                    location=facts.get("location", ""),
                    location_json=json.dumps(location_data, ensure_ascii=False, indent=2),
                ),
            }],
        )
        raw = resp.content[0].text.strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            m = re.search(r'\{.*\}', raw, re.DOTALL)
            return json.loads(m.group()) if m else location_data
    except Exception as e:
        print(f"  Claude 검증 오류: {e}")
        return location_data


# ── HTML 패치 ───────────────────────────────────────────
def patch_location_html(html: str, loc: dict) -> str:
    """location_intro + 4개 카드(교통·학군·생활·의료) 텍스트 교체"""

    # 1. location_intro — <p> 태그 안 텍스트
    intro = loc.get("location_intro", "")
    if intro:
        html = re.sub(
            r'(<p style="[^"]*font-size: 16px[^"]*"[^>]*>\s*)'
            r'((?:(?!</p>).)+?)'
            r'(\s*</p>\s*<!-- 입지 별점)',
            lambda m: m.group(1) + intro + m.group(3),
            html,
            count=1,
            flags=re.DOTALL,
        )

    # 2. 카드 텍스트 교체 헬퍼
    CARD_ICONS = [
        ("🚇", "subway_detail"),
        ("🎓", "school_detail"),
        ("🛒", "life_detail"),
        ("🏥", "medical_detail"),
    ]

    for icon, key in CARD_ICONS:
        detail = loc.get(key, "")
        if not detail:
            continue
        # 카드 패턴: icon div → 카드 타이틀 div → 텍스트 div
        # 텍스트 div: font-size: 16px (또는 15px), color: #6A635C 등
        html = re.sub(
            rf'({re.escape(icon)}</div>\s*'
            rf'<div[^>]*>[^<]*</div>\s*'
            rf'<div[^>]*font-size: 1[56]px[^>]*>)'
            rf'([^<]*)'
            rf'(</div>)',
            lambda m, d=detail: m.group(1) + d + m.group(3),
            html,
            count=1,
            flags=re.DOTALL,
        )

    return html


# ── 메인 ───────────────────────────────────────────────
async def main(dry_run: bool = False):
    posts = sorted(POSTS_DIR.glob("*/post.html"))
    print(f"\n총 {len(posts)}개 포스트 입지 분석 재작성 시작\n")
    patched = 0

    for post_path in posts:
        html   = post_path.read_text(encoding="utf-8")
        facts  = extract_facts_from_html(html)
        name   = facts.get("apt_name", post_path.parent.name)

        print(f"[{name}]")
        print(f"  위치: {facts.get('location', '')[:60]}")

        # Gemini 생성
        loc = call_gemini_location(facts)
        if not loc:
            print("  → Gemini 결과 없음, 건너뜀\n")
            continue
        print(f"  Gemini subway_detail: {loc.get('subway_detail', '')[:60]}")

        # Claude 검증
        loc = await call_claude_verify(loc, facts)
        print(f"  Claude verified subway_detail: {loc.get('subway_detail', '')[:60]}")

        # HTML 패치
        updated = patch_location_html(html, loc)
        if updated == html:
            print("  → HTML 변경 없음 (패턴 불일치)\n")
            continue

        if not dry_run:
            post_path.write_text(updated, encoding="utf-8")
            print(f"  ✅ 패치 완료\n")
        else:
            print(f"  [DRY-RUN] 패치 예정\n")
        patched += 1

    print(f"완료: {patched}/{len(posts)}개 패치됨")


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    asyncio.run(main(dry_run=dry_run))
