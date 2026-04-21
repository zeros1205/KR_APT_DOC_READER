"""
test_pdf_extraction.py — 규제 정보 5개 항목 PDF 추출 모델 비교 테스트

대상 모델:
  A) Claude Sonnet 4.6   (claude-sonnet-4-6)
  B) Gemini 2.5 Pro      (gemini-2.5-pro-preview-05-06)
  C) Claude Opus 4.7     (claude-opus-4-7)

추출 대상 5개 필드:
  1. 규제지역 여부  (투기과열지구·청약과열지역·조정대상지역·비규제 등)
  2. 재당첨 제한    (X년 / 없음)
  3. 전매제한       (X년 / X개월 / 없음)
  4. 거주의무기간   (X년 / 없음)
  5. 분양가 상한제  (적용 / 미적용)

공덕역자이르네 정답 (PDF 확인):
  규제지역: 투기과열지구, 청약과열지역
  재당첨: 10년 / 전매제한: 3년 / 거주의무: 없음 / 분양가상한제: 미적용
"""

import asyncio
import json
import os
import time
import httpx
import pdfplumber
import io
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GEMINI_API_KEY    = os.getenv("GEMINI_API_KEY", "")

POSTS_DIR = Path(__file__).parent / "output" / "posts"

# ── 테스트 대상 포스트 (notice_url에 직접 PDF 링크가 있는 것) ─────────────────
TEST_POSTS = [
    "2026-04-20_힐스테이트_평거_센트럴",
    "2026-04-20_용인_고림_동문_디_이스트",
    "2026-04-20_아크로_드_서초",
]

# ── 추출 프롬프트 ─────────────────────────────────────────────────────────────
EXTRACT_PROMPT = """당신은 대한민국 아파트 입주자모집공고문 분석 전문가입니다.
아래 [공고 원문]에서 다음 5개 항목만 정확히 추출하여 JSON으로만 답하세요.
값이 명시되지 않은 경우 null로, 절대 추측하지 마세요.

추출 항목 (JSON 키명 고정):
- regulated_zone: 규제지역 해당 여부. 공고문의 "규제지역", "투기과열지구", "청약과열지역", "조정대상지역" 항목 참조.
  해당하는 모든 지역 구분을 쉼표로 나열. 예: "투기과열지구, 청약과열지역" / "조정대상지역" / "비규제지역" / "해당없음"
- readmission_limit: 재당첨 제한 기간. "재당첨 제한", "재당첨제한" 항목 참조.
  예: "10년" / "7년" / "없음". 공고에 없으면 null.
- resale_restriction: 전매제한 기간. "전매제한", "전매행위 제한기간" 항목 참조.
  예: "소유권이전등기일로부터 3년" / "입주 후 1년" / "없음". 공고에 없으면 null.
- live_requirement: 거주의무기간. "거주의무", "실거주 의무", "거주의무기간" 항목 참조.
  예: "2년" / "없음" / "해당없음". 공고에 없으면 null.
- price_cap: 분양가 상한제 적용 여부. "분양가상한제" 항목 참조.
  반드시 "적용" 또는 "미적용" 중 하나. 공고에 없으면 null.

[공고 원문]:
{text}

JSON만 출력하세요 (마크다운 코드블록 없이):"""


# ── PDF URL 확보 (웹 페이지인 경우 HTML에서 PDF 링크 추출) ───────────────────
def resolve_pdf_url(url: str) -> str:
    """notice_url이 웹 페이지면 HTML 파싱으로 실제 PDF URL을 찾아 반환."""
    import re
    if "static.applyhome.co.kr" in url:
        return url  # 이미 직접 PDF 링크
    try:
        r = httpx.get(url, timeout=20, follow_redirects=True,
                      headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        # static.applyhome.co.kr/ai/aia/getAtchmnfl.do 패턴 탐색
        matches = re.findall(
            r'(https?://static\.applyhome\.co\.kr/ai/aia/getAtchmnfl\.do\?[^"\'&\s]+)',
            r.text
        )
        if matches:
            return matches[0]
        # JavaScript에서 파라미터 조합 패턴 탐색
        hmno = re.search(r'houseManageNo[=\'"\s:]+(\d+)', r.text)
        pbno = re.search(r'pblancNo[=\'"\s:]+(\d+)', r.text)
        seq  = re.search(r'atchmnflSeqNo[=\'"\s:]+(\d+)', r.text)
        sn   = re.search(r'atchmnflSn[=\'"\s:]+(\d+)', r.text)
        if hmno and pbno and seq and sn:
            return (
                f"https://static.applyhome.co.kr/ai/aia/getAtchmnfl.do"
                f"?houseManageNo={hmno.group(1)}&pblancNo={pbno.group(1)}"
                f"&atchmnflSeqNo={seq.group(1)}&atchmnflSn={sn.group(1)}"
            )
    except Exception as e:
        print(f"  ⚠️ 페이지 파싱 실패: {e}")
    return ""  # 찾지 못함


# ── PDF 다운로드 → 텍스트 추출 ────────────────────────────────────────────────
def download_pdf_text(url: str, max_pages: int = 12, max_chars: int = 10000) -> str:
    pdf_url = resolve_pdf_url(url)
    if not pdf_url:
        return f"[PDF URL 추출 실패: {url[:60]}]"
    print(f"  PDF URL: {pdf_url[:90]}...")
    try:
        r = httpx.get(pdf_url, timeout=30, follow_redirects=True,
                      headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
    except Exception as e:
        return f"[PDF 다운로드 실패: {e}]"

    try:
        with pdfplumber.open(io.BytesIO(r.content)) as pdf:
            pages = pdf.pages[:max_pages]
            text = "\n".join(p.extract_text() or "" for p in pages)
        text = text[:max_chars]
        print(f"  텍스트 추출: {len(text)}자")
        return text
    except Exception as e:
        return f"[PDF 파싱 실패: {e}]"


# ── Claude 호출 ───────────────────────────────────────────────────────────────
async def call_claude(model: str, text: str) -> dict:
    import anthropic
    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    prompt = EXTRACT_PROMPT.format(text=text)
    t0 = time.time()
    try:
        msg = await client.messages.create(
            model=model,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        elapsed = time.time() - t0
        raw = msg.content[0].text.strip()
        # 코드블록 제거
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        result = json.loads(raw)
        result["_elapsed"] = round(elapsed, 1)
        return result
    except Exception as e:
        return {"error": str(e), "_elapsed": round(time.time() - t0, 1)}


# ── Gemini 호출 ───────────────────────────────────────────────────────────────
async def call_gemini(model: str, text: str) -> dict:
    from google import genai as google_genai
    from google.genai import types as genai_types
    client = google_genai.Client(api_key=GEMINI_API_KEY)
    prompt = EXTRACT_PROMPT.format(text=text)
    t0 = time.time()
    try:
        resp = await asyncio.to_thread(
            client.models.generate_content,
            model=model,
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                max_output_tokens=512,
                temperature=0,
            ),
        )
        elapsed = time.time() - t0
        raw = resp.text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        result = json.loads(raw)
        result["_elapsed"] = round(elapsed, 1)
        return result
    except Exception as e:
        return {"error": str(e), "_elapsed": round(time.time() - t0, 1)}


# ── 결과 출력 ─────────────────────────────────────────────────────────────────
FIELDS = ["regulated_zone", "readmission_limit", "resale_restriction",
          "live_requirement", "price_cap"]
FIELD_LABELS = {
    "regulated_zone":    "규제지역 여부",
    "readmission_limit": "재당첨 제한",
    "resale_restriction":"전매제한",
    "live_requirement":  "거주의무기간",
    "price_cap":         "분양가 상한제",
}
MODELS = {
    "Sonnet 4.6": ("claude", "claude-sonnet-4-6"),
    "Opus 4.7":   ("claude", "claude-opus-4-7"),
    "Gemini 2.5 Pro": ("gemini", "gemini-2.5-pro-preview-05-06"),
}


def print_comparison(post_name: str, results: dict[str, dict]):
    print(f"\n{'='*70}")
    print(f"  {post_name}")
    print(f"{'='*70}")
    model_names = list(results.keys())

    # 헤더
    col = 22
    print(f"{'항목':<16}", end="")
    for m in model_names:
        print(f"  {m:<{col}}", end="")
    print()
    print("-" * (16 + (col + 2) * len(model_names)))

    # 각 필드
    for field in FIELDS:
        label = FIELD_LABELS[field]
        print(f"{label:<16}", end="")
        for m in model_names:
            val = results[m].get(field) or "null"
            if isinstance(val, str) and len(val) > col:
                val = val[:col-2] + "…"
            print(f"  {str(val):<{col}}", end="")
        print()

    # 응답시간
    print("-" * (16 + (col + 2) * len(model_names)))
    print(f"{'응답시간(초)':<16}", end="")
    for m in model_names:
        elapsed = results[m].get("_elapsed", "?")
        print(f"  {elapsed:<{col}}", end="")
    print()

    # 오류
    for m in model_names:
        if "error" in results[m]:
            print(f"  ⚠️  {m} 오류: {results[m]['error']}")


# ── 메인 ──────────────────────────────────────────────────────────────────────
async def main():
    print("=== 규제 정보 5개 항목 PDF 추출 모델 비교 테스트 ===\n")
    print(f"모델: {', '.join(MODELS.keys())}")
    print(f"대상: {len(TEST_POSTS)}개 포스트\n")

    for post_name in TEST_POSTS:
        meta_path = POSTS_DIR / post_name / "post_meta.json"
        if not meta_path.exists():
            print(f"[{post_name}] post_meta.json 없음, 건너뜀\n")
            continue

        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        notice_url = meta.get("notice_url", "")
        print(f"\n[{post_name}]")
        pdf_text = download_pdf_text(notice_url)
        if pdf_text.startswith("["):
            print(f"  {pdf_text}")
            continue

        # 3개 모델 병렬 호출
        tasks = {}
        for model_label, (kind, model_id) in MODELS.items():
            if kind == "claude":
                tasks[model_label] = call_claude(model_id, pdf_text)
            else:
                tasks[model_label] = call_gemini(model_id, pdf_text)

        results = {}
        for label, coro in tasks.items():
            print(f"  → {label} 호출 중...")
            results[label] = await coro

        print_comparison(post_name, results)

    print(f"\n\n{'='*70}")
    print("테스트 완료. 위 결과를 PDF 원문과 직접 대조하세요.")
    print("="*70)


if __name__ == "__main__":
    asyncio.run(main())
