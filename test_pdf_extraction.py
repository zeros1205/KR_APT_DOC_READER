"""
test_pdf_extraction.py — 규제 정보 5개 항목 추출 모델 비교 테스트

PDF를 pdfplumber로 텍스트 추출하지 않고,
각 모델 API에 PDF를 직접(base64) 전달해 모델이 원문 레이아웃 그대로 읽게 함.

대상 모델:
  A) GPT-5.4            (gpt-5.4)
  B) Claude Opus 4.7    (claude-opus-4-7)
  C) Gemini 3.1 Pro     (gemini-3.1-pro-preview)

추출 항목:
  1. 규제지역 여부   2. 재당첨 제한   3. 전매제한
  4. 거주의무기간   5. 분양가 상한제
"""

import asyncio
import base64
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY", "")
GEMINI_API_KEY    = os.getenv("GEMINI_API_KEY", "")

ROOT = Path(__file__).parent

# ── 테스트 대상: (표시 이름, PDF 파일명) ─────────────────────────────────────
TEST_PDFS = [
    ("힐스테이트 평거 센트럴",     "2026000085 힐스테이트 평거 센트럴 입주자모집공고문.pdf"),
    ("용인 고림 동문 디 이스트",   "2026000112 용인 고림 동문 디 이스트 입주자모집공고문.pdf"),
    ("아크로 드 서초",             "2025000497 아크로 드 서초 입주자모집공고문.pdf"),
]

# ── 추출 프롬프트 ─────────────────────────────────────────────────────────────
PROMPT = """첨부된 입주자모집공고문 PDF에서 아래 5개 항목만 정확히 추출해 JSON으로만 답하세요.
공고문에 명시되지 않은 항목은 반드시 null로 표기하고, 절대 추측하지 마세요.

추출 항목 (키명 고정):
- regulated_zone: 규제지역 해당 여부.
  "규제지역", "투기과열지구", "청약과열지역", "조정대상지역" 항목을 찾아
  해당 구분을 모두 쉼표로 나열. 예: "투기과열지구, 청약과열지역" / "비규제지역" / "해당없음"
- readmission_limit: 재당첨 제한 기간.
  "재당첨 제한", "재당첨제한" 항목. 예: "10년" / "7년" / "없음"
- resale_restriction: 전매제한 기간.
  "전매제한", "전매행위 제한기간" 항목. 예: "소유권이전등기일로부터 3년" / "없음"
- live_requirement: 거주의무기간.
  "거주의무", "실거주 의무", "거주의무기간" 항목. 예: "2년" / "없음" / "해당없음"
- price_cap: 분양가 상한제 적용 여부.
  "분양가상한제" 항목. 반드시 "적용" 또는 "미적용" 중 하나.

JSON만 출력 (마크다운 코드블록 없이):"""

FIELDS       = ["regulated_zone", "readmission_limit", "resale_restriction",
                "live_requirement", "price_cap"]
FIELD_LABELS = {"regulated_zone": "규제지역 여부", "readmission_limit": "재당첨 제한",
                "resale_restriction": "전매제한", "live_requirement": "거주의무기간",
                "price_cap": "분양가 상한제"}

MODELS = [
    ("GPT-5.4", "openai", "gpt-5.4"),
    ("Opus 4.7",   "claude", "claude-opus-4-7"),
    ("Gemini 3.1 Pro", "gemini", "gemini-3.1-pro-preview"),
]


# ── OpenAI — PDF input_file 직접 전달 ───────────────────────────────────────
async def call_openai(model_id: str, pdf_b64: str) -> dict:
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    t0 = time.time()
    try:
        resp = await client.responses.create(
            model=model_id,
            max_output_tokens=512,
            text={"format": {"type": "json_object"}},
            input=[{
                "role": "user",
                "content": [
                    {
                        "type": "input_file",
                        "filename": "notice.pdf",
                        "file_data": f"data:application/pdf;base64,{pdf_b64}",
                    },
                    {"type": "input_text", "text": PROMPT},
                ],
            }],
        )
        raw = (resp.output_text or "").strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        result = json.loads(raw)
        result["_elapsed"] = round(time.time() - t0, 1)
        return result
    except Exception as e:
        return {"error": str(e), "_elapsed": round(time.time() - t0, 1)}


# ── Claude — PDF document block 직접 전달 ─────────────────────────────────────
async def call_claude(model_id: str, pdf_b64: str) -> dict:
    import anthropic
    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    t0 = time.time()
    try:
        msg = await client.messages.create(
            model=model_id,
            max_tokens=512,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": pdf_b64,
                        },
                    },
                    {"type": "text", "text": PROMPT},
                ],
            }],
        )
        raw = msg.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        result = json.loads(raw)
        result["_elapsed"] = round(time.time() - t0, 1)
        return result
    except Exception as e:
        return {"error": str(e), "_elapsed": round(time.time() - t0, 1)}


# ── Gemini — PDF inline_data 직접 전달 ───────────────────────────────────────
async def call_gemini(model_id: str, pdf_bytes: bytes) -> dict:
    from google import genai as google_genai
    from google.genai import types as genai_types
    client = google_genai.Client(api_key=GEMINI_API_KEY)
    t0 = time.time()
    try:
        resp = await asyncio.to_thread(
            client.models.generate_content,
            model=model_id,
            contents=[
                genai_types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
                PROMPT,
            ],
            config=genai_types.GenerateContentConfig(
                max_output_tokens=512,
                temperature=0,
            ),
        )
        raw = resp.text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        result = json.loads(raw)
        result["_elapsed"] = round(time.time() - t0, 1)
        return result
    except Exception as e:
        return {"error": str(e), "_elapsed": round(time.time() - t0, 1)}


# ── 결과 출력 ─────────────────────────────────────────────────────────────────
def print_comparison(name: str, results: dict):
    model_names = list(results.keys())
    col = 26
    print(f"\n{'━'*72}")
    print(f"  📄 {name}")
    print(f"{'━'*72}")
    print(f"{'항목':<16}", end="")
    for m in model_names:
        print(f"  {m:<{col}}", end="")
    print()
    print(f"{'─'*72}")
    for field in FIELDS:
        label = FIELD_LABELS[field]
        print(f"{label:<16}", end="")
        values = [str(results[m].get(field) or "null") for m in model_names]
        # 모든 모델 값이 같으면 ✅ 표시
        all_same = len(set(values)) == 1
        for v in values:
            disp = (v[:col-2] + "…") if len(v) > col else v
            print(f"  {disp:<{col}}", end="")
        print("  ✅" if all_same and values[0] != "null" else "")
    print(f"{'─'*72}")
    print(f"{'응답시간(초)':<16}", end="")
    for m in model_names:
        elapsed = str(results[m].get("_elapsed", "?"))
        print(f"  {elapsed:<{col}}", end="")
    print()
    for m in model_names:
        if "error" in results[m]:
            print(f"  ⚠️  {m}: {results[m]['error'][:80]}")


# ── 메인 ──────────────────────────────────────────────────────────────────────
async def main():
    print("=" * 72)
    print("  규제 정보 5항목 PDF 추출 모델 비교 (PDF 직접 읽기)")
    print(f"  모델: {', '.join(m[0] for m in MODELS)}")
    print("=" * 72)

    for display_name, pdf_filename in TEST_PDFS:
        pdf_path = ROOT / pdf_filename
        if not pdf_path.exists():
            print(f"\n⚠️  파일 없음: {pdf_filename}")
            continue

        pdf_bytes = pdf_path.read_bytes()
        pdf_b64   = base64.standard_b64encode(pdf_bytes).decode("utf-8")
        print(f"\n[{display_name}]  {len(pdf_bytes)//1024}KB")

        # 순차 호출 (API rate limit 고려)
        results = {}
        for label, kind, model_id in MODELS:
            print(f"  → {label} ...", end="", flush=True)
            if kind == "openai":
                res = await call_openai(model_id, pdf_b64)
            elif kind == "claude":
                res = await call_claude(model_id, pdf_b64)
            else:
                res = await call_gemini(model_id, pdf_bytes)
            print(f" {res.get('_elapsed','?')}초")
            results[label] = res

        print_comparison(display_name, results)

    print(f"\n{'━'*72}")
    print("  ✅ = 전 모델 동일값  |  빈칸 = 모델 간 불일치 또는 null")
    print("━" * 72)


if __name__ == "__main__":
    asyncio.run(main())
